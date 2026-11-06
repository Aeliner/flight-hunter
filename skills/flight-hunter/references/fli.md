# fli cookbook (Google Flights from the command line)

fli (github.com/punitarani/fli) queries Google Flights and returns structured results. It is the backbone of every hunt: fast, free, no browser.

## Install / repair

```bash
uv tool install --force "flights[mcp] @ git+https://github.com/punitarani/fli.git"
```
- Install from **GitHub**, not PyPI. The PyPI `flights` package (≤0.9.0) is stale and breaks when Google changes its page.
- The `[mcp]` extra is needed for `fli-mcp`. Without it you get "MCP dependencies are not installed".
- No pipx needed. `uv tool install` puts `fli`, `fli-mcp` and `fli-mcp-http` on PATH, under `~/.local/bin` on Windows too.
- MCP for a standalone install (the plugin does this automatically through uvx): `claude mcp add --scope user fli -- fli-mcp`
- On Windows, set `PYTHONIOENCODING=utf-8` before piping output. Otherwise ✈ and similar characters crash with UnicodeEncodeError (cp1252).

If searches start failing, check https://github.com/punitarani/fli/issues: Google changes its page every few months, and fixes land on GitHub first. Reinstall with the command above. Fallback chain: fast-flights ≥3.1.0 (`pip install fast-flights`), then the browser on google.com/travel/flights, then tell the user.

## Searches

```bash
# one-way, max 1 stop, layovers ≤5h, 2 adults, JSON to file
fli flights EZE,AEP DFW,DAL,AUS 2026-10-20 --stops 1 --max-layover 300 --passengers 2 --sort CHEAPEST --format json > raw/out_BUE-TX_2026-10-20.json

# same day sorted by duration (shows the fast-but-pricey end)
fli flights EZE DFW 2026-10-20 --stops 1 --sort DURATION --passengers 2 --format json > raw/out_EZE-DFW_1020_dur.json

# unrestricted stops on the best day (2-stops are sometimes much cheaper)
fli flights EZE DFW 2026-10-20 --stops ANY --passengers 2 --format json > raw/unres_EZE-DFW_1020.json

# nonstop only
fli flights EZE IAH 2026-10-22 --stops 0 --passengers 2 --format json

# cheapest day in a window (single airport pair, at most 93 days per call)
fli dates EZE DFW --from 2026-10-15 --to 2026-11-05 --stops 1 --max-layover 300 --passengers 2 --format json > raw/dates_EZE-DFW.json

# round-trip date grid: price per departure day for a 7-day trip (1 fetch per date)
fli dates MVD MCO --from 2027-01-06 --to 2027-01-14 --round --duration 7 --stops 1 --passengers 2 --format json

# round trip (costs 1 + top_n page fetches)
fli flights MVD MIA 2026-12-10 --return 2026-12-20 --top-n 5 --format json
```

Page-fetch cost: one-way = 1, round trip = 1 + `--top-n`, `fli dates` = 1 per date in the range. Budget with that in mind.

`"success": true, "count": 0` is not proof that no flights exist. Example: the MVD↔TPA round trip and round-trip grid both came back empty, yet each one-way direction had Copa flights. Retry as one-ways, try nearby dates, or try Kiwi or Kayak.

Useful flags:
- `--time 6-20`: departure window.
- `--airlines` / `--exclude-airlines`: e.g. drop an LCC.
- `--alliance ONEWORLD`
- `--layover MIA`: force a connection airport.
- `--min-layover 120`: avoid tight US connections.
- `--class BUSINESS`
- `--currency EUR`
- `--country US` / `--language en-US`: point-of-sale experiment, sets Google's `gl=`/`hl=`.
- `--children`, `--infants-on-lap`

## Output facts

- `price` in JSON is the **total for all passengers** in the query. `legs.py` derives `price_pp`.
- Each flight has `legs[]` with `departure_airport.code`, `arrival_airport.code`, `departure_time`, `arrival_time` (local ISO), `airline.code/name` and `flight_number`. It also has `duration` (minutes), `stops` and `booking_url`, a Google Flights link to put in the report.
- Round-trip results have no top-level `legs`. Each flight has `outbound{legs, duration, stops}` and `return{...}`, and `price` covers the whole round trip for everyone. `legs.py rows` handles both shapes.
- `fli dates` returns `dates[]` with `departure_date`, `price` and `booking_url` (plus `return_date` with `--round`): the cheapest fare that day under the given filters. Use it to choose days, then run `fli flights` for the actual itineraries.
- `--bags 1` prints "Filters not supported by the search-page transport, ignored: bags" to stderr. Prices are for the cheapest fare brand, so check bags on the airline site.

## Limitations (as of late 2026)

