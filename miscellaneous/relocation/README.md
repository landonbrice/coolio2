# Where to live — a relocation thought-exercise

A research brief for a finance + marketing couple deciding where to settle and raise
a family after college, optimizing **quality-of-life-per-dollar** against two hard
priorities: a warm, involved, Salt-Lake-City–style **community**, and a real
**finance career ceiling**. 36 metros, scored across 7 dimensions, with a live
weighting model.

> **Not financial or relocation advice.** Dimension scores (1–10) are calibrated
> editorial judgments from current (2025–2026) research, not hard indices. Home
> prices, taxes, and insurance figures are point-in-time and drift, and vary by exact
> town/school district. Everything here is directional — the value is in mapping the
> *trade-offs*, not the decimal places.

## How to use it

Open **`where_to_live.html`** in any browser (no server needed). It's fully
self-contained except city photos, which load live from Wikimedia Commons (cards fall
back to a colored header offline).

- **Section 1 — scoring model:** your priorities are pre-loaded (community 25, finance
  25, value 18, schools 12, marketing 8, safety 6, climate 6). Drag the sliders or hit
  a preset (*Career-max*, *Value & lifestyle*, *Family-first*, *Balanced*) and
  **everything below re-ranks live.**
- **Section 2 — tier list:** S/A/B/C/D by weighted composite.
- **Section 3 — the trade-off map:** finance ceiling (x) vs. community (y), bubble size
  = cost-of-living value, color = region. The upper-right is the sweet spot — notice how
  few metros live there.
- **Section 4 — full scorecard:** sortable table of every score.
- **Section 5 — metro profiles:** search/filter cards; expand any for suburbs,
  employers, community character, trade-offs, and "best for."
- **Section 6 — questions worth sitting with.**

Click any metro chip / table row / map bubble to jump to its profile.

## Re-generating

All data and the page template live in `generate.py`. Edit the `metro(...)` entries or
`DEFAULT_WEIGHTS`, then:

```bash
python3 generate.py   # rewrites where_to_live.html
```

## Headline findings (at the couple's default weights)

The two hard priorities **pull in opposite directions** — the deepest finance ceilings
(NYC, SF, Miami, Chicago, Dallas) tend to be big/transient/expensive, while the warmest
SLC-style communities (Greenville, Boise, Madison, Omaha) have thinner finance ceilings.
The metros that resolve that tension best rise to the top:

- **Dallas–Fort Worth** — the standout: now the #2 US finance hub (Goldman, JPMorgan,
  Schwab, Fidelity, Wells all building out), faith-or-secular family suburbs, elite
  schools, no income tax. Cost: brutal summers + property tax.
- **Chicago** — true global-city finance + marketing ceiling with elite, affordable
  family suburbs (Naperville, Hinsdale); priced in punishing property taxes, hard
  winters, and IL fiscal risk.
- **Charlotte** — the cleanest "finance ceiling *and* community" answer at good value
  (BofA/Truist/Wells HQs + church-and-sports suburbs like Davidson, Waxhaw, Fort Mill).
- **Cincinnati / Minneapolis / Pittsburgh / Columbus / Des Moines** — the Midwest
  value frontier: real (corporate/asset-mgmt) finance depth + strong family culture +
  high QoL-per-dollar. Cincinnati is also a top-5 marketing town (P&G).
- **Salt Lake City** — scores well on its own merits: a genuine Goldman hub + the best
  family culture and outdoors, lower taxes; ceiling is back-office-tilted.
- **The SLC-culture cousins** (Greenville, Madison, Omaha, Boise, Indy/Carmel) win on
  community + value but ask you to accept a narrower finance ceiling — great *if* the
  finance path is corporate/wealth/remote.
- **Florida** is mostly a tax/earnings play: the no-income-tax draw is partly eaten by
  the home-insurance crisis and hurricane risk, and none of it matches SLC's rooted
  community. Jacksonville is the best FL value (+ FL's #1 schools, St. Johns Co.);
  Miami has the real finance migration but the worst community fit and value.
- **NYC / SF / Boston / Greenwich** own the absolute career ceiling but, at this income,
  the worst quality-of-life-per-dollar — justified only if the finance trajectory is
  genuinely top-tier (then the suburban-ring strategy applies).

Move the weights to pressure-test all of this against your own priorities.
