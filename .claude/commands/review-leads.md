---
description: Review new leads one batch at a time; approve or reject, and teach the ICP from rejections
argument-hint: [batch size, default 5]
---

Walk the user through leads in stage `new`. Batch size from `$ARGUMENTS`, default 5.

## Steps

1. `python3 scripts/leads.py list --stage new --json`. If empty, say so and suggest `/find-leads`.
2. Take the top N by `fit_score`. For each, show a numbered card:

   ```
   1. Acme Corp (acme-corp)  score 82
      Logistics SaaS, 50-200 staff, Berlin
      Why: hiring 3 SDRs, lists HubSpot in stack, blog post on lead quality
      Contact: Jane Doe, Head of Growth (linkedin.com/in/...)  or "none found"
      Sources: <url>, <url>
   ```

3. Ask the user to reply in this form (explain it once):
   `approve 1,3  reject 2 "too big"  later 4  skip 5`
   Words: `approve`, `reject` (with optional reason in quotes), `later` (stage `not_now`), `skip` (leave as new).
4. Apply each decision with `python3 scripts/leads.py update <id> --stage approved|rejected|not_now --note "<reason or 'approved in review'>"`.
5. **Learn from rejections.** If any rejection reason suggests a rule (too big, wrong country, wrong industry, agency not product company, etc.), append a bullet to `## Learned disqualifiers` in `data/<product>/icp.md` in the form `- <rule> (from <id>, <date>)`. Don't add duplicates. Tell the user what you learned.
6. Offer the next batch if more `new` leads remain, otherwise show `python3 scripts/leads.py stats` and suggest `/find-leads` or `/pipeline`.

## Rules

- Never change a stage without an explicit decision from the user.
- Keep the cards short; the user can run `python3 scripts/leads.py get <id>` for everything.
