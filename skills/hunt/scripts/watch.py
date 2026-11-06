"""Trip watch: re-price a trip's finalists from site APIs only, and report what changed.

  python watch.py TRIP.json [--out DIR] [--only id1,id2] [--no-kayak] [--kayak-budget 20] [--pause 4]

TRIP.json (see references/watch.md for the full format):
  {"name": "...", "group": 5, "alertDrop": 50, "workspace": "~/trips/tokyo-feb",
   "finalists": [{"id": "rio", "label": "Rio + JAL", "notes": "US visa",
                  "baseline": {"date": "2026-11-02", "pp": 1629},
                  "legs": [{"id": "pos", "label": "MVD-GIG", "from": "MVD", "to": "GIG", "date": "2027-02-19",
                            "sources": ["jetsmart", "fli", "kayak"], "connectTo": "main", "minConnect": 180},
                           {"id": "main", "label": "GIG-HND", "from": "GIG", "to": "HND", "date": "2027-02-19",
                            "return": "2027-03-05", "sources": ["kayak"]}]}]}

Writes <workspace>/<today>/: raw/*.json (every search), results.csv, summary.json, report.md, and diffs
against the newest earlier run that has a summary.json (or each finalist's baseline). Searches run one at a
time; Kayak gets a pause between calls and a budget, and is skipped for the rest of the run once it blocks.
Prices are USD. Per-person totals use 1-adult fares; group totals use the cheapest split of the group into
bookings each source was actually priced at (e.g. 3 + 2). A leg priced only for 1 adult is flagged.
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flightapis as fa  # noqa: E402

# adult counts each source can price (Kayak one-way is learned for 1 adult; fli fails at 5+)
SIZES = {"kayak_rt": [1, 2, 3, 5], "kayak_ow": [1], "fli": [1, 2, 3, 4], "jetsmart": [1], "buquebus": None}


def minutes(t):
    """'2:15 pm' / '14:15' -> minutes after midnight, or None."""
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*([ap]m)?", t or "", re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return h * 60 + mi


class Runner:
    def __init__(self, raw_dir, kayak=True, kayak_budget=20, pause=4.0):
        self.raw, self.cache, self.rows = raw_dir, {}, []
        self.kayak_on, self.kayak_left, self.pause = kayak, kayak_budget, pause
        self.kayak_blocked, self.errors, self.calls = None, [], {}

    def search(self, source, o, d, day, ret, adults):
        key = (source, o, d, day, ret or "", adults)
        if key in self.cache:
            return self.cache[key]
        rows = []
        try:
            if source == "kayak":
                if not self.kayak_on or self.kayak_blocked or self.kayak_left <= 0:
                    self.cache[key] = None
                    return None
                if self.calls.get("kayak"):
                    time.sleep(max(0, self.pause - fa.KAYAK_GAP))  # flightapis already spaces Kayak calls
                self.kayak_left -= 1
                rows = fa.kayak(o, d, day, ret, adults, top=15)
            elif source == "fli":
                rows = fa.fli(o, d, day, ret, adults, top=10)
            elif source == "jetsmart":
                rows = fa.jetsmart(o, d, day)
            elif source == "buquebus":
                rows = fa.ferry(o, d, day, adults)
            self.calls[source] = self.calls.get(source, 0) + 1
        except fa.ApiBlocked as e:
            if source == "kayak":
                self.kayak_blocked = str(e)
            self.errors.append(f"{source} {o}-{d} {day}: blocked ({e})")
            rows = None
        except fa.ApiError as e:
            self.errors.append(f"{source} {o}-{d} {day}: {e}")
            rows = None
        tag = f"{source}_{o}-{d}_{day}" + (f"_{ret}" if ret else "") + f"_{adults}ad"
        (self.raw / f"{tag}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        for r in rows or []:
            self.rows.append({"search": tag, **r})
        self.cache[key] = rows
        return rows


def sizes_for(source, leg):
    if source == "kayak":
        return SIZES["kayak_rt"] if leg.get("return") else SIZES["kayak_ow"]
    return SIZES[source]


CONFIDENCE = {"exact": 0, "estimate": 1, "single": 2}


def price_leg(run, leg, group, connect_ok):
    """Cheapest 1-adult row, plus the group price for one leg across its sources.

    group price, best confidence first:
      exact    - the whole group in one booking (Kayak at 5, fli up to 4, Buquebus any count)
      estimate - group x per-person fare of the largest searchable count (fli for 5: the 4-adult fare)
      single   - group x the 1-adult fare (JetSMART cache, Kayak one-way); seats not checked
    split: two separate bookings (e.g. 3 + 2) when that is cheaper than one booking. Optimistic: both
    searches see the same seats, so confirm the seat count on the site before relying on it.
    """
    best1, group_best, split_best, notes, all_rows = None, None, None, [], []
    for src in leg.get("sources", ["kayak"]):
        if leg.get("fallback") and best1:  # later sources only when the earlier ones found nothing
            break
        sizes = sizes_for(src, leg)
        pp = {}

        def cheapest(n):
            rows = run.search(src, leg["from"], leg["to"], leg["date"], leg.get("return"), n) or []
            all_rows.extend(rows)
            rows = [r for r in rows if r.get("price_pp") and connect_ok(r)]
            return min(rows, key=lambda r: r["price_pp"]) if rows else None

        r1 = cheapest(1)
        if not r1:
            continue
        pp[1] = r1
        if not best1 or r1["price_pp"] < best1["price_pp"]:
            best1 = r1
        if group == 1:
            cand = {"total": r1["price_pp"], "how": "exact", "source": src, "row": r1}
        elif sizes is None or group in sizes:
            rg = cheapest(group)
            if rg:
                pp[group] = rg
            cand = {"total": round(group * rg["price_pp"], 2), "how": "exact", "source": src, "row": rg} if rg else None
            if rg and group == 5 and sizes and rg["price_pp"] > r1["price_pp"] + 1:
                for n in (3, 2):  # the full group costs more: price the two halves for a split option
                    if n in sizes and (rn := cheapest(n)):
                        pp[n] = rn
        else:
            m = max(s for s in sizes if s < group)
            rm = cheapest(m) if m > 1 else None
            if rm:
                pp[m] = rm
                cand = {"total": round(group * rm["price_pp"], 2), "how": "estimate", "source": src, "row": rm,
                        "flag": f"{group} adults not searchable on {src}: estimated from the {m}-adult fare"}
                # a fli round trip costs 1 + top_n Google fetches: no split searches for those
                if rm["price_pp"] > r1["price_pp"] + 1 and not (src == "fli" and leg.get("return")):
                    for n in (3, 2):
                        if n in sizes and n not in pp and (rn := cheapest(n)):
                            pp[n] = rn
            else:
                cand = {"total": round(group * r1["price_pp"], 2), "how": "single", "source": src, "row": r1,
                        "flag": "1-adult fare only; seats for the group not checked"}
        if cand and (not group_best or (CONFIDENCE[cand["how"]], cand["total"]) < (CONFIDENCE[group_best["how"]], group_best["total"])):
            group_best = cand
        for a in sorted(n for n in pp if 1 < n < group):
            b = group - a
            if b in pp and a >= b:
                total = round(a * pp[a]["price_pp"] + b * pp[b]["price_pp"], 2)
                if not split_best or total < split_best["total"]:
                    split_best = {"total": total, "split": [a, b], "source": src}
    if group_best and split_best and split_best["total"] >= group_best["total"] - 1:
        split_best = None
    # JetSMART's cache has no arrival time: borrow it from another source's row for the same flight
    if best1 and not best1.get("arr_time") and best1.get("flights"):
        twin = next((r for r in all_rows if r.get("arr_time") and r.get("flights") == best1["flights"]), None)
        if twin:
            best1 = {**best1, "arr_time": twin["arr_time"]}
    if not best1:
        notes.append("no price found")
    return best1, group_best, split_best, notes


def run_finalist(run, fin, group):
    group = fin.get("group", group)
    priced, out_legs, flags = {}, [], []
    # legs that connect to another leg are priced after it
    order = sorted(fin["legs"], key=lambda l: 1 if l.get("connectTo") else 0)
    for leg in order:
        target = priced.get(leg.get("connectTo"))

        def connect_ok(r, leg=leg, target=target):
            if not target or not target.get("best1") or r["depart"] != target["leg"]["date"]:
                return True
            arr, dep = minutes(r.get("arr_time")), minutes(target["best1"].get("dep_time"))
            return arr is None or dep is None or dep - arr >= leg.get("minConnect", 180)

        best1, gb, split, notes = price_leg(run, leg, group, connect_ok)
        priced[leg.get("id", leg["label"])] = {"leg": leg, "best1": best1, "group": gb, "split": split, "notes": notes}
    for leg in fin["legs"]:
        p = priced[leg.get("id", leg["label"])]
        if p["group"] and p["group"].get("flag"):
            flags.append(f'{leg["label"]}: {p["group"]["flag"]}')
        if p["split"]:
            s = p["split"]
            flags.append(f'{leg["label"]}: split {"+".join(map(str, s["split"]))} on {s["source"]} would be '
                         f'{fmt(s["total"])} vs {fmt(p["group"]["total"])} in one booking, if both searches saw '
                         f'different seats (confirm the seat count on the site)')
        target = priced.get(p["leg"].get("connectTo"))
        if target and p["best1"] and target["best1"] and p["best1"]["depart"] == target["leg"]["date"]:
            arr, dep = minutes(p["best1"].get("arr_time")), minutes(target["best1"].get("dep_time"))
            if arr is None or dep is None:
                flags.append(f'{leg["label"]} -> {target["leg"]["label"]}: self-transfer, connection time unknown')
            else:
                gap, need = dep - arr, p["leg"].get("minConnect", 180)
                flags.append(f'{leg["label"]} -> {target["leg"]["label"]}: self-transfer (separate tickets), '
                             f'{gap // 60}h{gap % 60:02d} between flights' + (f" — TOO TIGHT (want {need // 60}h+)" if gap < need else ""))
        out_legs.append(p)
    complete = all(p["best1"] for p in out_legs)
    pp = round(sum(p["best1"]["price_pp"] for p in out_legs), 2) if complete else None
    gt = round(sum(p["group"]["total"] for p in out_legs), 2) if complete and all(p["group"] for p in out_legs) else None
    gsplit = round(sum((p["split"] or p["group"])["total"] for p in out_legs), 2) \
        if gt is not None and any(p["split"] for p in out_legs) else None
    group_how = sorted({p["group"]["how"] for p in out_legs if p["group"]}, key=CONFIDENCE.get)[-1] if gt is not None else None
    # a leg meant for Kayak but priced elsewhere is not comparable with a Kayak-priced earlier run
    no_kayak = [p["leg"]["label"] for p in out_legs
                if "kayak" in p["leg"].get("sources", ["kayak"]) and (not p["best1"] or p["best1"]["source"] != "kayak")
                and (run.kayak_blocked or not run.kayak_on)]
    sources = "+".join(p["best1"]["source"] if p["best1"] else "-" for p in out_legs)
    return {"id": fin["id"], "label": fin["label"], "notes": fin.get("notes", ""), "group": group,
            "pp": pp, "group_total": gt, "group_how": group_how, "group_split_total": gsplit,
            "complete": complete, "flags": flags, "legs": out_legs, "baseline": fin.get("baseline"),
            "sources": sources, "no_kayak": no_kayak}


def previous_summary(base, today):
    runs = sorted(p for p in base.iterdir() if p.is_dir() and p.name < today and (p / "summary.json").exists())
    if not runs:
        return None, None
    return runs[-1].name, json.loads((runs[-1] / "summary.json").read_text(encoding="utf-8"))


def fmt(x):
    return f"${x:,.0f}" if isinstance(x, (int, float)) else "n/a"


def delta(now, before):
    if not isinstance(now, (int, float)) or not isinstance(before, (int, float)):
        return ""
    d = now - before
    return "=" if abs(d) < 1 else (f"↓ ${-d:,.0f}" if d < 0 else f"↑ ${d:,.0f}")


def report(trip, results, run, prev_name, prev, out_dir):
    group = trip.get("group", 1)
    prev_by = {f["id"]: f for f in (prev or {}).get("finalists", [])}
    lines = [f"# {trip['name']} — {date.today().isoformat()} (API run)", ""]
    srcs = ", ".join(f"{k} ×{v}" for k, v in run.calls.items())
    lines.append(f"Sources: {srcs or 'none'}" + (f". **Kayak blocked:** {run.kayak_blocked}" if run.kayak_blocked else "")
                 + (". Kayak skipped (--no-kayak)" if not run.kayak_on else ""))
    lines.append(f"Compared with: {prev_name or 'baselines in the trip file'}. Prices in USD.")
    lines += ["", f"| Finalist | Per person | Group of {group} | vs last (pp) | vs last (group) | Cheapest sellers |",
              "|---|---|---|---|---|---|"]
    alerts = []
    for f in results:
        before = prev_by.get(f["id"]) or {}
        b_pp = before.get("pp", (f.get("baseline") or {}).get("pp"))
        b_g = before.get("group_total", (f.get("baseline") or {}).get("group"))
        sellers = " + ".join(f'{p["best1"]["carriers"]} (Google)' if p["best1"]["source"] == "fli" else p["best1"]["seller"]
                             for p in f["legs"] if p["best1"])
        gl = f'{fmt(f["group_total"])}' + (f' (group of {f["group"]})' if f["group"] != group else "") + \
             ({"estimate": " (est.)", "single": " (1-adult fares)"}.get(f.get("group_how"), "")) + \
             (f'; split {fmt(f["group_split_total"])}?' if f.get("group_split_total") else "")
        # only a like-for-like comparison counts: same source per leg as the earlier run
        changed = bool(f["no_kayak"]) or (before.get("sources") and before["sources"] != f["sources"])
        star = " *" if changed else ""
        dp, dg = delta(f["pp"], b_pp), delta(f["group_total"], b_g)
        lines.append(f'| {f["label"]} | {fmt(f["pp"])}{"" if f["complete"] else " (incomplete)"} | {gl} | '
                     f'{dp + star if dp else ""} | {dg + star if dg else ""} | {sellers} |')
        if not changed and isinstance(f["pp"], (int, float)) and isinstance(b_pp, (int, float)) \
                and b_pp - f["pp"] >= trip.get("alertDrop", 50):
            alerts.append(f'{f["label"]}: per person {fmt(b_pp)} -> {fmt(f["pp"])}')
    if any(f["no_kayak"] for f in results) or any(" *" in l for l in lines):
        lines += ["", "\\* Not like-for-like: a leg's source changed since the last run (e.g. Kayak was blocked, "
                      "so Google Flights priced it). Google usually ran higher than Kayak on these routes, so an ↑ "
                      "here is not a real price move."]
    if alerts:
        lines += ["", "**Price drops:** " + "; ".join(alerts)]
    for f in results:
        lines += ["", f'## {f["label"]}', ""]
        if f["notes"]:
            lines.append(f["notes"])
            lines.append("")
        lines += ["| Leg | Source | 1 adult | Group | Group price is | Seller | Times | Bags | Link |", "|---|---|---|---|---|---|---|---|---|"]
        for p in f["legs"]:
            b, g = p["best1"], p["group"]
            if not b:
                lines.append(f'| {p["leg"]["label"]} | — | not found | | | | | | |')
                continue
            times = f'{b["dep_time"]}→{b["arr_time"]}' + (f' / back {b["back_dep"]}→{b["back_arr"]}' if b.get("back_dep") else "")
            how = f'{g["how"]}, {g["source"]}' if g else ""
            lines.append(f'| {p["leg"]["label"]} | {b["source"]} | {fmt(b["price_pp"])} | {fmt(g["total"]) if g else "n/a"} | '
                         f'{how} | {b["seller"]} {b["carriers"]} {b.get("flights", "")} | {times} | {b["bags"]} | [open]({b["link"]}) |')
        for fl in f["flags"]:
            lines.append(f"- {fl}")
    if run.errors:
        lines += ["", "## Not checked / errors", ""] + [f"- {e}" for e in run.errors]
    lines += ["", "Fares change constantly. Re-check on the seller's site right before buying.",
              "Not covered by this API run: Skyscanner, airline websites and other bot-walled sites (check them in Chrome)."]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return alerts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trip")
    ap.add_argument("--out", help="workspace folder (default: trip['workspace'] or the trip file's folder)")
    ap.add_argument("--only", help="comma list of finalist ids")
    ap.add_argument("--no-kayak", action="store_true")
    ap.add_argument("--kayak-budget", type=int, default=20)
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between Kayak searches")
    a = ap.parse_args()
    trip_path = Path(a.trip)
    trip = json.loads(trip_path.read_text(encoding="utf-8"))
    base = Path(a.out or trip.get("workspace") or trip_path.parent).expanduser()
    today = date.today().isoformat()
    out_dir = base / today
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    run = Runner(out_dir / "raw", kayak=not a.no_kayak, kayak_budget=a.kayak_budget, pause=a.pause)
    only = set(a.only.split(",")) if a.only else None
    t0 = time.time()
    results = []
    for fin in trip["finalists"]:
        if only and fin["id"] not in only:
            continue
        print(f"pricing {fin['label']} ...", file=sys.stderr, flush=True)
        results.append(run_finalist(run, fin, trip.get("group", 1)))
    prev_name, prev = previous_summary(base, today)
    summary = {"date": today, "trip": trip["name"], "seconds": round(time.time() - t0),
               "kayak_blocked": run.kayak_blocked, "calls": run.calls, "errors": run.errors,
               "finalists": [{k: v for k, v in f.items() if k != "legs"} |
                             {"legs": [{"label": p["leg"]["label"], "best1": p["best1"], "group": p["group"],
                                        "split": p["split"]} for p in f["legs"]]}
                             for f in results]}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if run.rows:
        with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(run.rows[0].keys()))
            w.writeheader()
            w.writerows(run.rows)
    alerts = report(trip, results, run, prev_name, prev, out_dir)
    print(json.dumps({"out": str(out_dir), "seconds": summary["seconds"], "calls": run.calls,
                      "kayak_blocked": run.kayak_blocked, "alerts": alerts,
                      "finalists": [{"id": f["id"], "pp": f["pp"], "group_total": f["group_total"]} for f in results]},
                     ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
