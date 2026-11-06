# Lead Agent

A lead-finding marketing agent that runs inside [Claude Code](https://claude.ai/code). No API keys: Claude Code does the research with its built-in web search, and your leads live in a plain CSV you can open in Google Sheets.

## Setup

```bash
git clone <this repo> lead-agent
cd lead-agent
claude
```

Requires Python 3.9+ (standard library only) and Claude Code.

## Commands

| Command | What it does |
|---|---|
| `/setup-product <url> "<description>"` | Reads your site and writes `data/product.md` |
| `/build-icp` | Works out your ideal customer profile and search plan in `data/icp.md` |
| `/find-leads [count] [segment]` | Searches the web, scores leads, saves them with source links |
| `/review-leads` | Approve or reject new leads; rejections teach the ICP |
| `/pipeline` | Stage counts, overdue follow-ups, top approved leads |
| `/update <id> <stage> ["note"] [date]` | Move a lead and log a note |
| `/export [stage]` | CSV export to `exports/` for Google Sheets or a CRM |
| `/enrich <id>` or `/enrich approved` | Deeper research on a lead: people, news, stack, re-score |
| `/more-like <id>` | Find lookalike companies of a lead you liked |
| `/draft-outreach <id> [email\|linkedin]` | Personalised first message and follow-ups in `outreach/` (never sent) |
| `/harvest [count] [platform]` | Bulk-collect unverified candidates from directories, Reddit, Instagram, LinkedIn, news |
| `/verify-candidates [count]` | Research candidates, score them, move them to `new` or `rejected` |
| `/digest [days]` | Weekly summary: what moved, what's overdue, what to search next |

## Data

Each product gets its own folder `data/<product>/` (`/setup-product` creates it from the domain; `python3 scripts/leads.py product <name>` switches, `products` lists them). Everything in `data/` is ignored by git by default. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the schema, stages and scoring rubric.

The helper `scripts/leads.py` is the only thing that writes `leads.csv`. Try `python3 scripts/leads.py --help`. Tests: `python3 -m unittest scripts/test_leads.py`.

## Rules the agent follows

- Every fact has a source URL.
- Contact details are never guessed. Blank means not public.
- Public pages only. Nothing is ever sent on your behalf.
