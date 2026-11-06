# flight-hunter

A Claude Code plugin that hunts flights the way an obsessive human would: Google Flights (through [fli](https://github.com/punitarani/fli)), Kiwi, and Kayak/Skyscanner/airline sites in your browser. After the baseline search it tries the routes most people never check:

- a cheap flight into the *wrong* city plus a short hop,
- positioning to a cheaper gateway,
- self-transfers on separate tickets,
- ferries and buses to bigger airports,
- airline US-site pricing,
- splitting the group into separate bookings.

Every option gets flags for tight connections, overnight layovers, airport changes, bags and visas.

**It only searches.** It never books, logs in or touches payment details.

## Install (Claude Code)

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git installed, plus Python 3.10+.

```
/plugin marketplace add <github-user>/flight-hunter
/plugin install flight-hunter@flight-hunter
```

Restart Claude Code. The plugin brings:
- the **flight-hunter** skill, which triggers automatically when you ask about flights. You can also call it as `/flight-hunter:flight-hunter`.
- the **fli** MCP server (Google Flights), which installs itself on first use through `uvx`.
- the **Kiwi** MCP server (remote, no install).

Recommended extras:
- `uv tool install "flights[mcp] @ git+https://github.com/punitarani/fli.git"` puts the `fli` CLI on your PATH. The skill uses it to save searches as JSON and rank them.
- The [Claude in Chrome](https://claude.com/chrome) extension, connected, so Claude can cross-check Kayak, Skyscanner and airline sites.
- Playwright, only for Google Flights multi-city prices. It runs automatically through `uv run --with playwright`.

Check your setup anytime: ask Claude to "run the flight-hunter doctor".

### Site APIs and trip watch (v0.3)

Kayak, JetSMART and Buquebus can be searched over plain HTTP with no browser. There's also a **trip watch** that re-prices your finalists and shows what changed since the last run. Setup, once (needs [Node.js](https://nodejs.org) 22.13+):

```
npm install --prefix skills/flight-hunter/apis
node skills/flight-hunter/apis/aa.mjs install
npx --prefix skills/flight-hunter/apis api-anything login kayak --window
```

In the Kayak window, load any Kayak search page, clear the check if one appears, then close the window. Do this again whenever Kayak starts answering "blocked". Then ask Claude to "watch my trip", or run `python skills/flight-hunter/scripts/watch.py my-trip.json`. The trip file format is in `references/watch.md`.

Kayak blocks after heavy use, so the watch searches one at a time with pauses and a budget. LATAM, Skyscanner, Despegar, Gol, Copa and ZIPAIR have bot walls, so they still need Claude in Chrome.

### Without the plugin system

Copy `skills/flight-hunter/` into `~/.claude/skills/`. Then add the MCP servers yourself:
```
claude mcp add --scope user fli -- uvx --from "flights[mcp] @ git+https://github.com/punitarani/fli.git" fli-mcp
claude mcp add --scope user --transport http kiwi https://mcp.kiwi.com
```

## Try it

> We're 2 adults in Montevideo. We need to be in Allen, Texas by Nov 5 for an event, then New York, then back home. Cheapest sane way? Separate tickets are OK.

> 5 of us from Uruguay to Tokyo around Feb 19. Three must be back by Mar 8. Find anything clever.

## What's inside

```
.claude-plugin/        plugin + marketplace manifests
.mcp.json              fli (uvx) + Kiwi MCP servers
skills/flight-hunter/
  SKILL.md             the method: intake → baseline → hidden routes → cross-check → rank → report
  references/          fli cookbook, per-website playbook, hidden-route plays, risk/visa rules
  scripts/legs.py      fli JSON → rows with risk flags, self-transfer combos, ranking
  scripts/gf_multi.py  Google Flights multi-city scraper (Playwright + your Chrome)
  scripts/sweep.py     scan many origin x destination pairs (gateway / hub sweeps)
  scripts/page_text.py headless page grabber (fallback; Kayak/LATAM block it)
  scripts/doctor.py    checks what's installed
```

Fares change by the hour. Always re-check on Google Flights or the airline's site before buying.
