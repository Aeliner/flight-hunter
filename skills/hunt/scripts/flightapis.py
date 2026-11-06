"""Fares from site APIs (no browser at call time), as one row shape.

  python flightapis.py kayak MVD HND 2027-02-19 --return 2027-03-05 [--adults 1|2|3|5] [--top 10]
  python flightapis.py kayak GIG JFK 2027-02-18                      # one-way, 1 adult
  python flightapis.py jetsmart MVD GIG 2027-02-19 [--days 3]        # 12-month fare cache, per person
  python flightapis.py buquebus MVD BUE 2026-11-20 [--adults 2]      # ferry, USD
  python flightapis.py fli MVD GIG 2027-02-19 [--return ...] [--adults 5]
  python flightapis.py doctor                                        # same as doctor.py --quick

Row: source, origin, dest, depart, ret, adults, price_pp, price_total, currency, seller, carriers,
dep_time, arr_time, back_dep, back_arr, stops, bags, link, note. Prices are USD unless currency says.
Kayak and JetSMART need Node 22.13+ and the npm install that `doctor.py --fix` does. A blocked Kayak
raises ApiBlocked: the user runs `npx --prefix ~/.flight-hunter/apis api-anything login kayak --window` once.

State lives in FLIGHT_HUNTER_HOME (default ~/.flight-hunter), not next to this file: an installed plugin
sits in a versioned cache that each update replaces. The node side (aa.mjs, sites/, package.json) is
copied there from ../apis and `npm install`ed there.
"""
import argparse
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HOME = Path(os.environ.get("FLIGHT_HUNTER_HOME") or Path.home() / ".flight-hunter")
APIS_SRC = Path(__file__).resolve().parent.parent / "apis"  # shipped with the plugin
APIS = HOME / "apis"  # what node runs; survives plugin updates
AA_HOME = Path(os.environ.get("API_ANYTHING_HOME") or Path.home() / ".api-anything")
sys.path.insert(0, str(APIS_SRC))
import buquebus  # noqa: E402

# Kayak blocks after heavy use. One budget and spacing for every caller (MCP tool, watch.py, CLI).
KAYAK_DAILY = int(os.environ.get("FLIGHT_HUNTER_KAYAK_DAILY", "40"))
KAYAK_GAP = 4  # seconds between Kayak searches
KAYAK_COOLDOWN = 600  # seconds to leave Kayak alone after a block
USAGE = HOME / "kayak-usage.json"
LOGIN_CMD = f'npx --prefix "{APIS}" api-anything login kayak --window'


class ApiBlocked(RuntimeError):
    pass


class BudgetSpent(ApiBlocked):
    pass


class ApiError(RuntimeError):
    pass


def sync_apis():
    """Copy the plugin's node files into HOME/apis (and specs into api-anything) when they differ."""
    APIS.mkdir(parents=True, exist_ok=True)
    (APIS / "sites").mkdir(exist_ok=True)
    files = ["aa.mjs", "package.json", "package-lock.json"] + [f"sites/{p.name}" for p in (APIS_SRC / "sites").glob("*.json")]
    for f in files:
        src, dst = APIS_SRC / f, APIS / f
        if not dst.exists() or not filecmp.cmp(src, dst, shallow=False):
            shutil.copyfile(src, dst)
    if (AA_HOME / "sites").exists():  # specs installed before: keep them current with the plugin
        for p in (APIS_SRC / "sites").glob("*.json"):
            dst = AA_HOME / "sites" / p.name
            if not dst.exists() or not filecmp.cmp(p, dst, shallow=False):
                shutil.copyfile(p, dst)


def _pkg_hash():
    return hashlib.sha256((APIS_SRC / "package-lock.json").read_bytes()).hexdigest()[:16]


def needs_install():
    """True until `npm install` has run in HOME/apis for the plugin's current package-lock.json."""
    stamp = APIS / ".installed"
    return not (APIS / "node_modules" / "api-anything").exists() or         not stamp.exists() or stamp.read_text(encoding="utf-8").strip() != _pkg_hash()


def mark_installed():
    (APIS / ".installed").write_text(_pkg_hash(), encoding="utf-8")


def _usage():
    try:
        u = json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        u = {}
    if u.get("date") != date.today().isoformat():
        u = {"date": date.today().isoformat(), "count": 0, "last": u.get("last", 0), "blocked_at": u.get("blocked_at", 0)}
    return u


def _save_usage(u):
    HOME.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(u), encoding="utf-8")


def kayak_gate():
    """Raise if Kayak is cooling down or today's budget is spent; otherwise wait out the gap and count the call."""
    u = _usage()
    session = AA_HOME / "sessions" / "kayak.json"
    relogged = session.exists() and session.stat().st_mtime > u.get("blocked_at", 0)
    if u.get("blocked_at") and not relogged and time.time() - u["blocked_at"] < KAYAK_COOLDOWN:
        until = datetime.fromtimestamp(u["blocked_at"] + KAYAK_COOLDOWN).strftime("%H:%M")
        raise ApiBlocked(f"Kayak blocked this machine earlier; leaving it alone until {until}. "
                         f"To clear it now, the user runs: {LOGIN_CMD}")
    if u["count"] >= KAYAK_DAILY:
        raise BudgetSpent(f"today's Kayak budget is spent ({u['count']}/{KAYAK_DAILY} searches). Kayak blocks heavy "
                          f"users, so carry on with fli/Kiwi. Raise it with FLIGHT_HUNTER_KAYAK_DAILY if you must.")
    wait = u.get("last", 0) + KAYAK_GAP - time.time()
    if wait > 0:
        time.sleep(wait)
    u["count"] += 1
    u["last"] = time.time()
    _save_usage(u)


def kayak_blocked_now():
    u = _usage()
    u["blocked_at"] = time.time()
    _save_usage(u)


def _node(*args, timeout=180):
    node = shutil.which("node")
    if not node:
        raise ApiError("node not found: install Node.js 22.13+ (https://nodejs.org), then run the flight-hunter setup")
    sync_apis()
    if needs_install():
        raise ApiError("Kayak/JetSMART support isn't installed (or the plugin update changed it). "
                       "Run the flight-hunter setup: doctor.py --fix")
    p = subprocess.run([node, str(APIS / "aa.mjs"), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    try:
        d = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ApiError((p.stderr or p.stdout)[-400:])
    if not d.get("ok"):
        if d.get("class") in ("blocked", "auth", "rate"):
            if args[0] == "kayak":
                kayak_blocked_now()
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
    # the stamp is epoch ms (17xx-19xx...) and an IATA code has a letter, so flight-number digits can't pose as either
    return re.findall(r"1[7-9]\d{11}([A-Z][A-Z0-9]|[0-9][A-Z])", leg_id or "")


def kayak(origin, dest, depart, ret=None, adults=1, top=10):
    if (ret and adults not in (1, 2, 3, 5)) or (not ret and adults != 1):
        raise ApiError("kayak: round trips take 1, 2, 3 or 5 adults; one-ways take 1 adult")
    kayak_gate()
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
    import doctor as doc  # the full check lives in doctor.py
    doc.main(["--quick"])


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
