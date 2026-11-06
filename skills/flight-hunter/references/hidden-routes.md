# Hidden-route plays

Each play below found real savings in a past hunt, or proved it doesn't help in a situation worth knowing about. For every play: run one cheap real search to test it, keep going only if it can beat the baseline, and log the result either way. In the report, "checked, didn't pay" is as valuable as a win.

Numbers below are real results from 2026 hunts, quoted to show the size of the effect. They are not current prices.

## First, prune with a lower bound

Before pricing every leg of a clever route, find its **floor**: the cheapest single component it can't avoid. If the floor plus known minimum add-ons already exceeds the best complete option, drop the whole ring after one scan.
- Example: hub+hop to Tokyo can only win if `origin↔hub < origin↔Tokyo − hop round trip`. GRU↔Taipei/Seoul/Bangkok/Manila round trips ($1,439–1,938 without the US) were all above GRU↔Tokyo ($1,282 on Kayak). One `sweep.py` run killed the ring before any hop was priced.
- Order the rings by likelihood. Destination ring (nearby airports) and origin ring (gateways) first, because they win most often. Third-continent and exotic corridors last.

## Contents
1. Wrong city + hop (destination side)
2. Gateway sweep (origin side)
3. Gateway round trip (the "friend's trick")
4. Self-transfer through a hub
5. Kiwi explore and virtual interlining
6. Low-cost carriers aggregators underplay
7. Point of sale
8. Same flight, cheaper seller (OTA vs airline)
9. Trip shape: one-ways vs round trip vs multi-city
10. Date shifting and demand cliffs
11. Group size and fare buckets
12. Split origins, meet at the hub
13. Ground legs (ferry, bus, train, drive)
14. Card and loyalty perks change the math
15. Running big sweeps with subagents
16. Neighbor hub + LCC hop
17. Alternate destination airport + rail, open-jaw
18. Third-continent split (two round trips meeting on another continent)
19. Visa corridors: which hubs actually connect where

---

## 1. Wrong city + hop (destination side)

**Idea:** some airline has a cheap one-stop into a city *near* the destination. Fly there, then take a separate domestic flight, a bus or a drive.

**How:**
- List every airport within about 400 km or 4h of the real destination (fli MCP `find_airports`, or your own knowledge).
- Search them all at once as a comma list: `fli flights ORIG DFW,DAL,AUS,IAH,HOU,SAT DATE --stops 1 --passengers N --format json`. See which city is cheap.
- Then price the hop: `fli flights AUS DFW,DAL DATE --stops 0 --passengers N --format json`.
- Combine: `legs.py combo long.json hop.json --min-connect 3`. Use 2.5h only if it's domestic, no bags and no immigration. Immigration happens at the first US airport, so the hop after it is domestic.
- Mention the drive or bus option and its rough duration, but don't invent a price.
- **Count the ground side honestly.** Rental pickup and return (return at the same airport to avoid one-way drop fees), transfers for travelers without a car, a hotel night if the long-haul lands late. For an open-jaw (in at one airport, out at another), a one-way rental drop fee applies. If none of this was priced, say so next to the saving.
- For a holiday (not a fixed venue), check the same wrong-city airport for the return. Copa priced Tampa→MVD at $816 for 2 every day for a week.

**Real example:** BUE→Allen, TX (near Dallas) on Nov 2.
- Copa EZE→PTY→AUS cost $1,119 for 2 on Kayak (bag included). An AUS→DFW/DAL hop cost $377 for 2. Total **$1,496**, 14.5h + 4h buffer + 1h.
- The cheapest single ticket to Dallas was $2,339 (24h, 2 stops). A 1-stop was $6,892.
- On Oct 19 the same trick was $993 + hop vs $1,889 for AA via MIA.
- Copa (Panama) serves many mid-size US cities. Dallas fares were inflated by event demand, but Austin's weren't.
- MVD→Orlando (Disney), January, 2 adults:
  - The best Orlando option was a Copa round trip at $2,376.
  - Copa **into Tampa** (about a 1h30 drive) as two one-ways was **$1,986** ($1,170 out + $816 back), each a protected Copa ticket.
  - On the same day Copa charged $1,170 to Tampa vs $1,688 to Orlando.

