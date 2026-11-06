---
description: Bulk-collect candidate leads from directories, lists, Reddit, Instagram, LinkedIn and news; saves them as unverified candidates
argument-hint: [target count, default 100] [platform or segment: reddit|instagram|linkedin|directories|news|<segment>]
---

Harvest candidate leads in bulk. `$ARGUMENTS`: optional target count (default 100) and an optional platform or segment focus. Candidates are saved with stage `candidate` and are **not** qualified leads until `/verify-candidates` has researched them.

## Sources, by platform (public pages and search snippets only)

- **Directories and lists**: industry directories, association member lists, "top N companies" articles, platform customer/case-study pages, franchise location lists, review-site category pages (G2, Capterra), conference exhibitor lists. One fetch often yields 20 to 100 names.
- **Reddit**: WebSearch `site:reddit.com <pain phrase>` and `site:reddit.com <category> recommendation`; fetch the thread. Businesses named in threads (and businesses posting) are candidates. For B2C products, subreddits and active communities themselves are partner candidates.
- **Instagram**: WebSearch `site:instagram.com <role> <keyword>` (for example `site:instagram.com golf coach "online lessons"`). Use only what the search snippet shows: handle, bio line, follower count if present. Profile URL goes in `website` if there is no site.
- **LinkedIn**: WebSearch `site:linkedin.com/company <category> <country>` and `site:linkedin.com/in "<title>" "<category>"`. Use only the snippet: company name, tagline, location; person name and title. Never fetch LinkedIn pages.
- **Facebook**: WebSearch `site:facebook.com <category> <city>`; snippets only.
- **YouTube / podcasts**: WebSearch `site:youtube.com <topic> channel`; channel name and URL.
- **News and funding**: `<category> raises OR launches OR opens 2026`, local business news.
- **Job boards**: `"<role>" <category> job` reveals companies with the pain.

Rotate platforms and regions (North America, UK/Ireland, DACH, Nordics, Benelux, Southern Europe, Middle East, India, SE Asia, Australia/NZ, LatAm, Africa) so the list is global, unless the user restricted it.

## Steps

1. Read `data/<product>/icp.md`; run `python3 scripts/leads.py searches` and `python3 scripts/leads.py domains`.
2. Run 10 to 30 searches and fetch the richest list pages. Delegate fetches to parallel helpers when available; each helper returns a JSON list.
3. For each candidate record: `company`, `website` (or public profile URL), `industry` (segment name), `location`, `size` (if the snippet says), `contact_name` / `contact_role` only if printed in the snippet, `fit_score` as a rough estimate (30 to 60), `fit_reason` starting with `unverified:` and naming the source type, `signals` (what the snippet shows), `sources` (the list/thread/search-result URL), `stage: "candidate"`.
4. Save with `python3 scripts/leads.py add --file <batch.json>`. Log every query with `leads.py log-search`.
5. Report: candidates added per platform and per region, duplicates skipped, and the top 10 by estimated score. Suggest `/verify-candidates 20`.

## Rules

- Candidates still need a source URL. Snippet-only records cite the search-result page they came from.
- Never guess emails or names. Snippet text only.
- Do not fetch Instagram, Facebook or LinkedIn pages; they block automated reading and it would break the public-pages rule anyway.
- Mark every candidate `fit_reason` with `unverified:` so nobody mistakes it for a researched lead.
