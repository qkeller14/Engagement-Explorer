import openpyxl, json, re, sys, os

# Usage: python3 build_directory.py [path/to/Master_List.xlsx] [path/to/engagement.json]
#
# Merges the League's roster/reference workbook (CEO + org directory, industry
# benchmarks, and a log of mergers/charter/name/CEO changes) into the same
# engagement.json the site already reads. Run this AFTER build_data.py for a
# given quarter's refresh, since it loads the existing engagement.json and adds
# to it rather than replacing it. This source updates far less often than the
# quarterly engagement export, so there's no need to re-run it every quarter,
# just whenever the roster/org info changes.
#
# Deliberately NOT included: the workbook's "Risk Report" tab (per-CU composite
# risk scores/trends). That's confidential supervisory-style data, and this
# site is only a soft-gated, publicly-reachable page, so it isn't pulled in
# here. Ask before changing that.

MASTER_PATH = sys.argv[1] if len(sys.argv) > 1 else "Master_List.xlsx"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "engagement.json")

wb = openpyxl.load_workbook(MASTER_PATH, data_only=True)


def norm_name(s):
    """Normalize a CU name for matching across sheets that spell it differently
    (all-caps, trailing 'FCU'/'CU', extra whitespace, etc.)."""
    s = re.sub(r"[^A-Za-z0-9]+", "", str(s or "")).upper()
    for suf in ("FEDERALCREDITUNION", "CREDITUNION", "FCU", "CU"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def clean_str(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None


# ---------------- primary directory: name/CEO/HQ/charter, keyed by charter # ----------------
ws = wb["Credit Unions + CEO List (All 3"]
rows = list(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True))
by_charter = {}
no_charter = []
for r in rows:
    name = clean_str(r[0])
    if not name:
        continue
    charter_raw = clean_str(r[11])
    entry = {
        "charter": int(charter_raw) if charter_raw and charter_raw.isdigit() else None,
        "name": name,
        "ceo": clean_str(r[1]),
        "ceo_email": clean_str(r[2]),
        "hq_address": clean_str(r[3]),
        "hq_city": clean_str(r[4]),
        "hq_state": clean_str(r[5]),
        "hq_zip": clean_str(r[6]),
        "county": clean_str(r[7]),
        "cong_dist": clean_str(r[8]),
        "member_status": clean_str(r[9]),
        "charter_type": clean_str(r[10]),
        "chapter": clean_str(r[12]),
    }
    if entry["charter"] is not None:
        by_charter[entry["charter"]] = entry
    else:
        no_charter.append(entry)

# ---------------- League Membership Status (Dues): phone, branches, tier, CDFI, low-income ----------------
ws = wb["League Membership Status (Dues)"]
rows = list(ws.iter_rows(min_row=4, max_row=ws.max_row, values_only=True))

MEM_LABELS = {"M": "Member", "NM": "Non-Member", "N-M": "Non-Member", "AM": "Associate Member"}


def mem_label(v):
    v = clean_str(v)
    if not v:
        return None
    return MEM_LABELS.get(v.strip().upper(), v.strip())


def yes_no(v):
    v = clean_str(v)
    if v in ("Yes", "No"):
        return v
    return None  # a few rows have stray numeric data in this column upstream; drop rather than guess


def fmt_phone(v):
    """A few phone numbers were entered as raw numbers in the sheet instead of
    formatted text (e.g. 8085313711 instead of "(808) 531-3711"). Format any
    plain 10-digit number consistently; leave already-formatted text alone."""
    v = clean_str(v)
    if not v:
        return None
    digits = re.sub(r"\D", "", v)
    if digits == re.sub(r"\D", "", v) and len(digits) == 10 and digits == v.strip():
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return v


for r in rows:
    charter = r[4]
    if not isinstance(charter, (int, float)):
        continue
    charter = int(charter)
    phone = fmt_phone(r[11]) or fmt_phone(r[10])
    extra = {
        "dues_tier": clean_str(r[2]),
        "ceo_phone": phone,
        "branches": r[17] if isinstance(r[17], (int, float)) else None,
        "cdfi": yes_no(r[6]),
        "low_income": yes_no(r[7]),
    }
    mstat = mem_label(r[1])
    if charter in by_charter:
        by_charter[charter].update({k: v for k, v in extra.items() if v is not None})
        if mstat and not by_charter[charter].get("member_status"):
            by_charter[charter]["member_status"] = mstat
    else:
        # in the Dues sheet but not the CEO list, still worth keeping in the roster
        name = clean_str(r[3])
        if name:
            by_charter[charter] = {
                "charter": charter, "name": name, "ceo": clean_str(r[8]),
                "ceo_email": clean_str(r[9]), "member_status": mstat, **extra,
            }

directory = list(by_charter.values()) + no_charter
directory.sort(key=lambda d: d["name"].lower())

# ---------------- name changes (also used to tag "formerly" on matching CU profiles) ----------------
ws = wb["Name Changes"]
name_changes = []
for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    if not r[1] or not r[2]:
        continue
    name_changes.append({"year": r[0], "old_name": clean_str(r[1]), "new_name": clean_str(r[2])})

# ---------------- CEO transitions / mergers / charter changes ----------------
ws = wb["CEO Transitions"]
ceo_transitions = []
for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    if not r[1] or not r[2]:
        continue
    ceo_transitions.append({"year": r[0], "cu": clean_str(r[1]), "new_ceo": clean_str(r[2])})
ceo_transitions.sort(key=lambda d: (d["year"] or 0), reverse=True)

ws = wb["Mergers"]
mergers = []
for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    if not r[1] or not r[2]:
        continue
    mergers.append({"period": clean_str(r[0]), "merged": clean_str(r[1]), "surviving": clean_str(r[2])})

ws = wb["Charter Changes"]
charter_changes = []
for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
    if not r[1]:
        continue
    charter_changes.append({
        "year": r[0], "cu": clean_str(r[1]), "from": clean_str(r[2]), "to": clean_str(r[3]),
        "assets": r[4] if isinstance(r[4], (int, float)) else None,
    })
charter_changes.sort(key=lambda d: (d["year"] or 0), reverse=True)

changes = {
    "ceo_transitions": ceo_transitions,
    "mergers": mergers,
    "charter_changes": charter_changes,
    "name_changes": name_changes,
}

# ---------------- industry snapshot (Financial Snapshot tab: US vs CA benchmarks) ----------------
ws = wb["Financial Snapshot"]
fs = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))


