---
description: Export leads for Google Sheets, HubSpot, Pipedrive, JSON or a follow-up calendar
argument-hint: [stage] [hubspot|pipedrive|json|ics] [--tag T] [--min-score N] [--out path]
---

Export leads with `python3 scripts/leads.py export`.

- No arguments: all leads as CSV, sorted by score.
- A stage name in `$ARGUMENTS` (or several separated by commas): `--stage <stage>`.
- A format word (`hubspot`, `pipedrive`, `json`, `ics`): `--format <format>`. `ics` is a calendar of open next actions.
- `--tag`, `--min-score` and `--out` pass through.

Report the file path and the row count. For Google Sheets: File → Import → Upload, "Replace current sheet", separator "Comma". For HubSpot: Contacts → Import → File from computer, one object (Contacts) with the company association; the headers already match HubSpot's names. For Pipedrive: Import data → Leads, the headers already match. Remind the user that candidates are unverified; suggest `--stage new,approved,contacted,replied,meeting,won` if they only want researched leads.
