// web/app.js — render the World Cup tipping UI from web/data.json.
import { flag } from "./flags.js";

const $ = (sel, root = document) => root.querySelector(sel);

// Order + labels for the metric pills in a country breakdown.
const METRICS = [
  ["win", "Win"], ["draw", "Draw"], ["gf", "GF"], ["ga", "GA"],
  ["yellow", "YC"], ["red", "RC"], ["group_winner", "Grp win"],
  ["qualify", "Qual"], ["r16", "R16"], ["qf", "QF"], ["sf", "SF"], ["final", "Final"],
  ["winner", "Champion"],
];
const WEIGHT_LABELS = {
  win: "Win", draw: "Draw", loss: "Loss", gf: "Goal for", ga: "Goal against",
  yellow: "Yellow card", red: "Red card", group_winner: "Group winner",
  qualify: "Qualify (R32)", r16: "Round of 16", qf: "Quarter-final", sf: "Semi-final",
  final: "Reach final", winner: "Champion",
};
const MEDALS = { 1: "🥇", 2: "🥈", 3: "🥉" };
const STAGE_LABEL = {
  r32: "Round of 32", r16: "Round of 16", qf: "Quarter-final",
  sf: "Semi-final", third: "3rd place", final: "Final",
};

const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function signed(n) { return n > 0 ? `+${n}` : `${n}`; }

