/* ---------------- access gate (soft, client-side only, see README) ---------------- */
const PASSPHRASE = "league2026"; // change me before sharing the link further

(function gate() {
  const gateEl = document.getElementById("gate");
  const appEl = document.getElementById("app");
  if (localStorage.getItem("mee_unlocked") === "1") {
    gateEl.classList.add("hidden");
    appEl.style.display = "";
    return;
  }
  document.getElementById("gate-btn").addEventListener("click", tryUnlock);
  document.getElementById("gate-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") tryUnlock();
  });
  function tryUnlock() {
    const v = document.getElementById("gate-input").value;
    if (v === PASSPHRASE) {
      localStorage.setItem("mee_unlocked", "1");
      gateEl.classList.add("hidden");
      appEl.style.display = "";
    } else {
      document.getElementById("gate-err").textContent = "That's not it. Try again.";
    }
  }
})();

/* ---------------- state ---------------- */
let DATA = null;
let sortKey = "q1_total";
let sortDir = "desc";
let filters = { q: "", group: "all", state: "all" };

const fmtMoney = (v) => (v == null ? "–" : "$" + Math.round(v).toLocaleString());
const fmtMoneyShort = (v) => {
  if (v == null) return "–";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
  return "$" + v.toLocaleString();
};
const fmtNum = (v) => (v == null ? "–" : v.toLocaleString());

function tierLabel(t) {
  return t === "high" ? "Highly Engaged" : t === "mod" ? "Moderately Engaged" : "Low Engagement";
}

/* one accent color per engagement category, used consistently across the
   detail meters, checklist headers, glossary cards, and category MVPs */
const CAT_COLOR_VAR = {
  advocacy: "--cat-advocacy",
  compliance: "--cat-compliance",
  education: "--cat-education",
  communications: "--cat-communications",
  collab: "--cat-collab",
};
function catColor(key) {
  return `var(${CAT_COLOR_VAR[key] || "--navy"})`;
}
function catColorPill(key) {
  const base = CAT_COLOR_VAR[key];
  if (!base) return "background:var(--grid);color:var(--ink-sec);";
  return `background:var(${base}-bg);color:var(${base}-tx);`;
}

function slugify(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

/* term key = "<category key>::<slugified term>" so the same label under two
   categories (e.g. "Online Educational Content") resolves to two different entries */
let TERM_LOOKUP = {};
function buildTermLookup() {
  TERM_LOOKUP = {};
  (DATA.glossary || []).forEach((cat) => {
    TERM_LOOKUP[cat.key + "::" + slugify(cat.label)] = {
      term: cat.label, definition: cat.description, source: "category",
      categoryKey: cat.key, categoryLabel: cat.label,
    };
    cat.terms.forEach((t) => {
      TERM_LOOKUP[cat.key + "::" + slugify(t.term)] = { ...t, categoryKey: cat.key, categoryLabel: cat.label };
    });
  });
}

/* Wraps a category/item label as a hoverable, clickable link into the Glossary
   tab when a matching definition exists; otherwise returns the plain label. */
function termSpan(categoryKey, label) {
  const key = categoryKey + "::" + slugify(label);
  const entry = TERM_LOOKUP[key];
  if (!entry) return `<span>${label}</span>`;
  const title = entry.source === "undocumented" ? "Not yet documented. Click for details." : entry.definition.replace(/"/g, "&quot;");
  return `<a class="term-link" href="#/glossary/${encodeURIComponent(key)}" title="${title}">${label}</a>`;
}

function deltaHtml(v) {
  if (v == null) return '<span class="delta flat">–</span>';
  if (v === 0) return '<span class="delta flat">▬ flat</span>';
  if (v > 0) return `<span class="delta up">▲ +${v}</span>`;
  return `<span class="delta down">▼ ${v}</span>`;
}

/* ---------------- boot ---------------- */
fetch("engagement.json")
  .then((r) => r.json())
  .then((d) => {
    DATA = d;
    buildTermLookup();
    window.addEventListener("hashchange", route);
    route();
    setupSearch();
    document.getElementById("print-fab").addEventListener("click", () => window.print());
  });

function currentRoute() {
  const h = location.hash.replace(/^#/, "") || "/";
  return h;
}

function route() {
  const r = currentRoute();
  const navKey = r.startsWith("/cu/") ? "" : r.startsWith("/glossary") ? "/glossary" : r;
  document.querySelectorAll("#nav-tabs a").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("data-route") === navKey);
  });
  if (r === "/" ) { renderLeaderboard(); window.scrollTo(0, 0); }
  else if (r === "/awards") { renderAwards(); window.scrollTo(0, 0); }
  else if (r.startsWith("/cu/")) { renderDetail(decodeURIComponent(r.slice(4))); window.scrollTo(0, 0); }
  else if (r.startsWith("/glossary")) {
    const rest = r.slice("/glossary".length).replace(/^\//, "");
    const target = rest ? decodeURIComponent(rest) : null;
    renderGlossary(target);
    if (!target) window.scrollTo(0, 0); // renderGlossary handles its own scroll when jumping to a term
  }
  else { renderLeaderboard(); window.scrollTo(0, 0); }
}

/* ---------------- search ---------------- */
function setupSearch() {
  const input = document.getElementById("global-search");
  const box = document.getElementById("global-results");
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { box.classList.remove("show"); box.innerHTML = ""; return; }
    const matches = DATA.cus.filter((c) => c.cu.toLowerCase().includes(q)).slice(0, 8);
    box.innerHTML = matches.map((c) =>
      `<a href="#/cu/${encodeURIComponent(c.charter)}">${c.cu} <span style="color:var(--ink-muted)">· ${c.state}, Group ${c.asset_group}</span></a>`
    ).join("") || `<a style="color:var(--ink-muted)">No matches</a>`;
    box.classList.add("show");
  });
  document.addEventListener("click", (e) => {
    if (!box.contains(e.target) && e.target !== input) box.classList.remove("show");
  });
  box.addEventListener("click", () => { input.value = ""; box.classList.remove("show"); });
}

