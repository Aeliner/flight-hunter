# Site APIs and trip watch

Some sites can be called over plain HTTP, the way their own pages call them, so a re-check needs no
browser. They're wrapped in `scripts/flightapis.py` (CLI + library), the `flight-apis` MCP server
(`kayak_search`, `jetsmart_fares`, `buquebus_fares`, `trip_watch`) and `scripts/watch.py`.

## Sources

| Source | What | Limits |
|---|---|---|
| Kayak (`apis/aa.mjs`, api-anything specs in `apis/sites/`) | Round trip for 1/2/3/5 adults, one-way for 1. Per-person price, seller, bags, times, link | ~10–25 s per search. Blocks after heavy use: pace it, budget ~20 a run |
| JetSMART (api-anything) | The airline's own 12-month lowest-fare cache from an airport | 1-person fares, base fare (carry-on only), no arrival time |
| Buquebus (`apis/buquebus.py`, stdlib) | Every ferry sailing × seat class × tariff, total for the group | MVD/COL/PDE ↔ BUE |
| fli (Google Flights) | One-ways and round trips, 1–4 adults | 5+ adults returns nothing; 1 Google fetch per one-way |

Bot-walled in testing (Nov 2026), so Chrome only: LATAM, Skyscanner, Despegar, Gol, Copa, ZIPAIR,
Turismocity, Expedia results, Iberia's own site. Don't try to get around them.

## Setup (once per machine)

```sh
python scripts/flightapis.py doctor                       # shows what's missing
npm install --prefix apis                                 # Node 22.13+; installs api-anything 0.3.2
node apis/aa.mjs install                                  # copies the specs, keeps catalog sharing off
npx --prefix apis api-anything login kayak --window       # load Kayak once in the window, then close it
```

The Kayak login is needed on a fresh machine and again whenever Kayak starts answering `blocked`. Kayak's
search API only accepts requests that carry cookies its own anti-fraud script sets in a real browser. The
window gives a person the chance to clear any check. api-anything then reuses those cookies until they expire.
After a block it also stops sending to Kayak for 10 minutes. Don't retry during that time.

## Trip file

```json
{
  "name": "Japan Feb 2027",
  "group": 5,
  "alertDrop": 50,
  "workspace": "C:/coding/flight/japan-2027",
  "finalists": [
    {
      "id": "rio-jal", "label": "Rio + JAL", "notes": "US visa",
      "group": 5,
      "baseline": {"date": "2026-11-02", "pp": 1629, "group": 7895},
      "legs": [
        {"id": "pos-out", "label": "MVD→GIG Feb 19", "from": "MVD", "to": "GIG", "date": "2027-02-19",
         "sources": ["jetsmart", "fli"], "connectTo": "main", "minConnect": 180},
        {"id": "main", "label": "GIG↔HND", "from": "GIG", "to": "HND", "date": "2027-02-19",
         "return": "2027-03-05", "sources": ["kayak"]}
      ]
    }
  ]
}
```

Field notes:
- `group` sets the number of travellers. A finalist can override it, e.g. 2 people on a later return.
- `sources` are tried in order. The cheapest 1-adult fare across them wins.
- With `"fallback": true`, later sources run only if the earlier ones found nothing. Use
  `["kayak", "fli"]` with fallback for main legs: Google covers for Kayak when it blocks, without doubling
  the traffic on a normal day.
- `connectTo` and `minConnect` apply to a positioning leg on the same day as the leg it feeds. Fares that
  land less than `minConnect` minutes before that leg departs are dropped, and the report shows the gap.
- `baseline` is used for "vs last" until the first run's `summary.json` exists.

## How group prices are worked out

The report never prices a group as N copies of the 1-adult fare without saying so. Each leg gets one of these labels:

- **exact**: the whole group was searched as one booking (Kayak at 5, fli up to 4, Buquebus any count).
- **estimate**: the group is too big for the source (fli at 5), so the price is the group size times the largest searchable fare (the 4-adult fare).
- **1-adult fares**: the source only has single-person fares (JetSMART cache, Kayak one-way). It's flagged.
- **split?**: two separate bookings (e.g. 3 + 2) are cheaper than one. This is optimistic: both searches see the same seats, so confirm the seat count on the site.

## Running it

```sh
python scripts/watch.py path/to/trip.json [--only id1,id2] [--no-kayak] [--kayak-budget 20] [--pause 4]
```

It writes `<workspace>/<YYYY-MM-DD>/` containing `raw/` (every search), `results.csv`, `summary.json` and
`report.md`. The report has a finalists table (per person, group, ↑/↓ since the last run, sellers),
per-leg detail with links, self-transfer gaps, and what wasn't checked. Searches run one at a time.

To run it daily on Windows, use Task Scheduler with `python <path>\watch.py <trip.json>`. Set it up only
when the user asks: it's a standing change on their machine.
