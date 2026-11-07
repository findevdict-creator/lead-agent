#!/usr/bin/env python3
"""Lead store helper. Standard library only, no API keys.

All writes to data/leads.csv go through this script so the file stays valid
and deduplicated.

Usage:
  leads.py add  '<json>'            add one lead (JSON object), dedupes by domain/id
  leads.py add  --file leads.json   add many leads (JSON list)
  leads.py list [--stage S] [--limit N] [--sort fit_score] [--json]
  leads.py get  <id>
  leads.py update <id> [--stage S] [--note "text"] [--next-action "text"]
                       [--next-date YYYY-MM-DD] [--set col=value ...]
  leads.py stats
  leads.py digest [--days 7] [--ahead 7]
  leads.py export [--stage S] [--out path]
  leads.py log-search "<query>" [--found N]
  leads.py searches
  leads.py domains                  print known domains (for dedupe before research)
  leads.py product [name]           show the active product, or switch to / create one
  leads.py products                 list all product workspaces

  leads.py list [--q text] [--min-score N] [--tag T] [--due]   filter the list
  leads.py bulk-update <id> [<id> ...] [--stage S] [--note "text"] [--add-tag T] [--remove-tag T]
  leads.py tag <id> <tag> [<tag> ...] [--remove]
  leads.py due [--days 7]           follow-ups that are overdue, due today or due soon
  leads.py analytics [--json]       funnel, conversion, score spread, sources, contactability
  leads.py import <file.csv> [--stage candidate] [--source URL] [--dry-run]
  leads.py dupes                    likely duplicates (same company name, email or LinkedIn)
  leads.py merge <keep-id> <dup-id> fold a duplicate into another lead
  leads.py export [--format csv|hubspot|pipedrive|json|ics] [--stage S] [--tag T] [--min-score N]
  leads.py templates                list outreach templates
  leads.py render <template> <id> [--save]   fill a template for a lead (draft only, never sent)
  leads.py views                    list saved views (filters saved from the GUI)

Each product has its own folder: data/<product>/ (product.md, icp.md, leads.csv,
notes/, searches.log), exports/<product>/ and outreach/<product>/. The active
product is stored in data/.active (override with LEAD_AGENT_PRODUCT=<name>).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(os.environ.get("LEAD_AGENT_ROOT", Path(__file__).resolve().parent.parent))
DATA_ROOT = ROOT / "data"
ACTIVE_FILE = DATA_ROOT / ".active"


def active_product() -> str:
    """Name of the active product folder under data/. Env var wins, then data/.active, then 'default'."""
    env = os.environ.get("LEAD_AGENT_PRODUCT")
    if env:
        return env.strip()
    if ACTIVE_FILE.exists():
        name = ACTIVE_FILE.read_text(encoding="utf-8").strip()
        if name:
            return name
    return "default"


TEMPLATES_BUILTIN = ROOT / "templates"


def use_product(name: str) -> None:
    """Point every module-level path at product `name` (used by the GUI server and tests)."""
    global PRODUCT, DATA, LEADS_CSV, NOTES_DIR, SEARCH_LOG, EXPORTS, OUTREACH, TEMPLATES_DIR, VIEWS_FILE
    PRODUCT = name
    DATA = DATA_ROOT / PRODUCT
    LEADS_CSV = DATA / "leads.csv"
    NOTES_DIR = DATA / "notes"
    SEARCH_LOG = DATA / "searches.log"
    EXPORTS = ROOT / "exports" / PRODUCT
    OUTREACH = ROOT / "outreach" / PRODUCT
    TEMPLATES_DIR = DATA / "templates"
    VIEWS_FILE = DATA / "views.json"


use_product(active_product())

COLUMNS = [
    "id", "company", "website", "industry", "size", "location",
    "contact_name", "contact_role", "contact_email", "contact_linkedin",
    "fit_score", "fit_reason", "signals", "sources",
    "stage", "next_action", "next_action_date", "added_on", "updated_on", "notes",
    "tags",
]

STAGES = ["candidate", "new", "approved", "contacted", "replied", "meeting", "won",
          "rejected", "lost", "not_now"]
FUNNEL = ["candidate", "new", "approved", "contacted", "replied", "meeting", "won"]


# ---------- helpers ----------

def today() -> str:
    return date.today().isoformat()


def slugify(text: str) -> str:
    import unicodedata
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("æ", "ae"), ("ø", "o")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "lead"


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower()
    host = host.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def ensure_files() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not LEADS_CSV.exists():
        with LEADS_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
    if not SEARCH_LOG.exists():
        SEARCH_LOG.touch()


def read_leads() -> list[dict]:
    ensure_files()
    with LEADS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for c in COLUMNS:
            r.setdefault(c, "")
    return rows


def write_leads(rows: list[dict]) -> None:
    ensure_files()
    tmp = LEADS_CSV.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    tmp.replace(LEADS_CSV)


def score_of(row: dict) -> int:
    try:
        return int(float(row.get("fit_score") or 0))
    except ValueError:
        return 0


def append_note(lead_id: str, text: str) -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{lead_id}.md"
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write(f"# {lead_id}\n\n")
        f.write(f"- {today()}: {text.strip()}\n")


def join_list(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def split_tags(value: str) -> list[str]:
    seen = []
    for t in re.split(r"[;,]", value or ""):
        t = slugify(t) if t.strip() else ""
        if t and t not in seen:
            seen.append(t)
    return seen


def join_tags(tags: list[str]) -> str:
    return "; ".join(tags)


CLOSED = ("won", "lost", "rejected")


def is_open(row: dict) -> bool:
    return row["stage"] not in CLOSED


def matches(row: dict, q: str = "", stage: str = "", min_score=None, max_score=None,
            tag: str = "", due: bool = False) -> bool:
    """Filter used by `list`, `export` and the GUI. `q` matches any text column, all words must match."""
    if stage and row["stage"] not in stage.split(","):
        return False
    s = score_of(row)
    if min_score is not None and s < int(min_score):
        return False
    if max_score is not None and s > int(max_score):
        return False
    if tag and slugify(tag) not in split_tags(row.get("tags", "")):
        return False
    if due and not (row["next_action_date"] and row["next_action_date"] <= today() and is_open(row)):
        return False
    if q:
        hay = " ".join(str(row.get(c, "")) for c in COLUMNS).lower()
        if not all(word in hay for word in q.lower().split()):
            return False
    return True


def find_lead(rows: list[dict], lead_id: str) -> dict | None:
    return next((r for r in rows if r["id"] == lead_id), None)


def apply_update(target: dict, stage=None, next_action=None, next_date=None, fields=None,
                 add_tags=None, remove_tags=None) -> list[str]:
    """Change one lead row in memory. Returns a list of human-readable changes; raises ValueError."""
    changes = []
    if stage:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage}; valid: {', '.join(STAGES)}")
        if stage != target["stage"]:
            changes.append(f"stage {target['stage']} -> {stage}")
            target["stage"] = stage
    if next_action is not None and next_action != target["next_action"]:
        target["next_action"] = next_action
        changes.append(f"next action: {next_action}" if next_action else "next action cleared")
    if next_date is not None and next_date != target["next_action_date"]:
        if next_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", next_date):
            raise ValueError(f"next date must be YYYY-MM-DD, got {next_date}")
        target["next_action_date"] = next_date
        changes.append(f"next date: {next_date}" if next_date else "next date cleared")
    for col, value in (fields or {}).items():
        if col not in COLUMNS or col in ("id", "added_on", "updated_on", "stage", "tags"):
            raise ValueError(f"cannot set column {col}")
        value = str(value)
        if col == "fit_score":
            value = str(score_of({"fit_score": value}))
        if value != target[col]:
            target[col] = value
            changes.append(f"{col} = {value}")
    if add_tags or remove_tags:
        tags = split_tags(target.get("tags", ""))
        for t in split_tags(join_list(add_tags or [])):
            if t not in tags:
                tags.append(t)
                changes.append(f"tag +{t}")
        for t in split_tags(join_list(remove_tags or [])):
            if t in tags:
                tags.remove(t)
                changes.append(f"tag -{t}")
        target["tags"] = join_tags(tags)
    return changes


def update_lead(lead_id: str, note: str = "", **kw) -> list[str]:
    """Update one lead on disk and log the change to its notes. Raises KeyError / ValueError."""
    rows = read_leads()
    target = find_lead(rows, lead_id)
    if target is None:
        raise KeyError(lead_id)
    changes = apply_update(target, **kw)
    if note:
        changes.append(note.strip())
    if changes:
        target["updated_on"] = today()
        write_leads(rows)
        append_note(lead_id, "; ".join(changes))
    return changes


def bulk_update(ids: list[str], note: str = "", **kw) -> tuple[list[str], list[str]]:
    """Apply the same change to many leads in one write. Returns (updated ids, missing ids)."""
    rows = read_leads()
    index = {r["id"]: r for r in rows}
    done, missing, logs = [], [], {}
    for lead_id in ids:
        target = index.get(lead_id)
        if target is None:
            missing.append(lead_id)
            continue
        changes = apply_update(target, **kw)
        if note:
            changes.append(note.strip())
        if changes:
            target["updated_on"] = today()
            logs[lead_id] = "; ".join(changes)
            done.append(lead_id)
    if done:
        write_leads(rows)
        for lead_id, text in logs.items():
            append_note(lead_id, text)
    return done, missing


def read_notes(lead_id: str) -> str:
    path = NOTES_DIR / f"{lead_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------- commands ----------

def add_leads(items: list[dict], default_stage: str = "new") -> tuple[list[dict], list[tuple[str, str]]]:
    """Add lead dicts to the store with dedupe. Returns (added rows, [(id, reason skipped)])."""
    rows = read_leads()
    by_id = {r["id"]: r for r in rows}
    by_domain: dict[str, list[dict]] = {}
    for r in rows:
        if r["website"]:
            by_domain.setdefault(normalize_domain(r["website"]), []).append(r)

    added, skipped = [], []
    for item in items:
        company = str(item.get("company", "")).strip()
        if not company:
            skipped.append(("?", "missing company"))
            continue
        website = str(item.get("website", "")).strip()
        domain = normalize_domain(website)
        lead_id = slugify(item.get("id") or company)
        if lead_id in by_id:
            skipped.append((lead_id, "duplicate id"))
            continue
        if domain and domain in by_domain:
            new_person = str(item.get("contact_name", "")).strip().lower()
            # Different named people at the same organisation (e.g. coaches at one academy) are all kept;
            # a record without a person, or with a person already stored, is a duplicate.
            clash = next((o for o in by_domain[domain]
                          if not new_person or o["contact_name"].lower() == new_person), None)
            if clash is not None:
                skipped.append((lead_id, f"duplicate domain {domain} ({clash['id']})"))
                continue
        sources = join_list(item.get("sources"))
        if not sources:
            skipped.append((lead_id, "no sources given; every lead needs at least one source URL"))
            continue
        stage = str(item.get("stage") or default_stage)
        if stage not in STAGES:
            skipped.append((lead_id, f"unknown stage {stage}"))
            continue
        row = {c: "" for c in COLUMNS}
        for c in COLUMNS:
            if c in item and c not in ("signals", "sources", "tags"):
                row[c] = str(item[c]).strip()
        row.update({
            "id": lead_id,
            "company": company,
            "website": website,
            "signals": join_list(item.get("signals")),
            "sources": sources,
            "tags": join_tags(split_tags(join_list(item.get("tags")))),
            "fit_score": str(score_of(item)),
            "stage": stage,
            "added_on": today(),
            "updated_on": today(),
        })
        rows.append(row)
        by_id[lead_id] = row
        if domain:
            by_domain.setdefault(domain, []).append(row)
        added.append(row)
        if item.get("research"):
            append_note(lead_id, item["research"])

    if added:
        write_leads(rows)
    return added, skipped


def cmd_add(args) -> int:
    if args.file:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    elif args.json:
        payload = json.loads(args.json)
    else:
        payload = json.load(sys.stdin)
    items = payload if isinstance(payload, list) else [payload]
    added, skipped = add_leads(items)
    for r in added:
        print(f"added    {r['id']:<30} score={r['fit_score']:>3}  {r['company']}")
    for lead_id, why in skipped:
        print(f"skipped  {lead_id:<30} {why}")
    print(f"\n{len(added)} added, {len(skipped)} skipped, {len(read_leads())} total")
    return 0


def cmd_list(args) -> int:
    rows = [r for r in read_leads()
            if matches(r, q=args.q or "", stage=args.stage or "", min_score=args.min_score,
                       tag=args.tag or "", due=args.due)]
    key = args.sort
    if key == "fit_score":
        rows.sort(key=score_of, reverse=True)
    else:
        rows.sort(key=lambda r: r.get(key, ""))
    if args.limit:
        rows = rows[: args.limit]
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no leads")
        return 0
    print(f"{'id':<28} {'score':>5} {'stage':<10} {'next':<11} company / contact")
    for r in rows:
        contact = f"{r['contact_name']} ({r['contact_role']})" if r["contact_name"] else "-"
        print(f"{r['id']:<28} {r['fit_score']:>5} {r['stage']:<10} {r['next_action_date']:<11} "
              f"{r['company']} / {contact}")
    return 0


def cmd_get(args) -> int:
    for r in read_leads():
        if r["id"] == args.id:
            for c in COLUMNS:
                print(f"{c:<18} {r[c]}")
            note = NOTES_DIR / f"{args.id}.md"
            if note.exists():
                print("\n--- notes ---")
                print(note.read_text(encoding="utf-8"))
            return 0
    print(f"not found: {args.id}", file=sys.stderr)
    return 1


def cmd_update(args) -> int:
    fields = {}
    for kv in args.set or []:
        col, _, value = kv.partition("=")
        fields[col] = value
    if not any([args.stage, args.next_action is not None, args.next_date is not None, fields, args.note]):
        print("nothing to update", file=sys.stderr)
        return 1
    try:
        changes = update_lead(args.id, note=args.note or "", stage=args.stage, next_action=args.next_action,
                              next_date=args.next_date, fields=fields)
    except KeyError:
        print(f"not found: {args.id}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"updated {args.id}: " + ("; ".join(changes) if changes else "no change"))
    return 0


def cmd_bulk_update(args) -> int:
    try:
        done, missing = bulk_update(args.ids, note=args.note or "", stage=args.stage,
                                    next_action=args.next_action, next_date=args.next_date,
                                    add_tags=args.add_tag, remove_tags=args.remove_tag)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"updated {len(done)}: {', '.join(done) or '-'}")
    if missing:
        print(f"not found {len(missing)}: {', '.join(missing)}", file=sys.stderr)
    return 0 if not missing else 1


def cmd_tag(args) -> int:
    kw = {"remove_tags": args.tags} if args.remove else {"add_tags": args.tags}
    try:
        changes = update_lead(args.id, **kw)
    except KeyError:
        print(f"not found: {args.id}", file=sys.stderr)
        return 1
    print(f"{args.id}: " + ("; ".join(changes) if changes else "no change"))
    return 0


def cmd_stats(args) -> int:
    rows = read_leads()
    counts = {s: 0 for s in STAGES}
    for r in rows:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
    print(f"total leads: {len(rows)}\n")
    for s in STAGES:
        if counts.get(s):
            print(f"  {s:<10} {counts[s]}")
    t = today()
    overdue = [r for r in rows if r["next_action_date"] and r["next_action_date"] < t
               and r["stage"] not in ("won", "lost", "rejected")]
    if overdue:
        print("\noverdue next actions:")
        for r in sorted(overdue, key=lambda r: r["next_action_date"]):
            print(f"  {r['next_action_date']}  {r['id']:<28} {r['next_action']}")
    cands = [r for r in rows if r["stage"] == "candidate"]
    if cands:
        print(f"\nunverified candidates: {len(cands)} (run /verify-candidates to research and score them)")
    todo = sorted((r for r in rows if r["stage"] == "approved"), key=score_of, reverse=True)[:10]
    if todo:
        print("\ntop approved, not yet contacted:")
        for r in todo:
            print(f"  {r['fit_score']:>3}  {r['id']:<28} {r['company']}")
    return 0


# ---------- export formats ----------

HUBSPOT_COLUMNS = [
    ("Company name", "company"), ("Company Domain Name", "_domain"), ("Website URL", "website"),
    ("Industry", "industry"), ("Number of Employees", "size"), ("City", "location"),
    ("First Name", "_first"), ("Last Name", "_last"), ("Job Title", "contact_role"),
    ("Email", "contact_email"), ("LinkedIn URL", "contact_linkedin"),
    ("Lead Status", "_hs_status"), ("Lifecycle Stage", "_hs_lifecycle"),
    ("Fit Score", "fit_score"), ("Fit Reason", "fit_reason"), ("Signals", "signals"),
    ("Sources", "sources"), ("Tags", "tags"), ("Next Action", "next_action"),
    ("Next Action Date", "next_action_date"), ("Lead Agent ID", "id"),
]
PIPEDRIVE_COLUMNS = [
    ("Organization - Name", "company"), ("Organization - Website", "website"),
    ("Organization - Address", "location"), ("Organization - Industry", "industry"),
    ("Person - Name", "contact_name"), ("Person - Job title", "contact_role"),
    ("Person - Email", "contact_email"), ("Person - LinkedIn", "contact_linkedin"),
    ("Lead - Title", "_deal_title"), ("Lead - Labels", "tags"), ("Note - Content", "_note"),
]
HS_STATUS = {"candidate": "NEW", "new": "NEW", "approved": "OPEN", "contacted": "ATTEMPTED_TO_CONTACT",
             "replied": "CONNECTED", "meeting": "IN_PROGRESS", "won": "CONNECTED", "lost": "UNQUALIFIED",
             "rejected": "UNQUALIFIED", "not_now": "BAD_TIMING"}
HS_LIFECYCLE = {"meeting": "salesqualifiedlead", "won": "customer", "replied": "marketingqualifiedlead"}


def _derived(row: dict, key: str) -> str:
    name = row["contact_name"].split()
    if key == "_domain":
        return normalize_domain(row["website"])
    if key == "_first":
        return name[0] if name else ""
    if key == "_last":
        return " ".join(name[1:]) if len(name) > 1 else ""
    if key == "_hs_status":
        return HS_STATUS.get(row["stage"], "NEW")
    if key == "_hs_lifecycle":
        return HS_LIFECYCLE.get(row["stage"], "lead")
    if key == "_deal_title":
        return f"{row['company']} ({row['stage']})"
    if key == "_note":
        return f"Fit {row['fit_score']}: {row['fit_reason']}\nSignals: {row['signals']}\nSources: {row['sources']}"
    return row.get(key, "")


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_ics(rows: list[dict]) -> str:
    """An iCalendar file with one all-day event per open lead that has a next action date."""
    stamp = date.today().strftime("%Y%m%dT000000Z")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//lead-agent//follow-ups//EN",
           f"X-WR-CALNAME:Lead follow-ups ({PRODUCT})"]
    for r in rows:
        d = r["next_action_date"]
        if not d or not is_open(r) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            continue
        start = d.replace("-", "")
        from datetime import timedelta
        end = (date.fromisoformat(d) + timedelta(days=1)).strftime("%Y%m%d")
        who = f" ({r['contact_name']})" if r["contact_name"] else ""
        out += ["BEGIN:VEVENT", f"UID:{PRODUCT}-{r['id']}-{start}@lead-agent", f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}",
                f"SUMMARY:{_ics_escape((r['next_action'] or 'Follow up') + ': ' + r['company'] + who)}",
                f"DESCRIPTION:{_ics_escape('Stage: ' + r['stage'] + '. ' + r['fit_reason'])}"]
        if r["website"]:
            out.append(f"URL:{r['website']}")
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def export_text(rows: list[dict], fmt: str = "csv") -> str:
    """Serialise rows in one of the export formats and return the text."""
    import io
    rows = sorted(rows, key=score_of, reverse=True)
    if fmt == "json":
        return json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    if fmt == "ics":
        return calendar_ics(rows)
    buf = io.StringIO()
    if fmt == "csv":
        w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
        return buf.getvalue()
    mapping = {"hubspot": HUBSPOT_COLUMNS, "pipedrive": PIPEDRIVE_COLUMNS}.get(fmt)
    if mapping is None:
        raise ValueError(f"unknown format {fmt}; use csv, hubspot, pipedrive, json or ics")
    w = csv.writer(buf)
    w.writerow([h for h, _ in mapping])
    for r in rows:
        w.writerow([_derived(r, k) if k.startswith("_") else r.get(k, "") for _, k in mapping])
    return buf.getvalue()


EXPORT_EXT = {"csv": "csv", "hubspot": "csv", "pipedrive": "csv", "json": "json", "ics": "ics"}


def cmd_export(args) -> int:
    rows = [r for r in read_leads()
            if matches(r, stage=args.stage or "", tag=args.tag or "", min_score=args.min_score)]
    try:
        text = export_text(rows, args.format)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    EXPORTS.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.stage}" if args.stage else ""
    if args.tag:
        suffix += f"-{slugify(args.tag)}"
    if args.format not in ("csv",):
        suffix += f"-{args.format}"
    out = Path(args.out) if args.out else EXPORTS / f"leads-{today()}{suffix}.{EXPORT_EXT[args.format]}"
    out.write_text(text, encoding="utf-8", newline="")
    print(f"exported {len(rows)} leads to {out}")
    return 0


# ---------- follow-ups ----------

def due_buckets(rows: list[dict], days: int = 7) -> dict[str, list[dict]]:
    from datetime import timedelta
    t = today()
    until = (date.today() + timedelta(days=days)).isoformat()
    out = {"overdue": [], "today": [], "soon": [], "no_date": []}
    for r in rows:
        if not is_open(r) or r["stage"] == "candidate":
            continue
        d = r["next_action_date"]
        if not d:
            if r["stage"] in ("approved", "contacted", "replied", "meeting"):
                out["no_date"].append(r)
        elif d < t:
            out["overdue"].append(r)
        elif d == t:
            out["today"].append(r)
        elif d <= until:
            out["soon"].append(r)
    for k in ("overdue", "today", "soon"):
        out[k].sort(key=lambda r: (r["next_action_date"], -score_of(r)))
    out["no_date"].sort(key=score_of, reverse=True)
    return out


def cmd_due(args) -> int:
    b = due_buckets(read_leads(), args.days)
    labels = {"overdue": "overdue", "today": "due today", "soon": f"due in the next {args.days} days",
              "no_date": "active leads with no next action date"}
    for key, label in labels.items():
        print(f"{label}: {len(b[key])}")
        for r in b[key]:
            print(f"  {r['next_action_date'] or '-':<11} {r['id']:<28} {r['stage']:<10} {r['next_action']}")
        print()
    return 0


# ---------- analytics ----------

FUNNEL_RANK = {s: i for i, s in enumerate(FUNNEL)}
# Side exits tell us how far a lead got before leaving the funnel.
EXIT_RANK = {"rejected": FUNNEL_RANK["new"], "not_now": FUNNEL_RANK["new"], "lost": FUNNEL_RANK["contacted"]}


def analytics(rows: list[dict]) -> dict:
    from collections import Counter
    from datetime import timedelta
    stages = Counter(r["stage"] for r in rows)
    reached = []
    for i, s in enumerate(FUNNEL):
        n = sum(1 for r in rows if FUNNEL_RANK.get(r["stage"], EXIT_RANK.get(r["stage"], -1)) >= i)
        reached.append({"stage": s, "count": n})
    for i in range(1, len(reached)):
        prev = reached[i - 1]["count"]
        reached[i]["rate"] = round(100 * reached[i]["count"] / prev) if prev else None
    researched = [r for r in rows if r["stage"] != "candidate"]
    buckets = [("0-39", 0, 39), ("40-59", 40, 59), ("60-69", 60, 69), ("70-79", 70, 79), ("80-100", 80, 100)]

    def hist(rs):
        return [{"bucket": b, "count": sum(1 for r in rs if lo <= score_of(r) <= hi)} for b, lo, hi in buckets]

    t = date.today()
    monday = t - timedelta(days=t.weekday())
    weeks = []
    for i in range(11, -1, -1):
        start = monday - timedelta(weeks=i)
        end = start + timedelta(days=7)
        weeks.append({"week": start.isoformat(),
                      "count": sum(1 for r in rows if start.isoformat() <= r["added_on"] < end.isoformat())})
    src = Counter()
    for r in rows:
        for u in sorted({normalize_domain(x) for x in r["sources"].split(";") if x.strip()}):
            if u:
                src[u] += 1
    loc = Counter((r["location"].split(",")[-1].strip() or "unknown") for r in rows if r["location"])
    ind = Counter(r["industry"].strip() for r in rows if r["industry"].strip())
    tags = Counter(t for r in rows for t in split_tags(r.get("tags", "")))

    def pct(n, d):
        return round(100 * n / d) if d else 0

    active = [r for r in researched if is_open(r)]
    contact = {
        "researched": len(researched),
        "email": pct(sum(1 for r in researched if r["contact_email"]), len(researched)),
        "name": pct(sum(1 for r in researched if r["contact_name"]), len(researched)),
        "linkedin": pct(sum(1 for r in researched if r["contact_linkedin"]), len(researched)),
    }
    closed = stages.get("won", 0) + stages.get("lost", 0)
    return {
        "product": PRODUCT,
        "total": len(rows),
        "stages": {s: stages.get(s, 0) for s in STAGES},
        "funnel": reached,
        "score_researched": hist(researched),
        "score_candidates": hist([r for r in rows if r["stage"] == "candidate"]),
        "avg_score": round(sum(score_of(r) for r in researched) / len(researched)) if researched else 0,
        "added_per_week": weeks,
        "top_sources": src.most_common(10),
        "top_locations": loc.most_common(10),
        "top_industries": ind.most_common(10),
        "top_tags": tags.most_common(15),
        "contactability": contact,
        "active": len(active),
        "win_rate": pct(stages.get("won", 0), closed) if closed else None,
        "reply_rate": pct(sum(1 for r in rows if r["stage"] in ("replied", "meeting", "won")),
                          sum(1 for r in rows if r["stage"] in ("contacted", "replied", "meeting", "won", "lost"))),
        "searches": sum(1 for ln in SEARCH_LOG.read_text(encoding="utf-8").splitlines() if ln.strip())
        if SEARCH_LOG.exists() else 0,
    }


def cmd_analytics(args) -> int:
    a = analytics(read_leads())
    if args.json:
        print(json.dumps(a, indent=2))
        return 0
    print(f"product {a['product']}: {a['total']} leads, {a['contactability']['researched']} researched, "
          f"avg score {a['avg_score']}, {a['searches']} searches logged\n")
    print("funnel (reached this stage or further):")
    for f in a["funnel"]:
        rate = f" ({f['rate']}% of previous)" if f.get("rate") is not None else ""
        print(f"  {f['stage']:<10} {f['count']:>5}{rate}")
    print(f"\nreply rate: {a['reply_rate']}%   win rate: "
          f"{'-' if a['win_rate'] is None else str(a['win_rate']) + '%'}")
    c = a["contactability"]
    print(f"researched leads with email {c['email']}%, named contact {c['name']}%, LinkedIn {c['linkedin']}%")
    print("\nscore spread (researched):  " + "  ".join(f"{h['bucket']}: {h['count']}" for h in a["score_researched"]))
    print("top sources:  " + ", ".join(f"{d} {n}" for d, n in a["top_sources"][:6]))
    print("top locations:  " + ", ".join(f"{d} {n}" for d, n in a["top_locations"][:6]))
    if a["top_tags"]:
        print("tags:  " + ", ".join(f"{d} {n}" for d, n in a["top_tags"]))
    return 0


# ---------- import ----------

IMPORT_ALIASES = {
    "company": ["company", "company name", "organization", "organisation", "account", "business", "name"],
    "website": ["website", "url", "domain", "web", "company website", "website url"],
    "industry": ["industry", "sector", "category"],
    "size": ["size", "employees", "company size", "headcount", "number of employees"],
    "location": ["location", "city", "address", "country", "region"],
    "contact_name": ["contact_name", "contact", "contact name", "full name", "person", "person name"],
    "contact_role": ["contact_role", "role", "title", "job title", "position"],
    "contact_email": ["contact_email", "email", "e-mail", "email address", "contact email"],
    "contact_linkedin": ["contact_linkedin", "linkedin", "linkedin url", "linkedin profile"],
    "fit_score": ["fit_score", "score", "fit"],
    "fit_reason": ["fit_reason", "reason", "why"],
    "signals": ["signals", "signal"],
    "sources": ["sources", "source", "source url", "source_url"],
    "notes": ["notes", "note", "comments", "description"],
    "tags": ["tags", "labels", "tag", "label"],
    "stage": ["stage", "status"],
    "next_action": ["next_action", "next action"],
    "next_action_date": ["next_action_date", "next action date", "follow up", "follow-up date"],
}


def map_import_headers(headers: list[str]) -> dict[str, str]:
    """Map CSV headers to lead columns (case-insensitive, with common aliases). Returns {header: column}."""
    out, used = {}, set()
    norm = {h: re.sub(r"\s+", " ", h.strip().lower().replace("_", " ")) for h in headers}
    for col, aliases in IMPORT_ALIASES.items():
        for alias in aliases:
            alias = alias.replace("_", " ")
            h = next((h for h in headers if norm[h] == alias and h not in out), None)
            if h and col not in used:
                out[h] = col
                used.add(col)
                break
    return out


def import_rows(text: str, stage: str = "candidate", source: str = "", dry_run: bool = False,
                tags: str = "") -> dict:
    """Import CSV text. Every row needs a source: its own sources column or the `source` given."""
    reader = csv.DictReader(text.splitlines())
    mapping = map_import_headers(reader.fieldnames or [])
    if "company" not in mapping.values():
        raise ValueError("no company column found; name one column 'company'")
    items = []
    for raw in reader:
        item = {col: (raw.get(h) or "").strip() for h, col in mapping.items()}
        if not item.get("sources") and source:
            item["sources"] = source
        if item.get("stage") and item["stage"] not in STAGES:
            item["stage"] = ""
        item["tags"] = "; ".join(x for x in (item.get("tags", ""), tags) if x)
        items.append(item)
    if dry_run:
        return {"mapping": mapping, "rows": len(items), "preview": items[:5], "added": [], "skipped": []}
    added, skipped = add_leads(items, default_stage=stage)
    return {"mapping": mapping, "rows": len(items), "added": [r["id"] for r in added], "skipped": skipped}


def cmd_import(args) -> int:
    text = Path(args.file).read_text(encoding="utf-8-sig")
    try:
        res = import_rows(text, stage=args.stage, source=args.source or "", dry_run=args.dry_run,
                          tags=args.tag or "")
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print("columns: " + ", ".join(f"{h} -> {c}" for h, c in res["mapping"].items()))
    if args.dry_run:
        print(f"{res['rows']} rows would be imported (dry run)")
        for item in res["preview"]:
            print(f"  {item.get('company')}  {item.get('website', '')}")
        return 0
    for lead_id, why in res["skipped"]:
        print(f"skipped  {lead_id:<30} {why}")
    print(f"\n{len(res['added'])} added, {len(res['skipped'])} skipped of {res['rows']} rows")
    return 0


# ---------- duplicates ----------

LEGAL_SUFFIXES = r"\b(gmbh|ag|ug|kg|se|inc|llc|ltd|limited|plc|co|corp|corporation|company|bv|sa|sas|srl|spa|oy|ab|as|aps|pty)\b"


def company_key(name: str) -> str:
    key = slugify(name).replace("-", " ")
    key = re.sub(LEGAL_SUFFIXES, " ", key)
    return re.sub(r"\s+", " ", key).strip()


def find_dupes(rows: list[dict]) -> list[dict]:
    """Groups of leads that look like the same organisation or person, ignoring rejected duplicates."""
    groups: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        if "duplicate" in split_tags(r.get("tags", "")):
            continue
        keys = []
        ck = company_key(r["company"])
        if ck:
            keys.append(("company name", ck + "|" + r["contact_name"].strip().lower()))
        if r["contact_email"]:
            keys.append(("email", r["contact_email"].strip().lower()))
        if r["contact_linkedin"]:
            keys.append(("linkedin", r["contact_linkedin"].strip().lower().rstrip("/").split("?")[0]))
        for k in keys:
            groups.setdefault(k, []).append(r["id"])
    seen, out = set(), []
    for (kind, key), ids in groups.items():
        if len(ids) > 1 and tuple(sorted(ids)) not in seen:
            seen.add(tuple(sorted(ids)))
            out.append({"reason": kind, "key": key.split("|")[0], "ids": ids})
    return out


def merge_leads(keep_id: str, dup_id: str) -> list[str]:
    """Fold dup into keep: fill blanks, union sources/signals/tags, copy notes, mark dup rejected."""
    if keep_id == dup_id:
        raise ValueError("cannot merge a lead into itself")
    rows = read_leads()
    keep, dup = find_lead(rows, keep_id), find_lead(rows, dup_id)
    if keep is None or dup is None:
        raise KeyError(keep_id if keep is None else dup_id)
    filled = []
    for c in ("website", "industry", "size", "location", "contact_name", "contact_role",
              "contact_email", "contact_linkedin", "fit_reason", "next_action", "next_action_date", "notes"):
        if not keep[c] and dup[c]:
            keep[c] = dup[c]
            filled.append(c)
    for c in ("sources", "signals"):
        parts = [x.strip() for x in (keep[c] + ";" + dup[c]).split(";") if x.strip()]
        keep[c] = "; ".join(dict.fromkeys(parts))
    keep["tags"] = join_tags(list(dict.fromkeys(split_tags(keep["tags"]) + split_tags(dup["tags"]))))
    if score_of(dup) > score_of(keep):
        keep["fit_score"] = str(score_of(dup))
        filled.append("fit_score")
    keep["updated_on"] = dup["updated_on"] = today()
    dup["stage"] = "rejected"
    dup["tags"] = join_tags(list(dict.fromkeys(split_tags(dup["tags"]) + ["duplicate"])))
    write_leads(rows)
    old = read_notes(dup_id)
    append_note(keep_id, f"merged {dup_id} into this lead" + (f" (filled {', '.join(filled)})" if filled else ""))
    if old.strip():
        with (NOTES_DIR / f"{keep_id}.md").open("a", encoding="utf-8") as f:
            f.write("\n".join(f"  {ln}" for ln in old.splitlines() if ln.startswith("- ")) + "\n")
    append_note(dup_id, f"duplicate of {keep_id}; merged and moved to rejected")
    return filled


def cmd_dupes(args) -> int:
    groups = find_dupes(read_leads())
    if not groups:
        print("no likely duplicates")
        return 0
    for g in groups:
        print(f"{g['reason']:<13} {g['key'][:40]:<40} {', '.join(g['ids'])}")
    print(f"\n{len(groups)} groups; merge with: leads.py merge <keep-id> <dup-id>")
    return 0


def cmd_merge(args) -> int:
    try:
        filled = merge_leads(args.keep, args.dup)
    except (KeyError, ValueError) as e:
        print(f"cannot merge: {e}", file=sys.stderr)
        return 1
    print(f"merged {args.dup} into {args.keep}" + (f"; filled {', '.join(filled)}" if filled else ""))
    return 0


# ---------- outreach templates ----------

def list_templates() -> dict[str, Path]:
    """Built-in templates in templates/outreach/, overridden by data/<product>/templates/ with the same name."""
    found = {}
    for folder in (TEMPLATES_BUILTIN / "outreach", TEMPLATES_DIR):
        if folder.exists():
            for f in sorted(folder.glob("*.md")):
                found[f.stem] = f
    return found


def product_name() -> str:
    path = DATA / "product.md"
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.startswith("# "):
                return ln[2:].strip()
    return PRODUCT


def merge_fields(row: dict) -> dict[str, str]:
    signals = [s.strip() for s in row["signals"].split(";") if s.strip()]
    first = row["contact_name"].split()[0] if row["contact_name"].strip() else ""
    return {
        "company": row["company"], "website": row["website"], "industry": row["industry"],
        "location": row["location"], "size": row["size"],
        "contact_name": row["contact_name"], "first_name": first, "contact_role": row["contact_role"],
        "contact_email": row["contact_email"], "contact_linkedin": row["contact_linkedin"],
        "fit_reason": row["fit_reason"], "hook": signals[0] if signals else "",
        "signals": ", ".join(signals), "source": row["sources"].split(";")[0].strip(),
        "product": product_name(), "sender": "[Your name]",
        "greeting": f"Hi {first}," if first else "Hello,",
    }


def render_template(name: str, lead_id: str) -> tuple[str, list[str]]:
    """Fill {{field}} placeholders for a lead. Missing values become [field] so they are easy to spot."""
    templates = list_templates()
    if name not in templates:
        raise KeyError(f"template {name}")
    row = find_lead(read_leads(), lead_id)
    if row is None:
        raise KeyError(lead_id)
    fields = merge_fields(row)
    missing = []

    def sub(m):
        key = m.group(1).strip()
        val = fields.get(key, "")
        if not val:
            if key not in missing:
                missing.append(key)
            return f"[{key}]"
        return val

    text = re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", sub, templates[name].read_text(encoding="utf-8"))
    return text, missing


def save_outreach(lead_id: str, text: str, label: str) -> Path:
    """Append a draft to outreach/<product>/<id>.md and log it on the lead (stage unchanged)."""
    from datetime import timedelta
    rows = read_leads()
    row = find_lead(rows, lead_id)
    if row is None:
        raise KeyError(lead_id)
    OUTREACH.mkdir(parents=True, exist_ok=True)
    path = OUTREACH / f"{lead_id}.md"
    with path.open("a", encoding="utf-8") as f:
        if path.stat().st_size == 0:
            f.write(f"# Outreach: {row['company']} ({lead_id})\n")
        f.write(f"\n---\nDrafted: {today()} from template `{label}` (draft only, not sent)\n\n{text.strip()}\n")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    update_lead(lead_id, note=f"outreach drafted from template {label} in outreach/{PRODUCT}/{lead_id}.md",
                next_action=row["next_action"] or "Send first message",
                next_date=row["next_action_date"] or tomorrow)
    return path


def cmd_templates(args) -> int:
    t = list_templates()
    if not t:
        print("no templates")
        return 0
    for name, path in t.items():
        print(f"{name:<24} {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


def cmd_render(args) -> int:
    try:
        text, missing = render_template(args.template, args.id)
    except KeyError as e:
        print(f"not found: {e}", file=sys.stderr)
        return 1
    print(text)
    if missing:
        print(f"\n[missing fields, fill by hand: {', '.join(missing)}]", file=sys.stderr)
    if args.save:
        path = save_outreach(args.id, text, args.template)
        print(f"\nsaved to {path} (not sent)")
    return 0


# ---------- ICP learning ----------

def learn_disqualifier(rule: str, lead_id: str = "") -> bool:
    """Append a rule to '## Learned disqualifiers' in icp.md (the GUI's version of /review-leads step 5).
    Returns False if the same rule is already there."""
    rule = " ".join(rule.split())
    if not rule:
        raise ValueError("empty rule")
    path = DATA / "icp.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if rule.lower() in text.lower():
        return False
    line = f"- {rule} (from {lead_id}, {today()})" if lead_id else f"- {rule} ({today()})"
    lines = text.splitlines()
    idx = next((i for i, ln in enumerate(lines) if ln.strip().lower().startswith("## learned disqualifiers")), None)
    if idx is None:
        lines += ["", "## Learned disqualifiers", "", line]
    else:
        end = next((j for j in range(idx + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
    DATA.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip("\n") + "\n", encoding="utf-8")
    return True


# ---------- saved views ----------

def read_views() -> list[dict]:
    if VIEWS_FILE.exists():
        try:
            return json.loads(VIEWS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def save_view(name: str, filters: dict) -> list[dict]:
    views = [v for v in read_views() if v.get("name") != name]
    views.append({"name": name, "filters": filters})
    DATA.mkdir(parents=True, exist_ok=True)
    VIEWS_FILE.write_text(json.dumps(views, indent=2), encoding="utf-8")
    return views


def delete_view(name: str) -> list[dict]:
    views = [v for v in read_views() if v.get("name") != name]
    DATA.mkdir(parents=True, exist_ok=True)
    VIEWS_FILE.write_text(json.dumps(views, indent=2), encoding="utf-8")
    return views


def cmd_views(args) -> int:
    views = read_views()
    if not views:
        print("no saved views (save one from the GUI's Leads page)")
    for v in views:
        f = ", ".join(f"{k}={val}" for k, val in v["filters"].items() if val not in ("", None, False))
        print(f"{v['name']:<24} {f}")
    return 0


def cmd_digest(args) -> int:
    from datetime import timedelta
    rows = read_leads()
    t = date.today()
    since = (t - timedelta(days=args.days)).isoformat()
    until = (t + timedelta(days=args.ahead)).isoformat()
    added = [r for r in rows if r["added_on"] >= since]
    changed = [r for r in rows if r["updated_on"] >= since and r["added_on"] < since]
    overdue = [r for r in rows if r["next_action_date"] and r["next_action_date"] < t.isoformat()
               and r["stage"] not in ("won", "lost", "rejected")]
    due = [r for r in rows if r["next_action_date"] and t.isoformat() <= r["next_action_date"] <= until
           and r["stage"] not in ("won", "lost", "rejected")]
    stale = [r for r in rows if r["stage"] == "contacted" and r["updated_on"] < since]

    def activity(lead_id: str) -> list[str]:
        path = NOTES_DIR / f"{lead_id}.md"
        if not path.exists():
            return []
        return [ln[2:] for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.startswith("- ") and ln[2:12] >= since]

    print(f"digest: last {args.days} days (since {since}), looking ahead {args.ahead} days\n")
    print(f"added: {len(added)}")
    for r in sorted(added, key=score_of, reverse=True):
        print(f"  {r['fit_score']:>3}  {r['id']:<28} {r['stage']}")
    print(f"\nchanged: {len(changed)}")
    for r in changed:
        print(f"  {r['id']:<28} now {r['stage']}")
        for line in activity(r["id"]):
            print(f"      {line}")
    print(f"\noverdue: {len(overdue)}")
    for r in sorted(overdue, key=lambda r: r["next_action_date"]):
        print(f"  {r['next_action_date']}  {r['id']:<28} {r['next_action']}")
    print(f"\ndue soon: {len(due)}")
    for r in sorted(due, key=lambda r: r["next_action_date"]):
        print(f"  {r['next_action_date']}  {r['id']:<28} {r['next_action']}")
    print(f"\ncontacted with no update for {args.days}+ days: {len(stale)}")
    for r in stale:
        print(f"  {r['updated_on']}  {r['id']}")
    counts = {}
    for r in rows:
        counts[r["stage"]] = counts.get(r["stage"], 0) + 1
    print("\nfunnel: " + " → ".join(f"{s} {counts.get(s, 0)}" for s in FUNNEL))
    return 0


def cmd_product(args) -> int:
    if args.name:
        name = slugify(args.name)
        pinned = os.environ.get("LEAD_AGENT_PRODUCT", "").strip()
        if pinned and name != pinned:
            # Runs started from the GUI are pinned to one product; switching would split the work
            # across two folders, because every later leads.py call still follows the env var.
            print(f"product is pinned to {pinned} for this run (LEAD_AGENT_PRODUCT); not switching to {name}. "
                  f"Keep working in data/{pinned}/.", file=sys.stderr)
            return 1
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        ACTIVE_FILE.write_text(name + "\n", encoding="utf-8")
        (DATA_ROOT / name / "notes").mkdir(parents=True, exist_ok=True)
        print(f"active product: {name}  (data/{name}/)")
        return 0
    print(f"active product: {PRODUCT}  (data/{PRODUCT}/)")
    print(f"  product.md: {'yes' if (DATA / 'product.md').exists() else 'missing'}")
    print(f"  icp.md:     {'yes' if (DATA / 'icp.md').exists() else 'missing'}")
    print(f"  leads:      {len(read_leads()) if LEADS_CSV.exists() else 0}")
    return 0


def cmd_products(args) -> int:
    if not DATA_ROOT.exists():
        print("no products yet")
        return 0
    found = False
    for p in sorted(DATA_ROOT.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            found = True
            n = 0
            csv_path = p / "leads.csv"
            if csv_path.exists():
                with csv_path.open(newline="", encoding="utf-8") as f:
                    n = sum(1 for _ in csv.DictReader(f))
            mark = "*" if p.name == PRODUCT else " "
            print(f"{mark} {p.name:<24} leads={n:<4} product.md={'yes' if (p / 'product.md').exists() else 'no':<3} icp.md={'yes' if (p / 'icp.md').exists() else 'no'}")
    if not found:
        print("no products yet; run: python3 scripts/leads.py product <name>")
    return 0


def cmd_log_search(args) -> int:
    ensure_files()
    with SEARCH_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{today()}\t{args.found}\t{args.query.strip()}\n")
    print("logged")
    return 0


def cmd_searches(args) -> int:
    ensure_files()
    text = SEARCH_LOG.read_text(encoding="utf-8").strip()
    print(text if text else "no searches logged yet")
    return 0


def cmd_domains(args) -> int:
    for r in read_leads():
        d = normalize_domain(r["website"])
        if d:
            print(f"{d}\t{r['id']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("json", nargs="?")
    a.add_argument("--file")
    a.set_defaults(fn=cmd_add)

    l = sub.add_parser("list")
    l.add_argument("--stage", help="one stage or several separated by commas")
    l.add_argument("--limit", type=int)
    l.add_argument("--sort", default="fit_score")
    l.add_argument("--q", help="text search across all columns")
    l.add_argument("--min-score", type=int)
    l.add_argument("--tag")
    l.add_argument("--due", action="store_true", help="only open leads whose next action is due or overdue")
    l.add_argument("--json", action="store_true")
    l.set_defaults(fn=cmd_list)

    g = sub.add_parser("get")
    g.add_argument("id")
    g.set_defaults(fn=cmd_get)

    u = sub.add_parser("update")
    u.add_argument("id")
    u.add_argument("--stage")
    u.add_argument("--note")
    u.add_argument("--next-action")
    u.add_argument("--next-date")
    u.add_argument("--set", action="append", metavar="col=value")
    u.set_defaults(fn=cmd_update)

    sub.add_parser("stats").set_defaults(fn=cmd_stats)

    d = sub.add_parser("digest")
    d.add_argument("--days", type=int, default=7, help="look back this many days")
    d.add_argument("--ahead", type=int, default=7, help="list actions due within this many days")
    d.set_defaults(fn=cmd_digest)

    e = sub.add_parser("export")
    e.add_argument("--stage", help="one stage or several separated by commas")
    e.add_argument("--tag")
    e.add_argument("--min-score", type=int)
    e.add_argument("--format", default="csv", choices=list(EXPORT_EXT))
    e.add_argument("--out")
    e.set_defaults(fn=cmd_export)

    bu = sub.add_parser("bulk-update")
    bu.add_argument("ids", nargs="+")
    bu.add_argument("--stage")
    bu.add_argument("--note")
    bu.add_argument("--next-action")
    bu.add_argument("--next-date")
    bu.add_argument("--add-tag", action="append")
    bu.add_argument("--remove-tag", action="append")
    bu.set_defaults(fn=cmd_bulk_update)

    t = sub.add_parser("tag")
    t.add_argument("id")
    t.add_argument("tags", nargs="+")
    t.add_argument("--remove", action="store_true")
    t.set_defaults(fn=cmd_tag)

    du = sub.add_parser("due")
    du.add_argument("--days", type=int, default=7)
    du.set_defaults(fn=cmd_due)

    an = sub.add_parser("analytics")
    an.add_argument("--json", action="store_true")
    an.set_defaults(fn=cmd_analytics)

    im = sub.add_parser("import")
    im.add_argument("file")
    im.add_argument("--stage", default="candidate", choices=STAGES)
    im.add_argument("--source", help="source URL or reference for rows that have no sources column")
    im.add_argument("--tag", help="tag every imported lead")
    im.add_argument("--dry-run", action="store_true")
    im.set_defaults(fn=cmd_import)

    sub.add_parser("dupes").set_defaults(fn=cmd_dupes)
    m = sub.add_parser("merge")
    m.add_argument("keep")
    m.add_argument("dup")
    m.set_defaults(fn=cmd_merge)

    sub.add_parser("templates").set_defaults(fn=cmd_templates)
    r = sub.add_parser("render")
    r.add_argument("template")
    r.add_argument("id")
    r.add_argument("--save", action="store_true", help="append to outreach/<product>/<id>.md")
    r.set_defaults(fn=cmd_render)

    sub.add_parser("views").set_defaults(fn=cmd_views)

    s = sub.add_parser("log-search")
    s.add_argument("query")
    s.add_argument("--found", type=int, default=0)
    s.set_defaults(fn=cmd_log_search)

    sub.add_parser("searches").set_defaults(fn=cmd_searches)
    sub.add_parser("domains").set_defaults(fn=cmd_domains)

    pr = sub.add_parser("product", help="show or switch the active product")
    pr.add_argument("name", nargs="?")
    pr.set_defaults(fn=cmd_product)
    sub.add_parser("products", help="list product workspaces").set_defaults(fn=cmd_products)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