## 2. Gateway sweep (origin side)

**Idea:** a big hub one cheap hop from home may have much cheaper long-haul fares, thanks to more competition and different point-of-sale markets.

**How:**
- List candidate gateways: neighboring-country hubs and big domestic hubs.
  - From Uruguay/Argentina: GRU, GIG, SCL, EZE, POA, FLN, LIM, BOG, PTY.
  - From Europe's edges: the big LCC bases.
- Check them cheaply: fli `search_dates` with start = end (one call each), `fli dates` per pair, or Kiwi `search-flight` with a city per call.
- For the cheapest 2–3 gateways, price the positioning legs separately. Add a hotel night if the timing forces one, plus the extra hours.

**Real example:** MVD→Tokyo, February, per person.
- MVD baseline: $2,290 (Iberia+Qatar).
- Gateways: EZE $2,118, SCL $1,660, GRU $1,398–1,421 (Air Canada), **GIG $1,329** (AA via JFK).
- Positioning: MVD↔GIG on Sky cost $252 round trip. MVD→GRU on Gol about $263 one-way.
- GIG + AA came to about $1,690–1,800 all-in with bags and a hotel night. That's $500+ per person saved.

**Watch:** a gateway route through the US or Canada triggers visa needs (see risks.md). Brazil-origin point of sale wasn't reliably cheaper when tested.

## 3. Gateway round trip (the "friend's trick")

**Idea:** book home↔gateway on one ticket, and a separate gateway↔destination round trip from a hub with fierce competition. Examples: LAX/SFO/HNL for Asia, MIA/NYC for Europe, Lisbon/Madrid for Africa.

**How:**
- Sweep nonstops from several hubs at once: `fli flights LAX,SFO,SJC,SEA,HNL NRT,HND DATE --stops 0`. This surfaces LCCs (ZIPAIR $429 from LAX, $331 from HNL).
- Then price legacy round trips with the LCC excluded (`--exclude-airlines ZG`). Full-service fares with bags often win once LCC extras are added. ANA LAX↔NRT cost $846 round trip with 2 bags and meals, vs ZIPAIR $892 base + ~$187 extras.
- Price home↔gateway separately (LATAM MVD↔LAX about $1,105).

**Real example:** MVD→Tokyo via LAX came to about $1,951 per person, vs $2,080 for the best protected ticket. It was beaten by the GIG gateway. Worth checking every time.

## 4. Self-transfer through a hub

**Idea:** two separate tickets that meet at a hub: home→hub on airline A, hub→destination on airline B (often a US LCC like Frontier or Spirit).

**How:**
- Search leg 1 into the hub and leg 2 from the hub. Leg 2 goes on the arrival day and the next morning.
- Run `legs.py combo leg1.json leg2.json --min-connect 4`.
- Flag airport changes (MIA→FLL) and overnights.

**Real examples:**
- EZE→MIA (AA) $774 + MIA→DFW (Frontier) $208 = $982 for 2. That saved $907 vs AA's own connection, but only **$11** vs Copa to Austin. Under the $150 bar, so it wasn't recommended.
- MVD→MIA on AA at $660 for 2 plus Frontier MIA→DFW gave $718 for 2.
- Kayak and Skyscanner surface these as "hacker fares". Kiwi builds them automatically.

## 5. Kiwi explore and virtual interlining

**Idea:** let Kiwi's engine propose combinations no human would think of: Sky + Copa via Santiago, JetSMART to Rio + LATAM, LATAM + Volaris via Lima and Mexico City.

**How:** `search-flight` with `flyTo` set to a **country** and `one_for_city: true` gives the cheapest fare to every city. Always set `max_fly_duration`, `currency: "USD"`, and `exclude_stopover_countries` where the travelers lack a visa.

