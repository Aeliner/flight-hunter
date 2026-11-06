---
name: hunt
argument-hint: "[quick|deep] <trip: from, to, dates, people>"
description: Find the cheapest or best-value flights for any trip. Searches Google Flights through the fli CLI/MCP, Kiwi, and Kayak/Skyscanner/airline sites in Chrome, then looks for the routes most people never check. These include positioning flights to cheaper gateway cities, self-transfer combos on separate tickets, alternate airports, ferry or bus legs, one-ways vs round trips, point-of-sale and group-size pricing. Flags tight connections, overnight layovers, airport changes, separate-ticket risk, bag fees and visa needs. Use it whenever someone wants flights or airfare, asks for the cheapest way to get somewhere, is planning travel for a trip or event, compares dates or routes, or mentions Google Flights, Kayak, Skyscanner or an airline, even if they never say "search". Search only, never books.
---

# Flight Hunter

Find what a patient, obsessive human would find after a weekend on Google Flights, Kayak and airline sites, in minutes. The cheapest fare is rarely the obvious one. It might be a one-stop through Panama to the *wrong* city plus a $90 hop. It might be a ferry to a bigger airport, or the airline's US website instead of its local one. The method is: get an honest baseline, then systematically try the plays in `references/hidden-routes.md`, verifying each with a real search.

## Ground rules

These protect the user. Keep them even if asked to "just book it".

- **Search only.** Never book, never enter names, passport numbers, emails, phone numbers or payment details, never log in. Stop at the price or seat-selection page and hand the user the link.
- **Report only what a tool or page actually showed.** Every price in the report needs a source: fli, Kiwi, kayak.com, latam.com and so on. If something wasn't searched, say "not checked". Don't estimate it. Approximate totals are fine only as sums of real prices, labeled as such.
- **Remind the user** that fares and schedules change constantly. They should re-check on Google Flights or the airline's site right before buying.
- **Be gentle with sites.** Run searches one at a time, not in parallel bursts. Keep to the depth's Google budget below unless the user wants more. A one-way `fli flights` costs 1 fetch, a round trip 1 + `top_n`, and `fli dates` 1 per date in the range, so a 9-day grid costs 9. Google may rate-limit a hammering IP. Kayak has its own daily cap, enforced by the tools.

## Profile

Saved when the plugin was installed (`/plugin` → flight-hunter → configure to change). A value that is blank, or still reads `${user_config...}`, isn't set: ask for it in Step 1 as usual.

- Home airports: `${user_config.home_airports}`
- Passports: `${user_config.passports}`
- Currency: `${user_config.currency}`
- Trips folder: `${user_config.trips_dir}`

Use set values as defaults without asking again. Still confirm them when the request hints otherwise ("flying from my parents' place", "my partner has a Brazilian passport").

## Depth

Pick from the arguments or the wording. Say which depth you're running in one line, and at the end offer to go one deeper.

| Depth | When | What runs | Google budget |
|---|---|---|---|
| **quick** | `quick`, or a casual "how much is X→Y in May?" | Step 1 with defaults, asking only what blocks a search. Step 2 items 1–2 for the main pair. Kiwi once. `kayak_search` on the top 2. Short report: the pick, top 5, flags | ~15 fetches, a few minutes |
| **standard** | default | Every step. In Step 3, only the plays that fit this trip, pruned with lower bounds | ~80 fetches |
| **deep** | `deep`, "leave no stone unturned", "find anything clever", big groups or long-haul with lots of flexibility | Every step and all six rings with `sweep.py`, the seller sweep for each finalist, Chrome sites, subagents for big sweeps | ~150 fetches |

## Tools

Run the bundled scripts as `uv run --no-project python ${CLAUDE_SKILL_DIR}/scripts/<script>.py ...`. uv is already required and works on every OS, while a bare `python` or `python3` is missing on many machines. Below, `PY` is short for `uv run --no-project python`.

