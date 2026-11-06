"""Turn flight-search JSON into comparable itinerary rows, build self-transfer and whole-trip
combos, log results found on websites, and rank everything into a report.

Subcommands (run `python legs.py <cmd> -h` for details):
  rows   FILE.json...            print/append rows from fli (one-way, round-trip, dates) or Kiwi JSON
  combo  LEG1.json LEG2.json     pair two one-way searches into self-transfer itineraries (same direction)
  trip   --out F.. --ret F..      pair outbound + return one-ways into whole-trip rows (incl. open-jaw)
  add                            append one row found on a website (Kayak, airline site, ferry...)
  top    RESULTS.csv             rank: fastest, cheapest under N hours, best value, cheapest, top-N table

Prices in fli and Kiwi JSON are the TOTAL for all passengers in the query; price_pp is derived.
Ranking uses price per person so rows with different passenger counts compare fairly.
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# US airports. An international arrival clears immigration + customs at the FIRST US airport
# (no sterile transit), so a short connection there is the classic missed-connection trap.
US = set("""ABQ ALB ANC ATL AUS BDL BHM BNA BOI BOS BTV BUF BUR BWI CHS CLE CLT CMH CVG DAL DCA DEN DFW DSM
DTW ELP EWR FAT FLL GEG GRR GSO GSP HNL HOU IAD IAH ICT IND ISP JAN JAX JFK KOA LAS LAX LGA LGB LIH
LIT MCI MCO MDW MEM MIA MKE MSN MSP MSY OAK OGG OKC OMA ONT ORD ORF PBI PDX PHL PHX PIT PNS PSP PVD
RDU RIC RNO ROC RSW SAN SAT SAV SDF SEA SFO SJC SJU SLC SMF SNA SRQ STL STT SYR TPA TUL TUS""".split())

COLS = ["source", "search_type", "date", "depart", "arrive", "price_total", "price_pp", "currency",
        "passengers", "duration", "duration_min", "stops", "airlines", "flights", "route", "layovers",
        "flags", "separate_tickets", "fare_note", "link"]


def fmt_min(m):
    return f"{int(m) // 60}h{int(m) % 60:02d}" if m not in (None, "") else ""


def parse_dur(s):
    """'14h31' / '14h 31m' / '871' -> minutes."""
    if s in (None, ""):
        return None
    if str(s).isdigit():
        return int(s)
    m = re.match(r"\s*(\d+)\s*h\s*(\d+)?", str(s))
    return int(m.group(1)) * 60 + int(m.group(2) or 0) if m else None


def analyse(legs):
    """legs: list of dicts with dep, arr (airport codes), dt, at (ISO local), carrier, carrier_name, num.
    Returns layovers, flags, route, airlines, flights strings."""
    lay, flags, entered_us = [], [], legs[0]["dep"] in US
    for a, b in zip(legs, legs[1:]):
        arr, dep = datetime.fromisoformat(a["at"]), datetime.fromisoformat(b["dt"])
        mins = int((dep - arr).total_seconds() // 60)
        ap_in, ap_out = a["arr"], b["dep"]
        lay.append(f"{ap_in} {fmt_min(mins)}" + ("" if ap_in == ap_out else f"->{ap_out}"))
        if ap_in != ap_out:
            flags.append(f"AIRPORT CHANGE {ap_in}->{ap_out}")
        if mins < 60:
            flags.append(f"tight {fmt_min(mins)} at {ap_in}")
        if ap_in in US and not entered_us:  # arriving into the US from abroad
            entered_us = True
            if mins < 120:
                flags.append(f"<2h at first US port {ap_in}")
        if arr.date() != dep.date():
            flags.append(f"OVERNIGHT layover {ap_in}")
        elif arr.hour < 5 and mins >= 180:
            flags.append(f"pre-dawn wait {ap_in}")
        if mins >= 8 * 60:
            flags.append(f"long layover {ap_in}")
    return {
        "layovers": "; ".join(lay), "flags": "; ".join(dict.fromkeys(flags)),
        "route": "-".join([legs[0]["dep"]] + [l["arr"] for l in legs]),
        "airlines": " / ".join(dict.fromkeys(l["carrier_name"] for l in legs)),
        "flights": " ".join(f'{l["carrier"]}{l["num"]}' for l in legs),
        "depart": legs[0]["dt"].replace("T", " ")[:16], "arrive": legs[-1]["at"].replace("T", " ")[:16],
    }


def fli_legs(legs):
    return [{"dep": l["departure_airport"]["code"], "arr": l["arrival_airport"]["code"],
             "dt": l["departure_time"], "at": l["arrival_time"], "carrier": l["airline"]["code"],
             "carrier_name": l["airline"]["name"],
             "num": str(l.get("flight_number", "")).removeprefix(l["airline"]["code"])} for l in legs]


def kiwi_legs(segs):
    return [{"dep": s["from"], "arr": s["to"], "dt": s["departureTime"], "at": s["arrivalTime"],
             "carrier": s.get("carrier", ""), "carrier_name": s.get("carrierName", s.get("carrier", "")),
             "num": str(s.get("flightNumber", "")).removeprefix(s.get("carrier", ""))} for s in segs]


def mins_between(a, b):
    return int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() // 60)


def make_row(source, tag, out, ret, price, pax, cur, link, note="", out_dur=None, ret_dur=None):
    """out/ret: analysed direction dicts (ret may be None). Durations are travel time (no stay)."""
    o_dur = out_dur if out_dur is not None else mins_between(out["depart"].replace(" ", "T"), out["arrive"].replace(" ", "T"))
    row = {"source": source, "search_type": tag, "date": out["depart"][:10], "depart": out["depart"],
           "arrive": out["arrive"], "price_total": price, "price_pp": round(price / pax) if price else None,
           "currency": cur, "passengers": pax, "stops": out["route"].count("-") - 1,
           "airlines": out["airlines"], "flights": out["flights"], "route": out["route"],
           "layovers": out["layovers"], "flags": out["flags"], "separate_tickets": "no",
           "fare_note": note, "link": link}
    dur = o_dur
    if ret:
        r_dur = ret_dur if ret_dur is not None else mins_between(ret["depart"].replace(" ", "T"), ret["arrive"].replace(" ", "T"))
        dur = o_dur + r_dur
        row.update({
            "arrive": ret["arrive"], "stops": row["stops"] + ret["route"].count("-") - 1,
            "airlines": " / ".join(dict.fromkeys(out["airlines"].split(" / ") + ret["airlines"].split(" / "))),
            "flights": f'{out["flights"]} // {ret["flights"]}', "route": f'{out["route"]} // {ret["route"]}',
            "layovers": f'{out["layovers"] or "nonstop"} // {ret["layovers"] or "nonstop"}',
            "flags": "; ".join(x for x in ([f"out: {out['flags']}"] if out["flags"] else []) +
                               ([f"ret: {ret['flags']}"] if ret["flags"] else [])),
        })
    row["duration_min"], row["duration"] = dur, fmt_min(dur)
    return row


def file_rows(path, tag=""):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    tag = tag or Path(path).stem
    if "itineraries" in d:  # Kiwi MCP search-flight result
        pax = sum((d.get("passengers") or {}).get(k, 0) for k in ("adults", "children", "infants")) or 1
        out = []
        for it in d["itineraries"]:
            o = analyse(kiwi_legs(it["outbound"]["segments"]))
            r = analyse(kiwi_legs(it["inbound"]["segments"])) if it.get("inbound") else None
            bg = it.get("baggage") or {}
            note = (f'Kiwi; bags incl: personal {bg.get("personalItem", 0)}, cabin {bg.get("cabinBag", 0)}, '
                    f'checked {bg.get("checkedBag", 0)}; may be a self-transfer (check carriers)')
            out.append(make_row("Kiwi", tag, o, r, it["price"], pax, d.get("currency", "EUR"), it.get("bookingUrl", ""),
                                note, it["outbound"].get("durationSeconds", 0) // 60 or None,
                                (it["inbound"].get("durationSeconds", 0) // 60 or None) if r else None))
        return out
    q = d.get("query", {})
    pax, cur = q.get("passengers", 1) or 1, q.get("currency", "USD")
    if "dates" in d:  # fli dates grid (one-way or --round)
        return [{
            "source": "fli dates (Google Flights)", "search_type": tag,
            "date": x["departure_date"], "arrive": x.get("return_date", ""),
            "route": f'{q.get("origin")}-{q.get("destination")}' + (" (round trip)" if x.get("return_date") else ""),
            "price_total": x["price"], "price_pp": round(x["price"] / pax), "currency": x.get("currency", cur),
            "passengers": pax, "separate_tickets": "no", "link": x.get("booking_url", ""),
            "fare_note": f'cheapest of day, max_stops={q.get("max_stops")}' +
                         (f', return {x["return_date"]}' if x.get("return_date") else ""),
        } for x in d.get("dates", [])]
    out = []
    for f in d.get("flights", []):
        if f.get("legs"):
            o = analyse(fli_legs(f["legs"]))
            out.append(make_row("fli (Google Flights)", tag, o, None, f.get("price"), pax, cur,
                                f.get("booking_url", ""), out_dur=f.get("duration")))
        elif f.get("outbound") and f.get("return"):
            o, r = analyse(fli_legs(f["outbound"]["legs"])), analyse(fli_legs(f["return"]["legs"]))
            out.append(make_row("fli (Google Flights)", tag, o, r, f.get("price"), pax, cur, f.get("booking_url", ""),
                                "round trip, one ticket", f["outbound"].get("duration"), f["return"].get("duration")))
    if not out and d.get("success") and not d.get("dates"):
        print(f"note: {Path(path).name} returned 0 itineraries (success={d.get('success')}). That does NOT mean no "
              f"flights exist - try one-ways per direction, nearby dates, Kiwi or Kayak.", file=sys.stderr)
    return out


def combo(a, b, min_h, max_h, tag):
    arr = datetime.fromisoformat(a["arrive"])
    dep = datetime.fromisoformat(b["depart"])
    gap = int((dep - arr).total_seconds() // 60)
    if gap < min_h * 60 or gap > max_h * 60:
        return None
    ap_a, ap_b = a["route"].split("-")[-1], b["route"].split("-")[0]
    flags = ["SEPARATE TICKETS"] + [x for x in (a["flags"], b["flags"]) if x]
    if ap_a != ap_b:
        flags.append(f"AIRPORT CHANGE {ap_a}->{ap_b}")
    if arr.date() != dep.date():
        flags.append(f"OVERNIGHT layover {ap_a}")
    pax = a["passengers"]
    total = a["price_total"] + b["price_total"]
    dur = a["duration_min"] + gap + b["duration_min"]
    return {
        "source": "combo", "search_type": tag, "date": a["date"], "depart": a["depart"], "arrive": b["arrive"],
        "price_total": total, "price_pp": round(total / pax), "currency": a["currency"], "passengers": pax,
        "duration_min": dur, "duration": fmt_min(dur), "stops": (a["stops"] or 0) + 1 + (b["stops"] or 0),
        "airlines": " / ".join(dict.fromkeys(a["airlines"].split(" / ") + b["airlines"].split(" / "))),
        "flights": f'{a["flights"]} + {b["flights"]}', "route": f'{a["route"]}|{b["route"]}',
        "layovers": "; ".join(x for x in (a["layovers"], f"{ap_a} {fmt_min(gap)} (self-transfer)", b["layovers"]) if x),
        "flags": "; ".join(flags), "separate_tickets": "yes", "fare_note": "", "link": f'{a["link"]} | {b["link"]}',
    }


def trip(a, b, tag):
    """Outbound one-way + return one-way = whole trip on two tickets (each protects its own connections)."""
    open_jaw = a["route"].split("-")[-1] != b["route"].split("-")[0] or a["route"].split("-")[0] != b["route"].split("-")[-1]
    total = a["price_total"] + b["price_total"]
    dur = a["duration_min"] + b["duration_min"]
    flags = [f"out: {a['flags']}"] * bool(a["flags"]) + [f"ret: {b['flags']}"] * bool(b["flags"])
    if open_jaw:
        flags.append("OPEN-JAW (different airports out/back)")
    return {
        "source": "trip", "search_type": tag, "date": a["date"], "depart": a["depart"], "arrive": b["arrive"],
        "price_total": total, "price_pp": round(total / a["passengers"]), "currency": a["currency"],
        "passengers": a["passengers"], "duration_min": dur, "duration": fmt_min(dur),
        "stops": (a["stops"] or 0) + (b["stops"] or 0),
        "airlines": " / ".join(dict.fromkeys(a["airlines"].split(" / ") + b["airlines"].split(" / "))),
        "flights": f'{a["flights"]} // {b["flights"]}', "route": f'{a["route"]} // {b["route"]}',
        "layovers": f'{a["layovers"] or "nonstop"} // {b["layovers"] or "nonstop"}', "flags": "; ".join(flags),
        "separate_tickets": "per direction",
        "fare_note": f'two one-way tickets ({a["price_total"]:.0f} + {b["price_total"]:.0f})',
        "link": f'{a["link"]} | {b["link"]}',
    }


def append_csv(path, rows):
    path = Path(path)
    existing = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
    key = lambda r: tuple(str(r.get(k, "")) for k in ("source", "search_type", "date", "depart", "flights", "route", "price_total"))
    keys = {key(r) for r in existing}
    new = []
    for r in rows:
        if key(r) not in keys:
            keys.add(key(r))
            new.append(r)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(existing + new)
    print(f"+{len(new)} rows ({len(rows) - len(new)} dupes skipped) -> {path} [{len(existing) + len(new)} total]")


def show(rows, limit):
    for r in rows[:limit]:
        p = r.get("price_total")
        print(f'{r.get("date", ""):10} {r.get("currency", "")}{p if p is not None else "?":>8} '
              f'({r.get("price_pp", "")}pp x{r.get("passengers", "")}) {r.get("duration", ""):>6} {r.get("route", ""):<24} '
              f'{r.get("flights", ""):<22} dep {str(r.get("depart", ""))[11:]} arr {str(r.get("arrive", ""))[5:]} '
              f'| {r.get("layovers", "")} | {r.get("flags", "")}')


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


SORTS = {"price": lambda r: (num(r.get("price_pp")) or 9e9, r.get("duration_min") or 9e9),
         "duration": lambda r: (r.get("duration_min") or 9e9, num(r.get("price_pp")) or 9e9),
         "date": lambda r: (r["date"], num(r.get("price_pp")) or 9e9)}


def cmd_rows(a):
    rows = [r for p in a.files for r in file_rows(p, a.tag)]
    rows.sort(key=SORTS[a.sort])
    show(rows, a.limit)
    if a.csv:
        append_csv(a.csv, rows)


def cmd_combo(a):
    l1, l2 = file_rows(a.leg1), file_rows(a.leg2)
    tag = a.tag or f"selftransfer_{Path(a.leg1).stem}+{Path(a.leg2).stem}"
    rows = [c for x in l1 for y in l2 if (c := combo(x, y, a.min_connect, a.max_connect, tag))]
    rows.sort(key=lambda r: (r["price_total"], r["duration_min"]))
    print(f"{len(rows)} combos with {a.min_connect}-{a.max_connect}h self-transfer")
    show(rows, a.limit)
    if a.csv:
        append_csv(a.csv, rows)


def cmd_trip(a):
    pick = lambda rows: sorted([r for r in rows if r.get("price_total") and r.get("duration_min")],
                               key=lambda r: (r["price_total"], r["duration_min"]))[:a.k]
    outs, rets = pick(r for p in a.out for r in file_rows(p)), pick(r for p in a.ret for r in file_rows(p))
    tag = a.tag or "trip"
    rows = [trip(x, y, tag) for x in outs for y in rets if y["depart"] > x["arrive"]]
    rows.sort(key=lambda r: (r["price_total"], r["duration_min"]))
    print(f"{len(rows)} whole trips from the {len(outs)} cheapest outbounds x {len(rets)} cheapest returns")
    show(rows, a.limit)
    if a.csv:
        append_csv(a.csv, rows)


def cmd_add(a):
    dur = parse_dur(a.duration)
    flags = a.flags or ""
    if a.separate and "SEPARATE TICKETS" not in flags:
        flags = "; ".join(x for x in ("SEPARATE TICKETS", flags) if x)
    row = {"source": a.source, "search_type": a.tag, "date": a.date, "depart": a.depart, "arrive": a.arrive,
           "price_total": a.price_total, "price_pp": round(a.price_total / a.pax) if a.price_total else "",
           "currency": a.currency, "passengers": a.pax, "duration": fmt_min(dur) if dur else a.duration,
           "duration_min": dur, "stops": a.stops, "airlines": a.airlines, "flights": a.flights, "route": a.route,
           "layovers": a.layovers, "flags": flags, "separate_tickets": "yes" if a.separate else "no",
           "fare_note": a.note, "link": a.link}
    append_csv(a.csv, [row])


def cmd_top(a):
    with Path(a.csv).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if num(r["price_total"])]  # rows without duration still count for "cheapest"
    if a.filter:
        rows = [r for r in rows if re.search(a.filter, r["search_type"] + " " + r["route"])]
    if a.exclude_flag:
        rows = [r for r in rows if not re.search(a.exclude_flag, r["flags"] or "")]
    if a.pax:
        rows = [r for r in rows if int(num(r["passengers"]) or 1) == a.pax]
    if not rows:
        sys.exit("no priced rows with a duration match these filters")
    if len({r["passengers"] for r in rows}) > 1:
        print(f"note: mixed passenger counts {sorted({r['passengers'] for r in rows})} - ranking per person; "
              f"use --pax N to rank one group size", file=sys.stderr)
    if len({r["currency"] for r in rows}) > 1:
        print(f"WARNING: mixed currencies {sorted({r['currency'] for r in rows})} - convert before trusting the ranking",
              file=sys.stderr)
    for r in rows:
        r["_pp"], r["_m"] = num(r["price_pp"]) or num(r["price_total"]) / (num(r["passengers"]) or 1), num(r["duration_min"])
        r["_v"] = r["_pp"] + a.hour_value * r["_m"] / 60 if r["_m"] else r["_pp"] + a.hour_value * 999
    timed = [r for r in rows if r["_m"]]
    if len(timed) < len(rows):
        print(f"note: {len(rows) - len(timed)} rows have no duration - they count for 'cheapest' only "
              f"(log --duration with legs.py add to rank them fully)", file=sys.stderr)
    line = lambda title, r: print(
        f'**{title}:** {r["currency"]} {r["_pp"]:.0f} pp ({float(r["price_total"]):.0f} total for {r["passengers"]}), '
        f'{r["duration"] or "duration ?"}, {r["route"]} {r["flights"]}, {r["date"]} {r["depart"][11:]}, {r["source"]}'
        + (f' — {r["flags"]}' if r["flags"] else ""))
    if timed:
        line("Fastest", min(timed, key=lambda r: (r["_m"], r["_pp"])))
        under = [r for r in timed if r["_m"] <= a.max_hours * 60]
        if under:
            line(f"Cheapest under {a.max_hours:g}h", min(under, key=lambda r: (r["_pp"], r["_m"])))
        line(f"Best value (pp price + {a.hour_value:g}/travel hour)", min(timed, key=lambda r: r["_v"]))
    line("Cheapest any length", min(rows, key=lambda r: (r["_pp"], r["_m"] or 9e9)))
    # dominance filter: drop rows both pricier and slower (by > margin) than an already-kept row
    rows.sort(key=lambda r: r["_v"])
    keep, seen = [], set()
    for r in rows:
        k = (r["flights"], r["route"])
        if k in seen or (r["_m"] and any(o["_m"] and o["_pp"] <= r["_pp"] and o["_m"] + a.margin <= r["_m"] for o in keep)):
            continue
        seen.add(k)
        keep.append(r)
    print("\n| # | Date | pp | Total (pax) | Time | Airlines | Route | Layovers | Flags | Source | Link |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(keep[:a.n], 1):
        lk = " ".join(f"[{j + 1}]({u})" for j, u in enumerate(r["link"].split(" | ")) if u)
        print(f'| {i} | {r["date"]} {r["depart"][11:]} | {r["_pp"]:.0f} | {float(r["price_total"]):.0f} ({r["passengers"]}) | '
              f'{r["duration"]} | {r["airlines"]} | {r["route"]} | {r["layovers"]} | {r["flags"]} | {r["source"]} | {lk} |')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("rows", help="print rows from fli / Kiwi JSON files")
    p.add_argument("files", nargs="+")
    p.add_argument("--tag", default="", help="search_type label (default: file stem)")
    p.add_argument("--sort", choices=list(SORTS), default="price")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--csv", help="also append rows to this CSV")
    p.set_defaults(fn=cmd_rows)

    p = sp.add_parser("combo", help="self-transfer combos from two one-way searches (same direction)")
    p.add_argument("leg1")
    p.add_argument("leg2")
    p.add_argument("--min-connect", type=float, default=3, help="hours; 3 domestic carry-on, 4+ if bags/immigration")
    p.add_argument("--max-connect", type=float, default=14, help="hours")
    p.add_argument("--tag", default="")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--csv")
    p.set_defaults(fn=cmd_combo)

    p = sp.add_parser("trip", help="whole trips = cheapest outbound one-ways x cheapest return one-ways")
    p.add_argument("--out", nargs="+", required=True, help="outbound one-way JSON file(s)")
    p.add_argument("--ret", nargs="+", required=True, help="return one-way JSON file(s) (other airports = open-jaw)")
    p.add_argument("--k", type=int, default=6, help="cheapest K of each side to pair")
    p.add_argument("--tag", default="")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--csv")
    p.set_defaults(fn=cmd_trip)

    p = sp.add_parser("add", help="append one row seen on a website (only real, observed values)")
    for k in ("source", "tag", "date", "route"):
        p.add_argument(f"--{k}", required=True)
    p.add_argument("--price-total", type=float, required=True, help="total for ALL passengers")
    p.add_argument("--pax", type=int, required=True)
    for k in ("depart", "arrive", "duration", "stops", "airlines", "flights", "layovers", "flags", "note", "link"):
        p.add_argument(f"--{k}", default="")
    p.add_argument("--currency", default="USD")
    p.add_argument("--separate", action="store_true", help="itinerary uses separate tickets (self-transfer)")
    p.add_argument("--csv", required=True)
    p.set_defaults(fn=cmd_add)

    p = sp.add_parser("top", help="rank a results CSV (per person)")
    p.add_argument("csv")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--max-hours", type=float, default=20, help="for whole trips use out+back hours, e.g. 30")
    p.add_argument("--hour-value", type=float, default=20, help="money per travel hour per person for value score")
    p.add_argument("--margin", type=int, default=60, help="minutes; dominance filter tolerance")
    p.add_argument("--filter", help="regex on search_type+route, e.g. '^trip' or 'outbound'")
    p.add_argument("--exclude-flag", help="regex; drop rows whose flags match, e.g. 'AIRPORT CHANGE'")
    p.add_argument("--pax", type=int, help="only rows with this passenger count")
    p.set_defaults(fn=cmd_top)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
