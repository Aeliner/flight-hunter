# Contributing

The most useful contributions come from real hunts: a route trick that saved money, a site that beat Google, a visa rule that changed. Please include the numbers you saw and the date.

## Regional packs

`skills/hunt/references/south-america.md` is the template. A pack for another region covers:

1. **Airports and ground links:** which airports compete, and the ferries, trains and buses that reach a bigger one.
2. **Passports and visas:** transit and entry rules for the region's common passports, with the date you checked.
3. **Pricing quirks:** point-of-sale differences, local OTAs, card perks and taxes.
4. **Regional tools,** if any.

In `skills/hunt/SKILL.md`, add a line saying when to read it, next to the South America one.

## Sites

- **Website playbooks** (`references/sites.md`): URL templates, page quirks, what the site showed vs Google. Say whether it's bot-walled.
- **Plain-HTTP site APIs** (`apis/`, `scripts/flightapis.py`): only for endpoints the site's own page calls, without bypassing bot protection. Add the source to `watch.py`'s `SIZES` and to the `flight-apis` MCP server. Keep calls paced and budgeted.

## Before a pull request

```sh
claude plugin validate . --strict
uv run --no-project python skills/hunt/scripts/doctor.py --quick
```

Bump `version` in `.claude-plugin/plugin.json`. Users only get an update when it changes.

## Ground rules that don't change

Search only, never book. Report only prices a tool or page actually showed. Be gentle with sites. Don't evade bot detection.

## Pinned dependencies

The fli version is pinned to a commit in both `.mcp.json` and `skills/hunt/scripts/doctor.py` (`FLI_SRC`). When Google changes its page and fli ships a fix, bump both to the new commit.