/* ---------------- leaderboard ---------------- */
function renderLeaderboard() {
  const L = DATA.league;
  const view = document.getElementById("view");

  const groupOptions = Object.keys(L.asset_groups).sort((a, b) => a - b)
    .map((g) => `<option value="${g}">Group ${g} (${L.asset_groups[g].n} CUs)</option>`).join("");
  const stateOptions = [...new Set(DATA.cus.map((c) => c.state))].sort()
    .map((s) => `<option value="${s}">${s}</option>`).join("");

  view.innerHTML = `
    <div class="statstrip">
      <div class="stat-tile"><div class="label">Credit Unions</div><div class="value">${L.total_cus}</div></div>
      <div class="stat-tile"><div class="label">League Average</div><div class="value">${L.league_avg}<span style="font-size:13px;color:var(--ink-muted)">/${L.total_possible}</span></div></div>
      <div class="stat-tile"><div class="label"><span class="tier-dot" style="background:#0a5c0a"></span>Highly Engaged</div><div class="value">${L.tier_counts.high}</div><div class="sub">${pct(L.tier_counts.high, L.total_cus)}%</div></div>
      <div class="stat-tile"><div class="label"><span class="tier-dot" style="background:#8a5a00"></span>Moderately Engaged</div><div class="value">${L.tier_counts.mod}</div><div class="sub">${pct(L.tier_counts.mod, L.total_cus)}%</div></div>
      <div class="stat-tile"><div class="label"><span class="tier-dot" style="background:#8f1f1f"></span>Low Engagement</div><div class="value">${L.tier_counts.low}</div><div class="sub">${pct(L.tier_counts.low, L.total_cus)}%</div></div>
    </div>

    <div class="filters">
      <input type="text" id="tbl-search" placeholder="Search credit union…" value="${filters.q}"/>
      <select id="filter-group"><option value="all">All asset groups</option>${groupOptions}</select>
      <select id="filter-state"><option value="all">All states</option>${stateOptions}</select>
      <span class="count" id="result-count"></span>
    </div>

    <table class="board">
      <thead>
        <tr>
          <th data-key="overall_rank">Rank</th>
          <th data-key="cu">Credit Union</th>
          <th data-key="asset_group">Asset Group</th>
          <th data-key="assets">Assets</th>
          <th data-key="q1_total">Score</th>
          <th data-key="tier">Tier</th>
          <th data-key="peer_avg">Peer Avg</th>
          <th data-key="variance">vs Q4</th>
        </tr>
      </thead>
      <tbody id="board-body"></tbody>
    </table>
  `;

  document.getElementById("tbl-search").addEventListener("input", (e) => { filters.q = e.target.value; renderBody(); });
  document.getElementById("filter-group").addEventListener("change", (e) => { filters.group = e.target.value; renderBody(); });
  document.getElementById("filter-state").addEventListener("change", (e) => { filters.state = e.target.value; renderBody(); });
  document.querySelectorAll("th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const k = th.getAttribute("data-key");
      if (sortKey === k) sortDir = sortDir === "asc" ? "desc" : "asc";
      else { sortKey = k; sortDir = "desc"; }
      renderBody();
    });
  });

  renderBody();
}

