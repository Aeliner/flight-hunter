# Website playbook (Claude in Chrome)

Google Flights (through fli) covers most airlines, but not all fares or sellers. Each site below earned its place by beating Google at least once in real hunts. Use the browser tools: most of these sites block plain HTTP fetches (403) or render prices with JavaScript.

## General browser habits

- Start with `tabs_context_mcp` and open a new tab. Close it when done.
- Cookie banners: pick **Reject all / necessary only**.
- Set filters through **URL parameters, not checkboxes**. Clicking Kayak's "2+ stops" box flipped the search to *only* 2+ stops.
- Results stream in slowly. A single wait can't exceed 10s, so wait about 10s plus 5s and then read. Use `find`/`get_page_text` to extract cards, and use `read_page` on a card for bag tooltips.
- "Back" navigation can fail ("Cannot find a next page in history"), so re-navigate by URL.
- If the extension disconnects or a page fails 2–3 times, stop. Report what's unverified and give the user the URL to check. Don't loop.
- Never type passenger names, emails, passport or card data. Stop at the fare selection page.
- Note per-person vs total for every number you copy, plus the **fare brand** (Basic/Light/Classic...) and what bags it includes. Log each with `legs.py add`.

## Google Flights (in the browser)

- Itinerary link (from fli `booking_url`): `https://www.google.com/travel/flights/booking?tfs=<base64>&curr=USD`. Open it to see the sellers (airline vs OTAs) and fare brands.
- Search link: `https://www.google.com/travel/flights?q=Flights%20from%20MVD%20to%20GRU%20on%202027-02-19&curr=USD`. Natural-language `q=` works.
- Multi-city: build the URL with `scripts/gf_multi.py --url-only ...` and open it. The browser loads it in about 8s, more reliably than headless Playwright. The page says "Prices include required taxes + fees for N adults" and shows the **whole-trip total**.
- Date grid and price graph views are good for showing the user how flexible dates move the price.

## Kayak: cheapest OTA fares and "hacker fares"

- URL: `https://www.kayak.com/flights/BUE-DFW,DAL/2026-10-20/2adults?sort=price_a&fs=stops%3D0%2C1`
  - City codes work (BUE, NYC, TYO, LON). So do comma lists of airports.
  - Passengers: `1adults`, `2adults`, `2adults/children-11`.
  - Stops: `fs=stops%3D0` nonstop, `%3D0%2C1` max 1 stop, `%3D0%2C1%2C2` any.
  - Sort: `sort=price_a` cheapest, `sort=duration_a` fastest, `sort=bestflight_a` best.
  - Round trip: `/MVD-MIA/2026-12-10/2026-12-20/2adults`.
- Prices are **per person** ("$494 / person", with "$988 total" underneath). The footer says they exclude bag fees.
- Often $100–250 per person cheaper than Google on the *same* flights through OTAs. Examples: Copa EZE→PTY→AUS was $993 on Kayak vs $1,221 on Google for 2. The AA Basic fare was $1,889 vs $1,995.
- **Group size and airline in the URL:**
  - Use `/3adults` to see per person and total for the whole group. That reveals fare-bucket limits: Iberia was $1,770 at 1–2 adults and $1,824 at 3.
  - Use `&fs=airlines%3DIB` to show one airline.
- **Seller and fare brand:** click a card to expand it, then **Select**. A panel opens showing the seller ("Iberia", or the OTA name) and the fare-brand ladder with what each includes. Example: Basic+Optimal $1,770 carry-on only, Basic+Comfort $1,849, Basic with a checked bag $1,951. This doesn't book anything.
- **Marketing carrier variants:** the same flights can appear several times under different airline names. "Japan Airlines" on AA metal cost $1,310 with 2 bags, while "American Airlines" Main cost $1,707. Read past the first card.
- `find` with "first N flight result cards (airline, stops, durations, price, fare name, bags)" pulls the key data in one call. `read_page` on a card gives exact times, layovers and the bag tooltip.
- "Self-transfer hack" or "Hacker fare" labels mean separate tickets. The "Cheapest" tab often leads with 30–35h self-transfers, so check the "Best" tab too.
- Skip paid ad cards at the top.
- Read the bag tooltip on each card ("1 carry-on included / 0 checked bags, fee unknown").

## Skyscanner: more OTAs, good for self-transfers

