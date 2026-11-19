import json, sys, os, re, html, datetime

# Usage: python3 build_summary.py [engagement.json] [ai-summary.html]
#
# Writes ai-summary.html: a plain, static page (no JavaScript, no passphrase
# screen) with the site's key numbers as simple tables, so AI tools like
# Claude, and anyone skimming, can read them from a link. The interactive
# pages draw their numbers with JavaScript, which link-reading tools can't
# see. Contains aggregate figures and credit union names with activity
# counts only: no contact details and no PAC dollar amounts.
# Run it after build_data.py / build_directory.py whenever the data changes.

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "engagement.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "ai-summary.html")
d = json.load(open(SRC))
L = d["league"]

# --- same tiers and services as the Service Usage page (usage.html) ---
TIERS = [("A", 57.5e6, "Under $57.5M"), ("B", 274.5e6, "$57.5M-$274.5M"), ("C", 1.25e9, "$274.5M-$1.25B"), ("D", float("inf"), "$1.25B and up")]
def tier_of(a):
    return next(t for t, mx, _ in TIERS if a < mx)

SERVICES = [
    ("Compliance support", [
        ("Compliance hotline (ViClarity or League specialist)", "ext", "Hot Line Calls", "contacts"),
        ("InfoSight", "ext", "InfoSight Hits", "hits"),
        ("PolicyPro", "ext", "Policy Pro Log Ins", "log-ins"),
        ("ViClarity contracted services", "item", "compliance::ViClarity Contracted Services", None)]),
    ("Education", [
        ("Online educational content", "item", "education::Online Educational Content", None),
        ("Online education subscription", "ext", "Online Educational Content Subscription", None),
        ("eTrain", "ext", "eTrain Registrations", "registrations"),
        ("Programs and series", "item", "education::Programs & Series", None),
        ("Compliance Essentials", "ext", "Compliance Essentials", "attendances"),
        ("Certificate programs", "item", "education::Certificate Programs", None),
        ("Financial Counselors Academy", "ext", "Financial Councelors Academy", "participants")]),
    ("Peer connection and events", [
        ("CEO calls", "ext", "CEO Calls", "calls attended"),
        ("Local Networks", "item", "collab::Networks", None),
        ("Shapiro Network", "ext", "Shapiro Network", "participants"),
        ("CEO roundtables", "ext", "CEO Roundtable", "participants"),
        ("REACH (2025)", "ext", "2025 REACH", "attendees")]),
    ("Advocacy", [
        ("Connect for the Cause", "item", "advocacy::Connect For The Cause", None),
        ("GAC, GRR or Hike the Hill (any)", "item", "advocacy::GAC & GRR & HTH", None),
        ("Government Relations Rally", "itemre", r"^advocacy::(\d{4}\s+)?Government Relations Rally$", None),
        ("Government Affairs Conference", "itemre", r"^advocacy::(\d{4}\s+)?Government Affairs Conference$", None),
        ("Hike the Hill", "itemre", r"^advocacy::(\d{4}\s+)?Hike the Hill$", None)]),
]
CFTC_VOLUME = "12 Months Rolling CFTC - # of Participants"

def completed(v):
    if v is None: return False
    if isinstance(v, (int, float)): return v > 0
    s = str(v).strip().lower()
    if not s or re.fullmatch(r"(no|n|false|0|none|never.*|n/a|-)", s): return False
    return float(s) > 0 if re.fullmatch(r"-?[\d.]+", s) else True

def numval(v):
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip().replace(",", "")
    m = re.fullmatch(r"(-?[\d.]+)%?", s)
    return float(m.group(1)) if m else None

cus = []
for c in d["cus"]:
    ext = {e["label"]: numval(e["value"]) for e in c.get("extended", []) if numval(e["value"]) is not None}
    items = {f'{k["key"]}::{i["label"]}': i["value"] for k in c["categories"] for i in k["items"] if completed(i["value"])}
    scored = {f'{k["key"]}::{i["label"]}' for k in c["categories"] for i in k["items"] if i.get("scored", True) and completed(i["value"])}
    cus.append({"cu": c["cu"], "assets": c["assets"], "status": c.get("member_status"), "score": c["total"], "tier": c["tier"],
                "size": tier_of(c["assets"]), "ext": ext, "items": items, "scored": scored})