function pct(n, total) { return Math.round((n / total) * 1000) / 10; }

function renderBody() {
  let rows = DATA.cus.filter((c) => {
    if (filters.q && !c.cu.toLowerCase().includes(filters.q.toLowerCase())) return false;
    if (filters.group !== "all" && String(c.asset_group) !== filters.group) return false;
    if (filters.state !== "all" && c.state !== filters.state) return false;
    return true;
  });
  rows.sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === "cu") { av = a.cu; bv = b.cu; }
    if (typeof av === "string") { av = av.toLowerCase(); bv = bv.toLowerCase(); }
    if (av == null) av = -Infinity;
    if (bv == null) bv = -Infinity;
    if (av < bv) return sortDir === "asc" ? -1 : 1;
    if (av > bv) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  document.getElementById("result-count").textContent = `${rows.length} of ${DATA.cus.length} credit unions`;
  document.getElementById("board-body").innerHTML = rows.map((c) => `
    <tr onclick="location.hash='#/cu/${encodeURIComponent(c.charter)}'">
      <td class="rank-cell">#${c.overall_rank}</td>
      <td class="cu-cell"><div class="cu-name">${c.cu}</div><div class="cu-meta">${c.state} · CEO ${c.ceo || "–"}</div></td>
      <td>Group ${c.asset_group}</td>
      <td>${fmtMoneyShort(c.assets)}</td>
      <td class="score-cell">${c.q1_total}<span style="color:var(--ink-muted);font-weight:500;">/${DATA.league.total_possible}</span></td>
      <td><span class="tier-pill ${c.tier}">${tierLabel(c.tier)}</span></td>
      <td>${c.peer_avg ?? "–"}</td>
      <td>${deltaHtml(c.variance)}</td>
    </tr>
  `).join("");
}

/* ---------------- detail ---------------- */
function renderDetail(charter) {
  const c = DATA.cus.find((x) => String(x.charter) === String(charter));
  const view = document.getElementById("view");
  if (!c) { view.innerHTML = `<p>Credit union not found.</p>`; return; }

  const meters = c.categories.map((cat) => {
    const pct = cat.possible ? Math.min(100, Math.round((cat.actual / cat.possible) * 100)) : 0;
    const avg = DATA.league.category_avgs[cat.key];
    const over = cat.actual > cat.possible;
    const cc = catColor(cat.key);
    return `
      <div class="meter-row">
        <div class="meter-label"><span class="cat-dot" style="background:${cc}"></span>${termSpan(cat.key, cat.label)}</div>
        <div class="meter-track"><div class="meter-fill" style="width:${pct}%;background:${cc}"></div></div>
        <div class="meter-value"${over ? ' style="color:var(--gold)"' : ""}>${cat.actual}<span class="of">/${cat.possible}</span>${over ? '<span class="avgnote" style="color:var(--gold)">exceeds category max, see note below</span>' : `<span class="avgnote">league avg ${avg}</span>`}</div>
      </div>`;
  }).join("");
  const anyOverflow = c.categories.some((cat) => cat.actual > cat.possible);

  const checklist = c.categories.map((cat) => {
    const cc = catColor(cat.key);
    const rows = cat.items.map((it) =>
      `<div class="item-row">${termSpan(cat.key, it.label)}<span class="item-value">${it.value}</span></div>`
    ).join("") || `<div class="item-row muted">No qualifying activity this quarter</div>`;
    return `<div class="cat-block" style="border-left-color:${cc}"><div class="cat-head"><span class="cat-title-wrap"><span class="cat-dot" style="background:${cc}"></span>${termSpan(cat.key, cat.label)}</span><span>${cat.actual}/${cat.possible}</span></div>${rows}</div>`;
  }).join("");

  const ext = c.extended.map((it) =>
    `<div class="ext-row"><span class="ext-label">${it.label}</span><span class="ext-value">${it.value}</span></div>`
  ).join("");

  view.innerHTML = `
    <a class="back-link" href="#/">&larr; Back to leaderboard</a>
    <div class="detail-card">
      <div class="group-flag">ASSET GROUP ${c.asset_group} · RANK #${c.rank} OF ${c.group_n} · #${c.overall_rank} LEAGUE-WIDE</div>
      <div class="identity">
        <div>
          <div class="cu-name-lg">${c.cu}</div>
          <div class="cu-meta-lg">CEO ${c.ceo || "–"} · ${c.state} · Charter #${c.charter}</div>
        </div>
      </div>
      <div class="cu-stats">
        <div><div class="stat-label">Total Assets</div><div class="stat-value">${fmtMoney(c.assets)}</div></div>
        <div><div class="stat-label">Members</div><div class="stat-value">${fmtNum(c.members)}</div></div>
        <div><div class="stat-label">FTE</div><div class="stat-value">${fmtNum(c.fte)}</div></div>
        <div><div class="stat-label">Asset Group Range</div><div class="stat-value" style="font-size:12px;">${fmtMoneyShort(c.group_min)}–${fmtMoneyShort(c.group_max)}</div></div>
      </div>
      <div class="score-row">
        <div class="score-num">${c.q1_total}<span class="score-of">/${DATA.league.total_possible}</span></div>
        <div class="score-side">
          <span class="tier-pill ${c.tier}" style="width:fit-content;">${tierLabel(c.tier)}</span>
          <div>${deltaHtml(c.variance)} <span style="color:var(--ink-muted);font-size:11.5px;">vs Q4 2025</span></div>
          <div style="font-size:11.5px;color:var(--ink-sec);">Peer average (Group ${c.asset_group}): ${c.peer_avg ?? "–"}</div>
        </div>
      </div>
      <div class="section-title">Engagement by Category</div>
      <div class="meters">${meters}</div>
      ${anyOverflow ? `<div style="font-size:10.5px;color:var(--ink-muted);margin-top:10px;line-height:1.4;">Note: one or more categories above show more points than the usual max. The underlying data counts things like committee seats as a running total rather than a single yes/no, so a CU can exceed the typical category cap. Flagged here rather than hidden.</div>` : ""}
    </div>

    <div class="detail-card">
      <div class="section-title">Activity Checklist</div>
      <div class="checklist-grid">${checklist}</div>
    </div>

    ${ext ? `<div class="detail-card"><div class="section-title">Extended Activity Detail</div><div class="ext-grid">${ext}</div></div>` : ""}
  `;
}