**Real example:** MVD → "United States", Dec 10, 1 adult: IAD $451, ORD $473, MIA $492, DFW $535... It reveals which gateway is cheap. Then verify with fli: Google had MVD→MIA on AA at $330, cheaper than Kiwi.

**Didn't help:** for 5 people to Tokyo, Kiwi's best was $2,323 per person with 38–57h routings and only a personal item included.

## 6. Low-cost carriers aggregators underplay

Some LCCs block or under-surface on Google/Kayak, or only show their best fares on their own site:
- ZIPAIR, Scoot, Peach (Asia)
- Flybondi, JetSMART, Sky, Arajet (Latin America)
- Frontier, Spirit, Breeze (US); Southwest (not on OTAs)
- Norse, PLAY (transatlantic)

Run a nonstop sweep from several hubs to reveal them, then check their own sites (sites.md). Before comparing, add the bag, seat and meal fees.

## 7. Point of sale

The same fare can differ a lot between an airline's country sites.
- LATAM JFK→LIM→MVD: **$1,283.50 per person on the UY site vs $762.50 on the US site.**
- For flights that **start** outside your country, check the airline's site for the departure country and its US/English site.
- fli `--country US` / `--country UY` sets Google's market (`gl=`). Untested, but cheap to try.
- Kayak's own regional domains (kayak.com.ar, kayak.co.uk...) can also differ.

## 8. Same flight, cheaper seller

Google often shows the airline price. Kayak and Skyscanner show OTAs selling the *same flights* cheaper.
- Kayak was cheaper than Google every time it was checked: Copa $993 vs $1,221, Copa $1,115 vs $1,379, Copa $1,119 vs $1,385, AA $1,889 vs $1,995, Arajet $918 vs $957.
- It held for MVD↔Tokyo in Nov 2026:
  - Iberia was **$1,770 on Kayak (seller: Iberia itself) vs $2,193 on Google**, same flights.
  - Skyscanner had $1,933 and Despegar UY $2,179.
- **Codeshare marketing carrier matters.** The same AA flights GIG→JFK→HND sold as a **JAL ticket** cost $1,310 *with 2 checked bags*, vs $1,328 as AA Basic with none. Kayak lists each marketing carrier separately, so scan past the first airline name.
- Check the OTA's reputation and the fare brand. Know that changes and disruptions go through the OTA.

## 9. Trip shape: one-ways vs round trip vs multi-city

Never assume; test both.
- **Multi-city often costs the same as the one-ways, or more:**
  - AA EZE→DFW + JFK→EZE multi-city was $4,097 vs $3,644 as separate one-ways.
  - Copa's multi-city was exactly the sum of its one-ways.
- **Round trips** can beat two one-ways on legacy long-haul (ANA LAX↔NRT round trip). They usually don't on LCCs.
- **Open-jaw** means arriving in one city and leaving from another (Texas in, NYC out). Price it as one-ways plus a cheap domestic leg between. Dallas→NYC cost $202–273 for 2 on the right days.
- Very long round trips (3 months) returned 0 results on fli, so price those as one-ways.

## 10. Date shifting and demand cliffs

- Always run a date grid (`fli dates`) before choosing days. Neighboring days differ a lot:
  - Returning Nov 16 instead of Nov 15: LATAM $1,155 vs $1,525. Dallas→NYC Nov 9–11 $202–273 vs Nov 8 $438.
- **Event cliffs:** fares into an event city jump as the event nears. Dallas went from $1,995 (Oct 18–22) to $2,157, $2,801, then **$11,521** within days. Arriving a few days early can beat arriving "just in time". So can the wrong-city play.
- Day of week: Thursday departures beat Friday on long-haul (Iberia $2,080 vs $2,282; GRU $1,304 vs $1,398).
- Sales: Black Friday and Cyber Monday (late November) bring LCC flash sales. ZIPAIR one-ways from $259 the previous year.

## 11. Group size and fare buckets

