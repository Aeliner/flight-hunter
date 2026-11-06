# Site APIs and trip watch

Some sites can be called over plain HTTP, the way their own pages call them, so a re-check needs no
browser. They're wrapped in `scripts/flightapis.py` (CLI + library), the `flight-apis` MCP server
(`kayak_search`, `jetsmart_fares`, `buquebus_fares`, `trip_watch`) and `scripts/watch.py`.

## Sources

| Source | What | Limits |
|---|---|---|
| Kayak (`apis/aa.mjs`, api-anything specs in `apis/sites/`) | Round trip for 1/2/3/5 adults, one-way for 1. Per-person price, seller, bags, times, link | ~10–25 s per search. Blocks heavy users, so the tools space calls 4 s apart and cap them at 40 a day (`FLIGHT_HUNTER_KAYAK_DAILY`), shared by every caller |
| JetSMART (api-anything) | The airline's own 12-month lowest-fare cache from an airport (South America) | 1-person fares, base fare (carry-on only), no arrival time |
| Buquebus (`apis/buquebus.py`, stdlib) | Every ferry sailing × seat class × tariff, total for the group | MVD/COL/PDE ↔ BUE |
| fli (Google Flights) | One-ways and round trips, 1–4 adults | 5+ adults returns nothing; 1 Google fetch per one-way |

Bot-walled in testing (Nov 2026), so Chrome only: LATAM, Skyscanner, Despegar, Gol, Copa, ZIPAIR,
Turismocity, Expedia results, Iberia's own site. Don't try to get around them.

## Setup (once per machine)

`/flight-hunter:setup` does all of this. By hand (`PY` = `uv run --no-project python`, run from the skill folder):

```sh
PY scripts/doctor.py --quick      # shows each level and what's missing
PY scripts/doctor.py --fix        # installs the fli CLI, and api-anything into ~/.flight-hunter/apis (needs Node 22.13+)
npx --prefix ~/.flight-hunter/apis api-anything login kayak --window   # load Kayak once in the window, then close it
```

State lives in `~/.flight-hunter` (override with `FLIGHT_HUNTER_HOME`), not in the plugin folder, which each
plugin update replaces. After an update that changes the node side, the tools say so and `--fix` reinstalls it.

The Kayak login is needed on a fresh machine and again whenever Kayak starts answering `blocked`. Kayak's
search API only accepts requests that carry cookies its own anti-fraud script sets in a real browser. The
window gives a person the chance to clear any check. api-anything then reuses those cookies until they expire.
After a block the tools leave Kayak alone for 10 minutes, or until the login is run again. Don't retry during that time.

## Trip file

Each hunt writes `trip.json` into its trip folder. The format:

```json
{
  "name": "Lisbon to Tokyo, April 2027",
  "group": 2,
  "alertDrop": 50,
  "workspace": "~/trips/lisbon-tokyo-apr",
  "finalists": [
    {
      "id": "ist-tk", "label": "Turkish via Istanbul", "notes": "protected single ticket",
      "baseline": {"date": "2026-11-06", "pp": 912, "group": 1824},
      "legs": [
        {"id": "main", "label": "LIS↔NRT", "from": "LIS", "to": "NRT", "date": "2027-04-03",
         "return": "2027-04-17", "sources": ["kayak", "fli"], "fallback": true}
      ]
    },
    {
      "id": "mad-pos", "label": "Fly to Madrid + Iberia", "notes": "separate tickets",
      "baseline": {"date": "2026-11-06", "pp": 845, "group": 1690},
      "legs": [
        {"id": "pos-out", "label": "LIS→MAD Apr 3", "from": "LIS", "to": "MAD", "date": "2027-04-03",
         "sources": ["fli", "kayak"], "connectTo": "main", "minConnect": 180},
        {"id": "main", "label": "MAD↔NRT", "from": "MAD", "to": "NRT", "date": "2027-04-03",
         "return": "2027-04-17", "sources": ["kayak", "fli"], "fallback": true},
        {"id": "pos-back", "label": "MAD→LIS Apr 18", "from": "MAD", "to": "LIS", "date": "2027-04-18",
         "sources": ["fli", "kayak"]}
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
- `workspace` may start with `~`. Without it, runs go next to the trip file.

## How group prices are worked out

The report never prices a group as N copies of the 1-adult fare without saying so. Each leg gets one of these labels:

- **exact**: the whole group was searched as one booking (Kayak at 5, fli up to 4, Buquebus any count).
- **estimate**: the group is too big for the source (fli at 5), so the price is the group size times the largest searchable fare (the 4-adult fare).
- **1-adult fares**: the source only has single-person fares (JetSMART cache, Kayak one-way). It's flagged.
- **split?**: two separate bookings (e.g. 3 + 2) are cheaper than one. This is optimistic: both searches see the same seats, so confirm the seat count on the site.

## Running it

`/flight-hunter:watch <trip folder or trip.json>` runs it and summarises. By hand:

```sh
PY scripts/watch.py path/to/trip.json [--only id1,id2] [--no-kayak] [--kayak-budget 20] [--pause 4]
```

It writes `<workspace>/<YYYY-MM-DD>/` containing `raw/` (every search), `results.csv`, `summary.json` and
`report.md`. The report has a finalists table (per person, group, ↑/↓ since the last run, sellers),
per-leg detail with links, self-transfer gaps, and what wasn't checked. Searches run one at a time.

To run it daily, schedule `uv run --no-project python <plugin>/skills/hunt/scripts/watch.py <trip.json>`
with Task Scheduler (Windows), cron (Linux) or launchd (macOS). Set that up only when the user asks: it's a
standing change on their machine. It has to run on their machine, because the Kayak session is local.
