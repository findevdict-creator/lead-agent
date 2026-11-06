---
description: Move a lead to a new stage and log a note
argument-hint: <lead-id> <stage> ["note"] [next action] [YYYY-MM-DD]
---

Update one lead from `$ARGUMENTS`.

Parse: first token is the lead id (if the user gave a company name instead, find the id with `python3 scripts/leads.py list` and confirm the match in one line). Second token is the stage, one of `new, approved, contacted, replied, meeting, won, rejected, lost, not_now`. Anything in quotes is the note. A date-like token `YYYY-MM-DD` is the next action date; remaining words are the next action text. Relative dates such as "next week" or "in 3 days" are converted to a real date.

Run:

```bash
python3 scripts/leads.py update <id> --stage <stage> --note "<note>" --next-action "<text>" --next-date <date>
```

Omit flags the user did not give. If the stage is `contacted` and no next action was given, set `--next-action "Follow up"` and a date 4 days out, and say that you did.

Confirm in one line what changed, and show `python3 scripts/leads.py get <id>` only if the user asks.

To change other fields (for example a newly found contact), use `--set contact_name="Jane Doe" --set contact_role="CTO"` and add the source URL with `--set sources="<existing sources>; <new url>"` (read the current value first with `get`).
