---
description: Export leads to a CSV in exports/ for Google Sheets or a CRM
argument-hint: [stage] [--out path]
---

Export leads to CSV.

- No arguments: `python3 scripts/leads.py export` (all leads, sorted by score)
- A stage name in `$ARGUMENTS`: `python3 scripts/leads.py export --stage <stage>`
- `--out <path>`: pass it through.

Report the file path and the row count, and remind the user: in Google Sheets use File → Import → Upload, choose "Replace current sheet", separator "Comma". For a CRM import, the columns `company, website, contact_name, contact_role, contact_email, stage, notes` map to the usual fields.
