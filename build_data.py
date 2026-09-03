import openpyxl, json, datetime, sys, os

# Usage: python3 build_data.py [path/to/quarterly_export.xlsx] [path/to/output.json]
# Defaults assume everything lives in one flat folder (matching the live GitHub
# Pages repo layout): run this next to the quarterly xlsx export, and it writes
# straight into ./engagement.json (what index.html fetches) in the same folder.
IN_PATH = sys.argv[1] if len(sys.argv) > 1 else "data.xlsx"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "engagement.json")

wb = openpyxl.load_workbook(IN_PATH, data_only=True)
# IMPORTANT: this assumes the same "Worksheet" tab layout used for Q1 2026:
# same column order, same header row (row 3), same data start row (row 6).
# If a future quarter's export reorders or renames columns, update the CATS
# ranges and the fixed column indices below (charter/state/assets/etc.) to match.
ws = wb["Worksheet"]
rows = list(ws.iter_rows(min_row=6, max_row=ws.max_row, values_only=True))
header = list(ws.iter_rows(min_row=3, max_row=3, values_only=True))[0]

CATS = [
    ("advocacy", "Advocacy", 9, 21, 9, 22),
    ("compliance", "Compliance Support", 23, 27, 4, 28),
    ("education", "Education & Professional Development", 29, 32, 3, 33),
    ("communications", "Communications", 34, 40, 7, 41),
    ("collab", "Collaborative Events", 42, 47, 5, 48),
    # Executive Leadership (was columns 49-52, category total column 53, 3 points)
    # was removed as a scored category per the report redesign decision. Total
    # possible is now 28, not 31. Do not re-add without also revisiting q1_total
    # and peer_avg below, which are computed from the categories that remain.
]
TOTAL_POSSIBLE = sum(c[4] for c in CATS)

def clean_label(s):
    return " ".join(s.split()).strip()

