# Member Engagement Explorer

A small internal website for browsing the League's quarterly member engagement
data: a leaderboard, per-credit-union profile pages, an "Awards" page
(league champion, most improved, category MVPs, asset-group champions, etc.),
a Glossary page explaining what every scored item means, and a Directory,
Industry Snapshot, and Changes log built from the League's roster/reference
workbook. Built from the Q1 2026 finalized engagement dataset.

It's a static site: plain HTML/CSS/JS, no build step, no server-side code.
Everything runs in the browser and reads from `engagement.json`.

## Putting it on GitHub Pages

You don't need me (or anyone else) to have your GitHub login for this,
it's a few clicks in your own account:

1. On github.com, click **New repository**. Name it something like
   `engagement-explorer`. It can be **public or private**; see the note on
   access below before deciding.
2. Upload all the files in this folder (`index.html`, `styles.css`, `app.js`,
   `engagement.json`, `build_data.py`, `build_directory.py`, `build_summary.py`,
   `reach.html`, `participation.html`, `usage.html`, `ai-summary.html`, this `README.md`)
   to that repo, either drag-and-drop in the GitHub web UI ("Add file →
   Upload files"), or `git push` if you're comfortable with git. Keep them
   all at the top level of the repo, no subfolders. (The source workbooks,
   `data.xlsx` and `Master_List.xlsx`, are inputs to the two build scripts,
   not part of the site itself, so don't upload those.)
3. In the repo, go to **Settings → Pages**. Under "Build and deployment,"
   set Source to **Deploy from a branch**, branch `main`, folder `/ (root)`.
   Save.
4. GitHub gives you a URL like `https://<your-username>.github.io/engagement-explorer/`
   within a minute or two. That's the site, same idea as your friend's
   fantasy football page.

## About access: read this before sharing the link

You said this should stay internal to League staff. Two things to know:

- **GitHub Pages URLs are public by default.** Anyone with the exact link
  can open it, even from a "private" repo, unless your GitHub org is on a
  paid plan that supports private Pages. A public repo's Pages site is
  *always* public.
- **The passphrase gate in this site (`app.js`, `PASSPHRASE` near the top)
  is a soft deterrent, not real security.** It stops someone from casually
  landing on the page, but the data (`engagement.json`) is still a plain
  file anyone with the URL could fetch directly, gate or no gate.
  `index.html` also has `<meta name="robots" content="noindex, nofollow">`
  so search engines shouldn't index it, but that's a request, not an
  enforcement.

If you want real access control (only League staff can see it, full stop),
the cleaner options are: host it on something behind your existing staff
login (an internal SharePoint/Google Site embed, an intranet server), or
ask IT whether your GitHub org has private Pages available. Happy to help
adapt these files to either of those if you want to go that route instead.

Before sharing the link with anyone, change the passphrase in `app.js`
(the `PASSPHRASE` constant near the top of the file) to something not in
this README.

## Updating the data

The site reads one file: `engagement.json`, sitting next to `index.html`.
Rebuilding it takes two commands, run in this folder (requires
`pip install openpyxl`):

```
python3 build_data.py "path/to/Member Engagement workbook.xlsx" engagement.json
python3 build_directory.py path/to/Master_List.xlsx engagement.json
```

If you don't have a newer Master List, use this second command instead. It
re-uses the roster data from the copy of `engagement.json` that's currently
published (keep a copy of it before running `build_data.py`):

```
python3 build_directory.py --carry-from old_engagement.json engagement.json
```

Order matters: `build_data.py` rewrites `engagement.json` from scratch, which
removes the Directory/Industry/Changes data, and `build_directory.py` adds it
back. Then upload the new `engagement.json` to the GitHub repo.

### Which tab of the engagement workbook is used

- By default `build_data.py` reads the **"Source Data"** tab. That's the
  League's running source data: the newest financials (assets, members,
  full-time and part-time staff, asset group) and engagement activity, with
  a "Last Updated" row. It compares those scores against the **"Worksheet"**
  tab in the same file, which holds the last finalized quarter.
- The period label comes from the assets column header (e.g. "2ndQ 2026
  Assets" becomes "Q2 2026"). Data from the "Source Data" tab is labeled
  **preliminary** until that quarter is finalized; add `--final` to drop
  the label.
- To build from a finalized "Worksheet" tab instead: `--sheet Worksheet`.
  To compare against a tab in a different file:
  `--compare-file older.xlsx --compare-sheet Worksheet`.
- Columns are found by their header names, so the "Source Data" and
  "Worksheet" layouts (which don't line up column-for-column) both work.
  If a header gets renamed, the script stops and says which column it
  couldn't find.

### How scores are calculated

- Each category's points come from the workbook's own total column for that
  category; the overall score is the sum of the five (28 possible).
- Which checklist items count is read from the workbook's total formulas.
  In Advocacy, the formula counts eight items: the three event columns
  (Government Relations Rally, Government Affairs Conference, Hike the Hill)
  count through "GAC & GRR & HTH", and "Advocacy Workships" is tracked but
  not counted. The site shows those four items marked "not counted" so each
  category's list adds up to its score.
- If a total cell was typed over (it doesn't match its items), the site
  shows the workbook's number and notes the difference on that profile.
  The build prints every such case. As of this build there's one: Navy FCU's
  Advocacy total is 0 although two scored items are marked.
- Rows with no assets reported or no asset group are left off (they can't
  be placed in a peer group). The build prints which ones.

### The "Site Last Refreshed" date

The badge in the header ("Site Last Refreshed Nov 18, 2026") is the date
`build_data.py` was last run, i.e. when the site's data was last rebuilt.
Hover over it to see the date the workbook itself was last updated (the
newest date in the "Source Data" tab's "Last Updated" row) and the source
file. The footer shows both dates and appears on printed/PDF pages. Nothing
to edit by hand.

### Glossary

The glossary (Glossary page and the hover tooltips) is hand-curated inside
`build_data.py`, in the `CATEGORIES` list near the bottom. If an item is
renamed or added, update its entry there. Terms match with or without a
leading year, so the "REACH" entry also covers "2026 REACH".

## Directory / Industry / Changes data (the Master List)

The Directory, Industry Snapshot, and Changes pages, plus the "Organization
& Contact" panel on each CU's profile, come from the League's roster
workbook (the "Master List"), which updates on its own schedule.

`build_directory.py` expects the current Master List's sheet names and
layout (`Credit Unions + CEO List (All 3`, `League Membership Status (Dues)`,
`CEO Transitions`, `Mergers`, `Charter Changes`, `Name Changes`,
`Financial Snapshot`).

**When the two sources disagree**, the script prints every case, and:

- The engagement workbook wins for anything it has: name, CEO, member
  status, financials. The roster fills in contact info, HQ, county,
  district, charter type, chapter, branches, and CDFI/low-income flags.
- Exception for CEOs: if the roster's dated **CEO Transitions** log names a
  different CEO than the engagement workbook, the log wins, and the profile
  notes what the workbook said. (The workbook's CEO column has lagged
  behind documented transitions.)
- If the roster's CEO is a different person than the CEO shown on the site,
  the roster's email and phone are labeled "on file for [that person]"
  rather than presented as the current CEO's contact info.
- Converted charters: several CUs converted from state to federal charters
  (they're in the Charter Changes log) and appear in the engagement
  workbook under their new charter numbers (e.g. 24980-24993), while the
  roster still lists the old ones. They're matched by name, and the
  Directory links them to the right profile. Updating those charter numbers
  in the roster would remove the need for the name match.

**Two things left out on purpose:**

- **The "Risk Report" tab isn't pulled in.** It's a per-CU composite risk
  score and trend over the last six quarters, more like supervisory data
  than something to publish, even to a soft-gated internal site.
- **Branch-level addresses (the "HQ + Branch Locations" tab, ~1,745 rows)
  aren't included.** That sheet only has a credit union name to key off of,
  no charter number, and some names are similar enough that automatic
  matching risked attaching a branch to the wrong CU.

## Plain data summary for AI tools (ai-summary.html)

The interactive pages draw their numbers with JavaScript, so AI tools that
read a link (like Claude's web fetch) only see an empty page. `ai-summary.html`
is a plain, static page with the same key numbers as simple tables: service
usage by size tier and by membership status, volume by tier, engagement by
tier, initiative participation, and the top 5 on each activity measure. The same
text is also built into `index.html`, `usage.html`, and `participation.html`
(hidden from people and removed as soon as the page loads), so pasting any of
those links into an AI tool works too. `reach.html` carries its own text
summary of REACH registrant counts by role, state, city, and credit union,
with no names or emails. It has no contact
details and no PAC dollar amounts, and like `engagement.json` it opens
without the passphrase for anyone with the link.

Regenerate it after any data refresh (after `build_data.py` and
`build_directory.py`); this also refreshes the hidden text in the other pages:

```
python3 build_summary.py
```

## Service Usage tab (usage.html)

Who uses League services powered by Fuel, by credit union size, built to
tell the utilization story behind the "How credit unions use League
services" report:

- A heatmap of the share of each asset tier using each service (compliance
  hotline, InfoSight, PolicyPro, ViClarity services, online education,
  eTrain, programs and series, Compliance Essentials, certificate programs,
  Financial Counselors Academy, CEO calls, Local Networks, Shapiro Network,
  CEO roundtables, REACH, Connect for the Cause, GAC/GRR/Hike the Hill).
  Click any cell for the credit unions using and not using that service,
  with a "copy names" button for outreach lists.
- Volume by tier (total and per user), engagement scores by tier on the
  site's 28-point basis, and four headline figures computed from the data.
- Members by default; associate members, non-members, or everyone with one
  click. "Copy table" puts the tier table on the clipboard for Excel or
  slides, and there's a Print / PDF button.

Tiers use the report's asset cutoffs (under $57M, $58M-$274M, $275M-$1.24B,
$1.27B+), split at the midpoints and applied to current assets. Like the
Participation tab, it reads `engagement.json` directly and needs no rebuild
when the data is refreshed. If a measure is renamed in a future workbook,
update its name in the SERVICES list in the page source (ask Claude to
rebuild `usage.html`).

## Participation tab (participation.html)

A leaderboard of how many of the 27 scored initiatives each credit union has
completed: headline cards, search, asset-size / member-status / category /
status filters, sorting by rank, name, category, or any single initiative,
gold/silver/bronze for the top three ranks, an expandable row showing what's
done and what's missing, and a "Copy summary" button that puts a short
text summary of the top performers on the clipboard.

It reads `engagement.json` directly, so it updates automatically whenever the
data is refreshed (no separate rebuild). It needs the `initiatives` list that
the current `build_data.py` writes into `engagement.json`.

A second view, **Activity leaderboards** (`participation.html#activity`,
also linked from each profile's "Extended Activity Detail" panel), ranks
credit unions on each of the 41 numeric measures in the extended activity
detail (PAC dollars, hot line calls, email opens, training registrations,
event attendance, CEO call rate, and so on), grouped by section. You can
filter by asset size and member status, switch between top 5 and top 10,
expand any board to the full list, "spotlight" one credit union to see where
it ranks on every board, and copy a top-3 summary. Measures where every
participant has the same value (e.g. attended once) list who took part
instead of ranking them. Dates and text fields aren't ranked. The list of
measures comes from `build_data.py` (`extended_metrics` in engagement.json).

- **Completed** = any participation recorded for that item (a number above
  zero, Yes/True, or a date).
- **Rank** = initiatives completed, then engagement score; identical results
  share a rank, so a few positions differ from the main Leaderboard (which
  ranks by score alone).
- **Needs follow-up** = under 40% of initiatives, in line with the
  "Low Engagement" tier (under 11 of 28 points).

## REACH 2026 tab (reach.html)

The "REACH 2026" tab opens `reach.html`, an attendee explorer: a map of
attendees by credit union HQ city, headline numbers, filters (search, role
group, location, registration type), a sortable attendee table, and an
"Export filtered CSV" button for follow-up lists.

**The attendee list is built into `reach.html`**, so it shows up as soon as
someone opens the tab. That includes names, titles, and emails, and like the
rest of the site the file is reachable by anyone who has the link (the
passphrase is only a soft gate). Take `reach.html` down from the repo once the
list is no longer needed.

To update it with a newer attendee export, send the file to Claude to rebuild
`reach.html` (it bundles the dashboard code, which isn't kept in this repo).

How the dashboard prepares the data:

- **Map location** is each credit union's HQ city from the League roster
  (built into the page). If a credit union isn't in the roster, the
  attendee's work city from the spreadsheet is used.
- **Role groups** come from job titles: C-suite = CEO, President, or any
  "Chief … Officer" title; VP / SVP includes EVP and AVP; Board / Volunteer
  covers board, supervisory committee, chair, treasurer, and a bare
  "Director" title.
- **Credit unions represented** merges spelling variants and doesn't count
  vendors, foundations, or League staff.
- Note rows at the bottom of the spreadsheet are skipped.
- The map background (state and California/Nevada county outlines, U.S.
  Census boundaries) is built into the page, so it needs no map service,
  account, or API key.

## What's on each page

- **Leaderboard** (`#/`): every credit union, sortable by any column,
  filterable by asset group, state, and member status (non-members and
  associate members are tracked too, and carry a badge), with a quick
  search box and a "vs Q1" change column. Click a row to open that CU's
  profile.
- **Credit union profile** (`#/cu/<charter>`): the same category breakdown,
  peer comparison, and activity detail used in the report-card mockups,
  now for every CU in the dataset, with assets, members, full-time and
  part-time staff as of the latest quarter. Any item with a known
  definition is underlined; hover for a quick tooltip, or click to jump
  straight to its full entry on the Glossary page.
- **Awards** (`#/awards`): league champion, most improved, steadiest,
  perfect-score club, asset-group champions, and a "category MVP" for each
  of the five engagement categories.
- **Glossary** (`#/glossary`): what every scored item means, grouped by
  category. Each term is tagged with where its definition comes from:
  confirmed against the League's official Definitions sheet, an educated
  guess based on how the item lines up with older documentation, or not
  documented anywhere we could find. That last group is worth a look,
  it's a real list of items nobody has ever written a definition for.
- **Directory** (`#/directory`): every credit union in the Master List
  (319 entries, a superset of the 260 in the engagement data), with CEO,
  phone, HQ, charter type, member status, and branch count. Sortable and
  searchable like the leaderboard; rows for CUs also in the engagement
  data link through to their full profile.
- **Industry Snapshot** (`#/industry`): US-wide vs. California credit union
  industry benchmarks (counts, scale, and key ratios) as of Q4 2025, so
  the league's own numbers have something external to compare against.
- **Changes** (`#/changes`): a running log pulled from the Master List, CEO
  transitions, mergers, charter conversions, and name changes, newest
  first.
- **CU profile "Organization & Contact" panel**: CEO email/phone, HQ
  address, county, congressional district, charter type, chapter, member
  status, branch count, CDFI and low-income designations, and a "Formerly
  ___" badge for CUs that have changed their name. Populated from the
  Master List for any CU it could be matched to.

Some credit unions can show a category total higher than that category's
usual point cap (flagged in gold on their profile and on the Awards page).
That's not a bug in the site, it's because a few items in the source data
(like GAC & GRR & HTH attendance) are stored as running counts rather than
a simple yes/no, so they can add up past the typical maximum. Worth a
mention in the report redesign discussion.

## Executive Leadership category (removed)

As of this update, Executive Leadership is no longer a scored category.
Committee Seat, America's Credit Unions Committees, and Voted in 2025 League
Elections have been pulled out of every CU's checklist, meters, and the
Glossary, and every score, tier, rank, and peer average on the site is
recalculated out of 28 points instead of 31.

The "vs Q1" comparison is like-for-like: both quarters are scored the same
way, on the five remaining categories out of 28 points.
