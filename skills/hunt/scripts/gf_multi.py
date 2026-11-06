"""Price a multi-city / open-jaw itinerary on Google Flights (fli can't do multi-city).

Each positional arg is one itinerary; legs separated by '/', fields by ','.
  uv run --with fast-flights --with typing_extensions --with playwright python gf_multi.py \
      EZE,DFW,2026-10-20/JFK,EZE,2026-11-15 --pax 2 --stops 1

--url-only   just print the Google Flights URL (open it with the Claude in Chrome tools - most reliable)
--show       run Chrome visibly instead of headless
--out DIR    where to save the page text (default: current dir)

Uses your installed Chrome (channel="chrome"), so no `playwright install` download is needed.
Output: aria-labels Google puts on each result card ("From 4097 US dollars total ..."). The price on a
multi-city page is the WHOLE-TRIP total for all passengers. Compare it with the sum of one-way searches -
in practice separate one-ways were usually equal or cheaper.
"""
import argparse
import sys
from pathlib import Path


def url_for(legs, pax, stops, currency, max_layover):
    from fast_flights import FlightQuery, Passengers, create_query
    q = create_query(
        flights=[FlightQuery(date=d, from_airport=o, to_airport=t, max_layover_minutes=max_layover) for o, t, d in legs],
        trip="multi-city", passengers=Passengers(adults=pax), currency=currency, language="en", max_stops=stops)
    return q.url()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("itins", nargs="+", help="ORIG,DEST,YYYY-MM-DD/ORIG,DEST,YYYY-MM-DD[/...]")
    ap.add_argument("--pax", type=int, default=1)
    ap.add_argument("--stops", type=int, default=1, help="max stops per leg")
    ap.add_argument("--max-layover", type=int, default=300, help="minutes")
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--url-only", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    jobs = []
    for it in a.itins:
        legs = [x.split(",") for x in it.split("/")]
        if any(len(l) != 3 for l in legs):
            sys.exit(f"bad itinerary '{it}': each leg must be ORIG,DEST,YYYY-MM-DD")
        jobs.append((legs, url_for(legs, a.pax, a.stops, a.currency, a.max_layover)))
    if a.url_only:
        for legs, u in jobs:
            print(" + ".join("-".join(l) for l in legs), "\n ", u)
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=not a.show)
        pg = b.new_page(locale="en-US")
        for legs, u in jobs:
            name = " + ".join("-".join(l) for l in legs)
            print("=" * 20, name, "\nURL:", u)
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            body, labels, prev = "", [], -1
            js = ("els => els.map(e => e.getAttribute('aria-label'))"
                  ".filter(t => /dollars|[$]|total/i.test(t) && /flight|Leaves|departure/i.test(t))")
            for i in range(30):  # results stream in client-side; wait_for_selector alone times out
                pg.wait_for_timeout(2000)
                body = pg.inner_text("body")
                labels = pg.eval_on_selector_all("div[aria-label]", js)
                if "No results" in body or "No flights" in body:
                    break
                if "Loading results" not in body and labels and len(labels) == prev:
                    break  # result count stable across two polls
                prev = len(labels)
            print(f"waited {(i + 1) * 2}s")
            out = Path(a.out) / f"gf_multi_{'_'.join(l[0] + l[1] + l[2][5:] for l in legs)}.txt"
            out.write_text(body, encoding="utf-8")
            print(f"{len(labels)} priced results (page text saved to {out})")
            for t in labels[:15]:
                print(" -", t[:420])
            if not labels:
                print("  none parsed - open the URL above in the browser tools instead")
        b.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
