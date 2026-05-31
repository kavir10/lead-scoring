# Channel 07 — Cookbook Author → Restaurant Mapping

**Motion:** Curation
**Vertical fit:** Destination restaurants, neighborhood restaurants, bakeries
**Status:** Not yet built
**Owner:** TBD
**Cost target:** ≤ $10/run

## Premise

A working chef who publishes a cookbook on a prestige food-publishing imprint
is almost certainly running a T1 or upper-T2 restaurant. The publisher's
own marketing pages name the chef, the book, and the chef's current
restaurant — explicitly, for SEO and book-launch press.

Volume is small (a few hundred chef-author restaurants nationally), but
**hit rate per row is exceptionally high**. Almost no overlap with awards
or press archive (cookbook publication is a separate signal from restaurant
acclaim).

## Source publishers

| Publisher | Imprint | Food list size | Page structure |
|---|---|---:|---|
| **Phaidon** | Phaidon main + Hamlyn | ~150 chef titles | Author bio pages link to restaurant |
| **Ten Speed Press** (Crown / PRH) | Ten Speed | ~200 chef titles | Author bio + venue mention |
| **Artisan Books** (Workman / Hachette) | Artisan | ~100 chef titles | Author bio |
| **Knopf** (Penguin Random House) | Knopf food list | ~80 chef titles (high prestige) | Author bio |
| **Clarkson Potter** (PRH) | Clarkson Potter | ~120 chef titles | Author bio |
| **Houghton Mifflin Harcourt** | HMH food | ~50 chef titles | Author bio |
| **Hardie Grant** | Hardie Grant Books | ~60 chef titles (US authors) | Author bio |
| **Chronicle Books** | Chronicle food | ~70 chef titles | Author bio |
| **Hardie Grant + Plum (HG imprint)** | overlap with above | — | — |
| **Princeton Architectural Press / Roost Books** | — | ~30 chef titles | Author bio |
| **Apartamento / Apollo + niche imprints** | — | <30 each | Direct fetch |

After dedupe across imprints (an author publishes with one), target = **~700
unique chef-authors**, of which ~500 will have a current working US
restaurant.

## Recipe

For each publisher:

1. **Crawl the food/cooking category** — paginated listing pages. httpx +
   selectolax. Capture author name per title.
2. **Fetch author bio page** — most publishers have `/author/firstname-lastname`
   or `/book/title -> Author Bio` section.
3. **Extract restaurant** — LLM extraction (Haiku 4.5) over the bio prose:

   > Extract the chef's current restaurant(s). Return:
   > - restaurant_name
   > - city
   > - state
   > - country
   > - role (chef-owner | head chef | consulting chef | pastry chef | former)
   >
   > If the bio mentions multiple restaurants, return all current ones.
   > Exclude restaurants the chef has left.

4. **Verify via Serper Maps** — confirm the restaurant exists at the named
   city and is currently operating. Drop closed restaurants.

## Output schema

`output/directories/cookbook_author_restaurants_<YYYYMMDD>.csv`:

```
source = "cookbook_author_<publisher_slug>"
tier = 1
business_type = "restaurant" | "bakery" (pastry-focused authors)
distinction = "{author_name} author of '{book_title}' ({pub_year}, {publisher})"
year = <pub_year>
+ extra cols: author_name, book_title, book_pub_year, publisher,
              author_role_at_venue
```

## Aggregation

A venue mentioned across multiple cookbooks (the chef has published several
titles, or the venue's whole team has published) is **strong A-list signal**.
Add `cookbook_count` column for visibility.

## Volume & cost

- ~10 publishers × ~100 titles = ~1,000 author bio fetches
- Haiku extraction: 1,000 × 1.5K tokens ≈ ~$1
- Serper Maps verify: 1,000 × $0.30/1K = ~$0.30
- **Per-run total: ~$2-5**
- **Net-new venues per run (first run): ~500 unique current US restaurants**
- **Subsequent runs: ~50-100/year (new cookbook releases)**

## Refresh cadence

Twice a year — major cookbook release windows are spring (April-May) and
fall (October-November).

## Risks

- **Author churn** — chef may have left the restaurant named in the bio
  (especially for older books). LLM must extract `role` = `former` and we
  drop those. Recency filter: only books published in last 8 years.
- **Multi-restaurant chefs** — Daniel Boulud, Marcus Samuelsson, etc. each
  have 5+ venues. Capture all; let scoring decide which is highest priority.
- **Ghostwritten celebrity cookbooks** — Gordon Ramsay etc. are noise. The
  bio will usually be specific to a working chef, but flag ambiguous cases.
- **International authors** — Phaidon especially leans European. US filter at
  the LLM step.

## Repo placement

```
directories/
  restaurants/
    cookbook_authors.py          # single orchestrator
    _cookbook_publishers.py      # publisher-specific page parsers
```

Single module rather than per-publisher because the LLM extraction step is
the bulk of the work; per-publisher logic is just URL patterns.

## Open questions

1. **Wine writers** — Eric Asimov, Karen MacNeil, Jancis Robinson — same
   logic but the named venue is a wine shop or restaurant they recommend, not
   one they run. Separate sub-channel? Probably overlaps too much with
   Substack channel (#6). Skip.
2. **Self-published cookbooks** (Amazon KDP, Substack-launched) — too noisy,
   skip for v1.
3. Cross-reference against **Eater 38** and **JBF Outstanding Chef** —
   intersection is gold but is already on the Wave 1 list. Use this channel
   to find the **non-overlapping** chef-authors.
