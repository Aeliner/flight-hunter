# Risk flags, self-transfers, bags and visas

The cheapest itinerary often carries risk that the price hides. Name each risk in plain words in the report, so the user picks it knowingly.

## Flags `legs.py` adds automatically

| Flag | Meaning | Why it matters |
|---|---|---|
| `<2h at first US port XXX` | Less than 2h connection at the first US airport | The US has no sterile transit. Everyone clears immigration and customs, collects bags, re-checks them and goes back through security. Under 2h is tight, under 1h30 is a coin flip at MIA/JFK/IAH. |
| `tight 0hNN at XXX` | Connection under 60 min anywhere | Legal on one ticket, but a short delay means a missed flight. The airline rebooks you, but maybe tomorrow. |
| `OVERNIGHT layover XXX` | Layover crosses midnight | Hotel cost, and a transit visa may be needed to leave the airport. Many people refuse these outright. |
| `pre-dawn wait XXX` | Lands before 05:00 and waits 3h+ | Miserable, but cheap. Mention it. |
| `long layover XXX` | 8h+ | Could be a bonus city visit (needs a visa?) or just dead time. |
| `AIRPORT CHANGE A->B` | Arrive at one airport, depart from another (AEP→EZE, LGA→JFK, ORY→CDG, NRT→HND) | Ground transfer time and cost. On separate tickets nobody waits for you. |
| `SEPARATE TICKETS` | Itinerary built from two or more bookings | See below. |

## Separate tickets (self-transfer)

What can go wrong: leg 1 is late, you miss leg 2, and leg 2's airline treats you as a no-show. The ticket is lost, and often any return on that booking too. On a single ticket the airline must rebook you for free.

Rules of thumb:
- **Minimum connection:** 3h domestic with carry-on only. **4h+** if you must clear immigration or re-check bags. 5–6h on the first day of a long trip, or if leg 1 is a long-haul with a history of delays.
- **Buy the risky leg last.** Book the long-haul first. Then pick the hop with the biggest buffer that costs the same; several departures often share one price.
- **Bags:** each ticket checks bags separately, so you collect and re-check them. Budget the time.
- **Returns:** never put the outbound of a round trip as leg 2 of a self-transfer. A missed leg 2 cancels the return too.
- **Plan B:** know the next flight on that route and its price. Mention travel insurance with missed-connection cover, which some premium credit cards include.
- **The savings threshold:** recommend a self-transfer only when it saves meaningfully over the best protected ticket. Suggest at least about $150 per person, or the user's own threshold. Show both options side by side.

### Not every multi-ticket trip is a self-transfer

- **One ticket per direction:** an outbound one-way plus a return one-way, each a normal ticket covering its own connections. This is *not* a self-transfer and carries no extra connection risk. It has an advantage over a round trip: missing or changing the outbound doesn't cancel the return. `legs.py trip` labels these `separate_tickets = per direction`. Don't apply the self-transfer savings threshold to them.
- **Open-jaw on two one-ways** (in at TPA, out of MCO) is the same, plus the ground leg between the airports.
- **Self-transfer** is when two tickets meet *within one direction*. Only that needs the buffers and threshold above.

## Fare classes and bags

- "Basic Economy" (AA/UA/DL), "Light" (LATAM), "Economy Basic" (Copa) and similar fares often exclude a checked bag. Some also exclude carry-on and seat choice, or allow no changes at all.
- When comparing, note what's included. The 1-bag fare often beats a cheaper Basic fare plus $35–70 per bag per direction.
- fli has `--bags 1` and `--exclude-basic` flags, but the current search-page transport may ignore them. Check the fare on the booking page before trusting it.
- Co-branded cards and elite status can add a free bag. Example: Itaú's LATAM Pass Visa Infinite in Uruguay gives automatic LATAM Pass Gold and an extra 23 kg bag on LATAM-operated flights, for the cardholder only. It needs the LATAM Pass number on the booking. Ask about cards before dismissing a bag-less fare.
- LCCs (Frontier, Spirit, ZIPAIR, Flybondi, JetSMART) charge for everything, so add bags, seats and meals before comparing.

## Visas and passports (check every connection country)

- **US:** an airside transit still needs a US visa or ESTA. Nationals of non-Visa-Waiver countries need a visa just to connect in MIA/ATL/IAH/JFK. Uruguay, Argentina and Brazil are not in the VWP. Chile is.
- **Canada:** the eTA is for visa-exempt nationalities. Some others, Uruguayans and Argentines among them, can get an eTA (by air only) only if they hold a valid US non-immigrant visa or held a Canadian visa in the last 10 years. Otherwise they need a full visa. Re-check current rules.
- **Schengen/UK:** airport-transit visa rules vary by nationality. Changing airports (ORY→CDG, LHR→LGW) means formally entering the country.
- **Overnight or airport change:** usually requires entering the country, so check entry rules, not just transit rules.
- **Passport quirks matter.** Example: Uruguayan passports issued April–August 2025 lacked a place of birth, and Japan warned travelers. Search "[country] visa [nationality] transit [current year]" and link the official government page.
- Always name the visa need in the report next to the itinerary that triggers it.

## Weather and season

Winter hubs (ORD, DEN, JFK, YYZ) cancel more often from December to February. Hurricane season (Jun–Nov) affects MIA, IAH and PTY less, but it happens. Prefer warmer or bigger hubs for self-transfers in those months.
