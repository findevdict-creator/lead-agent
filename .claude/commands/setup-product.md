---
description: Analyse the user's product site and write data/product.md
argument-hint: <url> "<one-line description>"
---

Analyse the product at the URL in `$ARGUMENTS` and write `data/<product>/product.md`. The rest of the arguments after the URL is the user's own description of the product; treat it as the most reliable statement of what the product is.

## Steps

0. **Pick the product workspace.** If the `LEAD_AGENT_PRODUCT` environment variable is set (the run was started from the GUI), use that product as it is and skip the rest of this step: do not create or switch products. Otherwise derive a short slug from the domain (for `https://anchorstance.com` use `anchorstance`) and run `python3 scripts/leads.py product <slug>`. This creates `data/<slug>/` and makes it active; every other command then works on this product until you switch. `<product>` below means that folder.
1. **Fetch the site.** WebFetch the given URL. From the page, find links to pricing, about, customers / case studies, docs, blog, and integrations pages, and WebFetch up to 6 of the most useful ones. If a page fails to load, note it and continue; do not stop.
2. **Search for outside context.** Run 2 to 3 WebSearch queries: `"<product name>"`, `"<product name>" alternatives`, `"<product name>" review`. Use them to find competitors, how others describe the product, and any public customer mentions.
3. **Write `data/<product>/product.md`** with exactly these sections (use "Unknown" rather than guessing):

   ```markdown
   # <Product name>

   Source URL: <url>
   User's description: <their words verbatim>
   Analysed on: <today>

   ## What it does
   2 to 4 sentences, plain language.

   ## Problems it solves
   Bullet list, one pain per line, in the words a buyer would use.

   ## Key features
   Bullets.

   ## Who it is for (as stated by the site)
   Industries, roles, company sizes the site itself targets.

   ## Pricing
   Plans and prices if public, else "Not public".

   ## Proof points
   Named customers, testimonials, numbers, integrations. Each with its source URL.

   ## Competitors / alternatives
   Names with URLs, from search.

   ## Tone and positioning
   One or two lines on how the product talks about itself.

   ## Sources
   Every URL fetched or cited.
   ```

4. **Report back** in the chat: a 5-line summary (what it does, who it's for, pricing, top 3 competitors, anything you could not find), then ask the user to correct anything wrong. Mention that they can edit `data/<product>/product.md` directly.
5. Suggest the next command: `/build-icp`.

## Rules

- Do not invent customers, prices or numbers. "Unknown" is a valid answer.
- Cite the URL for every proof point.
- If `data/<product>/product.md` already exists, show a one-line diff summary of what changed after rewriting it.
