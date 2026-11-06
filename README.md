# flight-hunter

A Claude Code plugin that hunts flights the way an obsessive human would after a weekend on Google Flights, Kayak and airline sites, but in minutes. It gets an honest baseline first, then tries the routes most people never check:

- a cheap flight into the *wrong* city plus a short hop or train,
- positioning to a cheaper gateway (fly or ride to a bigger airport first),
- self-transfers on separate tickets through a hub,
- ferries, buses and trains to bigger airports,
- the airline's other-country website (point of sale),
- splitting a group into separate bookings when fare buckets run out,
- the same seat from a cheaper seller.

Every option is quoted door to door, per person and for the group, with flags for tight connections, overnight layovers, airport changes, bags and **visas for your passport**. Then it saves your finalists so you can re-price them later and see what moved.

**It only searches.** It never books, logs in or touches payment or passport details.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git. In Claude Code:

```
/plugin marketplace add Aeliner/flight-hunter
/plugin install flight-hunter@flight-hunter
```

It asks for an optional profile (home airports, passports, currency, trips folder) so hunts don't ask every time. Restart Claude Code, then run:

```
/flight-hunter:setup
```

Setup checks your machine, installs what's missing with your OK, and shows which levels work.

## Levels: what you need for what

Only Base is needed. Each level adds sources, and the hunt always tells you which ones it skipped.

| Level | Needs | Adds |
|---|---|---|
| **Base** | uv + git | Google Flights (through [fli](https://github.com/punitarani/fli)) and Kiwi. Most of the hunt works here |
| **Kayak** | Node.js 22.13+, a one-time login window | Kayak's OTA fares at real group sizes. In testing it beat Google on every main route, by $100–400 per person |
| **Chrome** | The [Claude in Chrome](https://claude.com/chrome) extension and a paid Claude plan (Pro/Max/Team/Enterprise), turned on with `/chrome` | Skyscanner, airline websites (point-of-sale prices, low-cost carriers Google misses), Kayak's seller list |

**Why not just web fetch or a headless browser?** Flight sites build their prices with JavaScript and block plain requests and headless browsers. In testing, Kayak answered "you are a bot", and LATAM, Skyscanner, Copa and others threw captchas or 403s. Claude in Chrome works because it drives *your* real browser, the way you would. flight-hunter doesn't try to get around bot walls.

## Use it

Just ask in plain words. The skill triggers on any flight question. Or call it directly:

| Command | What it does |
|---|---|
| `/flight-hunter:hunt [quick\|deep] <trip>` | The hunt. **quick** takes a few minutes: baseline, Kiwi and Kayak on the top picks. The default runs every step. **deep** walks every alternate route and seller |
| `/flight-hunter:watch [trip]` | Re-prices a saved trip's finalists, shows ↑/↓ since the last check, and gives a buy-now-or-wait read |
| `/flight-hunter:setup` | Checks and installs dependencies, and shows your levels |

Examples:

> /flight-hunter:hunt quick Madrid to New York, March 10–20, 2 people, carry-on only

> We're 2 adults and 2 kids in Lyon, want Bangkok over Christmas, ±3 days. Separate tickets are fine if it saves real money.

> 5 of us from Montevideo to Tokyo around Feb 19. Three must be back by Mar 8. Find anything clever.

> /flight-hunter:watch tokyo-feb

Each hunt writes a folder in your trips folder: `raw/` (every search), `results.csv`, `report.md` and `trip.json`, which is what `watch` re-prices.

Change the profile any time with `/plugin configure flight-hunter@flight-hunter`.

## Privacy and fair use

- Everything runs on your machine. Searches go from your computer to Google Flights, Kiwi and (if set up) Kayak, as if you searched yourself. Nothing is sent anywhere else.
- Searches run one at a time, with budgets: about 80 Google fetches for a standard hunt, and at most 40 Kayak searches a day, spaced out. Please keep it that way. Hammering these sites gets your IP blocked and spoils it for everyone.
- **The Kayak level is experimental.** It calls the same endpoints kayak.com's own page calls, using cookies from your own browser session, which the one-time login window sets. It's for personal searching. If Kayak blocks you, it stops and tells you; it never tries to dodge the block.
- State lives in `~/.flight-hunter` (Kayak budget, node deps) and `~/.api-anything` (Kayak session). Delete them to reset.

## Updating

```
/plugin marketplace update flight-hunter
```

Then restart Claude Code. If an update changes the Kayak support, the hunt tells you to re-run `/flight-hunter:setup`.

## What's inside

```
.claude-plugin/          plugin + marketplace manifests (profile options live in plugin.json)
.mcp.json                fli (Google Flights, via uvx), Kiwi (remote), flight-apis (Kayak/JetSMART/Buquebus)
skills/hunt/             the method: intake → baseline → hidden routes → cross-check → rank → report
  references/            fli cookbook, website playbook, hidden-route plays, risks and visas, trip watch, regional packs
  scripts/doctor.py      checks levels; --fix installs the fli CLI and Kayak support
  scripts/legs.py        fli JSON → rows with risk flags, self-transfer combos, ranking
  scripts/sweep.py       scans many origin × destination pairs (gateway and hub sweeps)
  scripts/watch.py       trip watch: re-prices finalists from the APIs and diffs runs
  scripts/flightapis.py  Kayak / JetSMART / Buquebus / fli as one row format (CLI + library)
  scripts/gf_multi.py    Google Flights multi-city prices (Playwright + your Chrome)
  apis/                  Kayak and JetSMART request specs (api-anything), Buquebus client
skills/watch/            /flight-hunter:watch
skills/setup/            /flight-hunter:setup
```

Fares change by the hour. Always re-check on the seller's site right before buying.

## Contributing

Regional packs (airports, ground links, visa notes for local passports, local sites) and new site playbooks are the most useful additions. See [CONTRIBUTING.md](CONTRIBUTING.md).

MIT licensed.
