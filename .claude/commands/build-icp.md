---
description: Build the ideal customer profile and search plan in data/icp.md
argument-hint: [extra guidance, e.g. "focus on Germany" or "SMBs only"]
---

Build or refresh the ideal customer profile (ICP) in `data/<product>/icp.md`, using `data/<product>/product.md` and any guidance in `$ARGUMENTS`.

## Steps

1. **Read `data/<product>/product.md`.** If it does not exist, stop and tell the user to run `/setup-product <url> "<description>"` first.
2. **If `data/<product>/icp.md` already exists**, read it and keep the `## Learned disqualifiers` and `## Notes from the user` sections intact; everything else may be rewritten.
3. **Research who buys this kind of product.** Use WebSearch (4 to 8 queries), for example:
   - `"<competitor>" customers` and `"<competitor>" case study` for 2 to 3 competitors listed in product.md
   - `who uses <category> software`
   - `<category> for <industry>`
   - `"<pain phrase>" site:reddit.com` or `site:news.ycombinator.com` to see who complains about the problem
   WebFetch 2 to 4 of the most useful pages (competitor customer pages are gold: they list real company types and sizes).
4. **Write `data/<product>/icp.md`** with this structure:

   ```markdown
   # Ideal customer profile

   Built on: <today>   From: data/product.md
   Guidance from user: <$ARGUMENTS or none>

   ## Segment 1: <short name>  (priority: high/medium/low)
   - Industry / vertical:
   - Company size (employees, revenue if relevant):
   - Geography:
   - Buyer titles (who signs, who champions):
   - Pains they feel (in their words):
   - Why this product fits:
   - Buying signals to look for: (hiring for X, raised funding, uses competitor Y, launched Z, complained about W)
   - Disqualifiers: (too small, wrong stack, regulated out, etc.)
   - Example companies (with URLs, from research):

   ## Segment 2: ...   (1 to 3 segments total)

   ## Where to find them
   Bullet list of source types that work for these segments: directories, job boards, review sites (G2, Capterra), competitor customer pages, communities, funding news, app marketplaces, conference sponsor lists, etc. Be specific (name the sites).

   ## Search queries
   15 to 25 ready-to-run WebSearch queries grouped by segment. Mix: list/directory queries, job-post queries that reveal the pain, competitor-customer queries, signal queries (funding, launches), community queries. Each on its own line starting with `- `.

   ## Scoring rubric (total 100)
   | Factor | Points | How to judge |
   |---|---|---|
   | Industry / use-case match | 0-30 | ... tailored to this product |
   | Company size in range | 0-20 | ... |
   | Evidence of the problem | 0-25 | ... what on their site or posts shows it |
   | Buying signal | 0-15 | ... |
   | Reachable decision maker | 0-10 | named person with public role/profile |

   Score below 40: do not add. 40-59: add only if signals are strong. 60+: add.

   ## Learned disqualifiers
   (filled in by /review-leads from the user's rejections; keep existing entries)

   ## Notes from the user
   (keep existing entries)
   ```

5. **Report back**: list the segments in one line each, the top 5 queries you plan to run first, and ask the user to confirm or adjust (size, geography, industries to avoid). Suggest `/find-leads 10` as the next step.

## Rules

- Tailor the rubric to this product; do not leave the generic text.
- Every example company must have a URL.
- Keep the user's guidance in `$ARGUMENTS` as a hard constraint (if they say "Germany only", geography is Germany only).
