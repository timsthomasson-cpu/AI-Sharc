> Text copy of the Excel workbook, for reading and search. The .xlsx file is the controlling original; edits are made to the .xlsx and this copy is regenerated.

## Read Me
| Buying Pattern Trade Groups — for review |
| --- |
| INTERNAL ONLY. Created 2026-11-02 in the 2026-11-01 review package. Not a firm-facing document, not for publication. |
| Hierarchy, in order: Buying pattern -> Buying Pattern Trade Group (the set of Trades sharing that pattern) -> Template (the audit instrument for that Group) -> Trade (one Primary Business Category) -> Field Mapping Table (one per Template, with a Trade Variations sheet inside it). |
| One Group maps to one Template, and one Template maps to one Group. Do not create a Group per Trade, and do not create a Template per category — there are thousands of Primary Business Categories, and they map into Groups, not each into their own Template. |
| Status is the key column. Only the Licensed Home Trades Group is Validated, and only for four Trades. Every other Group and every trade list in a Proposed Group is a scoping example, not a validated crosswalk. Do not use a Proposed Group for a firm until its Template and Field Mapping Table are validated the same way the Licensed Home Trade Template was. |
| Agent Validation Matrix is blank by design. No shopping agent has been tested yet. 'Not tested' is the default, and no agent may be recorded as confirmed until it has actually been tested, with date, query, and location recorded. |
| Canonical source: AI Sharc-Audit-Specification.md in the same review package. Where this file conflicts with the Specification, the Specification wins. |

## Groups
| Group code | Buying Pattern Trade Group | Buying pattern — what the shopper does | Template | Trades in the Group (Primary Business Categories) | Trades explicitly NOT yet validated / excluded | Status | Field Mapping Table |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LHT | Licensed Home Trades | Shopper in a town/ZIP needs a licensed tradesperson to come to the home, for install/replacement or repair, with a diagnostic fee, a warranty, and a state licence to check | Licensed Home Trade Template (formerly Template 1 / T1) | HVAC; Plumbing; Electrical; Roofing | Pest control; garage door; locksmith; appliance repair; foundation repair — named earlier, NOT checked, NOT included | Validated — four Trades only | Licensed-Home-Trade-Field-Mapping.xlsx |
| UHT | Unlicensed Home Services | Shopper needs a home service with no state licence, booked by quote and dispatch, where insurance, price, and availability matter instead of a licence number | Unlicensed Home Service Template (to be created) | Examples for scoping only: house cleaning; landscaping; moving; snow removal | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| AUTO | Auto Repair and Service | Shopper drives to a shop or drops a vehicle off, for repair or maintenance, with a physical address, not a service-area ZIP | Auto Repair and Service Template (to be created) | Examples for scoping only: auto repair; auto service; tire service; oil change | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| PERS | Appointment Personal Services | Shopper books an appointment for a personal service, with a price range, a booking route, and a certification to check | Appointment Personal Service Template (to be created) | Examples for scoping only: salon; barber; nail salon; med spa (boundary case — see Notes) | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| HEALTH | Regulated Health Services | Shopper books a regulated health appointment, where provider credential, insurance accepted, and regulated claims change the gates | Regulated Health Service Template (to be created) | Examples for scoping only: dentist; chiropractor; veterinary; medical clinic | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| DINE | Dining | Shopper chooses where to eat, by cuisine, menu, price, hours, and reservations, with no diagnostic fee, warranty, or service-area ZIP in the home-trades sense | Dining Template (to be created) | Examples for scoping only: restaurant; cafe; bakery; bar | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| RETAIL | Retail Storefront | Shopper visits or orders from a store, by products, inventory, hours, and returns | Retail Storefront Template (to be created) | Examples for scoping only: clothing store; hardware store; gift shop | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |
| PROF | Professional Services | Shopper engages a professional for a project or advice, by credential, project pricing, and appointment, with no dispatch | Professional Service Template (to be created) | Examples for scoping only: legal; accounting; consulting | All Trades in this Group — none validated yet | Proposed — scoping only | Not created |

## Licensed Home Trades
| Trade | Trade code | Google Primary Business Category | Yelp category | NAICS 2022 | Licence check (summary) |
| --- | --- | --- | --- | --- | --- |
| HVAC | LHT-HVAC | HVAC Contractor (gcid:hvac\_contractor) | Heating & Air Conditioning/HVAC (hvac) | 23822 (238221 / 238222) | TDLR TACLA/TACLB number published |
| Plumbing | LHT-Plumbing | Plumber (gcid:plumber) | Plumbing (plumbing) | 23822 — same as HVAC; do NOT use NAICS alone | TSBPE named RMP + Master licence (begins M) + COI on file |
| Electrical | LHT-Electrical | Electrician (gcid:electrician) | Electricians (electricians) | 23821 (238211 / 238212) | TDLR TECL + named Master Electrician of Record |
| Roofing | LHT-Roofing | Roofing Contractor (gcid:roofing\_contractor) | Roofing (roofing) | 23816 (238161 / 238162) | No Texas state licence — RCAT, manufacturer, city, and insurance as High Priority Items, not a Critical gate |

## Agent Validation Matrix
| Shopping agent (company) | Agent product / surface tested | Template tested | Date tested | Query and location tested | Fields the agent read | Fields the agent did not read | Extra requirements found | Conflicts with AI Sharc fixes | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |
| Meta | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |
| Google | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |
| Anthropic | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |
| xAI (Grok) | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |
| NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | NaN | Not tested | NaN |

## Agent Validation — How to use
| Agent Validation — how to use (no agent has been tested yet) |
| --- |
| 1. Pick one Template and one agent. Run the same query a shopper would run, in a stated location, on a stated date, and record all three. Do not record a result without date, query, and location. |
| 2. For each Gate, Item, and Lever in that Template's Field Mapping Table, record whether the agent read the field, did not read it, or read it from a different source than AI Sharc checked. Record the source the agent actually used, not the source you expected it to use. |
| 3. Record any extra field the agent required that AI Sharc does not yet check. If it serves the shopper, propose it as a new Template field. If only one agent needs it, record it as an agent-specific note, not as a scored Item for all agents. |
| 4. Record any conflict: a fix AI Sharc recommends that the agent misreads, rejects, or weights differently. Do not change a scored Item for one agent without checking the other agents. |
| 5. Re-check on a stated date. Agent behaviour, weighting, and source access change without notice, and most agent requirements are inferred from behaviour, not published as a standard. A validation from one date is not a permanent confirmation. |
| 6. The firm-facing Report Card stays agent-agnostic. Validation results live in this matrix, not in the card. The card shows Grade first, as what the firm controls, and approximate ranking second, labelled with query, date, and competitor set. |
| 7. Validation does not guarantee inclusion or ranking. Even if a website contains every field an agent needs, the agent may still not recommend the firm, for reasons including query, location, competitor set, weighting, and its own policies. |
