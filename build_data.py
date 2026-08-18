import openpyxl, json, datetime, sys, os

# Usage: python3 build_data.py [path/to/quarterly_export.xlsx] [path/to/output.json]
# Defaults assume you run this from the scripts/ folder with the xlsx one level up,
# and write straight into ../data/engagement.json (what index.html fetches).
IN_PATH = sys.argv[1] if len(sys.argv) > 1 else "data.xlsx"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "data", "engagement.json")

wb = openpyxl.load_workbook(IN_PATH, data_only=True)
# IMPORTANT: this assumes the same "Worksheet" tab layout used for Q1 2026 —
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
    ("leadership", "Executive Leadership", 49, 52, 3, 53),
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

    records.append({
        "charter": r[0], "state": r[2], "assets": r[3], "members": r[4], "fte": r[5],
        "ceo": r[6], "cu": cu, "asset_group": ag,
        "q1_total": r[54] or 0, "q4_total": r[55], "variance": r[56], "peer_avg": r[57],
        "categories": cats, "extended": extended,
    })

# asset-group rank
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
    for d in items:
        d["group_min"] = lo
        d["group_max"] = hi

# overall rank
ranked_all = sorted(records, key=lambda d: d["q1_total"], reverse=True)
for i, d in enumerate(ranked_all, start=1):
    d["overall_rank"] = i
overall_n = len(records)

def tier(total):
    if total >= 21: return "high"
    if total >= 12: return "mod"
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

out = {"league": league, "cus": records}
with open(OUT_PATH, "w") as f:
    json.dump(out, f, default=str)

print("records:", len(records))
print("league:", json.dumps(league, indent=2, default=str)[:1500])
