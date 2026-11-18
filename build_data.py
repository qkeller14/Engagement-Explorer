import openpyxl, json, datetime, sys, os, re, argparse, warnings

# Usage:
#   python3 build_data.py <workbook.xlsx> [engagement.json] [--sheet NAME] [--compare-sheet NAME]
#                         [--compare-file OTHER.xlsx] [--final]
#
# Defaults: reads the "Source Data" tab (the League's running source data, which
# carries the newest financials and engagement activity) and compares it against
# the "Worksheet" tab in the same file (the last finalized quarter). If the
# workbook has no "Source Data" tab, it reads "Worksheet" and skips the comparison.
#
# Columns are found by their header names, not fixed positions, because the
# "Source Data" and "Worksheet" tabs don't line up (Source Data has an extra
# Part-Time Employees column, which shifts everything after it by one).
# The script stops with a clear error if an expected column can't be found.
#
# Run build_directory.py right after this one: this script rewrites
# engagement.json from scratch, which removes the Directory/Industry/Changes data.

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

ap = argparse.ArgumentParser()
ap.add_argument("workbook")
ap.add_argument("out", nargs="?", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "engagement.json"))
ap.add_argument("--sheet", default=None, help='tab to read (default: "Source Data" if present, else "Worksheet")')
ap.add_argument("--compare-sheet", default=None, help='tab holding the previous quarter (default: "Worksheet" when reading "Source Data")')
ap.add_argument("--compare-file", default=None, help="workbook holding the comparison tab (default: same workbook)")
ap.add_argument("--final", action="store_true", help='label the data as final rather than "preliminary" (Source Data is preliminary by default)')
args = ap.parse_args()

# The five scored categories, identified by their total column's header. Executive
# Leadership (3 points) was removed as a scored category in the report redesign, so
# the maximum is 28. Its columns are ignored even in tabs that still have them.
CATS = [
    # key, label, header of the category's total column, points possible
    ("advocacy", "Advocacy", "Advocacy Total", 9),
    ("compliance", "Compliance Support", "Compliance Support Total", 4),
    ("education", "Education & Professional Development", "Education & Professional Development Total", 3),
    ("communications", "Communications", "Total Communications", 7),
    ("collab", "Collaborative Events", "Collaborative Events Total", 5),
]
TOTAL_POSSIBLE = sum(c[3] for c in CATS)
assert TOTAL_POSSIBLE == 28

# Membership codes used in the "Member" column. No legend exists in the workbook;
# A-M is labeled the same way the roster file's "AM" code has been labeled on the site.
MEMBER_LABELS = {"M": "Member", "N-M": "Non-Member", "NM": "Non-Member", "A-M": "Associate Member", "AM": "Associate Member"}


def norm_header(h):
    return " ".join(str(h or "").replace("\xa0", " ").split())


def clean_str(v):
    if v is None:
        return None
    v = " ".join(str(v).replace("\xa0", " ").split())
    return v or None


