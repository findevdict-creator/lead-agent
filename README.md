# Lead Agent

A lead-finding marketing agent that runs inside [Claude Code](https://claude.ai/code). No API keys: Claude Code does the research with its built-in web search, and your leads live in a plain CSV you can open in Google Sheets.

## Setup

```bash
git clone <this repo> lead-agent
cd lead-agent
claude
```

Requires Python 3.9+ (standard library only) and Claude Code.

## GUI

```bash
python3 scripts/gui.py          # opens http://127.0.0.1:8765
```

A local web app for running and reviewing the pipeline without the terminal. Standard library only, nothing to install, listens on your computer only.

| Page | What you can do |
|---|---|
| Dashboard | Counts per stage, what to do next, follow-ups due, best approved and best new leads |
| Leads | Search and filter (stage, score, tag, due), sort, save views, select many rows to move stage, tag, set follow-ups or export |
| Lead panel | Every field with source links, change stage in one click, tags, next action with snooze, notes timeline, edit fields, outreach drafts, ask the agent to enrich or find lookalikes |
| Pipeline board | Drag cards between stages |
| Review queue | Approve, reject or park leads one at a time with keys A, R, L, S. Rejection reasons can be added to the ICP's learned disqualifiers. A second queue triages unverified candidates |
| Follow-ups | Overdue, today, next 14 days, and active leads with no date; snooze or mark done; download a calendar (.ics) |
| Outreach | Fill a template for a lead, edit it, save it as a draft, copy it or open it in your email app. Nothing is sent |
| Analytics | Funnel with conversion per stage, reply and win rate, score spread, leads per week, top sources, locations, industries and tags |
| Run agent | Start `/find-leads`, `/harvest`, `/verify-candidates`, `/enrich`, `/more-like`, `/draft-outreach`, `/digest`, `/build-icp`, `/setup-product` or a free-form request, and watch the log live |
| Product & data | Switch or create products, edit `product.md` and `icp.md`, import a CSV, merge duplicates, export, view the search log |

For a step-by-step guide to the whole workflow in the GUI, see the [operations manual](docs/OPERATIONS_MANUAL.md).

Run agent uses your local Claude Code CLI (`claude -p`) and your Claude Code login, so there are still no API keys. Run logs are saved to `data/<product>/runs/`. If `claude` is not on your PATH, set `LEAD_AGENT_CLAUDE=/path/to/claude`; every other page works without it.

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

The helper `scripts/leads.py` is the only thing that writes `leads.csv` (the GUI calls it too). Try `python3 scripts/leads.py --help`. Tests: `python3 -m unittest scripts/test_leads.py scripts/test_gui.py`.

Helper commands added for the GUI, also usable from the terminal:

| Command | What it does |
|---|---|
| `list --q text --min-score 70 --tag dach --due` | Filter the list; `--stage` takes several stages separated by commas |
| `bulk-update <id> <id> --stage approved --add-tag q4` | Change many leads at once |
| `tag <id> <tag>` / `tag <id> <tag> --remove` | Tags, stored in a new `tags` column |
| `due [--days 7]` | Overdue, due today, due soon, and active leads without a date |
| `analytics [--json]` | Funnel, conversion, reply and win rate, score spread, sources, contactability |
| `import file.csv [--stage candidate] [--source URL] [--tag T] [--dry-run]` | Import a list; common headers are mapped automatically and dedupe applies |
| `dupes` / `merge <keep> <dup>` | Find and fold together likely duplicates |
| `export --format csv\|hubspot\|pipedrive\|json\|ics` | Exports for Google Sheets, HubSpot, Pipedrive, or a follow-up calendar |
| `templates` / `render <template> <id> [--save]` | Outreach templates from `templates/outreach/` (or `data/<product>/templates/` to override) |

Older `leads.csv` files without a `tags` column keep working; the column is added on the next write.

## Rules the agent follows

- Every fact has a source URL.
- Contact details are never guessed. Blank means not public.
- Public pages only. Nothing is ever sent on your behalf.
