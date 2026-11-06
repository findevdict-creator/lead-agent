---
description: Weekly digest: what was added, what moved, what is overdue, what to search next
argument-hint: [days, default 7]
---

Produce a digest for the last N days (`$ARGUMENTS`, default 7).

1. Run `python3 scripts/leads.py digest --days <N>` and `python3 scripts/leads.py searches`.
2. Read `data/<product>/icp.md`, in particular `## Search queries` and `## Learned disqualifiers`, and compare against the search log to see which queries and segments have not been tried yet, and which segments produced the highest-scoring leads (use `python3 scripts/leads.py list --json` and group by industry).
3. Write the digest to `data/<product>/digests/<today>.md` (create the folder if needed) and show it in the chat:

   ```markdown
   # Digest <today> (last N days)

   ## Numbers
   Funnel line from the script, plus: leads added, approved, contacted, replies, meetings, won.

   ## Needs action
   - Overdue follow-ups (date, id, action)
   - Due in the next 7 days
   - Contacted leads with no update (suggest a follow-up or `not_now`)
   - New leads waiting for review (count), if any: suggest `/review-leads`

   ## What worked
   Which segments / query types produced the best-scoring leads, in 2 to 4 bullets with numbers.

   ## Suggested next searches
   5 concrete queries not yet run, with the segment each targets. Suggest `/find-leads 10 <segment>` or `/more-like <id>` for the strongest approved or won lead.

   ## ICP notes
   Any learned disqualifiers added this week, and 1 to 2 suggestions to tighten `icp.md` if the rejection rate is high.
   ```

4. Keep the chat version under 30 lines; the file can be longer.

To run this automatically, the user can start Claude Code with `claude "/digest"` from a cron job or a scheduled task, or use `/loop` while a session is open. Mention this once if they ask about automation.