def clean_value(label, v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%-m/%-d/%Y")
    if isinstance(v, float) and "%" in label:
        return f"{round(v * 100)}%"
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v

records = []
for r in rows:
    cu = r[7]
    ag = r[8]
    if not cu or ag is None:
        continue
    if not isinstance(r[3], (int, float)):
        continue
    cats = []
    for key, label, start, end, possible, total_idx in CATS:
        items = []
        for idx in range(start, end + 1):
            h = header[idx]
            v = r[idx]
            if not h or "OPEN" in str(h).upper():
                continue
            if v in (None, 0, ""):
                continue
            lbl = clean_label(str(h))
            items.append({"label": lbl, "value": clean_value(lbl, v)})
        cats.append({"key": key, "label": label, "actual": r[total_idx] or 0, "possible": possible, "items": items})

    extended = []
    for idx in range(58, 116):
        h = header[idx]
        v = r[idx] if idx < len(r) else None
        if not h:
            continue
        hl = clean_label(str(h))
        if hl in ("Advocacy", "Compliance", "Communications", "Collaborative Events", "Open", "Open Community"):
            continue
        if v in (None, 0, ""):
            continue
        if hl == "Permission Agreement Expiration Date":
            hl = "Permission Agmt Expires"
        extended.append({"label": hl, "value": clean_value(hl, v)})

    # q1_total is the sum of the category actuals above (not the workbook's own
    # "2026 Q1 Engagement Total" column, r[54]) so it always matches what the
    # checklist/meters show now that Leadership is excluded from that sum.
    q1_total = sum(c["actual"] for c in cats)

    records.append({
        "charter": r[0], "state": r[2], "assets": r[3], "members": r[4], "fte": r[5],
        "ceo": r[6], "cu": cu, "asset_group": ag,
        "q1_total": q1_total, "q4_total": r[55], "variance": r[56],
        "categories": cats, "extended": extended,
    })

# asset-group rank, and peer average recomputed on the new (Leadership-excluded)
# q1_total. The workbook's own "Peer Average" column (previously r[57]) was
# computed on the old 31-point basis and would no longer line up with scores
# shown on the site, so it's replaced with a same-basis average of this group.
by_group = {}
for d in records:
    by_group.setdefault(d["asset_group"], []).append(d)
for g, items in by_group.items():
    ranked = sorted(items, key=lambda d: d["q1_total"], reverse=True)
    for i, d in enumerate(ranked, start=1):
        d["rank"] = i
        d["group_n"] = len(ranked)
    assets = [d["assets"] for d in items]
    lo, hi = min(assets), max(assets)
    group_avg = round(sum(d["q1_total"] for d in items) / len(items), 1)
    for d in items:
        d["group_min"] = lo
        d["group_max"] = hi
        d["peer_avg"] = group_avg

# overall rank
ranked_all = sorted(records, key=lambda d: d["q1_total"], reverse=True)
for i, d in enumerate(ranked_all, start=1):
    d["overall_rank"] = i
overall_n = len(records)

def tier(total):
    # Thresholds rescaled proportionally from the original 21/31 and 12/31 cutoffs
    # now that the 3-point Leadership category is out and the max is 28, not 31
    # (21/31 -> ~19/28, 12/31 -> ~11/28), so "high"/"moderate"/"low" mean the same
    # relative share of total possible points as before.
    if total >= 19: return "high"
    if total >= 11: return "mod"
    return "low"

for d in records:
    d["tier"] = tier(d["q1_total"])

tier_counts = {"high": 0, "mod": 0, "low": 0}
for d in records:
    tier_counts[d["tier"]] += 1

cat_league_avg = {}
for key, label, *_ in CATS:
    vals = [next(c["actual"] for c in d["categories"] if c["key"] == key) for d in records]
    cat_league_avg[key] = round(sum(vals) / len(vals), 2)

group_labels = {}
for g, items in by_group.items():
    lo = min(d["assets"] for d in items)
    hi = max(d["assets"] for d in items)
    group_labels[g] = {"n": len(items), "min": lo, "max": hi}

league = {
    "quarter": "Q1 2026",
    "total_cus": overall_n,
    "total_possible": TOTAL_POSSIBLE,
    "tier_counts": tier_counts,
    "league_avg": round(sum(d["q1_total"] for d in records) / overall_n, 2),
    "category_avgs": cat_league_avg,
    "category_meta": [{"key": k, "label": l, "possible": p} for k, l, *_r, p, _t in [(c[0],c[1],c[2],c[3],c[4],c[5]) for c in CATS]],
    "asset_groups": group_labels,
}

# --- Glossary: hand-curated definitions, cross-referenced against the
# Definitions tab and the current column labels above. Update this list
# if items get renamed/added. It does not regenerate automatically.
CATEGORIES = [
  {
    "key": "advocacy", "label": "Advocacy", "possible": 9,
    "description": "Political and regulatory engagement: contributions, advocacy events, and direct contact with regulators or elected officials.",
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
      {"term": "GAC & GRR & HTH", "source": "definitions_sheet",
       "definition": "Attendance at GAC, GRR, and/or Hike the Hill within the past 12 months (originally listed as 'GRR / GAC / Hike The Hill'), pulled from Cvent and/or provided by Advocacy."},
      {"term": "Advocacy Workships", "source": "undocumented",
       "definition": "Not in the Definitions sheet (also a likely typo for \"Advocacy Workshops\" in the source column header, worth fixing either way)."},
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
       "definition": "Not in the Definitions sheet. Breaks down on page 2 into Solutions Webinars, Impact Power Hour, Ignite, and Compliance Essentials."},
      {"term": "Certificate Programs", "source": "undocumented",
       "definition": "Not in the Definitions sheet. Breaks down on page 2 into Financial Counselors Academy, Next Gen, and Succession Planning."},
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
      {"term": "2025 REACH", "source": "definitions_sheet",
       "definition": "Participation in REACH within the past 12 months, pulled from Cvent as events occur."},
      {"term": "Collaborative Events:", "source": "inferred",
       "definition": "Generic catch-all for collaborative events; possibly related to \"Communities\" (Breezio) in the Definitions sheet, unconfirmed."},
      {"term": "Networks", "source": "inferred",
       "definition": "Possibly related to \"Communities\" (Breezio) in the Definitions sheet. Breaks down on page 2 into Shapiro Network, Financial Counselors, Mid CU, and PR & Media Relations. Not confirmed under the current name."},
      {"term": "CEO Calls", "source": "definitions_sheet",
       "definition": "Current participant in CEO Calls, pulled from Cvent/Content Manager or sign-up sheets as events occur."},
      {"term": "CEO Roundtable", "source": "definitions_sheet",
       "definition": "Current participant in CEO Roundtables (SRT, WSRT, etc.), pulled from Cvent/Content Manager or sign-up sheets as events occur."},
    ],
  },
  # Executive Leadership was removed as a scored category per the report
  # redesign decision (Committee Seat, America's Credit Unions Committees,
  # Voted in 2025 League Elections). Its 3 points no longer count toward any
  # CU's total, and it's dropped from the Glossary below to match.
]

out = {"league": league, "cus": records, "glossary": CATEGORIES}
with open(OUT_PATH, "w") as f:
    json.dump(out, f, default=str)

print("records:", len(records))
print("league:", json.dumps(league, indent=2, default=str)[:1500])