def row_by_label(label):
    for r in fs:
        if r[0] and str(r[0]).strip() == label:
            return r
    return None


def pair(label):
    r = row_by_label(label)
    if not r:
        return None
    return {"us": r[1], "ca": r[2]}


industry = {
    "as_of": fs[0][1] if fs and fs[0][1] else None,
    "counts": {
        "total_cus": pair("Number of CUs"),
        "federal_chartered": pair("Federal Chartered CUs"),
        "state_chartered_ncusif": pair("State-Chartered CUs, NCUSIF insured"),
        "state_chartered_asi": pair("State-Chartered CUs, ASI insured"),
        "total_state_chartered": pair("Total State Chartered CUs"),
    },
    "scale": {
        "total_members": pair("Total Members"),
        "avg_members_per_cu": pair("Members, average per CU"),
        "total_assets": pair("Total Assets"),
        "total_loans": pair("Total Loans"),
        "total_shares": pair("Total Shares"),
        "total_capital": pair("Total Capital"),
        "avg_asset_size": pair("Average Asset Size"),
    },
    "ratios_pct_of_avg_assets": {
        "interest_income": pair("Interest Income (annualized)"),
        "interest_expense": pair("Interest Expense (annualized)"),
        "net_interest_margin": pair("Net Interest Margin"),
        "loss_provisions": pair("Loss Provisions (annualized)"),
        "operating_expenses": pair("Operating Expenses"),
        "noninterest_income": pair("Non-interest income (annualized)"),
        "roa": pair("ROA"),
    },
    "growth_and_ratios": {
        "loan_growth_12mo": pair("12-month loan growth"),
        "share_growth_12mo": pair("12-month share growth"),
        "capital_growth_12mo": pair("12-month capital growth"),
        "asset_growth_12mo": pair("12-month asset growth"),
        "loans_to_shares": pair("Loans/Shares"),
        "networth_to_assets": pair("Net Worth/Assets"),
        "capital_to_assets": pair("Capital/Assets"),
        "delinquency_ratio": pair("Delinquency Ratio"),
        "avg_loan_balance": pair("Average Loan Balance"),
        "avg_share_balance": pair("Average Share Balance"),
    },
}

# ---------------- merge into engagement.json ----------------
with open(OUT_PATH) as f:
    data = json.load(f)

matched = 0
matched_by_name_fallback = []
former_name_tagged = 0
name_change_by_norm = {norm_name(nc["new_name"]): nc for nc in name_changes}

# index the directory by normalized name, for CUs whose engagement-workbook
# charter # doesn't actually match the Master List (see fallback below)
by_norm_name = {}
for org in by_charter.values():
    by_norm_name.setdefault(norm_name(org["name"]), []).append(org)

for cu in data["cus"]:
    org = by_charter.get(cu.get("charter"))
    if not org:
        # Fallback: a handful of CUs in the quarterly engagement export carry a
        # charter # that doesn't match any real charter in the Master List (e.g.
        # 24980-24986, oddly sequential, vs. the Master List's 60784/68456/etc.
        # for the same credit unions) -- a data-quality issue in that source
        # workbook, not this script. Try matching by normalized name instead.
        candidates = by_norm_name.get(norm_name(cu["cu"]))
        if candidates and len(candidates) == 1:
            org = candidates[0]
            matched_by_name_fallback.append((cu["cu"], cu.get("charter"), org["charter"]))
    if org:
        matched += 1
        cu["org"] = {k: v for k, v in org.items() if k not in ("charter", "name")}
    nc = name_change_by_norm.get(norm_name(cu["cu"]))
    if nc:
        cu.setdefault("org", {})["former_name"] = f'{nc["old_name"]} (until {nc["year"]})'
        former_name_tagged += 1

data["directory"] = directory
data["changes"] = changes
data["industry"] = industry

with open(OUT_PATH, "w") as f:
    json.dump(data, f, default=str)

print(f"directory entries: {len(directory)}")
print(f"matched to an engagement CU: {matched} of {len(data['cus'])}")
if matched_by_name_fallback:
    print(f"  of which {len(matched_by_name_fallback)} needed the name fallback "
          f"(engagement charter # didn't match the Master List's charter # for that CU):")
    for name, eng_charter, ml_charter in matched_by_name_fallback:
        print(f"    {name}: engagement charter {eng_charter} vs Master List charter {ml_charter}")
print(f"former-name tags applied: {former_name_tagged}")
print(f"changes: {len(ceo_transitions)} CEO transitions, {len(mergers)} mergers, "
      f"{len(charter_changes)} charter changes, {len(name_changes)} name changes")
print(f"industry snapshot as_of: {industry['as_of']}")
