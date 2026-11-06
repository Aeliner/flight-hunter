"""Fares from site APIs (no browser at call time), as one row shape.

  python flightapis.py kayak MVD HND 2027-02-19 --return 2027-03-05 [--adults 1|2|3|5] [--top 10]
  python flightapis.py kayak GIG JFK 2027-02-18                      # one-way, 1 adult
  python flightapis.py jetsmart MVD GIG 2027-02-19 [--days 3]        # 12-month fare cache, per person
  python flightapis.py buquebus MVD BUE 2026-11-20 [--adults 2]      # ferry, USD
  python flightapis.py fli MVD GIG 2027-02-19 [--return ...] [--adults 5]
  python flightapis.py doctor                                        # node, api-anything, specs, Kayak session

Row: source, origin, dest, depart, ret, adults, price_pp, price_total, currency, seller, carriers,
dep_time, arr_time, back_dep, back_arr, stops, bags, link, note. Prices are USD unless currency says.
Kayak and JetSMART need Node 22.13+ and `npm install` in ../apis (doctor says how). A blocked Kayak
raises ApiBlocked: the user runs `npx --prefix <apis> api-anything login kayak --window` once.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

APIS = Path(__file__).resolve().parent.parent / "apis"
sys.path.insert(0, str(APIS))
import buquebus  # noqa: E402


class ApiBlocked(RuntimeError):
    pass


class ApiError(RuntimeError):
    pass


def _node(*args, timeout=180):
    node = shutil.which("node")
    if not node:
        raise ApiError("node not found: install Node.js 22.13+ (https://nodejs.org)")
    if not (APIS / "node_modules" / "api-anything").exists():
        raise ApiError(f"api-anything not installed: run `npm install --prefix \"{APIS}\"` then "
                       f"`node \"{APIS / 'aa.mjs'}\" install`")
    p = subprocess.run([node, str(APIS / "aa.mjs"), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    try:
        d = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ApiError((p.stderr or p.stdout)[-400:])
    if not d.get("ok"):
        if d.get("class") in ("blocked", "auth", "rate"):
            raise ApiBlocked(f'{args[0]}: {d.get("class")} - {str(d.get("reason"))[:200]}')
        raise ApiError(f'{args[0]}: {d.get("class")} - {str(d.get("reason"))[:300]}')
    return d


def row(**kw):
    base = dict(source="", origin="", dest="", depart="", ret="", adults=1, price_pp=None, price_total=None,
                currency="USD", seller="", carriers="", flights="", dep_time="", arr_time="", back_dep="",
                back_arr="", stops=None, bags="", link="", note="")
    base.update(kw)
    return base


def _kayak_carriers(leg_id):
    # leg ids look like MVDHND1803045600000IB1701803135600000IB719...: 13-digit stamp + carrier per segment
    return re.findall(r"\d{13}([A-Z0-9]{2})\d", leg_id or "")


def kayak(origin, dest, depart, ret=None, adults=1, top=10):
    d = _node("kayak", origin, dest, depart, ret or "ow", str(adults))
    search = f"https://www.kayak.com/flights/{origin}-{dest}/{depart}" + (f"/{ret}" if ret else "") + \
             (f"/{adults}adults" if adults > 1 else "") + "?sort=price_a"
    out = []
    for r in d["rows"][:top]:
        segs = _kayak_carriers(r.get("outLeg"))
        carriers = list(dict.fromkeys(segs + _kayak_carriers(r.get("backLeg"))))
        bags = "checked bag included" if r.get("checkedBag") == "Included" else \
               "carry-on only" if r.get("carryOn") == "Included" and r.get("checkedBag") == "Not included" else \
               f'bag {str(r.get("checkedBag") or "unknown").lower()}'
        out.append(row(source="kayak", origin=origin, dest=dest, depart=depart, ret=ret or "", adults=adults,
                       price_pp=r.get("price"), price_total=(r.get("price") or 0) * adults, seller=r.get("seller", ""),
                       carriers=" ".join(carriers), dep_time=r.get("outDep") or "", arr_time=r.get("outArr") or "",
                       back_dep=r.get("backDep") or "", back_arr=r.get("backArr") or "",
                       stops=max(len(segs) - 1, 0) if segs else None, bags=bags,
                       link=("https://www.kayak.com" + r["link"]) if r.get("link") else search,
                       note=f'{r.get("providers")} sellers' + ("; hacker fare" if r.get("hacker") else "")))
    return out


def jetsmart(dep, arr, day, days=0):
    d = _node("jetsmart", dep)
    lo = date.fromisoformat(day) - timedelta(days=days)
    hi = date.fromisoformat(day) + timedelta(days=days)
    out = []
    for r in d["rows"]:
        when = (r.get("date") or "")[:10]
        if r.get("arr") != arr or not when or not (lo <= date.fromisoformat(when) <= hi):
            continue
        out.append(row(source="jetsmart", origin=dep, dest=arr, depart=when, price_pp=round(r["totalUsd"], 2),
                       price_total=round(r["totalUsd"], 2), seller="JetSMART", carriers=r.get("carrier", "JA"),
                       flights=f'{r.get("carrier", "JA")}{r.get("flight")}',
                       dep_time=(r.get("date") or "")[11:16], stops=0, bags="carry-on only (base fare)",
                       link="https://jetsmart.com/uy/es/",
                       note=f'JA{r.get("flight")} class {r.get("fareClass")}; cached lowest fare for 1 person'))
    return sorted(out, key=lambda x: x["price_pp"])


def ferry(origin, dest, day, adults=1):
    out = []
    for r in buquebus.search(origin, dest, day, adults, "USD"):
        out.append(row(source="buquebus", origin=origin, dest=dest, depart=day, adults=adults,
                       price_pp=round(r["total"] / adults, 2), price_total=r["total"], seller="Buquebus",
                       carriers=r["ship"], dep_time=r["depart"], arr_time=r["arrive"],
                       stops=r["via"].count("+"), link="https://www.buquebus.com/uy",
                       note=f'{r["class"]} {r["tariff"]}; {r["via"]}'))
    return out


# fli wants airports; Kayak takes these city codes as they are
METROS = {"NYC": "JFK,EWR,LGA", "TYO": "HND,NRT", "LON": "LHR,LGW,STN,LTN,LCY", "PAR": "CDG,ORY",
          "SAO": "GRU,CGH,VCP", "RIO": "GIG,SDU", "BUE": "EZE,AEP", "CHI": "ORD,MDW", "WAS": "IAD,DCA,BWI",
          "MIL": "MXP,LIN,BGY", "ROM": "FCO,CIA", "OSA": "KIX,ITM", "SEL": "ICN,GMP"}


def fli(origin, dest, depart, ret=None, adults=1, stops="ANY", top=10):
    exe = shutil.which("fli")
    if not exe:
        raise ApiError('fli CLI not found: uv tool install "flights[mcp] @ git+https://github.com/punitarani/fli.git"')
    cmd = [exe, "flights", METROS.get(origin, origin), METROS.get(dest, dest), depart, "--stops", stops,
           "--passengers", str(adults),
           "--sort", "CHEAPEST", "--format", "json"]
    if ret:
        cmd += ["--return", ret, "--top-n", "2"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        d = json.loads(p.stdout)
    except ValueError:
        raise ApiError("fli: " + (p.stderr or p.stdout)[-300:])
    out = []
    for f in d.get("flights", []):
        if not f.get("price"):
            continue
        legs = f.get("legs") or f.get("outbound", {}).get("legs", [])
        back = f.get("return", {}).get("legs", []) if f.get("return") else []
        if not legs:
            continue
        carriers = list(dict.fromkeys(l["airline"]["name"] for l in legs + back))
        nums = " ".join(f'{l["airline"]["code"]}{str(l.get("flight_number", "")).removeprefix(l["airline"]["code"])}' for l in legs)
        out.append(row(source="fli", origin=origin, dest=dest, depart=depart, ret=ret or "", adults=adults,
                       price_pp=round(f["price"] / adults, 2), price_total=f["price"], seller="(Google Flights)",
                       carriers=" / ".join(carriers), flights=nums, dep_time=legs[0]["departure_time"][11:16],
                       arr_time=legs[-1]["arrival_time"][11:16],
                       back_dep=back[0]["departure_time"][11:16] if back else "",
                       back_arr=back[-1]["arrival_time"][11:16] if back else "",
                       stops=len(legs) - 1, link=f.get("booking_url", "")))
    return sorted(out, key=lambda x: x["price_pp"])[:top]


def doctor():
    checks = []
    node = shutil.which("node")
    if node:
        v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
        major, minor = (int(x) for x in v.lstrip("v").split(".")[:2])
        checks.append(("node " + v, (major, minor) >= (22, 13), "install Node.js 22.13+ from https://nodejs.org"))
    else:
        checks.append(("node", False, "install Node.js 22.13+ from https://nodejs.org"))
    has_aa = (APIS / "node_modules" / "api-anything").exists()
    checks.append(("api-anything in apis/node_modules", has_aa, f'npm install --prefix "{APIS}"'))
    home = Path.home() / ".api-anything"
    specs = all((home / "sites" / f"{s}.json").exists() for s in ("kayak", "jetsmart"))
    checks.append(("Kayak + JetSMART specs installed", specs, f'node "{APIS / "aa.mjs"}" install'))
    session = (home / "sessions" / "kayak.json").exists()
    checks.append(("Kayak session", session,
                   f'npx --prefix "{APIS}" api-anything login kayak --window   (load Kayak once in the window, then close it)'))
    checks.append(("fli CLI", bool(shutil.which("fli")),
                   'uv tool install "flights[mcp] @ git+https://github.com/punitarani/fli.git"'))
    for name, good, fix in checks:
        print(f"  {'OK  ' if good else 'MISS'} {name}" + ("" if good else f"\n       fix: {fix}"))
    print("  OK   Buquebus (stdlib, no setup)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", choices=["kayak", "jetsmart", "buquebus", "fli", "doctor"])
    ap.add_argument("origin", nargs="?")
    ap.add_argument("dest", nargs="?")
    ap.add_argument("date", nargs="?")
    ap.add_argument("--return", dest="ret")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--days", type=int, default=0, help="jetsmart: also show +/- this many days")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    if a.source == "doctor":
        return doctor()
    if not (a.origin and a.dest and a.date):
        ap.error("origin, dest and date are required")
    try:
        if a.source == "kayak":
            rows = kayak(a.origin, a.dest, a.date, a.ret, a.adults, a.top)
        elif a.source == "jetsmart":
            rows = jetsmart(a.origin, a.dest, a.date, a.days)
        elif a.source == "buquebus":
            rows = ferry(a.origin, a.dest, a.date, a.adults)[: a.top]
        else:
            rows = fli(a.origin, a.dest, a.date, a.ret, a.adults, top=a.top)
    except (ApiBlocked, ApiError) as e:
        print(json.dumps({"ok": False, "error": str(e), "blocked": isinstance(e, ApiBlocked)}))
        sys.exit(1)
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
