# Member Engagement Explorer

A small internal website for browsing the League's quarterly member engagement
data: a leaderboard, per-credit-union profile pages, an "Awards" page
(league champion, most improved, category MVPs, asset-group champions, etc.),
and a Glossary page explaining what every scored item means, built from the
Q1 2026 finalized engagement dataset.

It's a static site: plain HTML/CSS/JS, no build step, no server-side code.
Everything runs in the browser and reads from `engagement.json`.

## Putting it on GitHub Pages

You don't need me (or anyone else) to have your GitHub login for this,
it's a few clicks in your own account:

1. On github.com, click **New repository**. Name it something like
   `engagement-explorer`. It can be **public or private**; see the note on
   access below before deciding.
2. Upload all the files in this folder (`index.html`, `styles.css`, `app.js`,
   `engagement.json`, `build_data.py`, this `README.md`) to that repo,
   either drag-and-drop in the GitHub web UI ("Add file → Upload files"), or
   `git push` if you're comfortable with git. Keep them all at the top level
   of the repo, no subfolders.
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

## Updating it next quarter

The site reads one file: `engagement.json`, sitting next to `index.html`.
To refresh it from a new quarterly export, run this with both files in the
same folder:

```
python3 build_data.py /path/to/next_quarter_export.xlsx engagement.json
```

This assumes the new export uses the same "Worksheet" tab layout as the
Q1 2026 file (same column order, header row 3, data starting row 6). If a
future export reorders columns or renames the tab, open `build_data.py` and
adjust the column indices at the top (the `CATS` list and the fixed indices
for charter/state/assets/CEO/etc.) to match. Requires `pip install openpyxl`.

The glossary (term definitions on the Glossary page and the hover/click
tooltips throughout the site) is hand-curated inside `build_data.py`. Look
for the `CATEGORIES` list near the bottom of the file. If a future quarter
renames or adds a scored item, add or update its entry there so the glossary
stays in sync; it won't pick up new items automatically.

Then re-upload the updated `engagement.json` to the GitHub repo (or
`git push` it). GitHub Pages picks up the change automatically, usually
within a minute.

## What's on each page

- **Leaderboard** (`#/`): every credit union, sortable by any column,
  filterable by asset group and state, with a quick search box. Click a row
  to open that CU's profile.
- **Credit union profile** (`#/cu/<charter>`): the same category breakdown,
  peer comparison, and activity detail used in the report-card mockups,
  now for every CU in the dataset. Any scored item with a known definition
  is underlined; hover for a quick tooltip, or click to jump straight to
  its full entry on the Glossary page.
- **Awards** (`#/awards`): league champion, most improved, steadiest,
  perfect-score club, asset-group champions, and a "category MVP" for each
  of the five engagement categories.
- **Glossary** (`#/glossary`): what every scored item means, grouped by
  category. Each term is tagged with where its definition comes from:
  confirmed against the League's official Definitions sheet, an educated
  guess based on how the item lines up with older documentation, or not
  documented anywhere we could find. That last group is worth a look,
  it's a real list of items nobody has ever written a definition for.

A couple of credit unions show a category total higher than that category's
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

One tradeoff worth knowing about: the "vs Q4 2025" figure on each profile
and the leaderboard still comes from the quarterly export as-is. That
export doesn't break Q4 down by category, so there's no way to subtract
Q4's Leadership points back out, meaning that comparison is now measuring
this quarter's 5-category total against last quarter's 6-category total.
It's the best signal available, but it's not a perfectly apples-to-apples
comparison anymore. Flag that if it comes up, and let me know if you'd
rather hide that column until a like-for-like Q4 number is available.
