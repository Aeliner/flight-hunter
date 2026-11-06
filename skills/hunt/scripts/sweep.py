"""Sweep many origin x destination pairs with fli, one search at a time, and print the cheapest
fare per pair. Use it for gateway / hub scans ("which Asian hub is cheap from GRU?").

  python sweep.py --from MVD,GRU,GIG --to ICN,TPE,PVG,KIX --date 2027-02-19 [--return 2027-03-05] \
      --pax 1 --stops 1 --out raw --prefix hub_ [--top-n 3] [--sleep 2] [--extra "--exclude-airlines ZG"]

Each pair costs 1 Google page (one-way) or 1 + top_n (round trip). Saves raw/<prefix><O>-<D>_<date>.json,
skips pairs already saved (re-run safely), then prints a table sorted by price. Feed the files to
`legs.py rows` / `legs.py trip` / `legs.py combo` afterwards.
"""
import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path


def cheapest(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    fl = [f for f in d.get("flights", []) if f.get("price")]
    if not fl:
        return {"price": None, "n": 0}
    f = min(fl, key=lambda x: x["price"])
    legs = f.get("legs") or (f.get("outbound", {}).get("legs", []) + f.get("return", {}).get("legs", []))
    carriers = " / ".join(dict.fromkeys(l["airline"]["name"] for l in legs))
    pax = d.get("query", {}).get("passengers", 1) or 1
    return {"price": f["price"], "pp": round(f["price"] / pax), "n": len(fl), "carriers": carriers,
            "route": "-".join([legs[0]["departure_airport"]["code"]] + [l["arrival_airport"]["code"] for l in legs]) if legs else ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="orig", required=True, help="comma list of origin airports")
    ap.add_argument("--to", dest="dest", required=True, help="comma list of destination airports")
    ap.add_argument("--date", required=True)
    ap.add_argument("--return", dest="ret")
    ap.add_argument("--pax", type=int, default=1)
    ap.add_argument("--stops", default="1", help="0, 1, 2+ or ANY")
    ap.add_argument("--top-n", type=int, default=3, help="round trip only")
    ap.add_argument("--out", default="raw")
    ap.add_argument("--prefix", default="sweep_")
    ap.add_argument("--sleep", type=float, default=2, help="seconds between searches (be gentle)")
    ap.add_argument("--extra", default="", help="extra fli flags, quoted")
    a = ap.parse_args()

    fli = shutil.which("fli")
    if not fli:
        sys.exit('fli not found - uv tool install "flights[mcp] @ git+https://github.com/punitarani/fli.git"')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    pairs = [(o, d) for o in a.orig.split(",") for d in a.dest.split(",") if o != d]
    for i, (o, d) in enumerate(pairs, 1):
        f = out / f"{a.prefix}{o}-{d}_{a.date}{'_' + a.ret if a.ret else ''}.json"
        if not f.exists() or f.stat().st_size < 50:
            cmd = [fli, "flights", o, d, a.date, "--stops", a.stops, "--passengers", str(a.pax), "--format", "json"]
            if a.ret:
                cmd += ["--return", a.ret, "--top-n", str(a.top_n)]
            cmd += shlex.split(a.extra)
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
            f.write_text(p.stdout, encoding="utf-8")
            print(f"[{i}/{len(pairs)}] {o}-{d} exit {p.returncode}", file=sys.stderr)
            time.sleep(a.sleep)
        c = cheapest(f) or {"price": None, "n": 0}
        rows.append((o, d, c))
    rows.sort(key=lambda r: (r[2]["price"] is None, r[2]["price"] or 0))
    kind = f"round trip {a.date}->{a.ret}" if a.ret else f"one-way {a.date}"
    print(f"\nCheapest per pair ({kind}, {a.pax} pax, stops<={a.stops}; price = total, pp = per person)")
    for o, d, c in rows:
        if c["price"] is None:
            print(f"  {o}-{d}: no results (0 itineraries - not proof none exist)")
        else:
            print(f"  {o}-{d}: {c['price']:.0f} total / {c['pp']} pp  {c['carriers']}  {c['route']}  ({c['n']} options)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
