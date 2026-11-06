---
name: watch
argument-hint: "[trip folder or trip.json]"
description: Re-price a saved flight-hunter trip and report what changed since the last check. Use when the user wants to refresh, re-check or watch prices for a trip they already hunted ("did the Tokyo fares move?", "refresh my trip", "is it time to buy?"). Search only, never books.
---

# Trip watch

Re-price the finalists of a trip that `/flight-hunter:hunt` already found, and tell the user what moved. Ground rules from the hunt skill apply: search only, never book; report only prices a tool showed; searches one at a time.

`PY` below means `uv run --no-project python`. Scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/`.

## 1. Find the trip

- If the argument is a folder, use its `trip.json`. If it's a JSON file, use it.
- If there's no argument, look for `*/trip.json` in the trips folder `${user_config.trips_dir}` and in the current folder. If that value is blank or still reads `${user_config...}`, use only the current folder. One found: use it. Several: list them by name with their last run date (the newest `YYYY-MM-DD/` folder next to each) and ask which.
- None found: say so, and offer to run a quick hunt (`/flight-hunter:hunt quick ...`), which writes one.

Read the trip file and the newest `<date>/report.md` next to it, if any, so you know the last numbers.

## 2. Check the tools

Run `PY ${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/doctor.py --quick`. If the Kayak level isn't ready, say once that this run will use Google Flights only, and that `/flight-hunter:setup` adds Kayak. Then carry on.

## 3. Run the watch

Run `PY ${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/watch.py <trip.json>`, or the `trip_watch` MCP tool. It takes a few minutes, because Kayak is paced. It writes `<workspace>/<today>/` with `raw/`, `results.csv`, `summary.json` and `report.md`, diffed against the last run.

If Kayak answers "blocked", don't retry. Tell the user to run the Kayak login shown in the error, and finish with the other sources. If it says the daily budget is spent, the same applies without the login.

## 4. Quick scan for something new

Keep it to about 10 Google fetches:
- one `fli dates` round-trip grid for the main pair, ±2 days around the trip's dates;
- one Kiwi `search-flight` for the main pair.

Don't redo routes the original hunt marked as checked and lost, unless a finalist moved by more than ~15%.

## 5. Report (short)

Build on `report.md`:
1. A table of complete door-to-door prices per finalist: per person and group total. Say whether each group price is exact, an estimate or a split.
2. The change since the last run (↑/↓). A `*` means a leg's source changed (e.g. Kayak was blocked), so it isn't a real price move. Say so.
3. Who sells the cheapest finalist, with its link.
4. Anything new from step 4 that beats the finalists. If it should become a finalist, offer to add it to `trip.json` with today's price as its baseline.
5. A one-line "buy now or wait?" read. Base it on the trend across the dated runs and how close departure is: inside ~6 weeks, fares mostly climb. Say it's a judgement, not a forecast.

If the profile currency `${user_config.currency}` is set and isn't USD, add the converted group total for the cheapest finalist ("≈", with the rate and its date).

End with the reminder that fares change constantly, so re-check on the seller's site right before buying. If the user wants this daily, `references/watch.md` in the hunt skill has the scheduling note. Set that up only when they ask.