- **Multi-city is not supported** ("Multi-city search is not available through the search-page transport"). Use `scripts/gf_multi.py` or price legs as one-ways. One-ways usually come out cheaper anyway.
- fli now uses Google's public search page. Bag, basic-economy, alliance and emissions filters may be silently ignored, so verify the fare type on the booking page.
- Results are Google's. LCCs that block Google (some Asian and Latin American carriers) and Kiwi-style virtual interlines won't appear. That's why the hunt also uses Kiwi and the browser.
- `fli dates` takes one origin and one destination, no comma lists. Loop over pairs.
- Comma lists in `fli flights` return the cheapest across all pairs. Don't assume every pair is represented, so search the important pairs separately.
  - It's worse for **round trips**: only the cheapest `top_n` outbounds get expanded. A 10-hub comma list effectively priced 2 hubs.
  - Use `scripts/sweep.py`, which runs one search per pair, for hub scans.
- `--airlines` filters work. Some carriers (e.g. Turkish from South America) simply don't appear in Google's results for a route, even when filtered.
- Prices are cached snapshots from Google, and the airline site can differ by a few dollars. Report the source.

## fli MCP tools

The tools are `search_flights`, `search_dates`, `find_airports` and `get_booking_options`. Their full names depend on how the server was registered, e.g. `mcp__fli__search_flights` or `mcp__plugin_flight-hunter_fli__search_flights`. Parameters mirror the CLI (`max_stops`: ANY/NON_STOP/ONE_STOP/TWO_PLUS_STOPS, `sort_by`, `passengers`, `max_layover`, `country`, `currency`...).
- `find_airports("dallas")` lists the airports near a city. Use it when building the destination airport list.
- `get_booking_options` is meant to list who sells an itinerary (airline vs OTAs). In late 2026 it failed with "Google Flights declined the request with error 13 (INTERNAL)... requires a browser-signed x-goog-batchexecute-bgr header" (fli issue #223). Try it once. If it fails, open the itinerary's `booking_url` in the browser, where Google lists the sellers.
- If a call fails with `retryable: true`, back off a few seconds and retry once or twice. A 429 means slow down more.
- **MCP results can be huge.** One multi-origin search returned 195k characters and overflowed into a file. Keep `show_all_results: false`, a tight `max_stops`, and a small `top_n` for round trips. Or use the CLI and write the JSON to disk.
- fli MCP `search_dates` with `start_date == end_date` is a cheap one-call price check per gateway. That's handy when sweeping many origins.

Prefer the CLI with JSON files when you will combine or rank many searches, because MCP results don't land on disk.

## Kiwi MCP (`search-flight`)

Kiwi builds "virtual interlining" itineraries: separate tickets on unrelated airlines (Sky + Copa, JetSMART + LATAM, Volaris + Frontier...) sold as one booking with Kiwi's own guarantee. At the airport it's still a self-transfer. That makes it the best tool for **connections nobody would think of**.

Key parameters:
- `flyFrom`, `flyTo`: IATA code, city, **or country name**.
- `departureDate` in **dd/mm/yyyy**. Add `departureDateFlexDays` (±0–10) or `departureDateTo` for a range.
- `returnDate` (optional).
- `adults`, plus `adults_hold_bags` such as `[1,1]` to price checked bags in.
- `currency` defaults to **EUR**, so set `"USD"`.
- `sort`: price/duration/quality.
- `max_sector_stopovers`, `stopover_from`/`stopover_to` (hours), `stopover_airports`, `exclude_stopover_countries` (e.g. `US` for travelers without a US visa), `allow_self_transfer`, `allow_overnight_stopovers`, `allow_diff_airport_connection`.

**Explore mode (gateway discovery):** set `flyTo` to a country and `one_for_city: true`. You get the cheapest fare to *every* city in that country in one call. Example: MVD → "United States", 10/12/2026 → IAD $451 (Sky+Copa via SCL+PTY), ORD $473 (LATAM+Volaris via LIM+MEX), MIA $492 (Copa), JFK $598 (JetSMART to GIG + LATAM)... Use it to spot which gateway city is cheap, then verify that gateway with fli and price the onward hop.

Caveats: the `price` is for all passengers, and the baggage object shows what's included (often just a personal item). Always set `max_fly_duration` (e.g. 30–40 hours). Without it Kiwi returns absurd 50h+ routings. Kiwi also misses some inventory, e.g. the Gol/LATAM MVD-GRU nonstops. Kiwi isn't always cheapest: the same day, Google had MVD→MIA on AA at $330 pp vs Kiwi's $492 via Copa. Treat Kiwi as a route-idea generator plus one more price source, and verify the legs on Google or the airline.

Kiwi results arrive in the conversation, not on disk. Log the few that matter with `legs.py add --source Kiwi ...`. If a big result overflowed into a saved file, `legs.py rows <that file>` reads Kiwi JSON directly.
