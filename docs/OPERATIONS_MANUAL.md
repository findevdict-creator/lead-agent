# Lead Agent GUI: Operations Manual

This manual walks an operator through the full lead workflow in the Lead Agent web GUI, from first launch to a won deal. It covers every page, what each button changes on disk, and what to do when something goes wrong.

**Who it is for:** whoever runs lead generation day to day. You don't need to use the terminal after setup, but the CLI equivalents are listed where they help.

**Golden rule:** the GUI never sends anything. It finds, researches, organises and drafts. You send every message yourself.

---

## Contents

1. [The workflow at a glance](#1-the-workflow-at-a-glance)
2. [Setup and launch](#2-setup-and-launch)
3. [Finding your way around](#3-finding-your-way-around)
4. [Step 1: Define the product and ICP](#4-step-1-define-the-product-and-icp)
5. [Step 2: Get leads in](#5-step-2-get-leads-in)
6. [Step 3: Triage and verify candidates](#6-step-3-triage-and-verify-candidates)
7. [Step 4: Enrich leads](#7-step-4-enrich-leads)
8. [Step 5: Review researched leads](#8-step-5-review-researched-leads)
9. [Step 6: Move leads through the pipeline](#9-step-6-move-leads-through-the-pipeline)
10. [Step 7: Draft outreach](#10-step-7-draft-outreach)
11. [Step 8: Follow-ups](#11-step-8-follow-ups)
12. [Step 9: Analytics](#12-step-9-analytics)
13. [Step 10: Import, export and data hygiene](#13-step-10-import-export-and-data-hygiene)
14. [Daily and weekly routines](#14-daily-and-weekly-routines)
15. [Reference](#15-reference)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. The workflow at a glance

```
 Product & ICP ──► Get leads ──► Verify ──► Enrich ──► Review ──► Outreach ──► Follow up ──► Close
 (Product & data,   (Run agent,   (Review    (Lead      (Review    (Outreach    (Follow-ups,   (Board /
  /setup-product,    import,       queue:     panel,     queue:     page,        calendar)      lead panel)
  /build-icp)        add lead)     candidates) /enrich)   A/R/L/S)   drafts only)
```

Every lead sits in one **stage**. The main path is:

| Stage | Meaning | How a lead gets here |
|---|---|---|
| `candidate` | Harvested in bulk, **not researched**. Rough score, reason starts with `unverified:` | `/harvest`, CSV import (default), manual add |
| `new` | Researched and scored, waiting for your decision | `/find-leads`, `/more-like`, `/verify-candidates` |
| `approved` | You want to contact them | Review queue (A), board, lead panel |
| `contacted` | You sent the first message | You move it after sending |
| `replied` | They answered | You move it |
| `meeting` | A call or demo is booked | You move it |
| `won` | Customer | You move it |

Side exits: `rejected` (not a fit, or a merged duplicate), `lost` (talked, didn't buy), `not_now` (fit, but park it; the review queue's "Later").

> **Never treat a `candidate` as a qualified lead.** It has not been checked. Verify it first (section 6).

---

## 2. Setup and launch

### Requirements

| Need | Why |
|---|---|
| Python 3.9 or newer | Runs the GUI server and `scripts/leads.py`. Standard library only, nothing to `pip install` |
| A modern browser | Chrome, Edge, Firefox or Safari |
| Claude Code CLI (`claude`), signed in | Only for the **Run agent** page and the "Ask the agent" / "AI draft" buttons. Everything else works without it |

No API keys are used anywhere. Agent runs use your existing Claude Code login.

### First-time setup

```bash
git clone https://github.com/findevdict-creator/lead-agent.git
cd lead-agent
claude          # once, to make sure you're signed in to Claude Code; then exit
```

### Start the GUI

```bash
python3 scripts/gui.py
```

The terminal prints `Lead Agent GUI on http://127.0.0.1:8765  (product: <name>)` and your browser opens that address. Keep the terminal window open: closing it stops the GUI. Press **Ctrl+C** in the terminal to stop.

If the terminal also says `note: Claude Code CLI not found, so the Run page is disabled`, see [Troubleshooting](#16-troubleshooting).

### Launch options

| Option | Effect |
|---|---|
| `--port 9000` | Use another port (default 8765). Also settable with `LEAD_AGENT_PORT=9000` |
| `--no-browser` | Don't open a browser tab automatically |
| `--host <addr>` | Listen on another address. **Leave this alone.** The default `127.0.0.1` means only your computer can reach it; anything else exposes your lead data |

| Environment variable | Effect |
|---|---|
| `LEAD_AGENT_CLAUDE=/path/to/claude` | Use this Claude Code binary for agent runs, if `claude` isn't on your PATH |
| `LEAD_AGENT_GUI_DEBUG=1` | Print every HTTP request in the terminal (for debugging) |
| `LEAD_AGENT_ROOT=/path` | Use a different lead-agent folder as the data root |

### Safety built in

- The server only answers requests addressed to `localhost` / `127.0.0.1`, and every change needs a special header, so other websites open in your browser cannot read or change your leads.
- Only `product.md` and `icp.md` can be edited from the GUI. The Run page only runs the listed agent commands.
- All lead changes go through `scripts/leads.py`, so the CSV stays valid and deduplicated, and the GUI, the CLI and Claude Code slash commands all see the same data.

---

## 3. Finding your way around

### Layout

- **Sidebar (left):** the **Product** picker at the top, then the pages. Badges show:
  - **Review queue:** number of leads in `new` waiting for review.
  - **Follow-ups:** number of open leads whose next action date is today or earlier.
  - **Run agent:** number of agent runs in progress.
- **Main area:** the current page.
- **Lead panel (drawer):** opens on the right when you click any lead anywhere. Close it with ✕ or **Esc**.
- **Toasts:** short messages at the bottom confirm each change (green) or show an error (red, stays 6 seconds).

The sidebar badges refresh every 10 seconds, so new leads from a running agent appear without reloading.

### Pages

| Page | Use it to |
|---|---|
| Dashboard | See counts per stage and a "What to do next" list; start here every session |
| Leads | Search, filter, sort, bulk-edit and export the full list |
| Pipeline board | Drag leads between stages |
| Review queue | Approve or reject leads fast with the keyboard |
| Follow-ups | Work through due next actions; download a calendar |
| Outreach | Fill a template for a lead and save it as a draft |
| Analytics | Funnel, rates, score spread, sources |
| Run agent | Start agent commands and watch them work |
| Product & data | Products, `product.md`, `icp.md`, import, export, duplicates, search log |

### The Dashboard

Six tiles (each clickable): **Unverified candidates**, **To review**, **Approved**, **In conversation** (contacted + replied + meeting), **Won**, **Overdue**.

Below them:

- **What to do next:** the dashboard checks your data and lists the next jobs in priority order, with links: missing product description or ICP, overdue follow-ups, leads in conversation, leads waiting for review, approved leads without outreach, candidates to verify. "All caught up" means there is nothing urgent.
- **Due today and overdue:** up to 8 follow-ups with a **Done** button.
- **Best approved leads, not contacted** and **Top leads waiting for review:** the highest-scoring leads in each group. Click a name to open it.

---

## 4. Step 1: Define the product and ICP

Each product (for example `wattwisely`, `anchorstance`) has its own lead list, ICP, notes, templates and saved views under `data/<product>/`. Do this once per product.

### 4.1 Create or switch product

1. Open the **Product** picker in the sidebar.
2. Pick an existing product to switch to it, or pick **+ New product…** and type a short name.
   - A short name is best, for example the domain without its extension (`anchorstance` for anchorstance.com).
3. A toast confirms `Switched to <name>`. Every page now shows that product only.

> Switching product in the GUI also changes the active product for Claude Code in the terminal (it writes `data/.active`). If you also work in a terminal, check with `python3 scripts/leads.py product` before running commands there.

### 4.2 Write the product description (`product.md`)

**Recommended, agent does it:**

1. Make sure the right product is selected in the sidebar (for a new product, create it first with **+ New product…**). When run from the GUI, `/setup-product` writes into the selected product and never creates or switches products; the Run page reminds you which one that is.
2. Go to **Run agent**.
3. In **/setup-product**, type the URL and a one-line description in quotes, for example:
   `https://anchorstance.com "Posture coaching app for golf instructors"`
4. Click **Run** and watch the log. The agent reads your site and a few outside sources and writes `data/<product>/product.md` (what it does, pains, features, pricing, proof, competitors).
5. Check the result in **Product & data → Product description**. Fix anything wrong and click **Save**.

**Manual:** go to **Product & data**, type into **Product description `product.md`**, click **Save**. Start the file with `# Product name` so the GUI can show the name in headers and templates.

### 4.3 Build the ideal customer profile (`icp.md`)

1. In **Run agent**, find **/build-icp**. Optionally add guidance such as `focus on Germany` or `SMBs only`.
2. Click **Run**. The agent writes segments, buyer titles, buying signals, disqualifiers, search queries and the scoring rubric to `data/<product>/icp.md`.
3. Review it in **Product & data → Ideal customer profile**. Edit and **Save**.

The ICP drives everything downstream: which searches run and how leads are scored (out of 100: industry/use-case 30, size 20, evidence of the problem 25, buying signal 15, reachable decision maker 10). Spend time here; a sharp ICP saves hours of rejecting bad leads.

The ICP also has a **Learned disqualifiers** section. The review queue adds to it when you reject leads with a reason (section 8), so the agent stops bringing back the same kind of miss.

---

## 5. Step 2: Get leads in

There are five ways in. The first four use the agent from the **Run agent** page; the last is manual.

| Way | Best for | Lands in stage |
|---|---|---|
| `/find-leads` | A small batch of fully researched, scored leads | `new` |
| `/harvest` | Volume: many unverified names from directories, lists, Reddit, Instagram, LinkedIn snippets, news | `candidate` |
| `/more-like <id>` | Lookalikes of a lead or customer you like | `new` |
| Ask the agent anything | A specific request in plain words | depends on request |
| CSV import / Add lead | Lists you already have, leads you found yourself | your choice (import defaults to `candidate`, Add lead to `new`) |

### 5.1 Using the Run agent page

The left card lists the commands. Each has a short description and an argument box with a hint of what to type.

1. Type arguments in the box (or leave it empty for defaults).
2. Click **Run**. The page switches to the run's log on the right.
3. The log shows what the agent does as it happens: `→ WebSearch: …`, `→ WebFetch: …`, `→ Bash: python3 scripts/leads.py add …`, and its messages. It ends with `✓ finished` or `✗ finished with an error`, followed by the agent's summary.
4. Leads appear in your list while the run is going. Badges update within 10 seconds.
5. **Stop** cancels a running job. Leads already saved stay saved.

The **Runs** list shows every run since the GUI started, with status (`running`, `done`, `failed`, `cancelled`) and cost if Claude Code reports one. Click a run to see its log. Runs are not kept in the list after you restart the GUI, but every log is saved to `data/<product>/runs/<date>-<command>-<id>.log`.

You can start several runs at once, and you can keep using other pages while they run.

### 5.2 Find researched leads: `/find-leads`

Arguments: `[count, default 10] [segment name or extra guidance]`

Examples:
- `10`
- `15 golf academies in the UK`
- `10 segment: solar installers, hiring sales staff`

The agent checks the search log first so it never repeats a query, searches the web, scores each company with the ICP rubric and saves it with source links. Scores under 40 are usually left out and mentioned in the summary.

### 5.3 Harvest candidates in bulk: `/harvest`

Arguments: `[target count, default 100] [platform or segment: reddit|instagram|linkedin|directories|news|<segment>]`

Examples: `100`, `200 directories`, `50 reddit`.

Harvested leads are only name, website, location, a one-line snippet and the source URL, with a rough score whose reason begins `unverified:`. They go to `candidate` and are hidden from the Leads table by default. Next step: section 6.

### 5.4 Lookalikes: `/more-like`

From any lead panel, click **Find lookalikes**, or on Run agent type `<lead-id> [count, default 8]`. Use it on your best `approved`, `meeting` or `won` leads.

### 5.5 Ask the agent anything

The last box on Run agent takes a free-form request, for example `find 10 more Sportsbox-certified coaches in the UK`. Click **Ask**. The same rules apply: sources for every fact, no guessed contacts.

### 5.6 Import a CSV

Go to **Product & data → Import a CSV**.

1. **Choose file:** a `.csv` file. Headers are matched automatically, case-insensitive. Common names work: Company / Organization / Account / Name, Website / URL / Domain, Email, Title / Job title / Role, LinkedIn, Location / City / Country, Industry, Employees / Size, Source, Tags, Notes, Stage / Status, Next action, Follow-up date. At least one column must map to **company**.
2. **Import as stage:** default `candidate` (recommended for lists you haven't checked). Choose `new` only if the list is already researched. A `stage` column in the file wins over this, if its values are valid stages.
3. **Tag every row:** optional, for example `trade-show-2026`. Handy for filtering and analytics later.
4. **Source for rows without one:** every lead needs a source. If the file has no source column, type a URL or a description such as `Event attendee list, Nov 2026`. Rows without any source are skipped.
5. Click **Preview**. Check the column mapping (`Header → column`), the row count and the first company names. A red line warns if some rows have no source.
6. Click **Import**. The result reads, for example, `120 added, 14 skipped of 134. 12 × duplicate domain; 2 × missing company`.

Duplicates are skipped by website domain and id. Several different named people at the same organisation are all kept; the same person twice is skipped.

### 5.7 Add a lead by hand

**Leads → + Add lead** opens a form. **Company** and **sources** (one or more URLs separated by `;`) are required. Stage defaults to `new`. Put longer research in **research notes**; it goes into the lead's notes file. After saving, the lead panel opens.

---

## 6. Step 3: Triage and verify candidates

Candidates are cheap to collect and unreliable. Process them in two passes.

### 6.1 Quick triage (optional, by hand)

1. **Review queue → Unverified candidates** (button at the top right).
2. Candidates appear one at a time, best score first, with the snippet, signals and source links.
3. Use the keys:

| Key | Button | Effect on a candidate |
|---|---|---|
| **A** | Keep for verification | Adds tag `verify-next`, stays `candidate` |
| **R** | Reject | Moves to `rejected` |
| **L** | Later | Moves to `not_now` |
| **S** | Skip | Leaves it untouched for this session |

Type a **Reason** before R if you like; it is saved to the lead's notes. Tick **also add this reason to the ICP's learned disqualifiers** to teach the ICP (see section 8).

### 6.2 Verify with the agent

- **In bulk:** Dashboard → "Verify the next batch", or Run agent → **/verify-candidates** with `[count] [filter]`, for example `20`, `20 Germany`, or `20 tagged verify-next` (the filter is read as free text by the agent).
- **One lead:** open the candidate's panel and click **Verify this candidate**.

For each candidate the agent opens the homepage and about/team/contact pages (up to 3), confirms what the company does, its size and location, evidence of the problem, a named decision maker and any public email, then re-scores it:

| Result | What happens |
|---|---|
| Score 40 or more | Moves to `new` with a full `fit_reason`, new sources and signals |
| Below 40, competitor, closed, wrong fit | Moves to `rejected` with a `verify:` note |
| Site blocked or unreachable | Stays `candidate`, note "site blocked, check manually" |

Verified leads now show up in **Review queue → Researched leads**.

---

## 7. Step 4: Enrich leads

Enrichment is deeper research on a lead you're interested in: people and roles, recent news, tech stack, and a re-score. Do it on high-scoring `new` leads before review, or on `approved` leads before outreach.

- **One lead:** lead panel → **Enrich (people, news, re-score)**.
- **All approved leads:** Run agent → **/enrich** with argument `approved`.

The agent only uses public pages and never guesses contact details. A blank email means no public email was found, which is correct; don't fill it with a pattern guess.

---

## 8. Step 5: Review researched leads

This is where you decide who is worth contacting.

1. Open **Review queue** (badge shows how many are waiting). It opens on **Researched leads** (`new`), best score first.
2. Each card shows score, company, website, industry · size · location, **Why** (fit reason), **Signals**, **Contact** and **Sources**. Click source links to check the evidence. **Open full record** opens the lead panel with notes and research.
3. Decide with a key or button:

| Key | Button | Effect |
|---|---|---|
| **A** | Approve | Moves to `approved` |
| **R** | Reject | Moves to `rejected` |
| **L** | Later | Moves to `not_now` |
| **S** | Skip | Leaves it in `new`, moves on (comes back next visit) |

4. **Reason (optional):** type it before pressing a key; it's logged on the lead. Keys don't fire while the cursor is in the reason box, so click outside it (or press Tab) first, or use the buttons.
5. **Teach the ICP:** when rejecting, tick **also add this reason to the ICP's learned disqualifiers**. The reason is appended to `## Learned disqualifiers` in `icp.md` with the lead id and date (if the same rule isn't already there). Future `/find-leads`, `/harvest` and `/verify-candidates` runs read it and skip that kind of lead. Write reasons as general rules: `agency, not a product company`, `over 500 employees`, `outside EU`.
6. When the queue is empty it offers links to find more leads or triage candidates.

Tips:
- Clear the queue regularly; a short queue gets reviewed properly.
- Reject freely with a reason. That is how the agent gets better.
- Use **Later** for good fits with bad timing (just raised, hiring freeze); they're easy to find again with the `not_now` stage filter.

---

## 9. Step 6: Move leads through the pipeline

There are three ways to change a lead's stage. All of them log a note on the lead and set its `updated_on` date.

### 9.1 Lead panel

Click any lead to open its panel:

- **Header:** score, stage, id, added and updated dates, company, website, industry · size · location. Candidates show a yellow "Unverified candidate" warning.
- **Stage buttons:** one per stage; the current one is highlighted. Click another to move the lead.
- **Why, Signals, Contact, Sources, Tags:** the facts, each with its source. Add a tag by typing in **add tag** and pressing Enter; remove one with its ✕.
- **Next action:** a short text (`Send first email`) and a date. **Save** stores both. **Snooze** moves the date to +1 day, +3 days, +1 week or +1 month from today. **Clear** removes both.
- **Add a note:** free text, saved with today's date in the lead's notes file. **Activity and research** below shows the whole history: research, stage changes, notes, drafts.
- **Outreach:** saved drafts for this lead; **Draft from template** and **AI draft**.
- **Ask the agent:** **Verify this candidate** (candidates only), **Enrich**, **Find lookalikes**.
- **Edit fields:** fix company details, contact fields, score, fit reason, signals, sources and the notes column. **Save changes** logs "edited in GUI". Sources can't be emptied: every lead needs at least one source URL. Never type a guessed email.

### 9.2 Pipeline board

**Pipeline board** shows columns `new`, `approved`, `contacted`, `replied`, `meeting`, `won`, `lost`, `not_now` (tick **show unverified candidates** to add a `candidate` column).

- **Drag** a card to another column to change its stage.
- **Click** a card to open its panel.
- Each column shows the 40 highest-scoring leads; a "+N more" link opens the rest in the Leads table.
- **Filter cards…** narrows all columns by any text.
- Overdue next-action dates show in red on the card.

### 9.3 Bulk changes on the Leads page

1. On **Leads**, tick the checkbox on each row you want (the header checkbox selects every row on the current page).
2. A bar appears: **N selected**, with:
   - **Move to stage…** moves them all.
   - **tag** box with **+ Tag** / **− Tag**.
   - A date with **Set follow-up** (sets next action "Follow up" on that date).
   - **Export** downloads just the selected rows as CSV.
   - **Clear selection.**

Selections survive paging and filtering, so you can build a selection across several searches.

### 9.4 The Leads table in detail

- **Search box:** matches every column (company, contact, reason, signals, notes, tags, …). Several words must all match.
- **Stage:** one stage, or **active pipeline** (approved, contacted, replied, meeting).
- **hide candidates:** on by default. Unticked, or with stage `candidate` chosen, candidates show with an "unverified" label.
- **min score**, **Any tag**, **due now** (next action date today or earlier, on open leads).
- **Clear** resets the filters.
- **Saved views:** **Save view** stores the current filters under a name (per product, in `data/<product>/views.json`). Pick it later from **Saved views…**. Saving with an existing name replaces that view. To remove one, pick it in **Saved views…** and click **Delete view** (it asks you to confirm). Changing any filter deselects the view, so it's clear the table no longer matches it.
- Click a column header to sort; click again to reverse. 100 rows per page.
- **Export these (CSV)** downloads the rows matching the current filters.

Filters and sort are remembered in your browser between sessions.

### 9.5 When to move a lead

| Event | Move to | Also do |
|---|---|---|
| You approve after review | `approved` | Draft outreach (section 10) |
| You sent the first message | `contacted` | Set next action "Follow up" in 3 to 5 days |
| They replied | `replied` | Note what they said; set the next step |
| Call or demo booked | `meeting` | Next action = the meeting date |
| They bought | `won` | Run **Find lookalikes** on them |
| They said no after talking | `lost` | Note why |
| Good fit, wrong time | `not_now` | Set a next action months out if you want a reminder |

The GUI does not move a lead to `contacted` for you when you save a draft, because only you know whether you sent it.

---

## 10. Step 7: Draft outreach

### 10.1 From a template

1. Open **Outreach** (or **Draft from template** in a lead panel, which pre-selects that lead and fills the template straight away).
2. **1. Pick a lead and a template**
   - **Lead:** lists `approved`, `new`, `contacted`, `replied` and `meeting` leads, best score first.
   - **Template:** built-in templates are `cold-email`, `follow-up`, `linkedin` and `partnership`.
   - Click **Fill template**.
3. **2. Edit and save the draft**
   - The filled text appears on the right. Fields with no data appear as `[field]`, and a yellow box lists them ("Fill these by hand"). Square-bracket notes from the template (like `[One line, in their words, on the problem…]`) are also for you to replace.
   - Edit the text until it reads like you wrote it.
   - **Save draft to lead:** appends the draft to `outreach/<product>/<id>.md`, logs "outreach drafted" on the lead and, if the lead has no next action, sets it to "Send first message" for tomorrow. The stage doesn't change.
   - **Copy:** copies the text to your clipboard.
   - **Open in email app:** opens your mail app with the contact's email, the `Subject:` line and the body filled in. You review and send it from there.
4. After you send it, move the lead to `contacted` and set a follow-up date.

**Template fields:** `{{greeting}}` ("Hi Anna," or "Hello,"), `{{first_name}}`, `{{company}}`, `{{hook}}` (first signal), `{{signals}}`, `{{fit_reason}}`, `{{source}}` (first source URL), `{{industry}}`, `{{location}}`, `{{contact_role}}`, `{{product}}` (from `product.md`'s title), `{{sender}}` (always `[Your name]`; replace it, or save a product template with your name typed in). Also available: `{{website}}`, `{{size}}`, `{{contact_name}}`, `{{contact_email}}`, `{{contact_linkedin}}`.

**Your own templates:** edit the **Template text** box, click **Save as product template** and give it a name. It is saved to `data/<product>/templates/<name>.md` and used only for that product. Saving with the same name as a built-in template overrides it for this product. **Delete product template** removes a product template (built-in ones can't be deleted, and deleting an override brings the built-in back).

### 10.2 AI draft

**AI draft (/draft-outreach)** on the Outreach page or in a lead panel runs the agent, which reads the lead's research and sources and writes a personalised first message plus two follow-ups to `outreach/<product>/<id>.md`. Arguments on Run agent: `<lead-id> [email|linkedin|both] [tone or extra instructions]`. Read the draft in the lead panel's **Outreach** card before using it.

---

## 11. Step 8: Follow-ups

Every open lead can carry a **next action** and a **next action date**. The **Follow-ups** page groups them:

| Box | Contains |
|---|---|
| **Overdue** | Date before today |
| **Due today** | Date is today |
| **Next 14 days** | Date in the next two weeks |
| **Active, no follow-up date** | `approved`, `contacted`, `replied` or `meeting` leads with no date (top 30 by score). These are leads that can slip through the cracks: give each a date |

Candidates and closed leads (`won`, `lost`, `rejected`) are left out.

For each item:
- Click the company to open the lead panel.
- **+3d / +1w** snoozes: moves the date to 3 or 7 days from today, keeping the action text.
- **Done** logs `done: <old action>` on the lead and asks for the next step. Type the next action (or leave it empty for none), then its date (defaults to 4 days ahead).

**Calendar:** **Download calendar (.ics)** gives one all-day event per open lead with a next action date, titled `<action>: <company> (<contact>)`. Import it into Google Calendar, Outlook or Apple Calendar. It's a snapshot, so download it again after changes. Each event's id is built from the lead and the date, so re-importing doesn't duplicate unchanged follow-ups, but a snoozed lead shows up as a new event and the old one stays until you delete it. For a clean calendar, import into a dedicated calendar you can clear and re-import.

---

## 12. Step 9: Analytics

**Analytics** shows numbers for the active product.

| Tile | Definition |
|---|---|
| Researched leads | All leads except candidates |
| Average fit score | Mean score of researched leads |
| Reply rate | (replied + meeting + won) ÷ (contacted + replied + meeting + won + lost) |
| Win rate | won ÷ (won + lost); "–" until something is closed |
| Researched with an email | Share of researched leads with a public email |
| Researched with a named contact | Share with a named person |

Cards:
- **Funnel:** how many leads reached each stage, and the percent of the stage before. Side exits count as far as they got: `rejected` and `not_now` count as reaching `new`, `lost` as reaching `contacted`.
- **Leads added per week:** last 12 weeks, by the Monday of each week.
- **Fit score spread:** researched leads and candidates in buckets 0–39, 40–59, 60–69, 70–79, 80–100.
- **Where leads come from:** top source websites. Shows which directories or searches pay off.
- **Locations, Industries, Tags:** top values.

How to use it:
- Low reply rate: look at the outreach templates and the signals you lead with.
- Many leads at 40–59 and few at 70+: tighten the ICP or change search queries.
- One source site dominating good leads: harvest more from it.
- Low share with a named contact: run `/enrich approved` before outreach.

---

## 13. Step 10: Import, export and data hygiene

All on **Product & data** unless noted.

### 13.1 Export

1. Optional filters: stage (or **researched only (no candidates)**), min score, tag.
2. Click a format. The file downloads through your browser, named `<product>-leads-<date>[-format].<ext>`.

| Format | Use |
|---|---|
| All columns (CSV) | Google Sheets (File → Import) or Excel; full backup of the list |
| HubSpot import (CSV) | HubSpot's contact import, with HubSpot column names, lead status and lifecycle stage |
| Pipedrive import (CSV) | Pipedrive's import, with person, organisation and deal title columns |
| JSON | Other tools and scripts |
| Follow-up calendar (.ics) | Same as the Follow-ups page download |

You can also export from **Leads** (**Export these (CSV)** for the current filters, or **Export** in the bulk bar for selected rows).

On the Leads page, **Export these (CSV)** always matches what the table shows: search, stage, "hide candidates", min score, tag and "due now" all apply, however many rows there are.

### 13.2 Duplicates

**Likely duplicates** lists groups that look like the same organisation or person: same company name (ignoring legal suffixes like GmbH or Ltd) with the same contact, same email, or same LinkedIn URL.

For a pair, **Merge into first** (after a confirm): keeps the first lead, fills its blank fields from the second, combines sources, signals and tags, keeps the higher score, copies the notes across, and moves the second lead to `rejected` with tag `duplicate`. Open each lead first if you're unsure which to keep. Groups of three or more are merged from the CLI: `python3 scripts/leads.py merge <keep-id> <dup-id>`.

### 13.3 Search log

**Search log** shows every query the agent has run for this product (`date, results found, query`). The agent skips queries already in it. Read it when planning new segments.

### 13.4 Editing `product.md` and `icp.md`

Both are plain Markdown text boxes. Click **Save** under each. Changes take effect on the next agent run.

---

## 14. Daily and weekly routines

### Daily (15 to 30 minutes)

1. **Dashboard:** read "What to do next".
2. **Follow-ups:** clear **Overdue** and **Due today**. Send the messages yourself, then **Done** with the next step, or snooze.
3. **Leads replied or with a meeting:** update their stage and next action.
4. **Review queue:** clear the researched leads (A/R/L/S), with reasons for rejects.
5. **Outreach:** draft and send messages for the best approved leads; move each to `contacted` with a follow-up date.
6. **Run agent:** start a `/find-leads 10` or `/verify-candidates 20` to refill the queue for tomorrow.

### Weekly

1. **Run agent → /digest** (`7` days): summary of what was added, what moved, what's overdue and what to search next. Saved to `data/<product>/digests/<date>.md`.
2. **Analytics:** check reply rate, the funnel and score spread.
3. **Product & data:** merge duplicates; read the search log; tune `icp.md`, especially Learned disqualifiers.
4. **Follow-ups → Active, no follow-up date:** give every lead a date.
5. **/enrich approved** before the week's outreach.
6. **Export** a CSV backup, or to your CRM.
7. **/harvest** a new source or segment if the candidate pool is low.

---

## 15. Reference

### Keyboard shortcuts

| Where | Key | Action |
|---|---|---|
| Review queue (researched) | A / R / L / S | Approve / Reject / Later / Skip |
| Review queue (candidates) | A / R / L / S | Keep for verification / Reject / Later / Skip |
| Anywhere with the lead panel open | Esc | Close the panel |
| Lead panel, add tag box | Enter | Add the tag |

Review keys are ignored while the cursor is in a text box or the lead panel is open.

### What each action writes

| Action | Files changed |
|---|---|
| Any stage, field, tag or next-action change | `data/<product>/leads.csv` (through `leads.py`) and a dated line in `data/<product>/notes/<id>.md` |
| Add a note | `data/<product>/notes/<id>.md` |
| Save draft | `outreach/<product>/<id>.md` (appended), plus a note and maybe a next action on the lead |
| Save product template | `data/<product>/templates/<name>.md` |
| Save view | `data/<product>/views.json` |
| Reject with "teach ICP" | `## Learned disqualifiers` in `data/<product>/icp.md` |
| Save product.md / icp.md | `data/<product>/product.md` / `icp.md` |
| Switch or create product | `data/.active`, and a new `data/<name>/` folder |
| Agent run | Whatever the command writes (leads, notes, outreach, digests), plus `data/<product>/runs/<date>-<command>-<id>.log` |
| Export | Nothing on disk; a browser download |

`data/`, `exports/` and `outreach/` are ignored by git, so your leads never get committed.

### CLI equivalents

Everything the GUI does can be done in a terminal with `python3 scripts/leads.py` (`--help` lists all commands): `list`, `get`, `update`, `bulk-update`, `tag`, `due`, `analytics`, `import`, `dupes`, `merge`, `templates`, `render`, `views`, `export --format csv|hubspot|pipedrive|json|ics`, `product`, `products`. The agent commands (`/find-leads`, `/harvest`, …) also run as slash commands inside `claude`.

### Agent rules (what to expect from every run)

1. Every fact has a source URL, or the field is left blank.
2. Contact details are never guessed: no pattern emails, no invented names.
3. Public pages only: no logins, nothing behind authentication, LinkedIn only as far as search snippets and public profile URLs.
4. Nothing is ever sent.
5. Searches are never repeated (search log).
6. Thin evidence is called out in `fit_reason`.

---

## 16. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Browser didn't open | `--no-browser`, or no default browser | Open http://127.0.0.1:8765 yourself |
| `Address already in use` on start | The GUI is already running, or another app uses port 8765 | Use the existing tab, stop the other process, or start with `--port 8766` |
| Page shows "Could not load" | The GUI server stopped | Check the terminal; restart `python3 scripts/gui.py` and reload |
| `bad host` (403) | Opened through a hostname other than localhost / 127.0.0.1 | Use http://127.0.0.1:8765 |
| Run buttons greyed out; yellow "Claude Code CLI not found" | `claude` isn't on the PATH the GUI was started with | Install Claude Code, or start with `LEAD_AGENT_CLAUDE=/full/path/to/claude python3 scripts/gui.py`. Find the path with `which claude` (macOS/Linux) or `where claude` (Windows) |
| A run ends at once with `✗` and a login message | Claude Code isn't signed in | Run `claude` in a terminal, sign in, then retry |
| A run stops with a permission error | A tool the command needs isn't allowed in unattended mode | The allowed tools are in `.claude/settings.json` (web search, web fetch, `leads.py`, writes to `data/`, `outreach/`, `exports/`). Run the command in a `claude` terminal session to approve it interactively, or add the permission to that file |
| Run shows "Run not found (the GUI was restarted)" | Run list is kept in memory only | Read the log in `data/<product>/runs/` |
| New leads from a run don't show | Page not refreshed yet | Wait 10 seconds, or click another page and back |
| Leads table looks empty | Filters, or "hide candidates" with only candidates in the list | Click **Clear**; untick **hide candidates** |
| Review keys do nothing | Cursor is in the reason box, or the lead panel is open | Click on an empty part of the page, or press Esc |
| "Not added: duplicate domain …" | A lead with that website and no different named person exists | Open the existing lead instead; use a different contact name only if it's really another person |
| "no sources given" / "A lead needs at least one source URL" | Every lead needs a source | Add the URL where you found the lead |
| Import: "no company column found" | No header matched company | Rename the company column to `company` |
| Import skipped many rows | Duplicates, or rows without a source | Read the reasons in the result; fill **Source for rows without one** |
| Outreach shows `[first_name]`, `[hook]` etc. | That field is blank on the lead | Replace by hand, or enrich the lead first |
| "Open in email app" does nothing | No default mail app set in the OS | Use **Copy** and paste into your email |
| Wrong product's data showing | Product was switched, maybe in a terminal | Pick the right product in the sidebar picker |
| `/setup-product` wrote into the wrong product | It writes into whichever product was selected when you clicked Run | Select or create the right product (section 4.1) and run it again. If it overwrote another product's description, switch to that product and fix it under **Product & data**, or run `/setup-product` there again |
| Merge button missing for a group | Group has three or more leads | Merge pairs from the CLI: `python3 scripts/leads.py merge <keep> <dup>` |
| Anything else | | Run the tests: `python3 -m unittest scripts/test_leads.py scripts/test_gui.py`. Start with `LEAD_AGENT_GUI_DEBUG=1` to see each request in the terminal |
