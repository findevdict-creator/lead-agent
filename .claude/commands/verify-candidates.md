---
description: Research unverified candidates, score them properly and move them to new (or rejected)
argument-hint: [count, default 10] [segment or region filter]
---

Verify harvested candidates. `$ARGUMENTS`: how many to process (default 10) and an optional filter.

## Steps

1. `python3 scripts/leads.py list --stage candidate --json`, sort by `fit_score`, apply the filter, take the top N.
2. For each: WebFetch the homepage and, if linked, about/team/contact (max 3 fetches). Confirm what they do, size, location, evidence of the ICP pain, a named decision maker with a public role, a public email if printed. Run helpers in parallel when available.
3. Score with the rubric in `data/<product>/icp.md`. Then:
   - Score 40+: `python3 scripts/leads.py update <id> --stage new --set fit_score=NN --set fit_reason="..." --set sources="<old>; <new urls>" --set signals="<old>; <new>" [--set contact_name=... --set contact_role=... --set contact_email=... --set contact_linkedin=... --set size=... --set location=...] --note "verified: <2 lines>"`
   - Below 40, or a competitor, closed, or wrong fit: `python3 scripts/leads.py update <id> --stage rejected --note "verify: <reason>"`.
   - Site unreachable or blocked: leave as `candidate`, add `--note "verify: site blocked, check manually"`.
4. Report a table: `id | before → after | stage | contact found?`, then the next suggested command (`/review-leads` for the new ones, `/verify-candidates` again if candidates remain).

## Rules

- Same hard rules as always: sources for every fact, no guessed contacts, public pages only.
- Always append to `sources` and `signals`; read the old values first with `get`.
