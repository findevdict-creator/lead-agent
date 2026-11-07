# Lead Agent: Implementation Plan

A marketing agent that runs **inside Claude Code**. You give it your product site and a description. It works out who your ideal customer is, finds matching leads on the web with source links, lets you review them, and tracks them through a simple pipeline.

**No API keys.** Claude Code itself is the brain and the search engine. Everything uses Claude Code's built-in tools (WebSearch, WebFetch, Read, Write, Edit, and Bash for a small stdlib Python helper). All data lives in plain files in the repo, so you can open them in any editor or paste them into Google Sheets.

---

## 1. How you use it

```
git clone <repo> && cd lead-agent && claude
> /setup-product https://yourproduct.com "One-line description of what it does"
> /build-icp
> /find-leads 15
> /review-leads
> /pipeline
> /update acme-corp contacted "Sent intro on LinkedIn"
> /export
```

Each command is a Markdown file in `.claude/commands/`. Claude Code reads it as instructions and does the work with its own tools.

---

## 2. Repo layout

```
lead-agent/
├── CLAUDE.md                  # Rules for Claude: data locations, schema, scoring rubric, honesty rules
├── README.md                  # Setup and usage for you
├── .claude/
│   ├── commands/
│   │   ├── setup-product.md   # Phase 1
│   │   ├── build-icp.md
│   │   ├── find-leads.md
│   │   ├── review-leads.md
│   │   ├── pipeline.md
│   │   ├── update.md
│   │   ├── export.md
│   │   ├── enrich.md          # Phase 2
│   │   ├── more-like.md
│   │   ├── draft-outreach.md
│   │   └── digest.md
│   └── settings.json          # Pre-allows WebSearch, WebFetch and the helper script (fewer prompts)
├── scripts/
│   └── leads.py               # Stdlib-only CSV helper: add, dedupe, list, update, stats, export
├── data/
│   ├── product.md             # What the product is, who it's for, pricing, proof points
│   ├── icp.md                 # Ideal customer profile + search queries + scoring rubric
│   ├── leads.csv              # The lead database (one row per company)
│   ├── searches.log           # Queries already run, so /find-leads doesn't repeat itself
│   └── notes/<lead-id>.md     # Free-form research and activity log per lead
├── outreach/<lead-id>.md      # Draft messages (Phase 2)
└── exports/leads-YYYY-MM-DD.csv
```

`data/` is in `.gitignore` by default so your leads aren't pushed to GitHub unless you choose to (open question below).

---

## 3. Data schema

### leads.csv

| Column | Example | Notes |
|---|---|---|
| `id` | `acme-corp` | Slug of the company name. Unique key. |
| `company` | Acme Corp | |
| `website` | https://acme.com | Normalised domain is used for dedupe. |
| `industry` | Logistics SaaS | |
| `size` | 50-200 | Employee range if found, else blank. |
| `location` | Berlin, DE | |
| `contact_name` | Jane Doe | Only if found on a public page. |
| `contact_role` | Head of Growth | |
| `contact_email` | jane@acme.com | Only if published publicly. Never guessed. |
| `contact_linkedin` | https://linkedin.com/in/... | Public URL if found. |
| `fit_score` | 82 | 0 to 100, from the ICP rubric. |
| `fit_reason` | "Hiring SDRs, uses HubSpot, 80 staff" | One line explaining the score. |
| `signals` | hiring; raised seed; new product | Buying signals, `;`-separated. |
| `sources` | https://...; https://... | Every URL a fact came from. Required. |
| `stage` | new | See stages below. |
| `next_action` | Follow up | |
| `next_action_date` | 2026-11-12 | |
| `added_on` | 2026-11-06 | |
| `updated_on` | 2026-11-06 | |
| `notes` | short text | Longer notes go in `data/notes/<id>.md`. |

### Stages

`new` → `approved` → `contacted` → `replied` → `meeting` → `won`
Side exits: `rejected` (from review), `lost`, `not_now` (revisit later).

### Fit score rubric (stored in icp.md, editable by you)

| Factor | Points |
|---|---|
| Industry / use-case match | 0 to 30 |
| Company size in range | 0 to 20 |
| Has the problem your product solves (evidence on their site/posts) | 0 to 25 |
| Buying signal (hiring, funding, launch, complaint about a competitor) | 0 to 15 |
| Reachable decision maker found | 0 to 10 |

---

## 4. Commands, step by step

### Phase 1 (MVP)

**`/setup-product <url> "<description>"`**
1. WebFetch the homepage, then pricing, about, customers/case studies pages if linked.
2. Write `data/product.md`: what it does, problems solved, features, pricing, existing customers, competitors mentioned, tone of voice.
3. Show you a short summary and ask you to correct anything wrong.

**`/build-icp`**
1. Read `product.md`. WebSearch for the product's competitors and their customer pages to see who buys this kind of thing.
2. Write `data/icp.md`: 1 to 3 customer segments, each with industry, size, geography, job titles of buyers, pains, buying signals, disqualifiers, and 10 to 20 ready-made search queries.
3. Include the scoring rubric. Ask you to confirm or edit.

