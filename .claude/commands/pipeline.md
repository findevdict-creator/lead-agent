---
description: Show the pipeline: counts per stage, overdue follow-ups, top approved leads
argument-hint: [stage to list in full]
---

Show the state of the pipeline.

1. Run `python3 scripts/leads.py stats`.
2. If `$ARGUMENTS` names a stage, also run `python3 scripts/leads.py list --stage <stage>`.
3. Present:
   - a one-line funnel: `new 12 → approved 5 → contacted 3 → replied 1 → meeting 0 → won 0` (plus rejected / lost / not_now counts in a second line)
   - overdue next actions, oldest first, as `date | id | action`
   - the top approved-but-not-contacted leads
4. End with 2 or 3 concrete suggestions, picked from: review the `new` leads (`/review-leads`), find more (`/find-leads`), follow up on overdue items (`/update <id> ...`), export (`/export`).

Keep it under 25 lines. Numbers come from the script; do not estimate.