/* ---------------- awards ---------------- */
function renderAwards() {
  const cus = DATA.cus;
  const byScore = [...cus].sort((a, b) => b.q1_total - a.q1_total);
  const champion = byScore[0];

  const withVar = cus.filter((c) => c.variance != null);
  const mostImproved = [...withVar].sort((a, b) => b.variance - a.variance)[0];
  const biggestDrop = [...withVar].sort((a, b) => a.variance - b.variance)[0];
  const mostConsistent = [...withVar].filter((c) => c.variance === 0).sort((a, b) => b.q1_total - a.q1_total)[0];

  const groupChamps = Object.keys(DATA.league.asset_groups).sort((a, b) => a - b).map((g) => {
    const top = cus.filter((c) => String(c.asset_group) === g).sort((a, b) => b.q1_total - a.q1_total)[0];
    return { g, top };
  });

  const perfectClub = cus.filter((c) => c.q1_total === DATA.league.total_possible);

  const catMeta = DATA.league.category_meta;
  const mvps = catMeta.map((cm) => {
    const top = [...cus].sort((a, b) => {
      const av = a.categories.find((x) => x.key === cm.key).actual;
      const bv = b.categories.find((x) => x.key === cm.key).actual;
      return bv - av;
    })[0];
    const val = top.categories.find((x) => x.key === cm.key).actual;
    return { cm, top, val };
  });

  const view = document.getElementById("view");
  view.innerHTML = `
    <div class="section-title" style="margin-top:0;">League Leaders</div>
    <div class="award-grid">
      <div class="award-card">
        <div class="tag">League Champion</div>
        <div class="who">${link(champion)}</div>
        <div class="why">Highest total engagement score in the league this quarter.</div>
        <div class="fig">${champion.q1_total}/${DATA.league.total_possible} points</div>
      </div>
      <div class="award-card">
        <div class="tag">Most Improved</div>
        <div class="who">${link(mostImproved)}</div>
        <div class="why">Biggest jump in points since Q4 2025.</div>
        <div class="fig">+${mostImproved.variance} points</div>
      </div>
      <div class="award-card">
        <div class="tag">Steadiest</div>
        <div class="who">${mostConsistent ? link(mostConsistent) : "–"}</div>
        <div class="why">No change vs. Q4 2025, highest score among those holding flat.</div>
        <div class="fig">${mostConsistent ? mostConsistent.q1_total + " points, flat" : "–"}</div>
      </div>
    </div>

    ${perfectClub.length ? `
    <div class="section-title">Perfect Score Club (${DATA.league.total_possible}/${DATA.league.total_possible})</div>
    <div class="award-grid">
      ${perfectClub.map((c) => `
        <div class="award-card">
          <div class="tag">Group ${c.asset_group}</div>
          <div class="who">${link(c)}</div>
          <div class="why">Full marks across every category this quarter.</div>
        </div>`).join("")}
    </div>` : ""}

    <div class="section-title">Asset Group Champions</div>
    <div class="award-grid">
      ${groupChamps.map(({ g, top }) => `
        <div class="award-card">
          <div class="tag">Group ${g} · ${DATA.league.asset_groups[g].n} CUs</div>
          <div class="who">${link(top)}</div>
          <div class="why">Top score within its asset group peer set.</div>
          <div class="fig">${top.q1_total}/${DATA.league.total_possible} points</div>
        </div>`).join("")}
    </div>

    <div class="section-title">Category MVPs</div>
    <div class="mvp-grid">
      ${mvps.map(({ cm, top, val }) => `
        <div class="mvp-card" style="border-left-color:${catColor(cm.key)}">
          <div class="cat"><span class="cat-dot" style="background:${catColor(cm.key)}"></span>${cm.label}</div>
          <div class="who">${link(top)}</div>
          <div class="fig"${val > cm.possible ? ' style="color:var(--gold)"' : ""}>${val}/${cm.possible} points${val > cm.possible ? " *" : ""}</div>
        </div>`).join("")}
    </div>
    <div style="font-size:10.5px;color:var(--ink-muted);margin:6px 0 0;">* exceeds the usual category max. Some items (like committee seats) count as a running total rather than yes/no.</div>

    <div class="section-title">Room for Growth</div>
    <div class="award-grid">
      <div class="award-card">
        <div class="tag">Biggest Q1 Dip</div>
        <div class="who">${link(biggestDrop)}</div>
        <div class="why">Largest point decrease since Q4 2025. Could be a good outreach candidate.</div>
        <div class="fig">${biggestDrop.variance} points</div>
      </div>
    </div>
  `;
}

