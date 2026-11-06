---
name: setup
description: Check and install what flight-hunter needs on this machine (uv, the fli CLI, optional Kayak support, the Claude in Chrome extension) and show which search levels work. Use after installing the plugin, when a hunt says a source is missing, or when the user asks to set up, fix or check flight-hunter.
---

# flight-hunter setup

Get the user to the highest level they want, with as little effort from them as possible. Every level above Base is optional, so never make the user feel blocked.

| Level | Needs | Adds |
|---|---|---|
| Base | uv + git | Google Flights (fli) and Kiwi. Most hunts work here |
| Kayak | Node.js 22.13+, a ~50 MB npm install, a one-time login window | Kayak's OTA fares at real group sizes (it beat Google on every main route in testing), JetSMART |
| Chrome | Claude in Chrome extension, a paid Claude plan (Pro, Max, Team or Enterprise) | Skyscanner, airline websites, Kayak's seller list |

`PY` below means `uv run --no-project python`. Scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/`.

## 1. Check

Run `PY ${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/doctor.py`, without `--quick`, so it also tries one live Google Flights search. Show the user the "Levels" card it ends with.

If `uv` itself is missing, nothing above runs. Give the one-line installer for their OS (Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`, macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`). Suggest they paste it with a `!` prefix so it runs in this session, then restart Claude Code so the plugin's MCP servers start. Don't run remote install scripts yourself.

## 2. Install what's missing

Ask once, in one message, which of the missing pieces they want. Recommend Kayak if Node is already there.

- **fli CLI and Kayak support:** run `PY ${CLAUDE_PLUGIN_ROOT}/skills/hunt/scripts/doctor.py --fix --quick`. It runs `uv tool install` for fli, and `npm ci` for api-anything into `~/.flight-hunter/apis`. It needs no admin rights.
- **Node.js** missing or older than 22.13: point them to https://nodejs.org (LTS). Don't install system software for them.
- **Kayak login:** first tell them what will happen: "A browser window opens. Load any Kayak flight search, clear the check if one shows, then close the window." Then run the login command that doctor printed, with a 10-minute timeout. If no window can open (remote or headless machine), skip Kayak and say so.

## 3. Chrome

Check whether the `mcp__claude-in-chrome__*` tools are available in this session.
- Available: Chrome level is ready.
- Not available: it's optional. They'd need the extension (https://claude.com/chrome), a paid Claude plan signed in with `/login` (API keys, Bedrock and Vertex don't get it), then `/chrome`, with "Enabled by default" on. It isn't supported under WSL.

## 4. Profile

Show the saved profile:
- Home airports: `${user_config.home_airports}`
- Passports: `${user_config.passports}`
- Currency: `${user_config.currency}`
- Trips folder: `${user_config.trips_dir}`

A blank value, or one still reading `${user_config...}`, isn't set. If any are unset, say they save questions on every hunt and are set with `/plugin configure flight-hunter@flight-hunter`. All of them are optional.

## 5. Finish

Re-run `doctor.py --quick` and show the final Levels card. Also say:
- if the fli, kiwi or flight-apis tools didn't show up in this session, run `/mcp` to see their status, and restart Claude Code after installing uv;
- how to start: "Ask for a trip in plain words, or `/flight-hunter:hunt quick MAD to NYC in March, 2 people`."
