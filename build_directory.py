import openpyxl, json, re, sys, os, datetime, argparse, difflib, warnings

# Usage:
#   python3 build_directory.py Master_List.xlsx [engagement.json]
#       Reads the League's roster workbook (the "Master List") and merges it into
#       engagement.json. Run this right after build_data.py.
#
#   python3 build_directory.py --carry-from OLD_engagement.json [engagement.json]
#       Use this when you don't have a new Master List: it takes the roster data
#       already published in a previous engagement.json and re-merges it with the
#       new engagement data. (build_data.py rewrites engagement.json from scratch,
#       so without one of these two steps the Directory/Industry/Changes tabs and
#       the "Organization & Contact" panels would come up empty.)
#
# How conflicts between the two sources are handled:
# - The engagement workbook is the main source for anything it has (name, CEO,
#   member status, financials). The roster fills in contact info, HQ, county,
#   district, charter type, chapter, branches, and CDFI/low-income flags.
# - Exception: when the roster's dated CEO Transitions log names a different CEO
#   than the engagement data, the log wins (the engagement workbook's CEO column
#   has lagged behind documented transitions). Each override is printed below.
# - When the roster's CEO is a different person than the CEO shown on the site,
#   the roster's email/phone are labeled as belonging to that person rather than
#   presented as the current CEO's contact info.
#
# Deliberately NOT included: the workbook's "Risk Report" tab (per-CU composite
# risk scores/trends). That's confidential supervisory-style data, and this
# site is only a soft-gated, publicly-reachable page, so it isn't pulled in
# here. Ask before changing that.

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

ap = argparse.ArgumentParser()
ap.add_argument("master", nargs="?", help="path to Master_List.xlsx (omit when using --carry-from)")
ap.add_argument("out", nargs="?", default=None)
ap.add_argument("--carry-from", default=None, help="previous engagement.json to take roster data from")
args = ap.parse_args()
if args.carry_from and args.master and not args.out and args.master.lower().endswith(".json"):
    args.out, args.master = args.master, None  # build_directory.py --carry-from old.json engagement.json
if not args.carry_from and not args.master:
    sys.exit("ERROR: give a Master_List.xlsx path, or --carry-from a previous engagement.json")
OUT_PATH = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "engagement.json")


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


# ---------------- person-name matching (for CEO comparisons) ----------------
NICKNAMES = {"bill": "william", "will": "william", "chuck": "charles", "charlie": "charles", "beth": "elizabeth",
             "liz": "elizabeth", "kathy": "katherine", "kate": "katherine", "bob": "robert", "rob": "robert",
             "rick": "richard", "dick": "richard", "jim": "james", "mike": "michael", "steve": "stephen",
             "ken": "kenneth", "ed": "edward", "tom": "thomas", "ray": "raymond", "joe": "joseph", "tony": "anthony",
             "dave": "david", "dan": "daniel", "greg": "gregory", "jeff": "jeffery", "matt": "matthew",
             "pete": "peter", "sam": "samuel", "sue": "susan", "lucy": "lucille"}
DROP = {"mr", "mrs", "ms", "dr", "jr", "sr", "ii", "iii", "iv"}


def name_tokens(s):
    s = str(s or "").split(",")[0]                      # drop ", CUERME", ", Jr.", ", CPA" ...
    toks = re.findall(r"[a-z][a-z'\-]*", s.lower())
    return [t for t in toks if t not in DROP and len(t) > 1]


def same_person(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return True  # nothing to compare
    la, lb = ta[-1], tb[-1]
    last_ok = (set(la.split("-")) & set(lb.split("-"))) or difflib.SequenceMatcher(None, la, lb).ratio() >= 0.85
    if not last_ok:
        return False
    fa, fb = ta[0], tb[0]
    ca, cb = NICKNAMES.get(fa, fa), NICKNAMES.get(fb, fb)
    return ca == cb or fa[0] == fb[0] or fa in tb or fb in ta


# ---------------- source 1: the Master List workbook ----------------
def load_from_master(path):
    wb = openpyxl.load_workbook(path, data_only=True)

    # primary directory: name/CEO/HQ/charter, keyed by charter #
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

    # League Membership Status (Dues): phone, branches, tier, CDFI, low-income
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
        """Format plain 10-digit numbers entered as raw numbers; leave formatted text alone."""
        v = clean_str(v)
        if not v:
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) == 10 and digits == v.strip():
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
            name = clean_str(r[3])
            if name:
                by_charter[charter] = {
                    "charter": charter, "name": name, "ceo": clean_str(r[8]),
                    "ceo_email": clean_str(r[9]), "member_status": mstat, **extra,
                }

    directory = list(by_charter.values()) + no_charter
    directory.sort(key=lambda d: d["name"].lower())

    ws = wb["Name Changes"]
    name_changes = []
    for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if not r[1] or not r[2]:
            continue
        name_changes.append({"year": r[0], "old_name": clean_str(r[1]), "new_name": clean_str(r[2])})

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

    changes = {"ceo_transitions": ceo_transitions, "mergers": mergers,
               "charter_changes": charter_changes, "name_changes": name_changes}

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
    return directory, changes, industry, datetime.date.today().isoformat()


# ---------------- source 2: roster data already published in an engagement.json ----------------
DERIVED_KEYS = ("display_name", "display_ceo", "display_status", "contact_for", "profile", "former_name")