Run `PY ${CLAUDE_SKILL_DIR}/scripts/doctor.py --quick` first. It prints which levels work on this machine (Base: Google Flights + Kiwi; Kayak; Chrome) and the fix for each gap. If the user wants the missing pieces installed, that's `/flight-hunter:setup`. Fallback details are in `references/fli.md`.

| Tool | Use it for |
|---|---|
| `fli` CLI (Google Flights) | The workhorse. One-way and round-trip searches, date grids, comma-separated airport lists. Use `--format json` and save to files. Cookbook: `references/fli.md` |
| fli MCP tools (`search_flights`, `search_dates`) | Same data without a shell. Handy for quick looks; the CLI with JSON files is better for building a dataset |
| Kiwi MCP (`search-flight`) | Kiwi's "virtual interlining": self-transfer combos across airlines that don't partner. Good for weird cheap routes |
| `scripts/gf_multi.py` | Google Flights multi-city and open-jaw prices, which fli can't do. Run with `uv run --no-project --with fast-flights --with typing_extensions --with playwright python ${CLAUDE_SKILL_DIR}/scripts/gf_multi.py ORIG,DEST,DATE/ORIG,DEST,DATE --pax N`. Uses local Chrome. `--url-only` prints a link to open in the browser instead |
| flight-apis MCP (`kayak_search`, `jetsmart_fares`, `buquebus_fares`, `trip_watch`) / `scripts/flightapis.py` | Kayak, JetSMART and Buquebus over plain HTTP, no browser. Kayak gives round trips for 1/2/3/5 adults and one-ways for 1 adult, with seller, bags and a link. It's capped at about 40 searches a day, so spend them on finalists. **Use these before Chrome.** Setup, limits and the Kayak login: `references/watch.md` |
| `scripts/watch.py` | Trip watch. Re-prices a trip file's finalists from the APIs only, works out group splits and self-transfer gaps, and diffs against the last run. Each hunt writes the trip file (Step 6), and `/flight-hunter:watch` runs it later. Format: `references/watch.md` |
| Claude in Chrome | The sites with bot walls: Skyscanner, LATAM, Gol, Despegar, Copa, ZIPAIR and airline sites (point-of-sale pricing, LCCs Google misses). Also the Kayak seller list ("Step 2"), and Kayak itself when its API is blocked. Playbook: `references/sites.md` |
| `scripts/legs.py` | Turns fli JSON into rows with risk flags, builds self-transfer combos, logs browser-found fares, ranks everything into the report |
| `scripts/sweep.py` | Scans many origin × destination pairs, one fli search at a time, and prints the cheapest per pair. Use it for gateway and hub scans: `--from GRU,GIG,MVD --to ICN,TPE,PVG,KIX --date ... [--return ...]` |
| `scripts/page_text.py` | Headless Chrome page-text grabber, a fallback when the extension isn't connected. Kayak and LATAM block it; it reports BLOCKED and moves on |

Check whether the `mcp__claude-in-chrome__*` tools are available. If the browser isn't connected, do everything possible with fli, Kiwi and the site APIs. Then give the user links for the bot-walled sites to check themselves, and say which sources weren't covered. If `kayak_search` answers "blocked" or "budget is spent", don't retry it. For a block, ask the user to run the Kayak login once (`references/watch.md`). Carry on with the other sources either way.

Practical notes, learned the hard way:
- **Keep the workspace in the profile's trips folder, or else the folder Claude Code is running in. Never use a temp or scratch directory.** A temp folder got wiped mid-trip and every script and raw search was lost.
- Write scripts with the file-writing tool, not shell heredocs: nested quotes broke them repeatedly.
- On Windows, `python -I` ignores `PYTHONIOENCODING`. The bundled scripts reconfigure stdout to UTF-8 themselves, so do the same in any helper you write.
- MCP search results can be enormous (one was 195k characters). For anything beyond a quick look, use the CLI and write JSON to files.

If the trip starts or ends in South America, also read `references/south-america.md`. It covers airports, ferry links, Brazil gateways, visas for UY/AR/BR passports, pricing quirks, and the JetSMART and Buquebus tools.