function relTime(iso) {
  const then = new Date(iso).getTime();
  if (!then) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

function fmtDate(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleString(undefined,
    { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

let DATA = null;

boot();

async function boot() {
  try {
    const res = await fetch("data.json", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    DATA = await res.json();
  } catch (e) {
    $("#loading").outerHTML =
      `<div class="card-error"><strong>Couldn't load the standings.</strong>
       <p>Serve this folder with <code>python3 -m wc_scorer serve</code>, then open
       the printed URL — opening the file directly blocks data loading.</p></div>`;
    return;
  }
  $("#loading").hidden = true;
  renderUpdated();
  renderSummary();
  renderBoard();
  renderFixtures();
  renderCountries();
  renderRules();
  wireSearch();
  wireTabs();
}

function renderUpdated() {
  const el = $("#updated");
  const rel = relTime(DATA.generated_at);
  if (!rel) return;
  el.innerHTML = `<span class="dot">●</span> Updated ${rel}`;
  el.hidden = false;
}

function renderSummary() {
  const t = DATA.tournament;
  const top = DATA.entrants.slice(0, 3);
  const pct = Math.round((t.matches_played / t.matches_total) * 100);
  const order = [top[1], top[0], top[2]]; // silver, gold, bronze (podium shape)
  const pods = order.map((e) => {
    if (!e) return `<div class="pod"></div>`;
    const cls = e.rank === 1 ? "pod pod--1" : "pod";
    return `<div class="${cls}">
        <div class="pod__medal">${MEDALS[e.rank]}</div>
        <div class="pod__name">${esc(e.name)}</div>
        <div class="pod__pts num">${e.total}</div>
        <div class="pod__sub">${esc(e.star)}</div>
      </div>`;
  }).join("");
  $("#summary").innerHTML = `
    <div class="summary__eyebrow">Leaderboard <span class="pill">${esc(t.stage)}</span></div>
    <div class="podium">${pods}</div>
    <div class="progress">
      <div class="progress__row">
        <span class="progress__label">Matches played</span>
        <span class="progress__count num"><b>${t.matches_played}</b> / ${t.matches_total}</span>
      </div>
      <div class="progress__bar"><div class="progress__fill" style="width:${pct}%"></div></div>
    </div>`;
}

function renderBoard() {
  const board = $("#board");
  board.innerHTML = "";
  for (const e of DATA.entrants) {
    const li = document.createElement("li");
    li.className = "row" + (e.rank <= 3 ? " is-top" : "");
    li.dataset.name = e.name.toLowerCase();
    li.dataset.rank = e.rank;
    const rankCell = MEDALS[e.rank]
      ? `<span class="rank medal">${MEDALS[e.rank]}</span>`
      : `<span class="rank num">${e.rank}</span>`;
    li.innerHTML = `
      <button class="row__head" aria-expanded="false">
        ${rankCell}
        <span class="who">
          <span class="who__name">${esc(e.name)}</span>
          <span class="who__star"><span class="fl">${flag(e.star)}</span>
            <span class="st">★</span>${esc(e.star)}</span>
        </span>
        <span class="score"><span class="score__pts num">${e.total}</span><span class="score__u">pts</span></span>
        <span class="chev">▾</span>
      </button>`;
    li.querySelector(".row__head").addEventListener("click", () => toggleRow(li, e));
    board.appendChild(li);
  }
}

function toggleRow(li, entrant) {
  const open = li.classList.toggle("is-open");
  li.querySelector(".row__head").setAttribute("aria-expanded", open);
  let bd = li.querySelector(".bd");
  if (open && !bd) {
    bd = buildBreakdown(entrant);
    li.appendChild(bd);
  } else if (bd) {
    bd.hidden = !open;
  }
}

function buildBreakdown(entrant) {
  const countries = Object.entries(entrant.by_country)
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => b.points - a.points);
  const maxAbs = Math.max(1, ...countries.map((c) => Math.abs(c.points)));

  const wrap = document.createElement("div");
  wrap.className = "bd";
  wrap.innerHTML = `
    <p class="bd__hint">${countries.length} teams backed · tap a country for its points</p>
    <ol class="ct"></ol>
    <div class="bd__total">
      <span class="lbl">Total</span>
      <span class="val num">${entrant.total}<small>pts</small></span>
    </div>`;

  const list = wrap.querySelector(".ct");
  for (const c of countries) {
    const grp = DATA.team_group[c.name] || "?";
    const isStar = c.multiplier === 5;
    const multCls = isStar ? "star" : "m" + c.multiplier;
    const w = Math.round((Math.abs(c.points) / maxAbs) * 100);
    const li = document.createElement("li");
    li.className = "ctry";
    li.innerHTML = `
      <button class="ctry__head" aria-expanded="false">
        <span class="ctry__fl">${flag(c.name)}</span>
        <span class="ctry__main">
          <span class="ctry__top">
            <span class="ctry__name">${esc(c.name)}</span>
            <span class="grp">${grp}</span>
            <span class="mult ${multCls}">${isStar ? "★×5" : "×" + c.multiplier}</span>
          </span>
          <span class="bar${c.points < 0 ? " neg" : ""}"><i style="width:${w}%"></i></span>
        </span>
        <span class="ctry__pts num${c.points === 0 ? " zero" : ""}">${signed(c.points)}</span>
      </button>`;
    li.querySelector(".ctry__head").addEventListener("click", () => {
      const open = li.classList.toggle("is-open");
      li.querySelector(".ctry__head").setAttribute("aria-expanded", open);
      let pills = li.querySelector(".pills");
      if (open && !pills) li.appendChild(renderPills(c.components));
      else if (pills) pills.hidden = !open;
    });
    list.appendChild(li);
  }
  return wrap;
}

function renderPills(components) {
  const box = document.createElement("div");
  box.className = "pills";
  const parts = [];
  for (const [key, label] of METRICS) {
    const v = components[key];
    if (!v) continue;
    const cls = v > 0 ? "pos" : "neg";
    parts.push(`<span class="pill-m ${cls}">${label}<b>${signed(v)}</b></span>`);
  }
  box.innerHTML = parts.length ? parts.join("") :
    `<span class="pill-m">No points yet</span>`;
  return box;
}

/* ---------- Find me ---------- */
function wireSearch() {
  const input = $("#find");
  const clear = $("#find-clear");
  const result = $("#find-result");
  const rows = [...$("#board").children];

  function apply() {
    const q = input.value.trim().toLowerCase();
    clear.hidden = !q;
    let matches = [];
    for (const li of rows) {
      const hit = !q || li.dataset.name.includes(q);
      li.hidden = !hit;
      li.classList.remove("is-hit");
      const nameEl = li.querySelector(".who__name");
      nameEl.innerHTML = highlight(nameEl.textContent, q);
      if (hit && q) matches.push(li);
    }
    if (!q) { result.hidden = true; return; }
    result.hidden = false;
    if (matches.length === 1) {
      const li = matches[0];
      li.classList.add("is-hit");
      const nm = li.querySelector(".who__name").textContent;
      result.innerHTML = `<b>${esc(nm)}</b> — ${ordinal(+li.dataset.rank)} of ${rows.length}`;
      li.scrollIntoView({ block: "center", behavior: "smooth" });
    } else if (matches.length === 0) {
      result.textContent = `No one matches “${input.value.trim()}”.`;
    } else {
      result.innerHTML = `<b>${matches.length}</b> players match.`;
    }
  }
  input.addEventListener("input", apply);
  clear.addEventListener("click", () => { input.value = ""; apply(); input.focus(); });
}

function highlight(text, q) {
  if (!q) return esc(text);
  const i = text.toLowerCase().indexOf(q);
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length)) +
    "</mark>" + esc(text.slice(i + q.length));
}

function ordinal(n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/* ---------- Fixtures ---------- */
function renderFixtures() {
  const wrap = $("#fixtures");
  const ms = DATA.matches.filter((m) => m.team_a && m.team_b);
  const done = ms.filter((m) => m.completed).sort(byDateDesc);
  const next = ms.filter((m) => !m.completed).sort((a, b) => -byDateDesc(a, b));

  const t = DATA.tournament;
  wrap.innerHTML = `
    <div class="sec-head"><span class="ico">⚽</span>
      <div><h1>Fixtures</h1><div class="sub">${t.matches_played} of ${t.matches_total} played</div></div>
    </div>`;
  if (done.length) {
    wrap.insertAdjacentHTML("beforeend", `<div class="stage-h">Results</div>`);
    done.forEach((m) => wrap.insertAdjacentHTML("beforeend", fixtureCard(m)));
  }
  if (next.length) {
    wrap.insertAdjacentHTML("beforeend", `<div class="stage-h">Upcoming</div>`);
    next.slice(0, 24).forEach((m) => wrap.insertAdjacentHTML("beforeend", fixtureCard(m)));
  }
}

function byDateDesc(a, b) { return new Date(b.date) - new Date(a.date); }

function fixtureCard(m) {
  const aw = m.completed && m.ga > m.gb, bw = m.completed && m.gb > m.ga;
  const score = m.completed ? `${m.ga}–${m.gb}` : "vs";
  const round = m.stage === "group"
    ? "Group " + (DATA.team_group[m.team_a] || "?")
    : (STAGE_LABEL[m.stage] || "");
  const pen = m.penalties
    ? `<div class="fx__pen">Penalties · ${esc(m.shootout_winner || "")} advance</div>` : "";
  return `<div class="fx${m.completed ? "" : " fx--sched"}">
      <div class="fx__meta">
        <span class="fx__date">${esc(fmtDate(m.date))}</span>
        <span class="fx__rd">${esc(round)}</span>
      </div>
      <div class="fx__teams">
        <span class="fx__t a ${aw ? "win" : bw ? "lose" : ""}">
          <span class="fl">${flag(m.team_a)}</span><span class="nm">${esc(m.team_a)}</span></span>
        <span class="fx__score${m.completed ? "" : " live"}">${score}</span>
        <span class="fx__t b ${bw ? "win" : aw ? "lose" : ""}">
          <span class="nm">${esc(m.team_b)}</span><span class="fl">${flag(m.team_b)}</span></span>
      </div>${pen}
    </div>`;
}

/* ---------- Countries ---------- */
function renderCountries() {
  const wrap = $("#countries");
  // Backers per team, in live-rank order (DATA.entrants is already rank-sorted).
  const backers = {};
  for (const e of DATA.entrants) {
    for (const [team, info] of Object.entries(e.by_country)) {
      (backers[team] ||= []).push(
        { rank: e.rank, name: e.name, mult: info.multiplier, points: info.points });
    }
  }
  const teams = [...DATA.teams].sort((a, b) => a.name.localeCompare(b.name));

  wrap.innerHTML = `
    <div class="sec-head"><span class="ico">🌍</span>
      <div><h1>Countries</h1><div class="sub">${teams.length} teams · tap one to see who backed it</div></div>
    </div>
    <ol class="tlist"></ol>`;
  const list = wrap.querySelector(".tlist");

  for (const t of teams) {
    const li = document.createElement("li");
    li.className = "tcard";
    li.innerHTML = `
      <button class="tcard__head" aria-expanded="false">
        <span class="tcard__fl">${flag(t.name)}</span>
        <span class="tcard__main">
          <span class="ctry__name">${esc(t.name)}</span>
          <span class="grp">${t.group}</span>
        </span>
        <span class="ctry__pts num${t.points === 0 ? " zero" : ""}">${signed(t.points)}</span>
        <span class="chev">▾</span>
      </button>`;
    // Attribution pills are always shown — the "minimised" per-team breakdown.
    li.appendChild(renderPills(t.components));
    li.querySelector(".tcard__head")
      .addEventListener("click", () => toggleTeam(li, backers[t.name] || []));
    list.appendChild(li);
  }
}

function toggleTeam(li, backers) {
  const open = li.classList.toggle("is-open");
  li.querySelector(".tcard__head").setAttribute("aria-expanded", open);
  let cb = li.querySelector(".cb");
  if (open && !cb) {
    cb = document.createElement("ol");
    cb.className = "cb";
    cb.innerHTML = backers.length ? backers.map(backerRow).join("")
      : `<li class="cb__empty">No one backed this team.</li>`;
    li.appendChild(cb);
  } else if (cb) {
    cb.hidden = !open;
  }
}

function backerRow(b) {
  const isStar = b.mult === 5;
  const multCls = isStar ? "star" : "m" + b.mult;
  const rankCell = MEDALS[b.rank]
    ? `<span class="rank medal">${MEDALS[b.rank]}</span>`
    : `<span class="rank num">${b.rank}</span>`;
  return `<li class="cb__row">
      ${rankCell}
      <span class="cb__name">${esc(b.name)}</span>
      <span class="mult ${multCls}">${isStar ? "★×5" : "×" + b.mult}</span>
      <span class="cb__pts num${b.points === 0 ? " zero" : ""}">${signed(b.points)}</span>
    </li>`;
}

/* ---------- Rules ---------- */
function renderRules() {
  const w = DATA.weights;
  const cells = Object.entries(WEIGHT_LABELS)
    .filter(([k]) => k in w && w[k] !== 0)
    .map(([k, label]) => {
      const v = w[k];
      const cls = v > 0 ? "pos" : "neg";
      return `<div class="w"><span class="k">${label}</span><span class="v ${cls} num">${signed(v)}</span></div>`;
    }).join("");
  const mults = [
    ["★×5", "Star team — your top pick", "star"],
    ["×3", "Ranked 1st in a group", "m3"],
    ["×2", "Ranked 2nd in a group", "m2"],
    ["×1", "Ranked 3rd in a group", "m1"],
  ].map(([tag, desc, cls]) =>
    `<div class="mrow"><span class="tag ${cls}">${tag}</span><span class="desc">${desc}</span></div>`
  ).join("");

  $("#rules").innerHTML = `
    <div class="sec-head"><span class="ico">📋</span>
      <div><h1>Scoring</h1><div class="sub">How every point is earned</div></div>
    </div>
    <div class="rules-card">
      <h2>Team points</h2>
      <p class="note">Each team earns points for its results. Penalty-shootout games count as a draw for both sides.</p>
      <div class="wgrid">${cells}</div>
    </div>
    <div class="rules-card">
      <h2>Your multipliers</h2>
      <p class="note">A team's points are multiplied by how you ranked it. Your total is the sum across all backed teams.</p>
      <div class="mlist">${mults}</div>
    </div>`;
}

/* ---------- Tabs ---------- */
function wireTabs() {
  const tabs = [...document.querySelectorAll(".tab")];
  const views = {
    standings: $("#view-standings"),
    fixtures: $("#view-fixtures"),
    countries: $("#view-countries"),
    rules: $("#view-rules"),
  };
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    tabs.forEach((t) => { t.classList.remove("is-active"); t.setAttribute("aria-selected", "false"); });
    tab.classList.add("is-active");
    tab.setAttribute("aria-selected", "true");
    for (const [name, el] of Object.entries(views)) el.hidden = name !== tab.dataset.view;
    window.scrollTo({ top: 0 });
  }));
}
