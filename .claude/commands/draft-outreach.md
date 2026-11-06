---
description: Draft a personalised first message and two follow-ups for a lead (never sends)
argument-hint: <lead-id> [email|linkedin|both] [tone or extra instructions]
---

Draft outreach for the lead in `$ARGUMENTS`. First token is the id, optional second token is the channel (`email`, `linkedin` or `both`, default `both`), the rest is tone or instructions (for example "casual", "mention the Berlin meetup", "in German").

## Steps

1. Read `data/product.md` (for positioning, proof points and tone), `python3 scripts/leads.py get <id>`, and `data/notes/<id>.md`. If `outreach/<id>.md` already exists, read it and write a new version below it instead of overwriting.
2. Pick the **one specific hook** from the lead's signals or notes that makes this message about them, not about the product (a job post, a launch, a blog post, a tool they use, a complaint). Cite it by URL in the file so the user can check it.
3. Write `outreach/<id>.md`:

   ```markdown
   # Outreach: <Company> (<id>)

   To: <contact name, role>  (or "No named contact yet; address to the <buyer title> role")
   Hook: <the specific signal> (<source url>)
   Drafted: <date>   Channel: <channel>   Tone: <tone>

   ## Email 1 (first touch)
   Subject: <under 50 characters, no clickbait>

   <60 to 120 words. Line 1 is about them (the hook). Line 2 to 3: the problem and what the product does about it, in their words. One proof point if relevant. One low-friction ask (a question or a 15-minute call). Sign-off placeholder: [Your name].>

   ## Email 2 (follow-up, +4 days)
   <40 to 70 words. New angle or piece of value, not "just checking in".>

   ## Email 3 (break-up, +10 days)
   <30 to 50 words. Polite close, leave the door open.>

   ## LinkedIn connection note (if channel includes linkedin)
   <under 300 characters, no pitch, just the hook and a reason to connect.>

   ## LinkedIn message after connecting
   <under 80 words.>

   ## Why this angle
   Two lines on the reasoning, and what to personalise further by hand.
   ```

4. Log it: `python3 scripts/leads.py update <id> --note "outreach drafted (<channel>) in outreach/<id>.md" --next-action "Send first message" --next-date <tomorrow>` (do not change the stage; the user moves it to `contacted` when they actually send).
5. Show the first email in the chat and the file path. Remind the user to move the lead with `/update <id> contacted` once sent.

## Rules

- Never send anything and never pretend you can.
- No invented facts about the lead or about the product. If the only hook is weak, say so and suggest `/enrich <id>` first.
- No manipulative or fake-urgency language. Plain, specific, short.
- Match the product's tone from `product.md` unless the user gives a tone.
