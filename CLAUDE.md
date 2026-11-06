# Lead Agent

A marketing agent that runs inside Claude Code with **no API keys**. You (Claude Code) are the analyst, the search engine and the CRM. Use only built-in tools: WebSearch, WebFetch, Read, Write, Edit, Bash.

## Files

| Path | What it is |
|---|---|
| `data/product.md` | The user's product: what it does, pains it solves, pricing, proof, competitors |
| `data/icp.md` | Ideal customer profile: segments, buyer titles, signals, disqualifiers, search queries, scoring rubric, learned disqualifiers |
| `data/leads.csv` | Lead database. **Only write it through `scripts/leads.py`.** |
| `data/notes/<id>.md` | Research and activity log per lead (appended by `leads.py`) |
| `data/searches.log` | Queries already run (`date, found, query`). Check before searching. |
| `exports/` | CSV exports for Google Sheets |
| `outreach/<id>.md` | Draft messages (never sent) |
| `data/digests/<date>.md` | Weekly digests from `/digest` |

Commands live in `.claude/commands/`. Run tests with `python3 -m unittest scripts/test_leads.py`.

## Lead schema

Columns: `id, company, website, industry, size, location, contact_name, contact_role, contact_email, contact_linkedin, fit_score, fit_reason, signals, sources, stage, next_action, next_action_date, added_on, updated_on, notes`.

Stages: `new → approved → contacted → replied → meeting → won`. Side exits: `rejected`, `lost`, `not_now`.

Add leads with JSON, one object or a list:

```bash
python3 scripts/leads.py add '{"company":"Acme","website":"https://acme.com","industry":"...","size":"50-200","location":"...","contact_name":"","contact_role":"","contact_email":"","contact_linkedin":"","fit_score":78,"fit_reason":"one line","signals":["hiring SDRs"],"sources":["https://..."],"research":"longer notes, optional"}'
```

For several leads write them to a temp JSON file and use `--file`. `leads.py` dedupes by website domain and id, and rejects leads with no sources.

## Hard rules

1. **Every fact needs a source URL.** Put the URL in `sources`. If you can't cite it, leave the field blank.
2. **Never guess contact details.** No pattern-guessed emails (`first.last@`), no invented names. Blank is correct when it isn't public.
3. **Public pages only.** No logins, no scraping behind authentication, no LinkedIn content beyond what appears in search snippets or public profile URLs.
4. **Never send anything.** Outreach is drafted to `outreach/`, the user sends it.
5. **Never edit `leads.csv` by hand.** Use `scripts/leads.py` so the file stays valid and deduplicated.
6. **Don't repeat searches.** Read `data/searches.log` and `python3 scripts/leads.py domains` before researching; log every query with `leads.py log-search`.
7. **Be honest about confidence.** If a fit score rests on thin evidence, say so in `fit_reason`.
8. Paid enrichment services are off by default. Don't suggest adding keys unless the user asks.

## Scoring

Use the rubric in `data/icp.md` (total 100): industry/use-case match 30, size in range 20, evidence of the problem 25, buying signal 15, reachable decision maker 10. Scores below 40 usually aren't worth adding; mention them in the summary instead.

## Style

Keep replies short and in tables where possible. After any command that changes data, show what changed and the next suggested command.