## Step 1: Pin down the trip

Get these up front. Ask for whatever's missing in one short batch, not one question at a time. Guess sensible defaults where the user clearly doesn't care.

- **Real destination**, not just a city. Ask for the venue or address, then list every airport within about 3–4 hours' drive. Example: an event in Allen TX means DFW, DAL, and also AUS/IAH/HOU/SAT if paired with a cheap hop or drive.
- **All plausible origins.** Home airport, other airports reachable by cheap bus, ferry, train or short flight, and big gateways one hop away. A Montevideo traveler can reach EZE/AEP by ferry and GRU/GIG are cheap positioning targets; someone in Lyon can take the train to Geneva or Paris.
- **Dates and flexibility.** Hard limits, e.g. "arrive by Nov 5", plus how many days of wiggle.
- **Trip shape.** Round trip, open-jaw, multi-city. A trip like A→B, B→C, C→A is usually cheaper priced as separate one-ways. Verify, don't assume.
- **Passengers and cabin.** Ask whether people can fly on separate bookings or must share one.
- **Bags** checked or carry-on only. Basic-economy fares hide bag fees.
- **Passport nationality** for every traveler. This decides which connection countries need a visa: US transit always needs a visa or ESTA, and Canada's eTA is only for some nationalities. Read the visa section of `references/risks.md`.
- **Tolerance:** separate tickets/self-transfer OK? Overnight layovers? Maximum total hours? Price vs time priority. Loyalty programs or co-branded credit cards they hold, e.g. a LATAM Pass card that gives a free bag.

## Step 2: Baseline, protected single tickets

Set up a workspace in the trips folder (see Profile): `<trip-slug>/raw/` for JSON and `<trip-slug>/results.csv` for the dataset. Name files `<leg>_<ORIG>-<DEST>_<date>.json` so they're easy to recombine later.

1. **Date grid** for each main origin→destination pair:
   - One-way: `fli dates ORIG DEST --from ... --to ... --stops 1 --passengers N --format json`.
   - Round trip: add `--round --duration 7`. That gives the price per departure day for a fixed-length trip, the most useful single call for a simple holiday.
   - Pick the 3–5 cheapest days that fit the constraints.
2. **Flights** on those days, sorted twice: `--sort CHEAPEST` and `--sort DURATION`, using comma lists for airport groups (`EZE,AEP` → `DFW,DAL`). Start with `--stops 1 --max-layover 300`, then one unrestricted search (`--stops ANY`) on the best day. Sometimes a 2-stop is far cheaper.
3. **Round trips both ways.** Price the round trip (`--return DATE`), *and* price each direction as a one-way. Then pair them with `legs.py trip --out out*.json --ret ret*.json --csv results.csv`. Two one-ways often beat the round trip, and missing the outbound doesn't cancel the return. Return one-ways from a different airport give open-jaw options for free.
4. **Nonstops**, if any exist (`--stops 0`).
5. Log everything: `PY ${CLAUDE_SKILL_DIR}/scripts/legs.py rows raw/*.json --csv results.csv`. This handles fli one-way, round-trip and date-grid JSON, and Kiwi JSON if you saved it to a file.

`"success": true, "count": 0` does **not** mean no flights. In one test, fli's round trip to Tampa returned nothing while both one-way directions had Copa flights. When a route comes back empty, retry as one-ways, try nearby dates, or try another source before concluding anything.

This baseline is what every clever route has to beat.

## Step 3: Hunt the hidden routes

This step is where the savings come from. Read `references/hidden-routes.md`. It lists each play, when it pays off, how to search it, and real examples with numbers. In short:

- **Kiwi explore:** `flyTo` = a country with `one_for_city: true` gives the cheapest fare to every city there in one call. It's the fastest way to spot a cheap gateway or wrong-city option.
- **Wrong-city + hop:** a cheap long-haul into a nearby city, then a separate domestic flight or a drive.
- **Positioning:** ride or fly to a gateway with more competition first, e.g. GRU/GIG instead of MVD, or LAX for Asia.
- **Self-transfer through a hub** (MIA, PTY, LAX, Lisbon...) on two tickets. Build combos with `legs.py combo`.
- **Low-cost carriers Google barely shows** (ZIPAIR, Frontier, Flybondi, JetSMART, Arajet...). Check their own sites.
- **Point of sale:** the same airline is often much cheaper on its US/English site than on the local one.
- **Shape tricks:** one-ways vs round trip vs multi-city (`gf_multi.py`), open-jaw, nearby departure days.
- **Group size:** 1 passenger can be cheaper per head than 4. Fare buckets run out, so try splitting the booking.
- **Other origins:** ferry or bus to a bigger airport, or start from the city where part of the group already is.

**Generate the weird candidates systematically.** Don't rely on inspiration. Walk these rings and list concrete airports for each, then scan them with `sweep.py`:
1. **Origin ring:** home airports, places reachable by ferry or bus, and the big gateways one cheap hop away.
2. **Destination ring:** other airports in the destination country plus rail (Osaka for Tokyo, Austin for Dallas), and neighbor-country hubs plus an LCC hop (Seoul or Taipei for Tokyo).
3. **Hub ring:** where carriers with cheap long-haul fares connect (Panama, Madrid/Lisbon, Istanbul, Doha/Dubai, Addis, Mexico City, Santiago).
4. **Third-continent split:** two round-trip tickets that meet at a hub on another continent, e.g. South America→Europe + Europe→Asia.
5. **Visa corridor:** list which countries the travelers can transit or overnight in *without* a visa. For anyone without a US visa, drop the US and Canada and push corridors via Europe, the Middle East, Mexico or Asia.
6. **Marketing carrier:** the same metal sold under a partner's name can be cheaper and include more bags.

hidden-routes.md §16–19 has the method and real numbers for each ring.

**Prune with lower bounds.** Price each ring's unavoidable component first, e.g. origin↔hub before the hop. If it already exceeds the best complete option, drop the ring after one scan and log "checked, lost" with the number. In the Japan hunt this killed 8 Asian hubs and the Mexico/Oceania corridors in a few searches each.

For sweeps across many gateways or dates, split the work across parallel subagents. Recipe in hidden-routes.md §15.

Give each play a quick real search before spending effort on it. Drop plays that clearly can't beat the baseline, and say so in the report: "Dallas-direct checked: cheapest $2,339 vs $1,496 via Austin + hop".

## Step 4: Cross-check other engines

Google doesn't see everything, and **this step is not optional.** In real hunts Kayak beat Google on *every* main route: Iberia MVD↔Tokyo $1,770 vs $2,193, Copa to Austin $993 vs $1,221.
- Check the best 2–4 candidates on Kayak with `kayak_search`. It needs no browser; search at the real group size too (2/3/5 adults), because cheap buckets often hold fewer seats.
- Use Chrome for the Kayak card's seller list when fare brands and bag options matter, for Skyscanner, and for the operating airline's site (try its US site too).
- If neither the Kayak API nor the extension works, say clearly which sources were and weren't checked. Run one Kiwi search per main leg. Follow `references/sites.md` for the URL templates and page quirks. Log each real fare with `legs.py add --source kayak.com ...`. Note the fare class (Basic/Light/Classic) and whether a bag is included, because a "cheaper" Basic fare plus bags often loses.

### Seller sweep: once the route and airline are fixed

The same seat is sold by many shops at different prices. For each finalist itinerary, spend 3–5 page loads finding **who** sells it cheapest. Full method is in sites.md under "Seller sweep".
1. **Kayak card → Select → "Step 2: Same flight. Different deals."** This lists every seller with its price, airline direct and OTAs.
2. **Google Flights booking page** (the fli `booking_url`): airline-direct prices per marketing carrier, with fare brands and bag rules.
3. **Airline sites in 2–3 points of sale:** the origin country, the US, and sometimes the destination country.
4. **Partner/codeshare carriers selling the same flights.** In real hunts, JAL-marketed fares on AA metal were $1,310–1,332 with 2 bags. AA direct was $1,697 and JAL direct $2,126.