**`/find-leads [count] [segment]`** (default 10)
1. Read `icp.md`, `searches.log` and existing leads (to skip duplicates).
2. Pick queries not yet run. Use patterns such as: directory/list pages ("top logistics SaaS startups Berlin"), job posts that reveal the pain ("hiring SDR" + industry), competitor customer pages, review sites, communities, funding news.
3. WebFetch promising company sites to confirm fit and find a public contact (team/about/contact pages).
4. Score each against the rubric, write a one-line reason, record every source URL.
5. Append via `python scripts/leads.py add` (dedupes by domain), stage `new`. Log queries used.
6. Print a ranked table of what was added.

**`/review-leads`**
1. Show `new` leads one batch at a time (highest score first) with reason and sources.
2. You reply e.g. `approve 1,3,4  reject 2 "too big"`. Claude updates stages and saves rejection reasons to notes.
3. Rejection reasons are summarised back into `icp.md` under "Learned disqualifiers" so future searches improve.

**`/pipeline`**
1. `python scripts/leads.py stats` and `list`: counts per stage, overdue next actions, top 10 approved leads not yet contacted.

**`/update <lead-id> <stage> ["note"] [next-action-date]`**
1. Updates the row, stamps `updated_on`, appends the note to `data/notes/<id>.md`.

**`/export [stage]`**
1. Writes `exports/leads-YYYY-MM-DD.csv` (optionally filtered) ready to import into Google Sheets or a CRM.

### Phase 2

**`/enrich <lead-id|all-approved>`**: deeper research per lead: recent news, tech stack hints, more decision makers, public emails. Writes to notes, updates score.

**`/more-like <lead-id>`**: finds lookalike companies of a lead you liked (or a won customer). Uses competitor lists, "alternatives to", same directories.

**`/draft-outreach <lead-id> [email|linkedin]`**: writes a personalised first message and 2 follow-ups in `outreach/<id>.md`, citing the specific signal found. Never sends anything.

**`/digest`**: weekly summary: new leads found, stage changes, overdue follow-ups, suggested next searches. Can be run on a schedule with Claude Code's `/loop` or a cron job if you want.

---

## 5. Rules in CLAUDE.md (guardrails)

- Every fact in a lead must have a source URL. No source, no fact.
- Never invent or guess emails, names or phone numbers. Leave blank if not public.
- Only use public pages. Do not log in to sites or scrape LinkedIn behind login.
- Never send messages. Drafts only.
- Always go through `scripts/leads.py` to write `leads.csv` so the file stays valid and deduped.
- Optional paid enrichment (Apollo, Hunter, etc.) is **off by default** and only added later if you ask.

---

## 6. Milestones

| # | Milestone | What you can test |
|---|---|---|
| M1 | Skeleton: CLAUDE.md, README, settings.json, `leads.py` with tests | `python scripts/leads.py add/list/stats` work on sample data |
| M2 | `/setup-product` + `/build-icp` | Run on your real site. Check product.md and icp.md are accurate. |
| M3 | `/find-leads` | Get 10 scored leads with working source links, no duplicates on a second run |
| M4 | `/review-leads`, `/pipeline`, `/update`, `/export` | Approve/reject, move a lead through stages, open the export in Google Sheets |
| M5 | Phase 2 commands | Enrich a lead, find lookalikes, get an outreach draft, see a digest |

Phase 1 (M1 to M4) is the first working version.

---

## 7. Open questions for M

1. **Where should the code live?** I can't create a GitHub repo myself. Create an empty one (for example `lead-agent`) and tell me the name, and I'll push to it. Or I can just give you the files here.
2. **What's your product URL and one-line description?** I'll use it to test M2 and M3 for real.
3. **Target markets:** any countries, company sizes or industries to focus on or avoid?
4. **Lead type:** companies with a decision maker (B2B), or individual people (B2C / creators)?
5. **Should leads data be committed to git** (private repo) or kept local only? Default: local only.
6. **CRM:** happy with CSV + Google Sheets export for now? A HubSpot or Notion sync could come later and would need a connection.

---

## M10: GUI and pipeline features

A local web GUI (`scripts/gui.py` + `gui/`), standard library only, bound to 127.0.0.1. It never writes `leads.csv` itself; every change goes through the functions in `scripts/leads.py`, so the CLI, slash commands and GUI stay in sync. POST requests need an `X-Lead-Agent` header and a localhost `Host`, so other websites in the browser can't change data.

Added to `leads.py`: `tags` column, filters (`--q`, `--min-score`, `--tag`, `--due`, several stages), `bulk-update`, `tag`, `due`, `analytics`, `import` (header aliases, dedupe, a required source), `dupes` and `merge`, outreach `templates` and `render`, saved views (`data/<product>/views.json`), learned disqualifiers written from the review queue, and exports in HubSpot, Pipedrive, JSON and iCalendar formats.

The Run page starts commands through `claude -p --output-format stream-json`, with `LEAD_AGENT_PRODUCT` set so a run keeps to the product it was started for even if the GUI switches product. Logs go to `data/<product>/runs/`.
