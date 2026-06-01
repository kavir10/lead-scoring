# Table22 ICP & Lead Qualification Guide

**Audiences:** Sales qualification · Paid marketing (targeting & creative) · Video/ad production · Lead-discovery engineering
**Owner:** Kavir, Applied AI & Growth
**Last updated:** 2026-06-01
**Sources:** "Table22 ICP definition & lead qualification guide" (Feb 2026); "Wine shop ICP and lead-sourcing working session" (May 2026); lead-scoring ML model SHAP output.

---

## How to use this doc

Two layers:

- **Part I** is the cross-vertical ICP — the six observable dimensions, what the ML model actually weights, partner-type economics, and disqualifiers. Read this first for any vertical.
- **Part II** holds per-vertical playbooks — wine, butcher, restaurant, cheese, bakery — each with its own ideal-lead profile, positive signals, anti-ICP, and category-specific constraints. Evidence strength varies (wine/butcher/restaurant are structured; cheese/bakery are transcript-derived) and is flagged per section.
- **Part III** translates the ICP into action for sales triage, paid targeting, and creative.
- **Appendices** are reference tables for lead research.

The ICP is composite and **non-linear**: no single number qualifies or disqualifies a lead. Branch on context, weigh signals together.

---

# PART I — Table22 ICP (all verticals)

## TL;DR

Table22's highest-value partners are **established, premium-positioned F&B businesses with strong consumer demand signals, press recognition, and active digital audiences**. ICP fit is a composite of six observable dimensions, each scorable from public data / enrichment APIs / NLP tooling (Clay, GPT, social scraping). Together they form a 0–100 ICP Fit Score that, combined with the ML model's predicted Peak AGMV, drives lead prioritization.

---

## How we define ICP fit — the six dimensions

**1. Premium / quality signals.** Google rating (4.5+ ideal), review volume, price tier ($$–$$$ preferred), press mentions, awards, domain age, years in operation. High-quality businesses exhibit strong customer trust and consistently over-index on Table22 AOV and retention. _Notable exceptions exist_ — e.g. Helen's Wines at a 3.7 rating — so quality is a strong signal, not an absolute gate.

**2. Demand / devoted following.** Reservation difficulty, popular-times occupancy (especially off-peak, e.g. Tuesday 7pm), website traffic, and social engagement — particularly **video** engagement. Businesses with **more demand than they can serve through their physical space** are the natural Table22 fit. When customers can't get enough through normal channels, they'll pay for subscriptions and pre-orders.

**3. Artisanality / brand narrative fit.** Mission language like "farm to table," "seasonal," "craft," "purveyors," "community-driven," or "producer relationships." Tasting menus, curated wine lists, pairing events, special experiences. When **multiple** artisanal signals co-occur, the indicator is much stronger. This is the cultural-alignment variable — brands expressing hospitality and craftsmanship thrive in our ecosystem.

**4. Cuisine fit (restaurants only).** Italian, Wine Bar, French, Mediterranean, Israeli/Middle Eastern, American (Farm to Table), Thai, Meat/Steakhouse, and European have the strongest conversion and LTV. Korean, Japanese, Chinese, Mexican, Vietnamese, Filipino, BBQ, Spanish, and Nordic are strong when brand and quality indicators are present. **Cuisine fit should never overrule brand quality or demand**, but it meaningfully informs targeting and messaging tone. (Full detail in Appendix B.)

**5. Business characteristics.** Full-service or tasting-menu-oriented (not QSR, delivery-only, or counter-service). Independent or small group (<10 locations, ideally 1–3). Estimated revenue $1–10M (below $750K often too small for adoption). Presence of roles like Director of Operations, Marketing Director, or Events Manager correlates with willingness to test new channels. (Full role list in Appendix D.)

**6. Technical environment.** Compatible POS (Toast, Square, SpotOn, Shopify), website platform (BentoBox, Squarespace), email/CRM (Mailchimp, Klaviyo), reservation system (Resy, Tock, OpenTable). Tech-stack overlap shortens implementation and improves activation. Email/CRM presence specifically indicates **audience-nurturing behavior** — a strong predictor of success. (Full reference in Appendix C.)

---

## What the ML model actually weights (SHAP)

The lead-scoring model's SHAP summary plot ranks feature importance as follows (most → least predictive of Peak AGMV). Color = feature value (red high, blue low); horizontal spread = impact magnitude.

| Rank | Feature | ICP dimension it maps to |
|---:|---|---|
| 1 | **Partner Type** | Business characteristics — single most important predictor |
| 2 | **Reservation Difficulty Score** | Demand / devoted following |
| 3 | **Average Video Views** | Demand (video engagement) |
| 4 | **City Bucketed** | Geography / market |
| 5 | **Follower Count** | Demand (audience size) |
| 6 | **Domain Age (Years)** | Premium / establishment |
| 7 | **Google Business Type Bucketed** | Business characteristics |
| 8 | **Press Mentions Count** | Premium / quality |
| 9 | **Average Shares Count** | Demand (engagement) |
| 10 | **Cuisine Type Bucketed** | Cuisine fit |
| 11 | **Awards Count** | Premium / quality |
| 12 | **Monthly Website Traffic** | Demand |
| 13 | **Google Rating** | Premium / quality |
| 14 | **Average Likes Count** | Demand (lowest-weighted engagement signal, not noise — see engagement hierarchy) |
| 15 | **Occupancy on Tues 7pm** | Demand (off-peak) |
| 16 | **Price Tier** | Premium positioning |
| 17 | **Revenue Band / Revenue Value Cleaned** | Business characteristics |
| 18 | **Tier 0 Awards Count** | Premium (top-prestige awards) |

**Reads that matter:**