Each fare price comes in a limited number of seats (a "bucket"). A group can exhaust the cheap bucket, and then the *whole booking* prices at the next one.
- Run the same search with 1, 2, 3... N passengers and compare the per-person price.
  - Air Canada GRU→Tokyo: $1,408 per person up to 3 pax, $1,420 at 4 on another routing, **none at 5**. The cheapest 5-pax option was BA at $1,698 per person.
- Fix: split into separate bookings (e.g. 3 + 2), and book the larger group first.
- fli at 5+ passengers sometimes returns 0 or odd results. Treat that as a tool artifact and confirm on Kiwi or the airline site.
- Sometimes there's no effect. In the Texas hunt, 1-adult fares were exactly half of 2-adult fares. Still worth one check.

## 12. Split origins, meet at the hub

When travelers start in different cities (one in Buenos Aires, one in Montevideo), each books from their own city onto the same hub-to-destination flight. They don't have to gather first.
- Example: MVD→PTY→AUS (1 adult, $467) met the friend's EZE→PTY→AUS Copa flight in Panama. Total ~$2,832–2,965 vs ~$3,017 with a ferry to meet in BA first.
- Booking separately also dodges group-bucket problems.

## 13. Ground legs (ferry, bus, train, drive)

Include them in both the time and cost totals: ferry or bus fare, taxi to the airport, a possible hotel. They often **don't** pay:
- A ferry to Buenos Aires for a Texas trip: $3,571 vs $3,097 flying from MVD. For Tokyo: only about $80 saved.
- They do pay when the other city has a much cheaper long-haul, or when the group is meeting there anyway.
- A drive or bus from the wrong-city airport (play 1) can replace the hop. Give the rough duration, and say the cost wasn't checked unless you did check it.

## 14. Card and loyalty perks change the math

Ask what cards and statuses the travelers hold.
- A co-branded card can add a free checked bag, lounge access, seat selection or upgrades. These flip a "Light" fare into the best deal.
- Example: Itaú LATAM Pass Visa Infinite (Uruguay) gives automatic LATAM Gold, plus an extra 23 kg bag for the cardholder on LATAM-operated flights (LATAM Pass number on the booking), plus seat selection.
- In the Texas hunt the LATAM version cost $3,006 vs $3,001 for the cheapest alternative. With the perks, LATAM was the better pick.
- Miles redemptions are out of scope unless the user asks. Mention them if the user has a big balance.

## 15. Running big sweeps with subagents

Sweeping 10+ gateways or many dates floods the context. Do what worked in the Tokyo hunt:
- Split the sweep into 2–4 parallel subagents, e.g. US gateways + LCCs / Brazil gateways / direct from home.
- Give each the same instructions: use `legs.py` and the CSV columns, cap at about 25 searches, return a reply of 350 words or fewer with its best 3 finds and their sources.
- Merge their CSV rows and run `legs.py top`.

## 16. Neighbor hub + LCC hop

**Idea:** fly long-haul to a big hub in a neighboring country, then take a cheap LCC hop to the real destination. Examples: Seoul, Taipei, Hong Kong or Manila for Tokyo; Kuala Lumpur or Bangkok for Bali.

**How:**
- `sweep.py --from <gateways> --to <hubs> --date ... --return ... --top-n 2`, one search per pair.
- Apply the lower bound (top of this file) **before** pricing hops.
- Then: hub→destination one-ways with a 5h+ buffer or an overnight, and `legs.py combo`/`trip`.

**Typical LCC hops** (Tokyo, Feb 2027, one-way):
- ICN→NRT Peach $155
- TPE→NRT Scoot $176
- HKG→NRT $146
- NRT→ICN Air Seoul $112

**Real result (lost):** GRU round trips cost Taipei $1,235 and Hong Kong $1,266, but both connected *via the US*. Without the US: Manila $1,439, Beijing $1,602, Bangkok $1,637, Hong Kong $1,635, Shanghai $1,660, Taipei $1,938. All were above GRU↔Tokyo itself, so the best complete trip was $2,039 vs $1,607–1,770.