item_keys = {k for c in cus for k in c["items"]}
ext_keys = {k for c in cus for k in c["ext"]}

rows = []  # (section, label, uses(c)->bool, volume(c)->num|None, unit)
for section, svc in SERVICES:
    for label, kind, key, unit in svc:
        if kind == "itemre":
            hit = next((k for k in sorted(item_keys) if re.match(key, k)), None)
            if not hit: continue
            yr = re.search(r"::(\d{4})\s", hit)
            label = f"{label} ({yr.group(1)})" if yr else label
            kind, key = "item", hit
        if kind == "ext" and key not in ext_keys: continue
        if kind == "item" and key not in item_keys: continue
        if kind == "ext":
            uses = (lambda k: lambda c: c["ext"].get(k, 0) > 0)(key)
            vol = (lambda k: lambda c: c["ext"].get(k, 0))(key) if unit else None
        else:
            uses = (lambda k: lambda c: k in c["items"])(key)
            vol = (lambda c: c["ext"].get(CFTC_VOLUME, 0)) if label == "Connect for the Cause" and CFTC_VOLUME in ext_keys else None
            unit = "participants" if vol else None
        rows.append((section, label, uses, vol, unit))

def fmt(n, dec=0):
    return "–" if n is None else f"{n:,.{dec}f}"
def pct(a, b):
    return "–" if not b else f"{round(100 * a / b)}%"
def money(v):
    return f"${v/1e9:.2f}B" if v >= 1e9 else f"${v/1e6:.1f}M" if v >= 1e6 else f"${v:,.0f}"
def date_long(iso):
    if not iso: return None
    y, m, dd = map(int, iso.split("-"))
    return datetime.date(y, m, dd).strftime("%B %-d, %Y")
e = html.escape
out = []
def table(head, body, cls=""):
    out.append(f'<table class="{cls}"><thead><tr>' + "".join(f"<th>{e(str(h))}</th>" for h in head) + "</tr></thead><tbody>")
    for r in body:
        if isinstance(r, str):
            out.append(f'<tr class="sec"><td colspan="{len(head)}">{e(r)}</td></tr>')
        else:
            out.append("<tr>" + "".join(f"<td>{e(str(x))}</td>" for x in r) + "</tr>")
    out.append("</tbody></table>")

members = [c for c in cus if c["status"] == "Member"]
by_size = {t: [c for c in members if c["size"] == t] for t, _, _ in TIERS}
period = f'{L["quarter"]}{" (preliminary)" if L.get("preliminary") else ""}'

out.append(f"""<h1>Engagement Explorer: data summary</h1>
<p class="lede">Plain-text version of the key numbers on the Engagement Explorer, for AI tools and quick reading. The interactive pages have the same data with filters and drill-downs.</p>
<ul class="meta">
<li><b>Period:</b> {e(period)}{f' · workbook data last updated {date_long(L.get("as_of"))}' if L.get("as_of") else ""}</li>
<li><b>Site last refreshed:</b> {e(date_long(L.get("last_updated")) or "n/a")}</li>
<li><b>Source:</b> {e(L.get("source_file", ""))}{f' ("{e(L["source_sheet"])}" tab)' if L.get("source_sheet") else ""}</li>
<li><b>Credit unions tracked:</b> {len(cus)} ({len(members)} members, {sum(1 for c in cus if c["status"] == "Associate Member")} associate members, {sum(1 for c in cus if c["status"] == "Non-Member")} non-members)</li>
<li><b>Engagement score:</b> out of {L["total_possible"]} points across five categories; Highly Engaged 19+, Moderately Engaged 11-18, Low Engagement under 11.</li>
</ul>""")

# 1. service usage by tier (members)
out.append("<h2>1. Service usage by credit union size (League members)</h2>")
out.append("<p>Share of member credit unions in each asset tier with any recorded use of the service in the past 12 months (users / credit unions in tier).</p>")
head = ["Service"] + [f"Tier {t} ({lab}, {len(by_size[t])} CUs)" for t, _, lab in TIERS] + [f"All members ({len(members)})"]
body, last = [], None
for section, label, uses, vol, unit in rows:
    if section != last: body.append(section); last = section
    cells = []
    for grp in [by_size[t] for t, _, _ in TIERS] + [members]:
        u = sum(1 for c in grp if uses(c))
        cells.append(f"{pct(u, len(grp))} ({u}/{len(grp)})")
    body.append([label] + cells)
