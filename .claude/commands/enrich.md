---
description: Deeper research on one lead or all approved leads; update contacts, signals and score
argument-hint: <lead-id> | approved | "<company name>"
---

Enrich leads with deeper research. `$ARGUMENTS` is a lead id, the word `approved` (all leads in stage `approved`), or a company name to look up with `python3 scripts/leads.py list`.

## For each lead

1. `python3 scripts/leads.py get <id>` to see what is already known and which sources were used. Do not re-fetch those URLs unless they are the homepage.
2. Research, in parallel where possible (WebSearch and WebFetch only, public pages):
   - **People**: `"<company>" founder OR CEO OR "head of" <buyer title from icp.md>`, the company's team/about page, and `site:linkedin.com/in "<company>" <title>` (use only what the search snippet shows: name, title, public profile URL).
   - **Recent news**: `"<company>" funding OR raised OR launches OR partnership` from the last 12 months.
   - **Tech and tools**: careers page, job posts (`"<company>" jobs <relevant role>`), integrations page, anything that reveals the stack or the process your product replaces.
   - **The pain**: blog posts, reviews, community threads where the company or its staff describe the problem your product solves.
   - **Size and location**: confirm from the about page, job posts or press. Keep ranges.
3. Decide what changed. Re-score with the rubric in `data/<product>/icp.md` if the evidence moved; explain in `fit_reason`.
4. Save:
   ```bash
   python3 scripts/leads.py update <id> --set contact_name="..." --set contact_role="..." --set contact_linkedin="..." --set fit_score=NN --set fit_reason="..." --set signals="<old>; <new>" --set sources="<old>; <new url>; ..." --note "enriched: <2-line summary of what was found and what it changed>"
   ```
   Only pass `--set` for fields that actually changed. Always append, never replace, `sources` and `signals` (read the old values from `get`).
5. Write the longer findings (3 to 10 lines, with URLs) as one `--note`, or append a `## Enrichment <date>` section to `data/<product>/notes/<id>.md` if there is a lot.

## Report

A table: `id | score before → after | new contact? | key new signal`. Then suggest `/draft-outreach <id>` for the strongest ones.

## Rules

- Budget: at most 6 fetches per lead; stop when nothing new turns up.
- Never guess emails. A public email on the team or contact page is fine; `info@` is not a contact.
- If a lead turns out not to fit (acquired, shut down, wrong industry), say so and suggest `/update <id> rejected "reason"`; do not change the stage yourself.