- URL: `https://www.skyscanner.com/transport/flights/eze/dfw/261020/?adultsv2=2&cabinclass=economy&rtn=0&stops=!twoPlusStops&sortby=cheapest&currency=USD&market=US&locale=en-US`
  - The date is YYMMDD.
  - Without `currency/market/locale` it guesses from your IP, which showed Chilean pesos.
  - For a round trip: `/eze/dfw/261020/261115/?...&rtn=1`.
- Shows per-person and total. It found the cheapest Aerolíneas + Frontier self-transfer in one hunt.
- It may show a bot check. If so, don't solve it; skip the site.

## Kiwi.com: use the MCP, not the website

See `fli.md` → Kiwi MCP. The website is heavy. The MCP's explore mode (`flyTo` = country, `one_for_city`) is the fastest gateway-discovery tool there is.

## Airline sites: point of sale, fare brands, seat counts

**Point-of-sale trick:** the same flight can cost very different amounts depending on which country's version of the airline site you use. Check the site of the country where the trip *starts*, and the US/English site. Example: LATAM JFK→LIM→MVD was **$1,283.50 per person on latamairlines.com/uy but $762.50 per person on /us** (−41%). The MVD→DFW outbound cost the same on both. Pay in USD with a card that has no foreign-transaction fee.

**LATAM** (blocks WebFetch with 403, so use Chrome):
- UY: `https://www.latamairlines.com/uy/es/ofertas-vuelos?origin=MVD&destination=DFW&outbound=2026-10-20T12%3A00%3A00.000Z&inbound=null&adt=2&chd=0&inf=0&trip=OW&cabin=Economy&redemption=false&sort=RECOMMENDED`
- US: `https://www.latamairlines.com/us/en/flight-offers?` with the same parameters. A modal appears; click **"Continue with LATAM United States"**, then reject cookies.
- Prices are per person "from" (the cheapest brand: Light, with no checked bag). A date strip lets you hop to neighboring days.
- Some routes time out ("La búsqueda está tardando más de lo normal"). Try a neighboring airport (DFW worked when DAL failed).

**ZIPAIR** (zipair.net; Tokyo long-haul LCC, often missing from aggregators):
- Flow: `/en` → origin/destination → Search Flight → passport popup (click "Next") → `/en/booking/people` (+ for each adult) → `/booking/calendar/outbound` → `/calendar/return` → `/booking/class/outbound`. Stop there.
- The calendar shows the per-person lowest fare for the chosen headcount. The fare page shows "Only N seats left", which is useful for group bookings.
- Calendar months far ahead aren't in the accessibility tree. Scroll and use zoom screenshots.
- The base fare is carry-on 7 kg only. Add a checked bag (~$85) and meals before comparing.

**Other airline sites worth a look when they're on the candidate route:**
- Copa (copaair.com): Economy Basic vs Classic. Classic includes a bag.
- Aerolíneas Argentinas, JetSMART, Flybondi, Sky Airline: South American LCCs with their own promos.
- Arajet: Dominican LCC linking South America with the US and Caribbean, often cheap.
- Frontier/Spirit (US LCCs, cheap domestic hops). Southwest isn't sold on most OTAs, so check southwest.com. Google shows its fares.
- Iberia, TAP and Air Europa for Europe from South America.
- For Asia: ANA/JAL fare sales, and also ZIPAIR, Scoot and Peach.

Use airline sites to confirm the fare brand, the bag policy, and whether N seats exist at that price. Many show "only N left".

## Ferries, buses, trains (ground legs to a bigger airport)

- **Buquebus** (buquebus.com/uy), Montevideo/Colonia ↔ Buenos Aires:
  - Close the promo popup.
  - Choose one-way, then origin, then destination (it may need a second click), then the date, then Buscar.
  - Prices are per person in **UYU only**. Convert at a current rate from a live FX source, and say which rate you used.
  - Montevideo→BA takes about 2h15–4h30. Colonia + bus is cheaper.
  - Port to EZE is about 45–60 min by taxi. AEP (city airport) is about 15 min.
- **Colonia Express and Cacciola** are alternatives on the same crossing.
- In Europe and the US, Omio/Rome2Rio and FlixBus show bus or train positioning (e.g. a train to a bigger hub).

## FX and prices not in USD

- `https://open.er-api.com/v6/latest/USD` returns live rates as JSON. frankfurter.app redirected (301) in testing.
- Never use a rate from a months-old article. Say which rate and date you used.

## Without the browser extension

**Use the site APIs first** (`references/watch.md`):
- Kayak round trips (1/2/3/5 adults) and one-ways.
- JetSMART's fare cache.
- Buquebus ferries.