table(head, body)

out.append("<h2>2. Volume of use by credit union size (League members)</h2>")
out.append("<p>Total activity in the past 12 months, and per user (total divided by the credit unions in the tier that used the service).</p>")
head = ["Service (unit)"] + [f"Tier {t} total / per user" for t, _, _ in TIERS] + ["All members total / per user"]
body = []
for section, label, uses, vol, unit in rows:
    if not vol: continue
    cells = []
    for grp in [by_size[t] for t, _, _ in TIERS] + [members]:
        us = [c for c in grp if uses(c)]
        tot = sum(vol(c) for c in us)
        cells.append(f"{fmt(tot)} / {fmt(tot / len(us), 1) if us else '–'}")
    body.append([f"{label} ({unit})"] + cells)
table(head, body)

# 3. usage by member status
statuses = [s for s in ("Member", "Associate Member", "Non-Member") if any(c["status"] == s for c in cus)]
out.append("<h2>3. Service usage by membership status (all tracked credit unions)</h2>")
head = ["Service"] + [f"{s}s ({sum(1 for c in cus if c['status'] == s)})" for s in statuses] + [f"All tracked ({len(cus)})"]
body, last = [], None
for section, label, uses, vol, unit in rows:
    if section != last: body.append(section); last = section
    cells = []
    for grp in [[c for c in cus if c["status"] == s] for s in statuses] + [cus]:
        u = sum(1 for c in grp if uses(c))
        cells.append(f"{pct(u, len(grp))} ({u})")
    body.append([label] + cells)
table(head, body)

# 4. engagement by tier
out.append("<h2>4. Engagement scores by credit union size (League members)</h2>")
head = ["Measure"] + [f"Tier {t}" for t, _, _ in TIERS] + ["All members"]
grps = [by_size[t] for t, _, _ in TIERS] + [members]
table(head, [
    ["Credit unions"] + [len(g) for g in grps],
    [f"Average engagement score (of {L['total_possible']})"] + [fmt(sum(c["score"] for c in g) / len(g), 1) if g else "–" for g in grps],
    ["Highly engaged (19+)"] + [sum(1 for c in g if c["tier"] == "high") for g in grps],
    ["Moderately engaged (11-18)"] + [sum(1 for c in g if c["tier"] == "mod") for g in grps],
    ["Low engagement (under 11)"] + [sum(1 for c in g if c["tier"] == "low") for g in grps],
])

# 5. league-wide engagement overview
out.append("<h2>5. League-wide engagement (all tracked credit unions)</h2>")
tc = L["tier_counts"]
body = [["League average score", f'{L["league_avg"]} of {L["total_possible"]}'],
        ["Highly engaged", f'{tc["high"]} ({pct(tc["high"], L["total_cus"])})'],
        ["Moderately engaged", f'{tc["mod"]} ({pct(tc["mod"], L["total_cus"])})'],
        ["Low engagement", f'{tc["low"]} ({pct(tc["low"], L["total_cus"])})']]
for cm in L["category_meta"]:
    body.append([f'Average {cm["label"]} score', f'{L["category_avgs"][cm["key"]]} of {cm["possible"]}'])
table(["Measure", "Value"], body)