**Visa traps for Uruguayans** (Nov 2026; re-check):
- Taiwan requires a visa.
- Korea requires a K-ETA.
- China is visa-free only through Dec 31 2026, and Uruguay isn't on the 240h transit list.
- Thailand is uncertain.

**When it wins:** when the hub is an LCC long-haul base or has a fare war from your origin. Typically this is from Europe or Australia, rarely from South America.

## 17. Alternate destination airport + rail, open-jaw

**Idea:** another airport in the destination country plus a train or a short drive. Osaka KIX + shinkansen (~¥14,000 / ~$90, 2.5h) for Tokyo; Austin + hop for Dallas; Tampa + drive for Orlando.

**How:** scan the alternate airport like the main one. For open-jaws, price the one-ways and pair them with `legs.py trip`, which labels them OPEN-JAW automatically.

**Real results:**
- **Won:** Austin for Dallas (−$843 for 2), Tampa for Orlando (−$390 for 2).
- **Lost:** Osaka from GRU was $1,711 vs Tokyo $1,282. Open-jaw into KIX and out of Tokyo was $2,587, plus the train.

Wins come from a carrier (often Copa) serving the secondary city cheaply while the main city is pricey. Losses come when the main city has the competition.

## 18. Third-continent split (two round trips meeting on another continent)

**Idea:** buy home↔hub and hub↔destination as two round trips. The hub is on a third continent with cheap fares both ways, e.g. South America↔Madrid + Madrid↔Asia. Black Friday sales on the first leg can make this work.

**How:**
- Sweep hub→destination round trips from 8–10 hubs, one search per pair. The comma-list trap: a round trip with 10 hubs in one call only expands the cheapest 2.
- Then price home↔best hubs and combine with a 5h+ buffer or an overnight at the hub.
- Remember Schengen/UK entry rules at the hub, and that both connections are self-transfers.

**Real result (Japan, per person):**
- Iberia MVD↔MAD $888 + Korean Air MAD↔NRT $806 = **$1,694**: $76 under Iberia's single ticket ($1,770), but 58h out, landing a day later, with a 4h55 self-transfer back. **Under the $150 bar, so not recommended.**
- Iberia MVD↔BCN $915 + Qatar BCN↔HND $854 = $1,769 (ties).
- Also seen: Cathay MAD↔NRT $958; Air Astana IST↔NRT $790 (53h).

**When it wins:** a deep sale on one leg (check the hub city's airline sales), or a hub with ultra-cheap Asia fares (Chinese carriers from Europe).

## 19. Visa corridors: which hubs actually connect where

When travelers lack a visa for the obvious corridor (US/Canada for South America→Asia), list the hubs that *actually fly* to the destination before sweeping. Many don't:
- **Latin American hubs (MEX, PTY, BOG, LIM, SCL) have almost no Asia service** that avoids the US. The only one is ANA MEX↔NRT, $2,053 round trip. Kiwi restricted to LatAm stopovers and fli `--layover PTY/BOG/LIM/MEX` returned 0. Copa MVD↔MEX $745 + ANA = $2,798.
- **Oceania:** LATAM SCL↔AKL ($1,490 round trip) + SYD↔HND ($1,195) → $2,685+. Qantas via MEL $3,514.
- **So South America → Asia without a US visa really means Europe, the Middle East or Africa.** That's Iberia/BA via MAD/LHR ($1,770), LATAM/JAL via LHR ($1,282 from GRU), Emirates/Qatar via DXB/DOH ($1,653–2,106), Ethiopian via ADD ($2,050 from EZE).

Check transit rules per country:
- UK airside transit is ETA-exempt (temporarily, since Jan 2025).
- Qatar and Ethiopia airside transit need no visa.
- Australia has a transit-without-visa list for under 8h airside, otherwise a free subclass 771 visa.
- New Zealand needs an NZeTA for visa-waiver nationals.