def load_from_json(path):
    prev = json.load(open(path))
    for k in ("directory", "changes", "industry"):
        if k not in prev:
            sys.exit(f'ERROR: {path} has no "{k}" data to carry forward')
    directory = [{k: v for k, v in e.items() if k not in DERIVED_KEYS} for e in prev["directory"]]
    return directory, prev["changes"], prev["industry"], prev.get("roster_updated")


if args.carry_from:
    directory, changes, industry, roster_updated = load_from_json(args.carry_from)
else:
    directory, changes, industry, roster_updated = load_from_master(args.master)

# ---------------- merge into engagement.json ----------------
with open(OUT_PATH) as f:
    data = json.load(f)

by_charter = {e["charter"]: e for e in directory if e.get("charter") is not None}
by_norm_name = {}
for e in directory:
    by_norm_name.setdefault(norm_name(e["name"]), []).append(e)
name_change_by_norm = {norm_name(nc["new_name"]): nc for nc in changes["name_changes"]}
latest_transition = {}
for t in sorted(changes["ceo_transitions"], key=lambda t: t["year"] or 0):
    latest_transition[norm_name(t["cu"])] = t  # later years overwrite earlier ones

matched, by_name, ceo_overrides, contact_labeled, status_conflicts, renamed = 0, [], [], [], [], []

for cu in data["cus"]:
    e = by_charter.get(cu.get("charter"))
    if not e:
        # Several CUs converted from state to federal charters (see the Charter
        # Changes log) and have a new charter number in the engagement data while
        # the roster still lists the old one. Fall back to a unique name match.
        cands = by_norm_name.get(norm_name(cu["cu"]), [])
        if len(cands) == 1:
            e = cands[0]
            by_name.append(f'{cu["cu"]}: engagement charter {cu["charter"]}, roster charter {e["charter"]}')

    # CEO: engagement data, unless the dated transitions log says otherwise
    t = latest_transition.get(norm_name(cu["cu"]))
    if t and t.get("new_ceo") and not same_person(t["new_ceo"], cu.get("ceo")):
        ceo_overrides.append(f'{cu["cu"]}: "{cu.get("ceo")}" in the engagement data -> "{t["new_ceo"]}" '
                             f'(CEO Transitions log, {t["year"]})')
        cu["ceo_note"] = f'The engagement workbook lists {cu.get("ceo")}; the CEO Transitions log shows {t["new_ceo"]} as CEO since {t["year"]}.'
        cu["ceo"] = t["new_ceo"]

    org = {}
    if e:
        matched += 1
        org = {k: v for k, v in e.items() if k not in ("charter", "name")}
        if org.get("ceo") and cu.get("ceo") and not same_person(org["ceo"], cu["ceo"]):
            org["contact_for"] = org["ceo"]
            contact_labeled.append(f'{cu["cu"]}: site shows {cu["ceo"]}; roster contact is for {org["ceo"]}')
        if cu.get("member_status") and org.get("member_status") and org["member_status"] != cu["member_status"]:
            status_conflicts.append(f'{cu["cu"]}: engagement "{cu["member_status"]}", roster "{org["member_status"]}"')
        org.pop("member_status", None)  # the engagement workbook's status is shown instead
        org.pop("ceo", None)
        # Renamed since the comparison quarter (build_data.py sets prev_name when the
        # same charter had a different name). Roster and engagement names often differ
        # only in style ("EFCU" vs "Employees CU"), so that alone isn't treated as a rename.
        if cu.get("prev_name"):
            org["former_name"] = cu["prev_name"]
            renamed.append(f'{cu["prev_name"]} -> {cu["cu"]} (same charter {cu["charter"]})')
        # display fields for the Directory tab, so it agrees with the profile pages
        e["profile"] = cu["charter"]
        e["display_ceo"] = cu.get("ceo")
        if cu.get("member_status"):
            e["display_status"] = cu["member_status"]
        if org.get("contact_for"):
            e["contact_for"] = org["contact_for"]
        if org.get("former_name") and norm_name(e["name"]) == norm_name(org["former_name"]):
            e["display_name"] = cu["cu"]       # roster still has the old name
            e["former_name"] = org["former_name"]
    nc = name_change_by_norm.get(norm_name(cu["cu"]))
    if nc and not org.get("former_name"):
        org["former_name"] = f'{nc["old_name"]} (until {nc["year"]})'
    if org:
        cu["org"] = org

data["directory"] = directory
data["changes"] = changes
data["industry"] = industry
# Roster data refreshes on its own schedule, so it gets its own date (shown on
# the Directory page). The site-wide "Last updated" comes from build_data.py.
data["roster_updated"] = roster_updated

with open(OUT_PATH, "w") as f:
    json.dump(data, f, default=str)

print(f"roster source: {'carried forward from ' + args.carry_from if args.carry_from else args.master}")
print(f"directory entries: {len(directory)}; matched to an engagement CU: {matched} of {len(data['cus'])}")
for title, items in (("matched by name (charter number differs)", by_name),
                     ("CEO taken from the CEO Transitions log", ceo_overrides),
                     ("roster contact belongs to a different CEO (labeled on site)", contact_labeled),
                     ("member status differs (engagement workbook shown)", status_conflicts),
                     ("renamed (shown with former name)", renamed)):
    if items:
        print(f"{title}: {len(items)}")
        for i in items:
            print("  " + i)
unmatched = [c["cu"] for c in data["cus"] if "org" not in c or not any(k in c["org"] for k in ("hq_city", "ceo_email"))]
if unmatched:
    print(f"no roster match: {unmatched}")