- **Partner Type dominates.** Pick the right verticals first; everything else is secondary tuning (see partner-type economics below).
- **Demand signals cluster near the top** — reservation difficulty (#2), video views (#3), follower count (#5), shares (#9). The "more demand than they can serve" thesis is the model's strongest theme.
- **Video engagement (#3, #9) sits far above likes (#14)** — but low-weight is not no-weight. The canonical cross-vertical engagement hierarchy is **video views > shares/saves > comments > likes**: likes and comments are the lowest-weighted rungs, not noise. SHAP (video #3, shares #9, likes #14) and the sales-review engagement gradient **agree** on this ordering; the bottom of the ladder is still a real demand signal. See "Tiering rubric — from sales review" in Part III.
- **Press and awards (#8, #11, #18)** are mid-to-high — credibility matters, with top-tier awards (Tier 0) appearing as their own feature.

---

## Which partner types perform best

Partner type is the single most important predictor. Average Peak AGMV by partner type — this directly informs where to invest marketing dollars and sales time.

| Partner Type | Avg Peak AGMV | Fit notes |
|---|---:|---|
| **Butcher Shop** | $75,901 | Highest average. Strong subscription fit with recurring protein needs. Underpenetrated — major growth opportunity. |
| **Wine Shop** | $68,155 | Natural wine club model. Large proven base, consistent performance. |
| **Cheese Shop** | $63,752 | Excellent economics. Artisanal positioning aligns perfectly. |
| **Destination Restaurant** | $60,495 | Highest ceiling. Aspirational brands with devoted followings. |
| **Market / Deli** | $48,687 | Curated concepts with loyal local customer bases. |
| **Wine Bar** | $36,177 | Good fit only when paired with strong brand and wine program. |
| **Bakery** | $34,682 | Works with artisanal bakeries. Wide variance — quality signals matter. |
| **Neighborhood Restaurant** | $31,992 | Moderate average, high ceiling. Depends heavily on quality and demand. |
| **Specialty Grocer** | $27,927 | Best with curated selection and strong local brand. |
| **Fast Casual Restaurant** | $23,956 | Lower average. Counter-service / QSR models are a weaker fit. |

**Where to invest:** Butcher, wine, and cheese shops are the strongest combination of high performance and expansion headroom. Destination restaurants are high-value but the base is already large. Bakeries and specialty grocers are solid mid-range when targeting artisanal concepts specifically.

---

## Disqualification criteria

**Hard disqualifiers (business model doesn't align with subscription/pre-order commerce):**

- Caterers
- Pizza-first concepts (unless clearly artisanal/premium)
- Cocktail bars
- Liquor stores — perform **notably worse** than wine-focused retail; the curation and community elements that drive wine-shop success don't translate to general liquor retail
- Delivery-only / ghost kitchens
- Franchise operations
- Estimated revenue below $750K

**Additional disqualifiers to consider:**

- Fewer than 20 total Google reviews
- Live-music focus on the website
- Website extremely outdated or non-functioning
- Restaurant reservations wide open this weekend
- No social-media presence at all
- Significant mismatch between IG followers and likes (e.g. 100K followers but ~25 likes/post) — this is fundamentally a **low-engagement** flag, not a low-follower flag. Follower count is a separate, weaker signal; the real test is likes/comments/saves/views *relative to* following (Silence Please and 7th Street Burger both carry large followings yet land Tier 3 on thin engagement).
- Private chefs offering services specifically for private catering & events
- Breakfast/brunch highlighted throughout the website
- Sweets-only or single-product concepts (e.g. cookies-only) — a **heavy demotion, not a hard DQ**: strong engagement can lift them to Tier 2 (MYKA, Lysée), but average-or-worse engagement keeps them at Tier 3 (Julia Jean's, Bi-Rite, Tompkins Square Bagels). Caps at Tier 2 even with strong engagement.

**Field-level red flags (from Dannah):**

- Poor IG engagement / following under 1K
- Poor reviews (Google or Yelp)
- Clearly a discount store / big-box store
- Pushes generic liquor brands: Tito's, Smirnoff, Veuve, BuzzBallz, spiked seltzers, Michelob, Budweiser
- Sells commodity wine SKUs: Josh, Cupcake, Barefoot, Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic, André, Cloud Break
- **City Hive** and **Spot Hopper** are not outright disqualifiers but are red flags — more frequently used by liquor stores
- No "About Us" story — not a disqualifier, but usually means they aren't really up and running yet
- "Coming soon" on homepage or IG
- Located off a major highway
- 5+ locations — not a disqualifier, but usually a flag

---

## Nuances that affect signal quality

### Smaller cities have lower volume metrics — and that's fine

Google review counts and IG engagement are naturally lower in smaller markets. A restaurant with 150 reviews and 2K followers in a town of 25,000 can be just as dominant locally as one with 2,000 reviews and 50K followers in a major metro. When qualifying non-major-metro leads, focus on **relative local dominance**:

- Are they *the* spot in their town?
- Real engagement from locals (comments, not just likes)?
- Do they show up in regional "Best Of" lists?
- Is a reservation actually difficult *for their market*?

Disqualifying a strong small-market lead because their follower count looks low next to a Brooklyn restaurant is a mistake to avoid in both automated scoring and human qualification.

### Static-only social content is a negative signal — but not a disqualifier

Video engagement (avg video views, shares) is among the top-5 predictive features. Businesses posting only static images will almost certainly show lower engagement because platform algorithms deprioritize static content. So:

- A merchant with **moderate followers but strong video engagement** (reels with real comments and shares) beats one with **high followers but only static posts**.
- But static-only businesses aren't bad partners — their social metrics simply **understate** brand strength. If other signals are strong (press, reservation difficulty, price positioning), don't let weak content-driven social metrics disqualify an otherwise excellent lead.

---

# PART II — Vertical playbooks

Wine is the deepest playbook (full working session). **Butcher** and **restaurant** are backed by structured ICP docs in the vault. **Cheese** and **bakery** are distilled from Table22 sales-call transcripts — real signal, lighter evidence base — and flagged as such.

---

## Wine shops

> Source: ICP and lead-sourcing working session, May 2026. Distilled for outbound lead discovery and sales qualification.

### TL;DR

1. Wine shops have **two distinct qualification paths**: **transition** (they already run a club) and **new** (we help them build one). The signals you source on differ for each.
2. The strongest lead is a **wine shop (not a wine bar)** with an **existing club of 40+ members** sitting inside a **delivery range they don't yet serve**, plus active growth signals (newsletter, engaged Instagram).
3. Qualification is **not linear** — use an if/then decision tree. If the partner is **low-tech**, qualify on inventory and followers. If **high-tech**, qualify on engagement (a beautiful new site can mean zero customers).
4. For new builds, order of importance is roughly: **street cred** (owner/sommelier prominence) → **direct engaged audience** → **email-list presence** → **social engagement** (saves/shares/views, not likes).
5. **Shipping unlocks growth only when the shop is nationally known.** Shipping is the mechanism; national recognition is the actual driver.
6. **Wine bars are mostly out.** Same poor outcomes historically, with one geographic-monopoly exception.
7. **Affluence matters, with a counterintuitive catch:** the very wealthy often like to pick their own wine, which makes them poor subscribers for a curated shop club today.

### Two qualification paths

Every wine-shop lead falls into one of two motions, and they qualify differently:

- **Transition.** The shop already runs a wine club, and we move it onto Table22 with better tooling. This is where the hidden gems are.
- **New.** The shop has no club, and we help them launch one. Here you source on **audience potential and reputation** rather than an existing program.

### The ideal wine-shop lead

The best-fit **transition** lead is qualitative more than quantitative, but it looks like:

- An existing club of **~40+ members** (clubs of 5–25 are the sticky, frustrating zone — see below).
- Located inside a **Table22 delivery range the shop doesn't currently serve** — delivery is the immediate, deliverable growth lever.
- A **newsletter** on their site we can demonstrably improve.
- An **Instagram account with real engagement** (defined precisely below).
- **Disposable income in the trade area**, which heightens the convenience value of delivery.

**Worked example:** a strong wine shop in Miami with an existing club of ~50 could plausibly reach ~75, because some customers live too far to pick up monthly — delivery plus disposable income closes that gap.

**Curation/sourcing exemplars** (the shops the wine ICP list is modeled on): Helen's Wines (LA), Biondivino (SF), Leon & Son (Brooklyn). Profile: single-location or very small (1–3), founder- or sommelier-led, curated SKU count (~300–1,500 bottles, not a 10,000-bottle wall), heavy on natural/low-intervention/biodynamic/small-grower wines OR a Burgundy/Italian/Champagne specialty, design-forward identity, already running programs we plug into (clubs, tasting nights, classes).

### How to qualify: the decision tree

Branch on the partner's **tech maturity first**, then apply the relevant signals:

- **If low-tech** (bare-bones or near-empty website): qualify on **inventory** (what bottles they carry) and **follower count**. There's no digital footprint to read, so the product and the audience are your only evidence.
- **If high-tech** (polished, built-out website): qualify on **engagement**, because a beautiful site can simply mean the shop is brand new with no customers yet. A mailing-list signup paired with only ~100 IG followers almost certainly means **nobody is actually on that list**.

### Sourcing signals, ranked and defined

#### Existing club size

- **40+ members** is the target floor for a worthwhile transition.
- **5–25 members is the hard middle**: the owner wants growth we can't confidently promise, and the economics don't work for either side. A three-year-old club still stuck at 10 is unlikely to change trajectory.

#### Email list

- **No hard minimum size**, and you usually can't capture size during research anyway.
- The **presence** of an email list or email pop-up is itself a useful positive signal — enough to qualify on at scale. (This is how ~12,000 prospects were captured across the restaurant, wine, and butcher verticals.)
- A **small, direct, engaged list beats a large stale one.** West Coast Wine Club built a ~200-person waitlist, emailed it once, and converted ~25 orders / ~50 members — outperforming a 10,000-person list that deletes the email on sight.

#### Social engagement

- **Engagement, not audience size,** is the real signal — and only for **wine shops, not wine bars** (people follow bars for the experience, not to take wine home). Follower count is a separate, weaker audience signal — not engagement.
- **Weighted, most → least** (the canonical cross-vertical hierarchy): **video views > shares/saves > comments > likes**.
- **Likes and comments are the lowest-weighted rungs, not noise** — for *wine sourcing* specifically, saves/shares/views carry far more signal, but real likes and comments still count when reading strong vs. mixed engagement.
- **Saves are especially telling:** when a sommelier posts a bottle and someone saves it to find later, that's high-intent behavior.

#### Street cred (the strongest "new" signal)

- **Owner or sommelier prominence** is the closest analog to a restaurant's Michelin star or "best in town" status — arguably the only real overlap with the restaurant ICP besides an email list.
- It's what lets a shop **sell before it has a list or a following.** Examples: **West Palm Wines** (owner previously ran a beloved, well-known upstate NY shop) and **Verve** (a widely known master sommelier).
- Goal is to be the **local gem**, not necessarily the "best" shop in the country.
- **Sources of street cred:** the owner, the sommelier, affiliated operators (e.g. part of a respected restaurant group), and the writers/tastemakers who cover or frequent them. If a prospect **follows recognized industry accounts**, that's a positive sign.

#### Inventory and importer signals

- Use an **exclusion list** of wines that disqualify a shop rather than trying to build an inclusion list — far easier to spot what to avoid than to score "good" wine. (Exclusion list below; sourcing it fully is an open item.)
- What makes a shop good is **carrying things nobody else has.** "**Natural wine**" is a reliable positive keyword.
- **Importer/distributor as a trust signal:** if a shop stocks wine from a respected importer/distributor, trust that shop more. Source on the **importer/distributor**, not the broad supplier — the supplier is just an inventory fact. Respected importers seen across the ICP list: **Skurnik, Louis/Dressner, Jenny & François, Selection Massale, Zev Rovine, Rosenthal, Polaner, Vom Boden, T. Edward, José Pastor**.

### Exclusion & red-flag signals (the anti-ICP)

These generally disqualify a lead or serve as immediate red flags.

**Inventory red flags (the exclusion list):**

- Clearly pushes generic liquor brands: **Tito's, Smirnoff, Veuve, BuzzBallz, spiked seltzers, Michelob, Budweiser**.
- Sells commodity wine SKUs: **Josh, Cupcake, Barefoot, Kendall Jackson, Meiomi, Duckhorn, Bogle, J. Lohr, Yellowtail, Apothic, André, Cloud Break**.

**Reputation & engagement red flags:**

- Poor reviews on Google or Yelp.
- Poor Instagram engagement, or a following under 1K.
- A "Coming soon" notice on the homepage or Instagram.

**Operational & contextual red flags (warnings, not automatic disqualifiers):**

- Clearly operating as a discount store / big-box store.
- E-commerce platforms **City Hive** and **Spot Hopper** — more frequently used by liquor stores.
- No "About Us" story — usually suggests they aren't fully established yet.
- Located off a major highway.
- 5+ locations.

**Hard excludes (the chains):** Total Wine, BevMo, Binny's, Spec's, Wally's; generic neighborhood liquor stores; supermarket-attached wine departments; pure-play online retailers; wineries themselves; Costco / club stores.

### Affluence and neighborhood

- Affluence helps, but **unevenly.** Sensitivity rank: **wine bars > restaurants/butchers > wine shops.**
- **Counterintuitive catch:** the very wealthy often treat wine as a personal passion and prefer to pick their own — they dislike the "guessing" of a curated club, which makes them weak subscribers for a shop club today. _(This flips for vineyards once customized bundles exist: a wealthy customer will happily subscribe to receive a case of a specific cuvée.)_
- Favor **trendy/affluent neighborhoods with a residential base plus a small center or downtown** over purely residential areas. **Lincoln Park (Chicago)** is the model: wealthy, family-heavy, less dense than NYC, and underserved by wine shops — a convenience play.

### Best-of lists and directories

- Pull shops appearing on best-of lists (e.g. **The Infatuation**, local news/food press).
- Natural-wine directories such as **Raisin** surface candidates worth checking.

### Shipping as a growth lever

- For some partners, adding shipping is the unlock. **Main & Noir** (Portland, ME) added ~30 net-new members in their first month purely from enabling shipping.
- But **shipping is the mechanism, not the cause.** It only works when the shop is **nationally known** — if customers don't recognize the name nationally, they won't subscribe. ("If they don't know you in Kansas, they won't buy.") Other nationally known examples: **Domestique, Helen's.**
- Shipping is operationally harder than delivery and is expensive/complex in many states due to licensing and certification.

### Delivery range constraints

- A defined list of delivery ranges exists internally — **pull it before qualifying on delivery.** (See open items.)
- Watch for **alcohol-specific exceptions:** some markets have delivery coverage but **cannot deliver alcohol** (e.g. New York). Don't qualify a NY wine shop on delivery.

### Wine bars: mostly exclude

- **Default to excluding wine bars.** Even our best wine-bar launches landed the same weak outcomes; expect maybe one unicorn a year.
- **Why:** bars are experiential. A customer can drink the same wine at home for a third of the price, so there's little reason to subscribe — unless the bar offers access to something exclusive (e.g. imported wine others can't get).
- Bars also usually **lack the operational capacity** to run a club. They're often opened precisely because they're cheaper to operate (small space, low overhead, no kitchen), so club fulfillment doesn't fit. This is the most common objection at the bar level.
- **The one exception is geographic monopoly:** if the bar is the only place to get a certain type of wine for many miles — typically in smaller cities/towns outside major metros, in an affluent community — it can work.
- If you do consider a wine bar, qualify on **emphasis on wine over food** (people come for the wine and add food, not the reverse).

### Open items to gather

- **Delivery range list** (internal), including alcohol-delivery exceptions by state.
- **Wine exclusion list** — the bottles/types that disqualify a shop.
- A maintained **list of respected importers/distributors** to use as a trust signal.
- A short list of **recognized industry accounts** whose follows indicate street cred.

---

## Butcher shops

> Source: `table22/ICP - Premium Independent Butcher Shops - Summary.md` (structured ICP list, 1,059 verified shops) + butcher sales-call transcripts.

**Exemplars:** Beast and Cleaver (Seattle, chef-led whole-animal + supper clubs), McCall's Meat & Fish (LA, chef-couple urban premium), Left Bank Butchery (Saxapahaw NC, rural destination-town), Publican Quality Meats (Chicago, restaurant-group butcher arm), Dai Due (Austin, supper-club + butcher hybrid).

### The shop we want

- Single-location or very small (**1–3 stores**), owner-operated — typically **chef-led or master-butcher-led**.
- **Whole-animal / nose-to-tail** butchery: sources whole animals from **named local farms** and breaks them down in-house.
- Pasture-raised, grass-fed, or heritage-breed sourcing as **core identity, not a marketing line**.
- In-house **charcuterie, sausage, and dry-aging** program.
- Prepared foods, sandwiches, marinated cuts as a real revenue mix.
- **Programming already in place** — butchery classes, supper clubs, dinners, meat shares. These are the same hooks Table22 plugs into; a shop already running a **meat share / CSA / butcher subscription** is the bullseye.
- Premium urban or destination zip code, design-forward identity.
- Sources from networks like **Heritage Foods USA, Niman Ranch, Marin Sun Farms, White Oak Pastures, Joyce Farms**, or named regional pasture-based farms.

**Tiering:** Tier 1 = whole-animal + chef/butcher-led + programming (closest to Beast and Cleaver / McCall's). Tier 2 = premium independent but lighter scope (no charcuterie program, smaller curation, or a legacy butcher with less programming).

### Positive signals (search vocabulary that works)

Beyond "butcher shop": `whole animal butcher`, `nose to tail`, `craft butcher` (Butcher's Guild language), `pasture raised`, `heritage breed` / `heritage pork`, `dry aged` / `in-house dry-aging`, `chef butcher`, `in-house charcuterie` / `salumeria`, `boucherie` (French + Cajun), `farm to butcher` / `ranch to butcher`, and the bullseye club terms `meat share` / `meat CSA` / `butcher subscription`, plus programming terms `butchery class` / `butcher dinner`.

**Awards as a qualification signal:** Butcher's Guild membership, Good Food Awards (Charcuterie) winners, Food & Wine Best Butcher, Eater Essential/Best Butcher, StarChefs Rising Star Butcher, James Beard (Outstanding Butcher / America's Classics), Slow Food Snail of Approval. (See Appendix A.)

### Anti-ICP / exclusions

- Supermarket butcher counters generally: **Whole Foods, Wegmans, Publix, Bristol Farms, Gelson's, Erewhon, HEB, Mariano's**.
- Warehouse clubs: **Costco / Sam's / BJ's**.
- Chain operations **>3 locations**; generic neighborhood meat markets with no curation identity.
- **Pure-online meat delivery** (ButcherBox, Crowd Cow) — no physical retail/community anchor.
- Halal/kosher shops **without** a premium-curation identity.
- **BBQ joints that happen to sell sausage** — included only when the primary identity is raw-meat retail, not BBQ.

### Category-specific notes

- **No state-control carve-outs.** Unlike wine, meat retail is unrestricted everywhere — none of the PA/VA/NC liquor caveats apply. (The wine-list `BANNED_STATES` HI/IN/IA/KS/NV/ND/SD are applied operationally in code, but the summary doc flags these are worth reconsidering for butchers since shipping/club logistics differ from alcohol.)
- **Smaller universe than wine.** The premium-independent-butcher universe is ~**1,000–1,200 shops** total in the US (vs ~2,000+ wine shops) — whole-animal butchery is capital-intensive (cooler, cutter, sausage room, smoker, whole-carcass supply chain), so density is lower. Past the verifiable core, the long tail dilutes into generic neighborhood meat counters fast.
- **Restaurant-group / hybrid rows** (Gwen, Dai Due, Cochon Butcher, Toups' Meatery) fit ICP because they run programming and sell raw retail — segment them out only if outreach copy is shop-only. Restaurant groups whose "butcher arm" is back-of-house only (no public retail counter) are **not** ICP.

---

## Restaurants

> Source: `table22/restaurants-plg-icp.md` (structured PLG ICP, lead-scoring model validated at 1.67x lift) + restaurant sales-call transcripts.

### Tiers (partner type is the top scoring factor)

- **Tier 1 — Destination restaurants (primary target).** Worth traveling for. **~2x the AGMV of neighborhood restaurants.** Acclaimed chef/owner with media presence, reservation demand exceeds availability, premium price point ($50+/person), strong culinary identity, often media-featured.
- **Tier 2 — High-performing neighborhood restaurants.** Local favorites with a loyal repeat base. Baseline AGMV. Established (3+ yrs), strong local SEO, active community engagement, interest in membership offerings.
- **Tier 3 — Fast casual (deprioritized).** Counter-service, high-volume/low-margin, limited subscription fit. Pursue only with exceptional signals.

### Must-have gate criteria

| Signal | Threshold |
|---|---|
| Google reviews | **50+** minimum |
| Reservation difficulty | score **> 0.6** |
| Instagram | active account, **1K+** followers |
| Operating history | **2+ years** |

### Strong positive signals

Partner type = destination (highest weight) · high reservation-difficulty · Instagram **video views** · IG follower count · chef/owner media presence · **wine-program strength** (strong wine list = better fit) · email-list size. **Bonus:** press (Eater, Bon Appétit, local), James Beard, Michelin, an active subscription at a similar business, a partner referral ("heard about you from X").

**Engagement gradient (strongest single tier driver for restaurants).** Per the 210-lead sales review, real IG engagement maps near-monotonically to tier — strong → Tier 1, average/mixed → Tier 2, weak/none → Tier 3 — and **overrides acclaim** (award-winning restaurants with only average/weak engagement get demoted one tier: Biga, Feast Raw Bar, Gypsy Kitchen, Glin Thai, ONE65). Use the full hierarchy (video views > shares/saves > comments > likes), not video alone. Follower count is a weaker, separate signal. The one override is **partner/pipeline status**, which forces Tier 1 regardless. See "Tiering rubric — from sales review" in Part III.

### Firmographic & technographic fit

- **Firmographic:** revenue **$1–10M**, **1–3 locations**, **2–10 yrs** operating, staff **15–75**, top-50 US metro (initially).
- **Technographic:** **Toast POS** and **Resy/Tock** are strong positives (integration + demand-management signal). **No existing e-commerce = greenfield positive.** **Existing Shopify is neutral-to-harder** (already has e-comm, may resist switching). Active **Mailchimp/Klaviyo** is a positive (understands direct marketing).

### Disqualifiers

- **Hard (auto-reject):** <50 Google reviews · permanently/temporarily closed · chain/franchise (10+ locations) · fast-food category · no online presence at all · declining review-sentiment trend.
- **Soft (deprioritize):** fast-casual (unless exceptional) · <2 yrs operating · no reservation system (may signal low demand) · IG inactive >30 days · outside top-50 metros (for now) · already on a competitor subscription platform.

### Cuisine fit

Meaningfully informs targeting but never overrules quality/demand. Core-fit cuisines and the full list are in **Appendix B**.

> Note: `restaurants-plg-icp.md` carries its own restaurant-specific scoring weights (Partner Type 30% / Reviews 20% / Reservation 20% / IG 15% / Tech 10% / Referral 5%). These are the **restaurant-PLG triage weights** and are distinct from the cross-vertical SHAP feature ranking in Part I — don't conflate the two.

---

## Cheese shops

> Source: distilled from 6 Table22 cheese-shop sales-call transcripts (Culpeper Cheese, St. James Cheese, Walnut Creek Cheese, Surdyk's, Artisan Cheese). **No structured ICP doc yet — lightest evidence base of any vertical; treat as directional.**

### The shop we want

- Independent / small (**1–3 locations**), **founder-available** and actively seeking a club / repeat-revenue solution.
- **Curated sourcing mix** — imported + domestic, named producers, affineur relationships; **cut-to-order / hand-picked**, not pure wholesale distribution.
- Owner/buyer carries a **CCP (Certified Cheese Professional)** credential or equivalent expertise — signals real curation depth and category authority.
- Positioned around **education and community** (titles like "cheese educator / head monger"), so subscribers get producer stories, tasting notes, pairings.
- Either **no existing program**, or an existing one hampered by fulfillment friction we can solve.

### Positive signals

- CCP credential or named affineur/producer relationships.
- **Niche sourcing that fills a market gap** — e.g. halal/kosher-compliant cured meats where competitors only run pork→beef.
- A **complementary category to bundle** — wine + cheese, or charcuterie — so club boxes have a natural theme (the A/B/C + optional-D tier model fits).

### Anti-ICP / exclusions

- Corporate / multi-location chains (slow decisions, less founder urgency).
- High-volume wholesalers / large-inventory operations that don't need a club revenue model.
- Commodity sourcing with **no curation story** to drive subscription appeal.
- Prior club skeptics who won't engage (gatekeeping / voicemail-only is itself a low-need signal).

### Category-specific constraint

- **Cold-chain perishability is the live fulfillment gate.** Qualifying on delivery/shipping requires a **regional fulfillment partner** — the model is Table22 handles the admin and subs out local cold-chain fulfillment. Confirm a fulfillment path exists in the shop's market before qualifying on delivery.

---

## Bakeries

> Source: distilled from 7 Table22 bakery sales-call transcripts (Breadbelly, Proofreader, Ginger & Baker, Trompeau, Sea Level, Black Hole, Evergreen Bread). Moderate evidence base — two long calls carried most of the signal.

### The shop we want

- **Owner-operated**, **artisanal bread-first / naturally-leavened** (sourdough, laminated pastry as a complement) — not sweets-only.
- **Brand-conscious ownership** that rejects marketplace/delivery-app commoditization ("our product deserves attentive care") — aligns with Table22's not-a-marketplace positioning.
- A **limited, intentional menu** (quality control over volume) — signals craft, and makes a curated subscription box coherent.
- **In a growth phase** — this is the single strongest timing signal.

### Positive signals

- **Recent capacity expansion** (new space, commercial oven, dedicated production kitchen) = bandwidth to add a new channel = **prime moment to reach out**.
- **"Sells out daily"** is a green flag, not red — it means a supply-constrained brand with real demand (especially once they've just added capacity).
- **Seasonal / rotating offerings** — strong subscription appeal (monthly exclusives not on the everyday menu).
- **Gifting potential** — 3–6 month bundles for holidays/Mother's Day; the gift narrative sells itself for artisanal bread.
- Founder-operated / small team = faster buy-in.

### Anti-ICP / objections that stick

- **Margin / fee fatigue.** Bakeries already bleeding to wholesale + delivery apps treat a 15% take rate as a dealbreaker ("I keep getting 25% here, 15% there… end up making no money").
- **Acquisition / expansion mode = wrong moment.** No staff bandwidth to run a subscription mid-scramble.
- **Event / catering-pivot focus** — scaling toward B2B/events, not D2C subscriptions.
- **Sweets-only / single-product** (cupcakes, cakes, cookies) — a generic surprise box lacks bread's storytelling power. A heavy demotion, not a hard DQ: strong engagement can lift these to Tier 2 (never Tier 1) — see the tiering rubric in Part III.
- **Breakfast/brunch venues with incidental baking** — baking is secondary; lower fit and usually stretched on food service.
- **Next-day pre-order mindset** (e.g. "preorder cutoff is noon the day prior") clashes with Table22's ~3-week prepaid lead-time model.

### Deal sizing & fulfillment

- Healthy middle market is **~50–100 boxes/month** at **~$50–60/box**; ~300/mo is an outlier full operation.
- Freshness / daily-bake drives fulfillment — **pickup vs. ship** flexibility matters; temperature-sensitive add-ons (e.g. a kaya-toast kit with butter/jam) need refrigerated delivery.

---

# PART III — Activation

## Tiering rubric — from sales review (Alec, 210 leads)

> Source: Alec (sales manager) tier review of 210 leads (Beli + lookalike samples), mapped to a derived rubric via a multi-agent workflow. This is the **practitioner counterpart** to the SHAP weighting in Part I — where SHAP ranks features by predicted Peak AGMV, this captures how an experienced closer actually sorts real leads. The two agree on the engagement ordering; read them together.

### The headline finding: engagement is the spine of tiering

Across 210 leads, **real Instagram engagement (likes and comments, not follower count) is the single best predictor of tier**, and it maps almost monotonically:

- **Strong engagement → Tier 1** (real likes/comments + good reviews + no detractor): Jacqueline, Grisette, Dish Osteria Bar, Café Dear Leon, East Village Meat Market, Mike's Deli, Claro's Italian Market, Villabate Alba.
- **Average / mixed engagement → Tier 2** — the literal Tier 2 fingerprint. "Mixed social engagement" recurs verbatim across Mountain House, Dagg Thai, Sozai, Dando La Brasa, Pane e Vino, The Wine House, Silverlake Wine, Lira Beirut. Average engagement is the **ceiling for non-partners** — on its own it never reaches Tier 1.
- **Weak / no engagement → Tier 3** — and it overrides otherwise strong signals (Upstairs at Caroline demoted despite good reviews; Biga, Feast, Gypsy Kitchen, Glin Thai, ONE65 demoted from would-be Tier 1 to Tier 2 because award recognition was paired with only average/weak engagement).

This matches Alec's stated takeaway that engagement is one of the biggest predictors of demand/success on Table22, and it is **most decisive for restaurants**. Two hard rules sit on top of the gradient:

1. **Follower COUNT is not engagement.** A large following with thin likes/comments does not earn tier (Silence Please and 7th Street Burger both carry large followings and both land Tier 3). The test is likes/comments/saves/views *relative to* following.
2. **Weak engagement is a heavy demotion, not an automatic DQ.** Per Alec's **Thompson Italian** caveat, a place can still succeed as an outlier — so treat poor engagement as a strong negative, while strong engagement is near-deterministic for a high tier.

### Canonical engagement hierarchy (cross-vertical)

Use this exact order everywhere, most → least decisive:

**video views > shares / saves > comments > likes**

Provenance (who weighted what): **video views & shares — Kavir · saves — Dannah · comments & likes — Alec.**

Likes and comments are the **lowest-weighted rungs, not zero** — they are real demand signals, just below saves/shares/views. This is consistent with SHAP (Average Video Views #3, Average Shares #9, Average Likes #14): SHAP and the practitioner read **agree** on the ordering. The bottom of the ladder still counts — it is exactly what lets you read strong vs. mixed vs. weak engagement. Preserve the Part I nuances: small-market metrics run lower (weight relative local dominance), and static-only content understates brand strength rather than disqualifying it. **Butcher / deli / specialty-grocer verticals use Facebook engagement as the proxy** when IG is weak or absent (Gartner's, B & W Meat Company, Carnivore Oak Park, Don & Joe's — all Tier 2 on strong FB engagement).

### Tier decision rules

**Tier 1 (53 leads).** Any one of:

- **Partner / pipeline override** — existing, current, former, churned, in-pipeline, or "followed by current partners." Forces Tier 1 **regardless of engagement, website, or social** (Nari, Sea Wolf Bakers, Houston Dairymaids, Mondo Vino, Biondivino, Ardor Natural Wines, K&L Wine Merchants, Chambers Street Wines, Arrowine & Cheese). Aligns with the project rule that an existing club is a positive signal, not a disqualifier.
- **Strong engagement + good reviews + no active detractor** (Jacqueline, Grisette, Café Dear Leon, East Village Meat Market, Jack & Pat's, Mike's Deli, Cheese & Crack).
- **Acclaim / award (James Beard, Michelin, JBF finalist) + good reviews + no engagement detractor** (Scotch Lodge, 112 Eatery, Jargon, Mighty Bread Company, Kasama, The Cheese Store of Beverly Hills).
- **Established / popular brand or strong hospitality group with high review count + good reviews**, even when IG engagement is unmentioned (Mediterranean Exploration Company, Aba, Schaller & Weber, Murray's Cheese, The Alley Light, Le Veau d'Or).
- **Strong ICP fit** (wine+cheese+deli, chef-driven, fine dining with no existing takeout) + good reviews (Martha's Vineyard Fine Wine, Season to Taste, GW Fins, Ella Elli).

**Tier 2 (92 leads).** Good profile held back by exactly one soft drag:

- **Good reviews + high review count but average / mixed / weak engagement** — the most common Tier 2 pattern (a Cena, 1789 Restaurant, dLeña DC, Nori, Lira Beirut, Mountain House, Dagg Thai, Sozai, The Wine House, Silverlake Wine, Paulina Market, Hashems). High review count props weak-engagement leads up into Tier 2 instead of letting them fall to Tier 3.
- **Award / Michelin but only average/weak engagement** — drags one tier down from where acclaim alone would land (Biga, Feast Raw Bar, Gypsy Kitchen, Glin Thai Bistro, ONE65 Patisserie).
- **Exactly one soft detractor on an otherwise good, strongly-engaged profile:** single-product/sweets-only (MYKA, Lysée, Bellvale Farms Creamery), off-vertical coffee/tea but strong engagement + bakery (Yoka Tea, STAGGER Coffee, Lost Sock Roasters), multiple locations (La Pecora Bianca), more-pizza-than-pasta (Macoletta), on-premise bar but strong engagement (Cana, Charis Listening Bar, Farmacia).
- **Butchers / delis / specialty grocers with solid Facebook engagement + good reviews** even when IG is weak/absent (Gartner's, B & W Meat Company, Carnivore Oak Park, Don & Joe's, Sorrento Italian Market, Scandinavian Specialties).
- **Existing wine club / partner-adjacent but newer/fewer reviews** (Bay Grape, Slope Cellars, Augusta Food and Wine, Social Wines).
- **Popular but no social presence, or newer and just gaining traction** (Abuqir, SUSU, Hwa Mi Won).

**Tier 3 (62 leads).** Any of:

- **Weak/no engagement + no website AND/OR no social** (Sando Table, Red Lantern, 89 Charles, Fischer Meats, Korean Ice Co., Dining Yamamoto, Fu Zhou Wei Zhong).
- **Off-vertical that is not the food ICP** — coffee/tea-led, grocery, catering, delivery (DAMO, Millie's Coffee Co, Bukas Cafe, Matsu Matcha, Zupan's Markets, Citarella, Phoenicia, Yes! Organic Market, La Pera Catering, Goodhart Coffee Catering).
- **Sweets-only / single-product casual with average-or-worse engagement** (Julia Jean's, Yala Greek Ice Cream, Marco Polo Italian Ice Cream, Bi-Rite Creamery, Tompkins Square Bagels).
- **Cocktail / on-premise bar as the core experience with weak/average engagement** (Obvio Cocktail Bar, Reynold's Bar, Bar 821, People's, Upstairs at Caroline).
- **Chain / national brand** (Jeni's Splendid Ice Creams, PopUp Bagels, 7th Street Burger) — "established brand" flips negative when it means a chain.
- **Weak-fit fast-casual food trucks / taquerias** (El Gallo Giro Truck, Suavecito Birria & Tacos, Tacos La Cuadra).
- **Liquor-store-only / weak-fit retail with low engagement** (Schneider's of Capitol Hill).

### DQ rules

- **Hard DQ (Tier 3/DQ):** off-vertical retail that is not a food business at all — Breed & Company (a hardware store). Distinguished from food-adjacent retail (delis, cheese shops, specialty grocers) by total absence of food ICP, not merely weak engagement.
- **Effective DQ to Tier 3:** no website AND no social + weak/no engagement — overridden only by partner status or standalone popularity (Abuqir).
- **Closed businesses → Tier 3 regardless of metrics** (Salt & Time — "closed in 2024").
- **Demote to Tier 3:** national/multi-unit chains even with large following; cocktail/on-premise bar core with weak/average engagement; sweets-only/single-product with average-or-worse engagement; off-vertical coffee/tea/grocery/catering/delivery; liquor-store-only retail with low engagement.

### Outlier caveat (the rubric is non-linear)

Engagement is near-deterministic but not absolute — these cases show where it bends:

- **Engagement promotes despite a weak-ICP read:** MYKA (ice-cream-only, no website — very high engagement "keeps it Tier 2"); Miya Miya Shawarma (casual concept lifted to Tier 2 by extremely high engagement + large following).
- **Brand / review volume substitutes for engagement:** Schaller & Weber and Murray's Cheese reach Tier 1 with engagement unmentioned; The Address held at Tier 2 on excellent review score + volume despite weak engagement; Abuqir rescued to Tier 2 by popularity alone despite no website/no social.
- **Fit / relationship outweighs a sales-history negative:** The Cheese Store of Beverly Hills stays Tier 1 despite "declined us many times."
- **Following ≠ engagement ≠ fit:** Silence Please carries a large following yet lands Tier 3 (read as an audio-hardware brand); 7th Street Burger's large following does not rescue it from chain + weak-cuisine fit.

---

## Implications for sales qualification

A simple triage framework for inbound leads:

**Book a meeting immediately when you see:** butcher shop, wine shop, cheese shop, or destination restaurant with any strong award/press mention, hard-to-book signals, active video engagement, premium price positioning ($$$), and independent ownership with 1–3 locations. **Any 3+ of these → immediate outreach.**

**Research before outreach when you see:** neighborhood restaurant, bakery, specialty grocer, wine bar, or market/deli with moderate press or regional recognition, signs of active audience building (email list, events, social engagement), $$ price positioning with quality signals, compatible tech stack, and $1M+ estimated revenue. Quick check on whether brand quality and demand justify the sales investment.

**Deprioritize when you see:** fast casual, non-wine bar, brewery, or coffee/tea with no press/awards, low social engagement or inactive digital presence, $ price positioning, chain/franchise (10+ locations), or QSR/counter-service only. Pursue only with exceptional offsetting signals.

**Disqualify when you see:** caterers, pizza-first concepts (unless clearly artisanal/premium), cocktail bars, liquor stores, delivery-only/ghost kitchens, franchise operations, or estimated revenue below $750K.

**For small-market leads:** adjust volume thresholds downward and weight relative local dominance, regional press, and reservation difficulty more heavily than raw social or review metrics.

---

## Implications for paid marketing targeting

**Audience construction.** Build targeting around the ICP dimensions directly. Focus on owners and decision-makers at independent restaurants, wine shops, butcher shops, bakeries, cheese shops, and specialty retailers. Interest targeting: James Beard, Michelin Guide, Eater, Bon Appétit, Food & Wine, Punch Magazine, farm-to-table, artisanal food, craft beverage. Job titles: Owner, Chef-Owner, GM, Director of Operations, Marketing Director at F&B businesses. Build lookalikes from top-performing current partners, weighted toward the highest-AGMV partner types.

**Exclusions & negative keywords.** Exclude chain-restaurant employees, franchise owners, QSR/fast-food interests, and large restaurant-group corporate roles (10+ locations). Negative keywords: "franchise," "chain restaurant," "fast food," "delivery only," "ghost kitchen," "liquor store," "catering company," "pizza delivery."

**Budget allocation.** Weight spend toward partner types with the highest avg AGMV and the most growth headroom. Butcher, wine, and cheese shops are the strongest performance × expansion combination. Destination restaurants are high-value but already a large base. Bakeries and specialty grocers are solid mid-range, especially for artisanal concepts.

---

## Implications for ad creative production

**Principles (static and video):**

- **Lead with the merchant, not the platform.** Showcase beautiful food, artisanal craft, and the passion behind the business. Table22 is the enabler, not the star.
- **Use press and awards as social proof.** "Join the Michelin-starred restaurants, James Beard winners, and Eater favorites already on Table22" beats feature lists.
- **Speak to unmet demand.** "Your customers want more of you than a weekly reservation."
- **Be vertical-specific.** Butcher imagery/language for butchers, wine proof points for wine shops. Generic F&B underperforms. Build separate assets per top partner type.
- **Match the premium positioning.** Visual language should feel premium and artisanal — not discount, corporate, or generic SaaS.

**Static ads.** Feature the best-performing partner types: butcher shops with beautiful cuts, wine shops with curated selections, cheese shops with artisan wheels, destination restaurants with aspirational plating. Show the product, not the platform interface.

**Video ads.**

- **Top-of-funnel (15–30s):** short reels of beautiful product — a butcher breaking down a side of beef, a sommelier pulling a rare bottle, a baker scoring sourdough — with a simple CTA. Mirrors the content best-fit merchants already create; feels native in-feed. Testimonials too.
- **Mid-funnel retargeting (60–90s):** merchant testimonials from award-winning/press-featured partners. A Michelin-starred chef or James Beard-winning bakery owner explaining why they chose Table22 self-selects the right audience — aspirational merchants see themselves; poor-fit merchants self-filter out. Focus the narrative on revenue impact, customer loyalty, and operational simplicity.
- **Feature video-native businesses as social proof.** The model confirms strong-video-engagement partners perform best; showcasing them signals sophistication and resonates with similar prospects.

---

# Appendices

## Appendix A — Awards & recognition by vertical (tiered)

Awards are a strong qualification signal. Tiers: **1 = highest prestige, 2 = strong industry recognition, 3 = regional/specialized.**

### Restaurants
- **Tier 1:** Michelin Stars (1/2/3), Bib Gourmand, Green Star; James Beard Awards (restaurant/chef/hospitality); Eater (Restaurant of the Year, city lists); Resy 100; Esquire "Best" list; New York Times reviews/lists; Bon Appétit Best New Restaurants / Hot 10; World's 50 Best Restaurants.
- **Tier 2:** Food & Wine Best New Chefs / Global Tastemakers.
- **Tier 3:** Wine Spectator Restaurant Awards (wine program).

### Wine Producers / Wineries
- **Tier 1:** San Francisco International Wine Competition; Michelin "Grape" program; Punch Magazine features (domestic producers only).
- **Tier 2:** Decanter World Wine Awards (DWWA); International Wine Challenge (IWC); International Wine & Spirit Competition (IWSC); Robert Parker / Wine Advocate (90+); Wine Spectator (90+); Wine Enthusiast (90+); James Suckling (90+); Jancis Robinson (high ratings — often scores smaller/newer producers).
- **Tier 3:** New York Wine Classic; TEXSOM International Wine Awards; regional competition medals.

### Wine Stores / Retailers
- **Tier 1:** Wine Spectator Grand Awards; Wine Enthusiast Wine Star Awards (Retailer of the Year); Wine Enthusiast Best Wine Shops in America; James Beard Awards (wine program); Michelin "Grape" program; VinePair 50 Best Wine Shops; Punch Magazine features.
- **Tier 2:** World of Fine Wine Best Wine Lists; Sommeliers Choice Awards; Food & Wine Visionaries Awards / Global Tastemakers.
- **Tier 3:** Decanter World Wine Awards (retailer categories); "Best of [Local Area]" recognition.

### Bakeries
- **Tier 1:** James Beard Awards (Outstanding Bakery; Outstanding Pastry Chef/Baker); Bon Appétit best-bakery lists; Eater best-bakery lists; Food & Wine best-bakery lists.
- **Tier 2:** Coupe du Monde de la Boulangerie; IBIE World Bread Awards USA; Panettone World Cup.
- **Tier 3:** Regional bakery recognition.

### Cheesemongers / Cheese Retailers
_Note: many cheese-competition winners are producers rather than retail shops. Below are those most relevant to retail cheesemongers; overlap with producer recognition is common._
- **Tier 1:** Cheesemonger Invitational (CMI) Winners & Finalists; Mondial du Fromage; Culture Magazine features; Eater / Serious Eats national lists; Food & Wine Best Cheese Shops in America.
- **Tier 2:** American Cheesemonger Invitational; Academy of Cheese Young Cheesemonger of the Year.
- **Tier 3:** Regional cheese-shop recognition.

### Butchers / Charcuterie
- **Tier 1:** American Association of Meat Processors (AAMP) Awards; Good Food Awards (Charcuterie).
- **Tier 2:** sofi Awards (Charcuterie Meats); FABI Awards (NRA).
- **Tier 3:** Regional butcher/charcuterie recognition.

### Specialty Food Retail (general)
- **Tier 1:** sofi Awards (the "Oscars" of specialty food); Good Food Awards.
- **Tier 2:** FABI Awards; Specialty Food Association Leadership Awards; Wine Enthusiast Wine Star Awards (Retailer of the Year).
- **Tier 3:** Regional specialty-food recognition.

---

## Appendix B — Cuisine fit detail (restaurants only)

- **Core fit:** Italian, Wine Bar, French, Mediterranean, Israeli/Middle Eastern, American (Farm to Table), Thai, Meat/Steakhouse, European — proven resonance with the Table22 audience and merchandising model.
- **Emerging fit:** Korean, Japanese, Chinese, Mexican, Vietnamese, Filipino, BBQ, Spanish, Nordic — good fit where brand and quality indicators are strong.
- **Lower fit / experimental:** most Latin American (Venezuelan, Peruvian, Brazilian), most African cuisines, pizza-first concepts, burgers — possible niche fits but less scalable currently.

Cuisine alone should never disqualify a lead with strong quality and demand signals.

---

## Appendix C — Tech-stack compatibility reference

- **POS:** Toast, Square, SpotOn, Shopify
- **Website:** BentoBox, Squarespace, Wix, custom WordPress
- **Email/CRM:** Mailchimp, Klaviyo
- **Reservations:** Resy, Tock, OpenTable, Tripleseat

Each can be used as a binary fit flag or a weighted enrichment feature.

---

## Appendix D — Role-level predictors

Presence of these roles (verifiable via LinkedIn or People Data Labs) correlates with willingness to test new growth channels: **Catering Manager, Events Manager, Director of Operations, Marketing Director/Manager, Special Projects Lead.**