function link(c) {
  return `<a href="#/cu/${encodeURIComponent(c.charter)}">${c.cu}</a>`;
}

/* ---------------- glossary ---------------- */
const SOURCE_BADGE = {
  definitions_sheet: { label: "From the Definitions sheet", cls: "src-doc" },
  inferred: { label: "Best guess (unconfirmed)", cls: "src-guess" },
  undocumented: { label: "Not yet documented", cls: "src-none" },
  category: { label: "Category overview", cls: "src-doc" },
};

function renderGlossary(highlightKey) {
  const view = document.getElementById("view");
  const cats = DATA.glossary || [];

  view.innerHTML = `
    <div class="section-title" style="margin-top:0;">What Each Term Means</div>
    <p class="glossary-intro">Hover any underlined term on a credit union's profile page to see its definition, or click it to jump here.
      Definitions marked <span class="src-badge src-doc">From the Definitions sheet</span> come straight from the League's own reference tab.
      <span class="src-badge src-guess">Best guess</span> means this conversation traced a likely connection to an older definition but it isn't confirmed.
      <span class="src-badge src-none">Not yet documented</span> means there's no definition on file at all yet. Worth adding as part of the report redesign.</p>

    ${cats.map((cat) => `
      <div class="glossary-cat" style="border-left-color:${catColor(cat.key)}" id="term-${slugify(cat.key + "::" + cat.label)}">
        <div class="glossary-cat-head">
          <span class="glossary-cat-title"><span class="cat-dot" style="background:${catColor(cat.key)};display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;"></span>${cat.label}</span>
          <span class="glossary-cat-possible" style="${catColorPill(cat.key)}">${cat.possible} points possible</span>
        </div>
        <div class="glossary-cat-desc">${cat.description}</div>
        <div class="term-list">
          ${cat.terms.map((t) => {
            const key = cat.key + "::" + slugify(t.term);
            const badge = SOURCE_BADGE[t.source] || SOURCE_BADGE.undocumented;
            return `
              <div class="term-row" id="term-${slugify(key)}">
                <div class="term-name">${t.term} <span class="src-badge ${badge.cls}">${badge.label}</span></div>
                <div class="term-def">${t.definition}</div>
              </div>`;
          }).join("")}
        </div>
      </div>
    `).join("")}
  `;

  if (highlightKey) {
    const el = document.getElementById("term-" + slugify(highlightKey));
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("term-highlight");
      setTimeout(() => el.classList.remove("term-highlight"), 2200);
    }
  }
}
