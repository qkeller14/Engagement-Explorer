# Member Engagement Explorer

A small internal website for browsing the League's quarterly member engagement
data — a leaderboard, per-credit-union profile pages, and an "Awards" page
(league champion, most improved, category MVPs, asset-group champions, etc.),
built from the Q1 2026 finalized engagement dataset.

It's a static site: plain HTML/CSS/JS, no build step, no server-side code.
Everything runs in the browser and reads from `data/engagement.json`.

## Putting it on GitHub Pages

You don't need me (or anyone else) to have your GitHub login for this —
it's a few clicks in your own account:

1. On github.com, click **New repository**. Name it something like
   `engagement-explorer`. It can be **public or private** — see the note on
   access below before deciding.
2. Upload all the files in this folder (`index.html`, `styles.css`, `app.js`,
   the `data/` folder, this `README.md`) to that repo — either drag-and-drop
   in the GitHub web UI ("Add file → Upload files"), or `git push` if you're
   comfortable with git.
3. In the repo, go to **Settings → Pages**. Under "Build and deployment,"
   set Source to **Deploy from a branch**, branch `main`, folder `/ (root)`.
   Save.
4. GitHub gives you a URL like `https://<your-username>.github.io/engagement-explorer/`
   within a minute or two. That's the site — same idea as your friend's
   fantasy football page.

## About access — read this before sharing the link

You said this should stay internal to League staff. Two things to know:

- **GitHub Pages URLs are public by default.** Anyone with the exact link
  can open it, even from a "private" repo, unless your GitHub org is on a
  paid plan that supports private Pages. A public repo's Pages site is
  *always* public.
- **The passphrase gate in this site (`app.js`, `PASSPHRASE` near the top)
  is a soft deterrent, not real security.** It stops someone from casually
  landing on the page, but the data (`data/engagement.json`) is still a
  plain file anyone with the URL could fetch directly, gate or no gate.
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

The site reads one file: `data/engagement.json`. To refresh it from a new
quarterly export:

```
cd scripts
python3 build_data.py /path/to/next_quarter_export.xlsx ../data/engagement.json
```

This assumes the new export uses the same "Worksheet" tab layout as the
Q1 2026 file (same column order, header row 3, data starting row 6). If a
future export reorders columns or renames the tab, open `build_data.py` and
adjust the column indices at the top (the `CATS` list and the fixed indices
for charter/state/assets/CEO/etc.) to match. Requires `pip install openpyxl`.

Then re-upload the updated `data/engagement.json` to the GitHub repo (or
`git push` it) — GitHub Pages picks up the change automatically, usually
within a minute.

## What's on each page

- **Leaderboard** (`#/`) — every credit union, sortable by any column,
  filterable by asset group and state, with a quick search box. Click a row
  to open that CU's profile.
- **Credit union profile** (`#/cu/<charter>`) — the same category breakdown,
  peer comparison, and activity detail used in the report-card mockups,
  now for every CU in the dataset.
- **Awards** (`#/awards`) — league champion, most improved, steadiest,
  perfect-score club, asset-group champions, and a "category MVP" for each
  of the six engagement categories.

A couple of credit unions show a category total higher than that category's
usual point cap (flagged in gold on their profile and on the Awards page) —
that's not a bug in the site, it's because a few items in the source data
(like committee seats) are stored as running counts rather than a simple
yes/no, so they can add up past the typical maximum. Worth a mention in the
report redesign discussion, since it's the same kind of point-total question
raised about the Leadership category.