# 6. initiative participation
inits = [(k["label"], f'{k["key"]}::{i}', i) for k in L.get("initiatives", []) for i in k["items"]]
if inits:
    N = len(inits)
    out.append(f"<h2>6. Participation in the {N} scored initiatives (all tracked credit unions)</h2>")
    counts = [len(c["scored"]) for c in cus]
    out.append(f"<p>Average participation: {round(100 * sum(counts) / len(cus) / N)}% of initiatives. "
               f"Credit unions completing under 40% (needs follow-up): {sum(1 for n in counts if n / N < 0.4)}. "
               f"70% or more: {sum(1 for n in counts if n / N >= 0.7)}. All {N}: {sum(1 for n in counts if n == N)}.</p>")
    body = sorted(([lab, cat, f"{sum(1 for c in cus if key in c['scored'])} ({pct(sum(1 for c in cus if key in c['scored']), len(cus))})"]
                   for cat, key, lab in inits), key=lambda r: -int(r[2].split(" ")[0]))
    table(["Initiative", "Category", f"Credit unions completing (of {len(cus)})"], body)
    ranked = sorted(cus, key=lambda c: (-len(c["scored"]), -c["score"], c["cu"]))[:15]
    out.append("<h3>Top 15 by initiatives completed</h3>")
    table(["Credit union", f"Initiatives (of {N})", f"Engagement score (of {L['total_possible']})", "Assets"],
          [[c["cu"], len(c["scored"]), c["score"], money(c["assets"])] for c in ranked])

# 7. activity leaders (top 5 per measure; PAC dollar amounts left out)
out.append("<h2>7. Activity leaders (top 5 per measure, all tracked credit unions)</h2>")
out.append("<p>From the extended activity detail. Equal values share a rank. PAC contribution amounts are not included here.</p>")
body = []
for m in L.get("extended_metrics", []):
    if m["type"] == "money": continue
    vals = sorted(((c["ext"][m["label"]], c["cu"]) for c in cus if c["ext"].get(m["label"], 0) > 0), key=lambda x: (-x[0], x[1]))
    if not vals: continue
    if vals[0][0] == vals[-1][0]:
        body.append([m["label"], f"{len(vals)} credit unions took part (one each, not ranked)", ""]); continue
    total = sum(v for v, _ in vals)
    summary = f"average {round(total / len(vals))}%" if m["type"] == "percent" else f"total {fmt(total)}"
    tops = []
    for i, (v, name) in enumerate(vals[:5]):
        rank = 1 + sum(1 for w, _ in vals if w > v)
        tops.append(f"{rank}. {name} ({fmt(v)}{'%' if m['type'] == 'percent' else ''})")
    body.append([m["label"], f"{len(vals)} credit unions · {summary}", "; ".join(tops)])
table(["Measure", "Participation", "Leaders"], body)

out.append("""<h2>Notes</h2><ul>
<li>Tiers use the asset cutoffs from the League's services and usage report (under $57M, $58M-$274M, $275M-$1.24B, $1.27B+), split at the midpoints and applied to each credit union's latest assets.</li>
<li>"Using a service" means any activity recorded in the engagement workbook's 12-month data (a count above zero, or a completed checklist item). PolicyPro is counted as log-ins.</li>
<li>The engagement score has 27 initiatives but 28 possible points: Advocacy is worth 9 points with 8 initiatives, and the extra point can only come from the GAC &amp; GRR &amp; HTH item being recorded as more than 1.</li>
<li>Government Relations Rally, Government Affairs Conference, and Hike the Hill are tracked individually but scored through the combined GAC &amp; GRR &amp; HTH item.</li>
</ul>""")

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="robots" content="noindex, nofollow"/>
<title>Engagement Explorer data summary</title>
<style>
body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a;background:#f8fafc;margin:0;padding:24px 16px 60px}}
main{{max-width:1100px;margin:0 auto}} h1{{font-size:24px;margin:0 0 4px}} h2{{font-size:17px;margin:32px 0 6px;color:#1e3a8a}} h3{{font-size:14px;margin:18px 0 6px}}
.lede{{color:#475569;margin:0 0 12px}} .meta{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 12px 12px 30px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e2e8f0;font-size:13px;display:block;overflow-x:auto}}
th{{background:#0f172a;color:#fff;text-align:left;padding:7px 9px;font-weight:600;white-space:nowrap}} td{{border-top:1px solid #e2e8f0;padding:6px 9px;vertical-align:top}}
tr.sec td{{background:#eff6ff;font-weight:700;color:#1e3a8a;text-transform:uppercase;font-size:11px;letter-spacing:.04em}}
</style></head><body><main>
{chr(10).join(out)}
</main></body></html>"""
open(OUT, "w").write(page)
print(f"wrote {OUT}: {len(rows)} services, {len(cus)} credit unions, {len(members)} members")
