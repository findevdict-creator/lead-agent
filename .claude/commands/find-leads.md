---
description: Search the web for new leads matching the ICP, score them and save them with sources
argument-hint: [count, default 10] [segment name or extra guidance]
---

Find new leads. `$ARGUMENTS` may start with a number (how many leads to add, default 10) followed by optional guidance such as a segment name, a country, or a focus like "only companies that use Shopify".

## Before searching

1. Read `data/icp.md`. If missing, stop and tell the user to run `/build-icp`.
2. Run `python3 scripts/leads.py searches` and `python3 scripts/leads.py domains`. Do not re-run a logged query and do not add a company whose domain is already listed.
3. Pick the segment(s): the one named in the guidance, otherwise the highest-priority segment with the fewest leads so far (check `python3 scripts/leads.py list --json` and count by industry).

## Search loop

Repeat until you have the requested number of leads scoring 60+ (or 40+ with strong signals), or you have run 12 queries, whichever comes first:

1. Choose a query from `## Search queries` in icp.md that is not in the log, or write a new one in the same style. Rotate query types: a directory/list query, then a job-post query, then a competitor-customer query, then a signal query (funding, launch, "switching from").
2. WebSearch it. From the results pick candidate companies (not articles about the topic in general). A list article like "Top 20 X startups" is a good source: WebFetch it and extract the companies.
3. For each candidate, WebFetch their homepage and, if linked, the about / team / contact page. Confirm: what they do, approximate size, location, and whether the ICP pain is visible (features they lack, tools they list, jobs they post). Look for a named decision maker with a public role on the team page or in search results; capture their public LinkedIn URL only if it appears in search results.
4. Score using the rubric in icp.md. Write a one-line `fit_reason` that names the evidence. Put every URL you used for that company into `sources`.
5. Log the query: `python3 scripts/leads.py log-search "<query>" --found <n>`.

Run independent WebFetch calls in parallel to save time. Give up on a candidate after two failed fetches.

## Saving

Write all qualifying leads to a temp JSON list (for example `/tmp/leads-batch.json`) and add them in one call:

```bash
python3 scripts/leads.py add --file /tmp/leads-batch.json
```

Each object: `company, website, industry, size, location, contact_name, contact_role, contact_email, contact_linkedin, fit_score, fit_reason, signals (list), sources (list), research (2 to 5 lines of notes)`. Leave contact fields empty when not public. The script dedupes and rejects leads without sources; report any it skipped.

## Report

Show a table sorted by score: `id | score | company | why | contact (or "-")`, then the queries run, then how many candidates were seen but not added and the main reason (too small, wrong industry, no evidence). Suggest `/review-leads` next.

## Rules

- Never guess emails or names. If the only contact you found is a generic `info@`, leave `contact_email` blank and mention the contact page URL in sources.
- No company without at least one source URL.
- Prefer quality over count: 6 well-evidenced leads beat 10 thin ones. Say so if you stopped early.
- Respect the guidance in `$ARGUMENTS` as a hard filter.
