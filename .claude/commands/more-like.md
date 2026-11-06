---
description: Find lookalike companies of a lead you liked (or a won customer)
argument-hint: <lead-id> [count, default 8]
---

Find companies similar to the lead in `$ARGUMENTS` (first token is the id, optional second token is how many to add, default 8).

## Steps

1. `python3 scripts/leads.py get <id>` and read `data/<product>/notes/<id>.md`. Write a two-line "seed profile": industry, what they sell, size, location, stack, the signal that made them a fit.
2. `python3 scripts/leads.py domains` and `python3 scripts/leads.py searches` so you can skip known companies and queries.
3. Search for lookalikes using the seed, rotating these query types:
   - `"<seed company>" alternatives` and `"<seed company>" competitors` (then WebFetch comparison or review pages, they list peers)
   - `companies like <seed company>`
   - the directory or list page the seed was found in (see its `sources`), fetch it again for siblings not yet added
   - `<seed industry> <seed product type> <seed location>` list queries
   - job-post queries that reveal the same signal (`"<signal role>" <industry> <location>`)
   - review sites: `site:g2.com <category>`, `site:capterra.com <category>` for the category the seed belongs to
4. For each candidate, WebFetch the homepage (and about/team if linked), confirm it matches the seed profile and the ICP, score it with the rubric, and record all sources. Note in `fit_reason` that it is a lookalike of `<id>`.
5. Log every query with `python3 scripts/leads.py log-search "<query>" --found <n>`.
6. Save qualifying leads (score 60+, or 40+ with a strong signal) via a JSON file and `python3 scripts/leads.py add --file ...`. Put `lookalike of <id>` in `signals`.

## Report

The seed profile in two lines, then a table of what was added (`id | score | company | why like the seed`), then candidates seen and rejected with the reason. Suggest `/review-leads` next.

## Rules

- Same as `/find-leads`: sources for everything, no guessed contacts, public pages only, no repeated queries, quality over count.
- Stop after 10 queries or 20 fetched candidates, whichever comes first, and say how far you got.
