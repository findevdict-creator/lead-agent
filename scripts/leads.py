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


PRODUCT = active_product()
DATA = DATA_ROOT / PRODUCT
LEADS_CSV = DATA / "leads.csv"
NOTES_DIR = DATA / "notes"
SEARCH_LOG = DATA / "searches.log"
EXPORTS = ROOT / "exports" / PRODUCT
OUTREACH = ROOT / "outreach" / PRODUCT

COLUMNS = [
    "id", "company", "website", "industry", "size", "location",
    "contact_name", "contact_role", "contact_email", "contact_linkedin",
    "fit_score", "fit_reason", "signals", "sources",
    "stage", "next_action", "next_action_date", "added_on", "updated_on", "notes",
]

STAGES = ["new", "approved", "contacted", "replied", "meeting", "won",
          "rejected", "lost", "not_now"]


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


# ---------- commands ----------

def cmd_add(args) -> int:
    if args.file:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    elif args.json:
        payload = json.loads(args.json)
    else:
        payload = json.load(sys.stdin)
    items = payload if isinstance(payload, list) else [payload]

    rows = read_leads()
    by_id = {r["id"]: r for r in rows}
    by_domain = {normalize_domain(r["website"]): r for r in rows if r["website"]}

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
            skipped.append((lead_id, f"duplicate domain {domain} ({by_domain[domain]['id']})"))
            continue
        sources = join_list(item.get("sources"))
        if not sources:
            skipped.append((lead_id, "no sources given; every lead needs at least one source URL"))
            continue
        stage = str(item.get("stage") or "new")
        if stage not in STAGES:
            skipped.append((lead_id, f"unknown stage {stage}"))
            continue
        row = {c: "" for c in COLUMNS}
        for c in COLUMNS:
            if c in item and c not in ("signals", "sources"):
                row[c] = str(item[c]).strip()
        row.update({
            "id": lead_id,
            "company": company,
            "website": website,
            "signals": join_list(item.get("signals")),
            "sources": sources,
            "fit_score": str(score_of(item)),
            "stage": stage,
            "added_on": today(),
            "updated_on": today(),
        })
        rows.append(row)
        by_id[lead_id] = row
        if domain:
            by_domain[domain] = row
        added.append(row)
        if item.get("research"):
            append_note(lead_id, item["research"])

    write_leads(rows)
    for r in added:
        print(f"added    {r['id']:<30} score={r['fit_score']:>3}  {r['company']}")
    for lead_id, why in skipped:
        print(f"skipped  {lead_id:<30} {why}")
    print(f"\n{len(added)} added, {len(skipped)} skipped, {len(rows)} total")
    return 0


def cmd_list(args) -> int:
    rows = read_leads()
    if args.stage:
        rows = [r for r in rows if r["stage"] == args.stage]
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
    rows = read_leads()
    target = next((r for r in rows if r["id"] == args.id), None)
    if target is None:
        print(f"not found: {args.id}", file=sys.stderr)
        return 1
    changes = []
    if args.stage:
        if args.stage not in STAGES:
            print(f"unknown stage {args.stage}; valid: {', '.join(STAGES)}", file=sys.stderr)
            return 1
        changes.append(f"stage {target['stage']} -> {args.stage}")
        target["stage"] = args.stage
    if args.next_action is not None:
        target["next_action"] = args.next_action
        changes.append(f"next action: {args.next_action}")
    if args.next_date is not None:
        target["next_action_date"] = args.next_date
        changes.append(f"next date: {args.next_date}")
    for kv in args.set or []:
        col, _, value = kv.partition("=")
        if col not in COLUMNS or col in ("id", "added_on", "updated_on"):
            print(f"cannot set column {col}", file=sys.stderr)
            return 1
        target[col] = value
        changes.append(f"{col} = {value}")
    if args.note:
        changes.append(args.note)
    if not changes:
        print("nothing to update", file=sys.stderr)
        return 1
    target["updated_on"] = today()
    write_leads(rows)
    append_note(args.id, "; ".join(changes))
    print(f"updated {args.id}: " + "; ".join(changes))
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
    todo = sorted((r for r in rows if r["stage"] == "approved"), key=score_of, reverse=True)[:10]
    if todo:
        print("\ntop approved, not yet contacted:")
        for r in todo:
            print(f"  {r['fit_score']:>3}  {r['id']:<28} {r['company']}")
    return 0


def cmd_export(args) -> int:
    rows = read_leads()
    if args.stage:
        rows = [r for r in rows if r["stage"] == args.stage]
    rows.sort(key=score_of, reverse=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.stage}" if args.stage else ""
    out = Path(args.out) if args.out else EXPORTS / f"leads-{today()}{suffix}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    print(f"exported {len(rows)} leads to {out}")
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
    print("\nfunnel: " + " → ".join(f"{s} {counts.get(s, 0)}" for s in STAGES[:6]))
    return 0


def cmd_product(args) -> int:
    if args.name:
        name = slugify(args.name)
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
    l.add_argument("--stage", choices=STAGES)
    l.add_argument("--limit", type=int)
    l.add_argument("--sort", default="fit_score")
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
    e.add_argument("--stage", choices=STAGES)
    e.add_argument("--out")
    e.set_defaults(fn=cmd_export)

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