All three answer over plain HTTP. Kayak needs a one-time login window on each machine.

Tested 2026-11-03 and walled for headless or plain requests, so these stay in Chrome:
- LATAM (reCAPTCHA Enterprise)
- Skyscanner (PerimeterX)
- Despegar (403)
- Gol (406)
- Copa (bot sensor)
- ZIPAIR (Cloudflare, even its API host)
- Turismocity (Cloudflare tightened after a few hits)
- Expedia results (429)

Headless automation of your own Chrome (`scripts/page_text.py`, Playwright) was **blocked** in testing (2026-11-02):
- Kayak: "KAYAK thinks you are a bot".
- latamairlines.com: "For security reasons, we cannot grant you access".

Don't try to evade bot detection. Ask the user to connect the Claude in Chrome extension, which drives their real browser session and worked fine on these sites. `page_text.py` may still help on simpler sites (ferry and bus operators, small airlines), and it reports BLOCKED and moves on when it meets a bot wall.

## Seller sweep (who sells the chosen itinerary cheapest)

Run this after the route is chosen. Prices for the *same* flights differ by seller, marketing carrier and point of sale, and no single rule says which wins.

| Check | How | What it reveals |
|---|---|---|
| Kayak seller list | Open the result card → **Select** → scroll to "Step 2" | Every seller and its price (airline + OTAs). The top-right shows who the cheapest is |
| Google booking page | Open fli's `booking_url` | "Book with <airline>" per marketing carrier, fare brands (Main vs Basic) and bag rules, sometimes OTAs |
| Airline direct, other POS | Origin-country site, US site, destination-country site | Point-of-sale differences. LATAM's US site was 41% cheaper for a US-origin trip |
| Codeshare partner | Kayak lists marketing carriers separately. Check each partner's own site | JAL-marketed fare on AA metal: $1,310 (OTA) / $1,332 (Expedia) with 2 bags vs AA direct $1,697 / JAL direct $2,126 |
| Local OTA / local currency | Despegar, Expedia BR/AR, prices in BRL/ARS | Installments and local promos. Expedia BR had the Rio fare at R$9,227 (≈$1,697), no better |

Findings from the Nov 2026 Japan hunt:
- **Airline direct is not always cheapest.** For GIG↔HND the cheapest sellers were the budget OTAs (Justfly/FlightHub), then Expedia/Orbitz/Travelocity (+$22). The airlines' own sites were $365–794 more.
- **Sometimes the airline is the only and cheapest seller.** For Iberia MVD↔HND, Kayak's list had just Iberia at $1,770. Skyscanner showed $1,933 and Despegar $2,179.
- **The cheapest seller's quality matters:**
  - Airline direct: best for disruptions.
  - Mainstream OTA: fine.
  - Budget OTA (Justfly/FlightHub, Mytrip/Gotogate, eDreams, Kiwi): cheapest but painful for changes and refunds.
  - Tell the user which one they'd be dealing with.
- **Payment:** a card with no foreign-transaction fee (e.g. Itaú Visa Infinite, 0%) makes paying in USD on a US site safe. Otherwise compare paying in local currency.

## Regional OTAs

- **Despegar** (despegar.com.uy / .com.ar):
  - URL: `https://www.despegar.com.uy/shop/flights/results/roundtrip/MVD/TYO/2027-02-19/2027-03-05/1/0/0`. Dismiss the login popup with "No quiero beneficios".
  - It shows a price matrix by airline. It was **$400+ pricier** than Kayak for the same Iberia flights ($2,179 vs $1,770), even on Ciberlunes.
  - Check it only when a user's card gives installments or Despegar-specific promos.
- **Turismocity** (AR/UY) is a metasearch like Kayak, with local OTAs.
- **Elsewhere,** each market has its own big OTA or metasearch, e.g. Trip.com (Asia), MakeMyTrip (India), Opodo/eDreams (Europe), Almosafer (Middle East). Same rule: check one only when the user's card or location gets installments or local promos, and log what it showed. None of these was tested; note any bot wall in the report.

## Sites that wasted time

- **iberia.com/uy:** the search form ignored automated typing, even after rejecting cookies (2 tries). Kayak shows Iberia's own price as a seller, so use that.

- WebFetch on airline, Apple and retailer sites gets 403s or JavaScript shells. Use Chrome.
- Momondo and Cheapflights share Kayak's backend, so checking them adds nothing beyond Kayak.