**Judge the seller, not just the price.**
- Airline direct gives the best help when flights change or get cancelled.
- Mainstream OTAs (Expedia, Orbitz, Travelocity) are fine.
- Budget OTAs (Justfly/FlightHub, Mytrip/Gotogate, eDreams, Kiwi) are often cheapest, but they handle changes and refunds poorly.
- If the budget OTA saves less than ~$30–50 per person, recommend the reputable seller.

## Step 5: Assemble and rank

For multi-leg trips, price each leg and add them up. `legs.py trip` builds the whole-trip rows for out + back. For anything more complex, log the sums with `legs.py add` and a `trip_` tag. Label separate tickets.

`PY ${CLAUDE_SKILL_DIR}/scripts/legs.py top results.csv --max-hours 20` prints:

- the fastest,
- the cheapest under N hours,
- the best value (per-person price plus 20 per travel hour, adjustable with `--hour-value`),
- the cheapest of any length,
- a top-10 table with links, with dominated options removed.

Ranking is per person. Rank like with like:
- `--filter '^trip' --max-hours 30` for whole trips (hours = out + back).
- `--filter outbound` for one leg.
- `--pax 2` for one group size.

The value score knows nothing about ground time. For wrong-city options, add the drive or transfer time to the duration you log, or say it explicitly in the report.

## Step 6: Report

Save the report as `report.md` in the trip folder. If file writes aren't allowed, e.g. when running as a subagent, put the full report in your reply. Start with an **Assumptions** section whenever you had to guess anything: dates, bags, destination airport, car vs no car.

**Quote complete door-to-door trips, not pieces.**
- Every option's headline price is the **full round trip from the traveler's home airport and back, per person**, including positioning flights, hops and paid ground legs. Put the breakdown underneath ("= $155 MVD→GIG + $1,310 GIG↔HND + $142 GIG→MVD").
- Quoting a component, like "São Paulo↔Tokyo $1,308", as if it were the option's price confused a real user, because MVD↔GRU was missing.
- Add the group total for the actual group split, e.g. 3 back early + 2 later.
- Name hotel nights forced by the routing even when unpriced.

Lead with the answer, then the evidence:

1. **Recommendation:** the one itinerary to book and why, total for the group and per person.
2. **The four picks:** fastest / cheapest under N h / best value / cheapest of any length.
3. **Top-10 table:** date, total, per person, time, airlines, route, layovers, flags, source, link.
4. **Flags**, in plain language: tight connections (under 2h at the first US airport means immigration plus customs), overnight layovers, airport changes, separate tickets (what happens if leg 1 is late), basic economy/bags, visas.
5. **What was checked and lost:** one line per play that didn't pay, so the user trusts the search was thorough.
6. **Booking tips:** which site to book on and in what order, e.g. buy the long-haul first and then the hop with buffer. Add the reminder that prices change.
7. Path of `results.csv` and `trip.json`, plus the line: "Run `/flight-hunter:watch <trip folder>` any time to re-price these and see what moved."

**Write `trip.json`** next to the report, in the format in `references/watch.md`. Include the 3–5 finalists you'd actually consider, with today's prices as each finalist's `baseline`. Split each finalist into the legs it's bought as. Give every leg sources the APIs can re-price (`kayak`, `fli`, plus `jetsmart`/`buquebus` where they apply). For a fare found only in Chrome, still list `kayak`/`fli` and say in its `label` where it was found. Use `["kayak", "fli"]` with `"fallback": true` for main legs. Set `group`, `workspace` (the trip folder) and `connectTo`/`minConnect` for same-day self-transfers. In quick mode, write it only for the top 2–3.

**Currency.** Prices stay in USD. If the profile currency is something else, add the group total in that currency for the recommendation and the four picks. Mark it "≈", and give the rate and its date from one lookup.

When showing totals, always say whether a number is per person or for the whole group. fli JSON prices are the total for all passengers in the query. Kayak and most airline sites show per person.
