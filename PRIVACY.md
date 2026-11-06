# Privacy policy

Last updated: 2026-11-06

flight-hunter is a Claude Code plugin that runs entirely on your own computer. Its author runs no servers and collects, receives and stores nothing about you or your searches.

## What stays on your computer

- **Your profile** (home airports, passport nationalities, currency, trips folder), if you fill it in. Claude Code keeps it in its own settings on your machine.
- **Trip folders** each hunt writes in the folder you choose: raw search results, `results.csv`, `report.md`, `trip.json`.
- **`~/.flight-hunter`**: the Kayak/JetSMART helper and a daily Kayak search counter.
- **`~/.api-anything`**: the Kayak session cookies set by the one-time login window, if you use the Kayak level.

Delete these files or folders at any time to remove the data.

The plugin never asks for or handles names, emails, passport numbers or payment details. It searches only and never books.

## What leaves your computer

To find fares, your computer sends search queries straight to these services, as if you searched on their websites yourself: airports, dates, number of passengers, cabin and stops. Those services see your IP address, as they do for any visit, and their own privacy policies apply:

| Service | When | Privacy policy |
|---|---|---|
| Google Flights (through the open-source [fli](https://github.com/punitarani/fli) library) | Every hunt | https://policies.google.com/privacy |
| Kiwi.com (its official MCP server, mcp.kiwi.com) | Every hunt | https://www.kiwi.com/en/pages/content/privacy |
| Kayak | Only if you set up the optional Kayak level | https://www.kayak.com/privacy |
| JetSMART | Only for South America positioning legs, if you set up the Kayak level | See the privacy link on https://jetsmart.com |
| Buquebus | Only for Montevideo/Colonia ↔ Buenos Aires ferry searches | See the privacy link on https://www.buquebus.com |
| Websites you visit through Claude in Chrome | Only if you use the Chrome level | That site's policy |

Your conversation with Claude, including the trip details you type, is handled by Anthropic under its own terms and privacy policy, not by this plugin.

## Children

flight-hunter isn't directed at children under 18.

## Contact

Questions or concerns: open an issue at https://github.com/Aeliner/flight-hunter/issues. For security issues, see [SECURITY.md](SECURITY.md).