def norm_name(s):
    s = re.sub(r"[^A-Za-z0-9]+", "", str(s or "")).upper()
    for suf in ("FEDERALCREDITUNION", "CREDITUNION", "FCU", "CU"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def clean_value(label, v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, datetime.datetime):
        return f"{v.month}/{v.day}/{v.year}"
    if isinstance(v, float) and "%" in label:
        return f"{round(v * 100)}%"
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1  # 0-based


def scored_columns(formula):
    """Which columns a total formula like '=SUM(K7:O7)+S7+U7+V7+W7' adds up.
    Returns a set of 0-based column indexes, or None if the cell isn't a formula."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return None
    cols = set()
    for a, b in re.findall(r"\$?([A-Z]{1,3})\$?\d+:\$?([A-Z]{1,3})\$?\d+", formula):
        cols.update(range(col_index(a), col_index(b) + 1))
    stripped = re.sub(r"\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+", "", formula)
    for a in re.findall(r"\$?([A-Z]{1,3})\$?\d+", stripped):
        cols.add(col_index(a))
    return cols


def period_from_header(h):
    m = re.search(r"(1st|2nd|3rd|4th)\s*Q[\s-]*(\d{4})", h, re.I)
    return f"Q{m.group(1)[0]} {m.group(2)}" if m else None


def read_tab(path, sheet):
    wb_v = openpyxl.load_workbook(path, data_only=True)
    if sheet not in wb_v.sheetnames:
        sys.exit(f'ERROR: no "{sheet}" tab in {os.path.basename(path)} (tabs: {wb_v.sheetnames})')
    ws = wb_v[sheet]
    wb_f = openpyxl.load_workbook(path, data_only=False)
    wsf = wb_f[sheet]

    top = list(ws.iter_rows(min_row=1, max_row=15, values_only=True))
    hdr_row = next((i + 1 for i, r in enumerate(top) if norm_header(r[0]) == "Charter #"), None)
    if not hdr_row:
        sys.exit(f'ERROR: couldn\'t find the "Charter #" header row in "{sheet}"')
    header = [norm_header(h) for h in top[hdr_row - 1]]

    # "Last Updated:" row above the header (Source Data has one), newest date wins
    as_of = None
    for r in top[: hdr_row - 1]:
        if norm_header(r[0]).lower().startswith("last updated"):
            dates = [v for v in r[1:] if isinstance(v, datetime.datetime)]
            if dates:
                as_of = max(dates).date().isoformat()

    def find(pred, what, start=0, end=None):
        for i in range(start, end if end is not None else len(header)):
            if header[i] and pred(header[i]):
                return i
        sys.exit(f'ERROR: couldn\'t find the "{what}" column in "{sheet}"')

    first12 = 12
    C = {
        "charter": find(lambda h: h == "Charter #", "Charter #"),
        "member": find(lambda h: h == "Member", "Member", end=first12),
        "state": find(lambda h: h == "State", "State", end=first12),
        "assets": find(lambda h: "Assets" in h, "Assets", end=first12),
        "members": find(lambda h: h.endswith("Members"), "Members", end=first12),
        "fte": find(lambda h: "Full-Time" in h or h.endswith("FTE"), "Full-Time Employees / FTE", end=first12),
        "ceo": find(lambda h: h == "CEO", "CEO", end=first12),
        "cu": find(lambda h: h == "Credit Union", "Credit Union", end=first12),
        "group": find(lambda h: h == "Asset Group", "Asset Group", end=first12),
    }
    pte = [i for i in range(first12) if "Part-Time" in header[i]]
    C["pte"] = pte[0] if pte else None
    financial_period = period_from_header(header[C["assets"]])

    data_rows = []
    for rn, r in enumerate(ws.iter_rows(min_row=hdr_row + 1, values_only=True), start=hdr_row + 1):
        if isinstance(r[C["charter"]], (int, float)):
            data_rows.append((rn, r))
    if not data_rows:
        sys.exit(f'ERROR: no data rows found in "{sheet}"')
    first_data_row = data_rows[0][0]

    # categories: items run from just after the previous boundary to the total column
    cats = []
    boundary = C["group"]
    for key, label, total_hdr, possible in CATS:
        t = find(lambda h, th=total_hdr: h.lower() == th.lower(), total_hdr, start=boundary + 1)
        item_cols = [i for i in range(boundary + 1, t) if header[i] and header[i].lower() != "open"]
        formula = wsf.cell(row=first_data_row, column=t + 1).value
        sc = scored_columns(formula)
        scored = set(item_cols) if sc is None else (sc & set(item_cols))
        cats.append({"key": key, "label": label, "total_col": t, "possible": possible,
                     "items": item_cols, "scored": scored, "formula": formula})
        boundary = t

    peer_cols = [i for i in range(boundary + 1, len(header)) if header[i] == "Peer Average"]
    ext_start = (peer_cols[0] + 1) if peer_cols else None
    last_hdr = max(i for i, h in enumerate(header) if h)

    return {"sheet": sheet, "header": header, "C": C, "cats": cats, "rows": data_rows,
            "ext_range": (ext_start, last_hdr) if ext_start else None,
            "financial_period": financial_period, "as_of": as_of}


def parse_records(tab):
    header, C, cats = tab["header"], tab["C"], tab["cats"]
    records, excluded, formula_mismatch = [], [], []
    for rn, r in tab["rows"]:
        cu = clean_str(r[C["cu"]])
        ag = r[C["group"]]
        if not cu:
            continue
        if ag is None or not isinstance(r[C["assets"]], (int, float)):
            excluded.append(f'{cu} (charter {int(r[C["charter"]])}): ' +
                            ("no asset group" if ag is None else "no assets reported"))
            continue
        out_cats = []
        for cat in cats:
            items = []
            for i in cat["items"]:
                lbl = header[i]
                v = clean_value(lbl, r[i])
                if v in (None, 0, ""):
                    continue
                it = {"label": lbl, "value": v}
                if i not in cat["scored"]:
                    it["scored"] = False
                items.append(it)
            actual = num(r[cat["total_col"]])
            check = sum(num(r[i]) for i in cat["scored"])
            oc = {"key": cat["key"], "label": cat["label"], "actual": actual,
                  "possible": cat["possible"], "items": items}
            if check != actual:
                # The workbook's total cell was overridden (e.g. a typed-in 0). The
                # score follows the workbook; the site notes the discrepancy.
                formula_mismatch.append(f'{cu}: {cat["label"]} total {actual} vs items {check}')
                oc["items_sum"] = check
            out_cats.append(oc)

        extended = []
        if tab["ext_range"]:
            a, b = tab["ext_range"]
            for i in range(a, b + 1):
                h = header[i]
                if not h or h in ("Open", "Open Community") or i >= len(r):
                    continue
                v = clean_value(h, r[i])
                if v in (None, 0, ""):
                    continue
                if h == "Permission Agreement Expiration Date":
                    h = "Permission Agmt Expires"
                extended.append({"label": h, "value": v})

        code = clean_str(r[C["member"]])
        records.append({
            "charter": int(r[C["charter"]]),
            "cu": cu,
            "member_code": code,
            "member_status": MEMBER_LABELS.get((code or "").upper(), code),
            "state": clean_str(r[C["state"]]),
            "assets": r[C["assets"]],
            "members": r[C["members"]] if isinstance(r[C["members"]], (int, float)) else None,
            "fte": r[C["fte"]] if isinstance(r[C["fte"]], (int, float)) else None,
            "pte": (r[C["pte"]] if isinstance(r[C["pte"]], (int, float)) else None) if C["pte"] is not None else None,
            "ceo": clean_str(r[C["ceo"]]),
            "asset_group": int(ag),
            # Score = sum of the five category totals (Executive Leadership excluded),
            # not the workbook's own grand-total column, whose header can be stale.
            "total": sum(c["actual"] for c in out_cats),
            "categories": out_cats,
            "extended": extended,
        })
    return records, excluded, formula_mismatch


# ---------------- current data ----------------
wb_names = openpyxl.load_workbook(args.workbook, read_only=True).sheetnames
sheet = args.sheet or ("Source Data" if "Source Data" in wb_names else "Worksheet")
tab = read_tab(args.workbook, sheet)
records, excluded, mismatches = parse_records(tab)

# ---------------- comparison (previous quarter) ----------------
compare_sheet = args.compare_sheet
if compare_sheet is None and sheet == "Source Data" and not args.compare_file and "Worksheet" in wb_names:
    compare_sheet = "Worksheet"
compare_label = None
compare_matched_by_name = []
if compare_sheet:
    ctab = read_tab(args.compare_file or args.workbook, compare_sheet)
    prev_records, _, _ = parse_records(ctab)
    compare_label = ctab["financial_period"]
    prev_by_charter = {p["charter"]: p for p in prev_records}
    prev_by_name = {}
    for p in prev_records:
        prev_by_name.setdefault(norm_name(p["cu"]), []).append(p)
    for d in records:
        p = prev_by_charter.get(d["charter"])
        if not p:
            cands = prev_by_name.get(norm_name(d["cu"]), [])
            if len(cands) == 1:
                p = cands[0]
                compare_matched_by_name.append(f'{d["cu"]}: charter {p["charter"]} -> {d["charter"]}')
        d["prev_total"] = p["total"] if p else None
        d["variance"] = (d["total"] - p["total"]) if p else None
        if p and norm_name(p["cu"]) != norm_name(d["cu"]):
            d["prev_name"] = p["cu"]  # renamed since the comparison quarter (same charter)
else:
    for d in records:
        d["prev_total"] = None
        d["variance"] = None

# ---------------- ranks, peer averages, tiers ----------------
by_group = {}
for d in records:
    by_group.setdefault(d["asset_group"], []).append(d)
for g, items in by_group.items():
    ranked = sorted(items, key=lambda d: d["total"], reverse=True)
    for i, d in enumerate(ranked, start=1):
        d["rank"] = i
        d["group_n"] = len(ranked)
    lo, hi = min(d["assets"] for d in items), max(d["assets"] for d in items)
    group_avg = round(sum(d["total"] for d in items) / len(items), 1)
    for d in items:
        d["group_min"], d["group_max"], d["peer_avg"] = lo, hi, group_avg

for i, d in enumerate(sorted(records, key=lambda d: d["total"], reverse=True), start=1):
    d["overall_rank"] = i


def tier(total):
    # Cutoffs rescaled from the original 21/31 and 12/31 now that the max is 28.
    if total >= 19: return "high"
    if total >= 11: return "mod"
    return "low"


tier_counts = {"high": 0, "mod": 0, "low": 0}
for d in records:
    d["tier"] = tier(d["total"])
    tier_counts[d["tier"]] += 1

n = len(records)
league = {
    "quarter": tab["financial_period"],
    "preliminary": sheet == "Source Data" and not args.final,
    "as_of": tab["as_of"],
    "last_updated": datetime.date.today().isoformat(),
    "source_file": os.path.basename(args.workbook),
    "source_sheet": sheet,
    "compare_label": compare_label,
    "total_cus": n,
    "total_possible": TOTAL_POSSIBLE,
    "tier_counts": tier_counts,
    "league_avg": round(sum(d["total"] for d in records) / n, 2),
    "category_avgs": {key: round(sum(next(c["actual"] for c in d["categories"] if c["key"] == key) for d in records) / n, 2)
                      for key, *_ in CATS},
    "category_meta": [{"key": k, "label": l, "possible": p} for k, l, _h, p in CATS],
    "asset_groups": {g: {"n": len(items), "min": min(d["assets"] for d in items), "max": max(d["assets"] for d in items)}
                     for g, items in by_group.items()},
}

# --- Glossary: hand-curated definitions, cross-referenced against the
# Definitions tab and the current column labels. Update this list if items
# get renamed or added; it does not regenerate automatically. The site matches
# terms with or without a leading year, so "REACH" covers "2026 REACH".
CATEGORIES = [
  {
    "key": "advocacy", "label": "Advocacy", "possible": 9,
    "description": "Political and regulatory engagement: contributions, advocacy events, and direct contact with regulators or elected officials. Per the workbook's Advocacy Total formula, the score counts eight items; the three event columns (Government Relations Rally, Government Affairs Conference, Hike the Hill) count through GAC & GRR & HTH, and Advocacy Workshops are tracked but not scored.",
    "terms": [
      {"term": "Political Corporate Contribution", "source": "definitions_sheet",
       "definition": "Any corporate PAC contribution over the past 12 months. Data provided quarterly from Advocacy and through the dues process."},
      {"term": "Political Individual Contribution", "source": "definitions_sheet",
       "definition": "Any individual PAC contribution over the past 12 months. Pulled quarterly in Excel and logged as contributions occur."},
      {"term": "Permission Agreement", "source": "definitions_sheet",
       "definition": "Whether the CU has a current signed permission agreement on file. Individual signed forms are provided as received."},
      {"term": "Project Zip Code", "source": "definitions_sheet",
       "definition": "Whether Project Zip Code data was updated within the past 12 months. Pulled quarterly from CUNA/America's Credit Unions in Excel format."},
      {"term": "Connect For The Cause", "source": "definitions_sheet",
       "definition": "Any active participation in Connect For The Cause over the past 12 months, pulled from VoterVoice."},
      {"term": "Government Relations Rally", "source": "definitions_sheet",
       "definition": "Attendance at the Government Relations Rally (GRR). Shown for detail only: it counts toward the score through GAC & GRR & HTH, not separately."},
      {"term": "Government Affairs Conference", "source": "definitions_sheet",
       "definition": "Attendance at the Government Affairs Conference (GAC). Shown for detail only: it counts toward the score through GAC & GRR & HTH, not separately."},
      {"term": "Hike the Hill", "source": "definitions_sheet",
       "definition": "Attendance at Hike the Hill (HTH). Shown for detail only: it counts toward the score through GAC & GRR & HTH, not separately."},
      {"term": "GAC & GRR & HTH", "source": "definitions_sheet",
       "definition": "Attendance at GAC, GRR, and/or Hike the Hill within the past 12 months (originally listed as 'GRR / GAC / Hike The Hill'), pulled from Cvent and/or provided by Advocacy. This is the scored item for those three events and can be more than 1."},
      {"term": "Advocacy Workships", "source": "undocumented",
       "definition": "Not in the Definitions sheet (also a likely typo for \"Advocacy Workshops\" in the source column header). Tracked, but not counted in the Advocacy score: the workbook's Advocacy Total formula leaves this column out."},
      {"term": "Regulatory Activities & Events", "source": "definitions_sheet",
       "definition": "Attendance at regulatory activities/events within the past 12 months. Sourced from the Advocacy Blog / Mail Chimp and/or provided directly by Advocacy staff."},
      {"term": "Elected Officials Meetings & Fundraisers", "source": "definitions_sheet",
       "definition": "Attendance at elected-official activities/events (in-district meetings, fundraisers, official visits) within the past 12 months."},
    ],
  },
  {
    "key": "compliance", "label": "Compliance Support", "possible": 4,
    "description": "Use of the League's compliance tools and support channels, all sourced from ViClarity.",
    "terms": [
      {"term": "Hot Line Calls", "source": "definitions_sheet",
       "definition": "Participation in the Compliance Hot Line (phone & email) within the past 12 months. Provided monthly by ViClarity."},
      {"term": "Policy Pro", "source": "definitions_sheet",
       "definition": "Participation/log-ins in Policy Pro within the past 12 months. Provided monthly by ViClarity."},
      {"term": "Infosight", "source": "definitions_sheet",
       "definition": "Participation/hits on InfoSight within the past 12 months. Provided monthly by ViClarity."},
      {"term": "ViClarity Contracted Services", "source": "inferred",
       "definition": "Not directly defined under this name. The Definitions sheet lists a fourth ViClarity product, \"Policy Works Comply Site,\" that isn't separately tracked anywhere else in the current data; this may be what \"ViClarity Contracted Services\" is meant to capture, but that's an educated guess, not a confirmed definition. Flagged in the redesign discussion as needing a clear definition either way."},
    ],
  },
  {
    "key": "education", "label": "Education & Professional Development", "possible": 3,
    "description": "Use of League training content and structured learning programs. Called \"Education & Meetings\" in the older Definitions sheet.",
    "terms": [
      {"term": "Online Educational Content", "source": "inferred",
       "definition": "Likely the successor to \"Webinars\" in the Definitions sheet (participation in eTrain/Content Management webinars within the past 12 months), not confirmed under the current name. Note: this exact label is reused under Communications for a different measure (email opens); see the Communications section."},
      {"term": "Programs & Series", "source": "undocumented",
       "definition": "Not in the Definitions sheet. Breaks down in the extended detail into Solutions Webinars, Impact Power Hour, Ignite, and Compliance Essentials."},
      {"term": "Certificate Programs", "source": "undocumented",
       "definition": "Not in the Definitions sheet. Breaks down in the extended detail into Financial Counselors Academy, Next Gen, and Succession Planning."},
    ],
  },
  {
    "key": "communications", "label": "Communications", "possible": 7,
    "description": "Open/engagement activity across the League's member email channels. Called \"News\" in the older Definitions sheet.",
    "terms": [
      {"term": "CU Weekly", "source": "definitions_sheet",
       "definition": "Open activity on the CU Weekly newsletter within the past 12 months, pulled weekly from Mail Chimp."},
      {"term": "Online Educational Content", "source": "undocumented",
       "definition": "Not in the Definitions sheet under this name. Tracked here as an email-open count, distinct from the eTrain consumption measure of the same name under Education & Professional Development. Same label, two different things; worth renaming one of them."},
      {"term": "Advocacy Communications", "source": "inferred",
       "definition": "Possible successor to \"Advocacy Blog\" in the Definitions sheet, not confirmed under the current name."},
      {"term": "Desk of CEO & MFL", "source": "inferred",
       "definition": "\"MFL\" = Messages From the League. Possible successor to \"Desk of Diana\" in the Definitions sheet (the label has already been updated once from a specific name to \"CEO\"; see the naming-drift discussion from the report redesign review)."},
      {"term": "League Business Partner Communications", "source": "undocumented",
       "definition": "Not in the Definitions sheet."},
      {"term": "League Education & Events", "source": "undocumented",
       "definition": "Not in the Definitions sheet."},
      {"term": "Compliance Communications", "source": "undocumented",
       "definition": "Not in the Definitions sheet."},
    ],
  },
  {
    "key": "collab", "label": "Collaborative Events", "possible": 5,
    "description": "Participation in League-hosted events, networks, and CEO-level gatherings.",
    "terms": [
      {"term": "REACH", "source": "definitions_sheet",
       "definition": "Participation in REACH within the past 12 months, pulled from Cvent as events occur."},
      {"term": "Collaborative Events:", "source": "inferred",
       "definition": "Generic catch-all for collaborative events; possibly related to \"Communities\" (Breezio) in the Definitions sheet, unconfirmed."},
      {"term": "Networks", "source": "inferred",
       "definition": "Possibly related to \"Communities\" (Breezio) in the Definitions sheet. Breaks down in the extended detail into Shapiro Network, Financial Counselors, Mid CU, and PR & Media Relations. Not confirmed under the current name."},
      {"term": "CEO Calls", "source": "definitions_sheet",
       "definition": "Current participant in CEO Calls, pulled from Cvent/Content Manager or sign-up sheets as events occur."},
      {"term": "CEO Roundtable", "source": "definitions_sheet",
       "definition": "Current participant in CEO Roundtables (SRT, WSRT, etc.), pulled from Cvent/Content Manager or sign-up sheets as events occur."},
    ],
  },
]

out = {"league": league, "cus": records, "glossary": CATEGORIES}
with open(args.out, "w") as f:
    json.dump(out, f, default=str)

# ---------------- report ----------------
print(f'Read "{sheet}" from {os.path.basename(args.workbook)}: {n} credit unions, period {league["quarter"]}'
      f'{" (preliminary)" if league["preliminary"] else ""}, data as of {league["as_of"] or "n/a"}')
for cat in tab["cats"]:
    not_scored = [tab["header"][i] for i in cat["items"] if i not in cat["scored"]]
    print(f'  {cat["label"]}: {len(cat["scored"])} scored items' + (f'; not scored: {not_scored}' if not_scored else ""))
if excluded:
    print("Excluded (missing data):")
    for e in excluded:
        print("  " + e)
if mismatches:
    print(f"WARNING: {len(mismatches)} category totals don't equal the sum of their scored items:")
    for m in mismatches[:20]:
        print("  " + m)
if compare_label:
    have = sum(1 for d in records if d["prev_total"] is not None)
    print(f'Compared against "{compare_sheet}" ({compare_label}): {have} of {n} matched')
    for m in compare_matched_by_name:
        print("  matched by name (charter number changed): " + m)
print(f"League average {league['league_avg']} / {TOTAL_POSSIBLE}; tiers {tier_counts}")
