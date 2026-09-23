/* ResRec front-end: renders everything from window.RESREC_DATA (built by run_pipeline.py). */
(() => {
  const D = window.RESREC_DATA;
  if (!D) {
    document.body.insertAdjacentHTML("afterbegin",
      '<p style="padding:20px;background:#fde8e7">data.js not found. Run <code>.venv/bin/python run_pipeline.py</code> first.</p>');
    return;
  }
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => n.toLocaleString("en-US");
  const pct = x => Math.round(x * 100) + "%";
  const signed = x => (x > 0 ? "+" : "") + x.toFixed(2);

  const REVIEWS = D.reviews;
  const BY_ID = Object.fromEntries(REVIEWS.map(r => [r.id, r]));
  const RESTS = D.restaurants;
  const MIN = D.thresholds.min_mentions;
  const REST_EMOJI = { "Biriyani Nights": "🍛", "Night Food Joint": "🌙", "BOX8- Desi Meals": "📦" };
  const CAT = {
    "signature": { label: "★ Signature", name: "Signature" },
    "needs-improvement": { label: "⚠ Needs work", name: "Needs improvement" },
    "polarising": { label: "⇅ Polarising", name: "Polarising" },
    "steady": { label: "● Steady", name: "Steady" },
    "low-data": { label: "○ Few reviews", name: "Few reviews" },
  };
  const short = n => n.replace("- Desi Meals", "").replace("Biriyani ", "Biriyani ").trim();

  function emoji(d) {
    const s = d.toLowerCase();
    const map = [["biryani", "🍛"], ["kebab", "🍢"], ["tikka", "🍢"], ["salad", "🥗"], ["wrap", "🌯"], ["sandwich", "🥪"],
      ["brownie", "🍫"], ["cake", "🍰"], ["jamun", "🍡"], ["jamoon", "🍡"], ["halwa", "🍮"], ["lemonade", "🍋"], ["tea", "🧋"], ["noodles", "🍜"],
      ["fried rice", "🍚"], ["rice", "🍚"], ["pulao", "🍚"], ["paratha", "🫓"], ["naan", "🫓"], ["roti", "🫓"], ["kulcha", "🫓"],
      ["chapati", "🫓"], ["fries", "🍟"], ["wedges", "🍟"], ["potato", "🥔"], ["paneer", "🧀"], ["dal", "🥣"], ["rajma", "🥣"],
      ["chole", "🥣"], ["raita", "🥛"], ["lollypop", "🍗"], ["wings", "🍗"], ["popcorn", "🍗"], ["chicken", "🍗"], ["egg", "🥚"],
      ["gobi", "🥦"], ["mushroom", "🍄"], ["fish", "🐟"], ["manchurian", "🥘"], ["masala", "🥘"]];
    return (map.find(([k]) => s.includes(k)) || [0, "🍽️"])[1];
  }
  // real photo from src/image when the pipeline found one for this dish, emoji otherwise
  const IMAGES = D.images || {};
  const pic = (d, cls = "") => IMAGES[d] ? `<img class="food-img ${cls}" src="${IMAGES[d]}" alt="${esc(d)}" loading="lazy">` : emoji(d);
  const plateCls = d => IMAGES[d] ? " has-img" : "";
  const starStr = n => "★".repeat(Math.round(n)) + "☆".repeat(5 - Math.round(n));
  const badge = c => `<span class="badge ${c}">${CAT[c].label}</span>`;
  function sentBar(d) {
    const n = d.mentions;
    return `<div class="sent-bar" role="img" aria-label="${d.positive} positive, ${d.neutral} neutral, ${d.negative} negative">
      ${d.positive ? `<i class="p" style="flex:${d.positive}"></i>` : ""}${d.neutral ? `<i class="u" style="flex:${d.neutral}"></i>` : ""}${d.negative ? `<i class="n" style="flex:${d.negative}"></i>` : ""}
    </div><div class="sent-legend"><span><span class="dot p"></span><b>${pct(d.positive / n)}</b> pos</span><span><span class="dot u"></span><b>${pct(d.neutral / n)}</b> neu</span><span><span class="dot n"></span><b>${pct(d.negative / n)}</b> neg</span></div>`;
  }

  /* ---------------- nav ---------------- */
  window.addEventListener("scroll", () => $("#nav").classList.toggle("scrolled", scrollY > 10));
  $("#menuToggle").onclick = () => $("#navLinks").classList.toggle("open");
  document.querySelectorAll("#navLinks a").forEach(a => a.onclick = () => $("#navLinks").classList.remove("open"));

  /* ---------------- hero ---------------- */
  const totalRaw = D.funnel[0].remaining, totalClean = D.funnel.at(-1).remaining;
  const mentions = REVIEWS.reduce((a, r) => a + r.dishes.length, 0);
  const sigs = D.dishes.filter(d => d.category === "signature").sort((a, b) => b.love_score * Math.log(b.mentions) - a.love_score * Math.log(a.mentions));
  const top = sigs[0];
  $("#powerCard").innerHTML = `
    <div class="top"><span>Top signature dish</span><span class="stars">${starStr(top.avg_stars)}</span></div>
    <div class="body"><div class="mini-plate">${pic(top.dish)}</div>
      <div><h4>${esc(top.dish)}</h4><small>${esc(top.restaurant)} · ${top.mentions} mentions</small></div>
      <div class="score"><b>${signed(top.love_score)}</b><small>sentiment</small></div>
      <button class="round-add" style="background:#fff;color:var(--dark)" aria-label="Open reviews" data-open="${esc(top.restaurant)}|${esc(top.dish)}">→</button>
    </div>`;
  const heroDish = D.dishes.find(d => IMAGES[d.dish]);
  if (heroDish) {
    $(".big-plate").classList.add("has-img");
    $(".big-plate").innerHTML = pic(heroDish.dish);
  }
  const bubbles = [
    { e: "💬", b: fmt(totalRaw), t: "reviews analysed", s: "left:6%;top:7%" },
    { e: "🍛", b: fmt(mentions), t: "dish mentions", s: "right:6%;top:24%" },
    { e: "🏪", b: RESTS.length, t: "restaurants", s: "left:4%;bottom:12%" },
    { e: "🎯", b: pct(D.evaluation.accuracy), t: "agreement with stars", s: "right:10%;bottom:6%" },
  ];
  $("#heroBubbles").innerHTML = bubbles.map(x => `<div class="tag-bubble" style="${x.s}"><div class="ball">${x.e}</div><div class="lbl"><b>${x.b}</b>${x.t}</div></div>`).join("");

  // search across all dishes
  const search = $("#heroSearch"), results = $("#heroResults");
  search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    if (!q) { results.classList.remove("open"); return; }
    const hits = D.dishes.filter(d => d.dish.toLowerCase().includes(q)).slice(0, 8);
    results.innerHTML = hits.length ? hits.map(d => `<button data-open="${esc(d.restaurant)}|${esc(d.dish)}"><span class="search-pic">${pic(d.dish)}</span>
        <span>${esc(d.dish)}<small>${esc(d.restaurant)} · ${d.mentions} mentions · ${signed(d.love_score)}</small></span></button>`).join("")
      : `<div style="padding:12px;font-size:13px" class="muted">No dish matches "${esc(q)}"</div>`;
    results.classList.add("open");
  });
  document.addEventListener("click", e => { if (!e.target.closest(".search")) results.classList.remove("open"); });

  /* ---------------- signature cards ---------------- */
  const sigPick = [];
  for (const d of sigs) { if (!sigPick.some(x => x.restaurant === d.restaurant)) sigPick.push(d); if (sigPick.length === 3) break; }
  for (const d of sigs) { if (sigPick.length === 3) break; if (!sigPick.includes(d)) sigPick.push(d); }
  $("#sigCards").innerHTML = sigPick.map(dishCard).join("");

  function dishCard(d) {
    return `<article class="dish-card reveal">
      <div class="cat">${badge(d.category)}</div>
      <div class="rate" title="Average star rating of reviews that mention this dish"><span class="s">★</span>${d.avg_stars.toFixed(1)}</div>
      <div class="plate sm${plateCls(d.dish)}">${pic(d.dish)}</div>
      <h4>${esc(d.dish)}</h4>
      <div class="meta">${esc(d.restaurant)} · ${d.mentions} mention${d.mentions > 1 ? "s" : ""}</div>
      ${sentBar(d)}
      <div class="foot">
        <div class="love">${signed(d.love_score)}<small>sentiment score</small></div>
        <button class="round-add" aria-label="Open reviews for ${esc(d.dish)}" data-open="${esc(d.restaurant)}|${esc(d.dish)}">+</button>
      </div>
    </article>`;
  }


  /* ---------------- restaurants & menu ---------------- */
  const state = { rest: RESTS[0].name, filter: "all", sort: "mentions", page: 0, dish: null, q: "", sent: "", dishOnly: "", rpage: 0 };
  const MENU_PER = 6, REV_PER = 5;

  $("#restTabs").innerHTML = RESTS.map(r => `<button class="rest-tab" data-rest="${esc(r.name)}">
      <span class="emo">${REST_EMOJI[r.name] || "🍽️"}</span>
      <span><h4>${esc(r.name)}</h4><small>${esc(r.location)} · ${esc(r.rest_type)}</small></span>
      <span class="rt"><span style="color:var(--star)">★</span> ${esc(r.zomato_rate.replace("/5", ""))}<small>${fmt(r.reviews)} reviews</small></span>
    </button>`).join("");
  $("#restTabs").addEventListener("click", e => {
    const b = e.target.closest(".rest-tab"); if (!b) return;
    selectRestaurant(b.dataset.rest);
  });
  $("#footRests").textContent = RESTS.map(r => r.name).join(", ");

  function selectRestaurant(name, dish = null) {
    Object.assign(state, { rest: name, filter: "all", page: 0, dish, rpage: 0 });
    renderRestaurant();
  }

  function restDishes() {
    let ds = D.dishes.filter(d => d.restaurant === state.rest);
    if (state.filter !== "all") ds = ds.filter(d => d.category === state.filter);
    const key = { mentions: (a, b) => b.mentions - a.mentions, love: (a, b) => b.love_score - a.love_score, neg: (a, b) => b.neg_rate - a.neg_rate || b.mentions - a.mentions }[state.sort];
    return ds.sort(key);
  }

  function renderRestaurant() {
    document.querySelectorAll(".rest-tab").forEach(b => b.classList.toggle("active", b.dataset.rest === state.rest));
    const r = RESTS.find(x => x.name === state.rest);
    $("#restInfo").innerHTML = `<span>📍 <b>${esc(r.address)}</b></span><span>🍴 ${esc(r.cuisines)}</span><span>💰 ₹${esc(r.cost_for_two)} for two</span>
      <span>🗳️ ${fmt(r.votes)} Zomato votes</span><span>📝 ${r.with_dish} of ${r.reviews} reviews name a dish</span>`;
    const all = D.dishes.filter(d => d.restaurant === state.rest);
    const cats = ["all", "signature", "needs-improvement", "polarising", "steady", "low-data"];
    $("#menuFilters").innerHTML = cats.map(c => {
      const n = c === "all" ? all.length : all.filter(d => d.category === c).length;
      if (!n) return "";
      return `<button class="chip ${state.filter === c ? "active" : ""}" data-filter="${c}">${c === "all" ? "All dishes" : CAT[c].name}<span class="c">${n}</span></button>`;
    }).join("");
    renderMenu();
    renderReviews();
  }

  function renderMenu() {
    const ds = restDishes();
    const pages = Math.max(1, Math.ceil(ds.length / MENU_PER));
    state.page = Math.min(state.page, pages - 1);
    const slice = ds.slice(state.page * MENU_PER, (state.page + 1) * MENU_PER);
    $("#menuGrid").innerHTML = slice.length ? slice.map(dishCard).join("") : `<div class="empty">No dishes in this group.</div>`;
    $("#menuGrid").querySelectorAll(".reveal").forEach(el => el.classList.add("in"));
    $("#menuPager").innerHTML = `<button data-mp="-1" ${state.page === 0 ? "disabled" : ""} aria-label="Previous page">←</button>
      <button class="primary" data-mp="1" ${state.page >= pages - 1 ? "disabled" : ""} aria-label="Next page">→</button><span>Page ${state.page + 1} of ${pages} · ${ds.length} dishes</span>`;
  }
  $("#menuFilters").addEventListener("click", e => {
    const b = e.target.closest("[data-filter]"); if (!b) return;
    state.filter = b.dataset.filter; state.page = 0; renderRestaurant();
  });
  $("#menuSort").onchange = e => { state.sort = e.target.value; state.page = 0; renderMenu(); };
  $("#menuPager").addEventListener("click", e => { const b = e.target.closest("[data-mp]"); if (!b) return; state.page += +b.dataset.mp; renderMenu(); });

  /* ---------------- reviews before / after ---------------- */
  function highlightRaw(raw) {
    // mark the noise the preprocessing step removes
    const re = /(^\s*RATED\s*)|([ÃÂ\u0080-ÿ]+)|([^\x00-\x7F]+)|(https?:\/\/\S+)|(([!?.])\6{1,})|(\n+)/g;
    let out = "", last = 0, m;
    while ((m = re.exec(raw))) {
      out += esc(raw.slice(last, m.index));
      const t = m[0];
      if (m[1]) { out += `<span class="noise" title="platform prefix">${esc(t.trim())}\\n</span>\n`; last = m.index + t.length; continue; }
      const title = m[1] ? "platform prefix" : m[2] ? "broken encoding (mojibake)" : m[3] ? "emoji / non-ASCII" : m[4] ? "URL" : m[5] ? "repeated punctuation" : "line break";
      const shown = m[2] && t.length > 12 ? t.slice(0, 12) + "…" : t;
      out += m[7] ? `<span class="noise" title="${title}">\\n</span>${t}` : `<span class="noise" title="${title}">${esc(shown)}</span>`;
      last = m.index + t.length;
      if (t.length === 0) re.lastIndex++;
    }
    return out + esc(raw.slice(last));
  }

  function highlightClean(r, colourClauses = true) {
    const t = r.clean;
    return r.clauses.map(c => {
      let s = "", pos = c.start;
      for (const d of r.dishes.filter(d => d.start >= c.start && d.start < c.end)) {
        s += esc(t.slice(pos, d.start));
        const k = d.label === "positive" ? "p" : d.label === "negative" ? "n" : "u";
        s += `<mark class="dish ${k}" title="${esc(d.dish)} · ${d.label} ${signed(d.compound)}">${esc(t.slice(d.start, d.end))}</mark>`;
        pos = d.end;
      }
      s += esc(t.slice(pos, c.end));
      return colourClauses ? `<span class="cl ${c.label}" title="clause ${c.label} ${signed(c.compound)}">${s}</span>` : s;
    }).join(" ");
  }

  function dishWords(r) {
    const w = new Set();
    r.dishes.forEach(d => r.clean.slice(d.start, d.end).toLowerCase().split(/[^a-z0-9]+/).forEach(x => x && w.add(x)));
    return w;
  }

  function reviewCard(r) {
    const kept = new Set(r.tokens_nostop), hits = dishWords(r);
    const toks = r.tokens.map(t => `<span class="tok ${hits.has(t) ? "hit" : kept.has(t) ? "" : "stop"}">${esc(t)}</span>`);
    const kt = r.tokens_nostop.map(t => `<span class="tok ${hits.has(t) ? "hit" : ""}">${esc(t)}</span>`);
    const LIM = 40;
    const tokHtml = arr => arr.length > LIM ? arr.slice(0, LIM).join("") + `<span class="tok-more" hidden>${arr.slice(LIM).join("")}</span>` : arr.join("");
    const dishChips = [...new Map(r.dishes.map(d => [d.dish, d])).values()]
      .map(d => `<span class="sent-chip ${d.label}">${pic(d.dish, "inline")} ${esc(d.dish)} ${signed(d.compound)}</span>`).join("");
    return `<article class="review">
      <div class="review-head">
        <span class="stars">${starStr(r.rating)}</span><span class="sent-chip ${r.sentiment}">${r.sentiment}</span>
        <span class="score">VADER ${signed(r.compound)}</span>${dishChips}
        <span class="id">#${r.id}</span>
      </div>
      <div class="ba">
        <div class="ba-col before"><h5><span>Before · raw text</span><span>${r.raw.length} chars</span></h5><pre class="raw">${highlightRaw(r.raw)}</pre></div>
        <div class="ba-col after"><h5><span>After · cleaned &amp; tokenized</span><span>${r.clean.length} chars</span></h5>
          <div class="clean">${highlightClean(r)}</div>
          <div class="tok-title">Tokens (${r.tokens.length}) · <span style="text-transform:none;letter-spacing:0;font-weight:400">crossed out = stop word</span></div>
          <div class="toks">${tokHtml(toks)}</div>
          <div class="tok-title">After stop-word removal (${r.tokens_nostop.length})</div>
          <div class="toks">${tokHtml(kt)}</div>
          <button class="more-toggle" data-more>${r.tokens.length > LIM ? "Show all tokens + clause scores" : "Show clause scores"}</button>
          <table class="clause-table" hidden>${r.clauses.map(c => `<tr><td>${esc(c.text)}</td><td><span class="sent-chip ${c.label}">${signed(c.compound)}</span></td></tr>`).join("")}</table>
        </div>
      </div>
    </article>`;
  }

  function filteredReviews() {
    const q = state.q.toLowerCase();
    let ids = null;
    if (state.dish) ids = new Set(D.dishes.find(d => d.restaurant === state.rest && d.dish === state.dish)?.review_ids || []);
    return REVIEWS.filter(r => r.restaurant === state.rest
      && (!ids || ids.has(r.id))
      && (!state.sent || (state.dish ? r.dishes.some(d => d.dish === state.dish && d.label === state.sent) : r.sentiment === state.sent))
      && (!state.dishOnly || r.dishes.length)
      && (!q || r.clean.toLowerCase().includes(q)));
  }

  function renderReviews() {
    const rs = filteredReviews();
    const pages = Math.max(1, Math.ceil(rs.length / REV_PER));
    state.rpage = Math.min(state.rpage, pages - 1);
    $("#reviewsTitle").innerHTML = state.dish ? `${pic(state.dish, "inline title")} ${esc(state.dish)}: reviews before &amp; after tokenization`
      : `${esc(state.rest)}: reviews before &amp; after tokenization`;
    $("#dishFilterPill").innerHTML = state.dish ? `<span class="active-filter">Dish: ${esc(state.dish)} <button data-clear aria-label="Clear dish filter">✕</button></span>` : "";
    $("#reviewList").innerHTML = rs.length ? rs.slice(state.rpage * REV_PER, (state.rpage + 1) * REV_PER).map(reviewCard).join("")
      : `<div class="empty">No reviews match these filters.</div>`;
    $("#reviewPager").innerHTML = `<button data-rp="-1" ${state.rpage === 0 ? "disabled" : ""} aria-label="Previous page">←</button>
      <button class="primary" data-rp="1" ${state.rpage >= pages - 1 ? "disabled" : ""} aria-label="Next page">→</button><span>Page ${state.rpage + 1} of ${pages} · ${fmt(rs.length)} reviews</span>`;
  }
  $("#reviewPager").addEventListener("click", e => {
    const b = e.target.closest("[data-rp]"); if (!b) return;
    state.rpage += +b.dataset.rp; renderReviews(); $("#reviews").scrollIntoView({ behavior: "smooth" });
  });
  $("#reviewList").addEventListener("click", e => {
    const b = e.target.closest("[data-more]"); if (!b) return;
    const col = b.closest(".after");
    const open = b.dataset.expanded !== "1";
    col.querySelectorAll(".tok-more").forEach(x => x.hidden = !open);
    col.querySelector(".clause-table").hidden = !open;
    b.dataset.expanded = open ? "1" : "0";
    b.textContent = open ? "Hide details" : "Show all tokens + clause scores";
  });
  $("#dishFilterPill").addEventListener("click", e => { if (e.target.closest("[data-clear]")) { state.dish = null; state.rpage = 0; renderReviews(); } });
  let tmr;
  $("#reviewSearch").addEventListener("input", e => { clearTimeout(tmr); tmr = setTimeout(() => { state.q = e.target.value.trim(); state.rpage = 0; renderReviews(); }, 200); });
  $("#reviewSent").onchange = e => { state.sent = e.target.value; state.rpage = 0; renderReviews(); };
  $("#reviewDishOnly").onchange = e => { state.dishOnly = e.target.value; state.rpage = 0; renderReviews(); };

  // any [data-open="Restaurant|Dish"] button jumps to that dish's reviews
  document.addEventListener("click", e => {
    const b = e.target.closest("[data-open]"); if (!b) return;
    const [rest, dish] = b.dataset.open.split("|");
    results.classList.remove("open");
    selectRestaurant(rest, dish);
    $("#reviews").scrollIntoView({ behavior: "smooth" });
  });

  renderRestaurant();

  /* ---------------- spotlight ---------------- */
  const spots = REVIEWS.filter(r => r.rating >= 4 && r.dishes.some(d => d.label === "positive") && r.clean.length > 90 && r.clean.length < 380);
  let si = 0;
  function renderSpot() {
    const r = spots[(si % spots.length + spots.length) % spots.length];
    const d = r.dishes.find(x => x.label === "positive");
    $("#spotTitle").textContent = `Built on ${fmt(totalClean)}+ real customer reviews`;
    $("#spotText").innerHTML = highlightClean(r, false);
    $("#spotWho").textContent = `Review #${r.id}`;
    $("#spotDish").textContent = `${r.restaurant} · about ${d.dish}`;
    $("#spotStars").textContent = starStr(r.rating);
    $("#spotPlate").innerHTML = pic(d.dish);
    $("#spotPlate").className = "plate" + plateCls(d.dish);
    const ds = D.dishes.find(x => x.restaurant === r.restaurant && x.dish === d.dish);
    $("#spotF1").innerHTML = `<b>${signed(ds.love_score)}</b>${esc(d.dish)} score`;
    $("#spotF2").innerHTML = `<b>${ds.mentions}</b>reviews mention it`;
  }
  $("#spotPrev").onclick = () => { si--; renderSpot(); };
  $("#spotNext").onclick = () => { si++; renderSpot(); };
  renderSpot();

  /* ---------------- dashboard ---------------- */
  const css = getComputedStyle(document.documentElement);
  const C = k => css.getPropertyValue(k).trim();
  const COL = { pos: C("--pos"), neu: C("--neu"), neg: C("--neg"), dark: C("--dark"), sage: C("--sage"), line: C("--line"), ink2: C("--ink-2") };
  const charts = {};
  let dashRest = "all";
  if (window.Chart) {
    Chart.defaults.font.family = "Poppins, system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = COL.ink2;
    Chart.defaults.plugins.legend.display = false;
    Object.assign(Chart.defaults.plugins.tooltip, { backgroundColor: "#1f2927", padding: 10, cornerRadius: 10, boxPadding: 4 });
  }
  const grid = { color: COL.line, drawTicks: false };
  function draw(id, cfg) {
    if (!window.Chart) { $("#" + id).parentElement.innerHTML = '<p class="muted">Charts need an internet connection (Chart.js CDN).</p>'; return; }
    charts[id]?.destroy();
    charts[id] = new Chart($("#" + id), cfg);
  }

  $("#dashFilter").innerHTML = [["all", "All restaurants"], ...RESTS.map(r => [r.name, r.name])]
    .map(([v, l]) => `<button class="chip" data-dash="${esc(v)}">${v === "all" ? "🏪" : REST_EMOJI[v]} ${esc(l)}</button>`).join("");
  $("#dashFilter").addEventListener("click", e => { const b = e.target.closest("[data-dash]"); if (!b) return; dashRest = b.dataset.dash; renderDash(); });

  function renderDash() {
    document.querySelectorAll("[data-dash]").forEach(b => b.classList.toggle("active", b.dataset.dash === dashRest));
    const inRest = x => dashRest === "all" || x.restaurant === dashRest;
    const rv = REVIEWS.filter(inRest), ds = D.dishes.filter(inRest);
    const nd = rv.filter(r => r.dishes.length).length;
    const avg = rv.reduce((a, r) => a + r.rating, 0) / rv.length;
    const posShare = rv.filter(r => r.sentiment === "positive").length / rv.length;
    $("#kpis").innerHTML = [
      ["Clean reviews", fmt(rv.length), dashRest === "all" ? `from ${fmt(totalRaw)} raw` : "after preprocessing"],
      ["Reviews naming a dish", pct(nd / rv.length), `${fmt(nd)} reviews`],
      ["Average star rating", avg.toFixed(2) + " ★", `${pct(posShare)} of reviews read positive`],
      ["Dishes scored", ds.length, `${ds.filter(d => d.category === "signature").length} signature · ${ds.filter(d => ["needs-improvement", "polarising"].includes(d.category)).length} need work`],
    ].map(([s, b, t]) => `<div class="kpi"><small>${s}</small><b>${b}</b><span>${t}</span></div>`).join("");

    // dish sentiment score
    let rel = ds.filter(d => d.mentions >= MIN).sort((a, b) => b.love_score - a.love_score);
    if (dashRest === "all") rel = rel.sort((a, b) => b.mentions - a.mentions).slice(0, 16).sort((a, b) => b.love_score - a.love_score);
    const lbl = d => dashRest === "all" ? `${d.dish} · ${short(d.restaurant)}` : d.dish;
    $("#loveSub").textContent = `Average VADER compound per dish (−1 to +1), dishes with ≥${MIN} mentions${dashRest === "all" ? ", 16 most mentioned" : ""}.`;
    $(".chart-box.tall").style.height = Math.max(260, rel.length * 28 + 40) + "px";
    draw("loveChart", {
      type: "bar",
      data: { labels: rel.map(lbl), datasets: [{ data: rel.map(d => d.love_score), backgroundColor: rel.map(d => d.love_score >= 0 ? COL.pos : COL.neg), borderRadius: 4, borderSkipped: false, barThickness: 14 }] },
      options: {
        indexAxis: "y", maintainAspectRatio: false,
        scales: { x: { min: -1, max: 1, grid, border: { display: false } }, y: { grid: { display: false }, border: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => { const d = rel[c.dataIndex]; return [`Score ${signed(d.love_score)} · ${CAT[d.category].name}`, `${d.mentions} mentions · ${pct(d.pos_rate)} pos / ${pct(d.neg_rate)} neg`, `Avg ${d.avg_stars}★`]; } } } },
        onClick: (_, el) => { if (el[0]) { const d = rel[el[0].index]; selectRestaurant(d.restaurant, d.dish); $("#reviews").scrollIntoView({ behavior: "smooth" }); } },
        onHover: (e, el) => e.native.target.style.cursor = el.length ? "pointer" : "default",
      },
    });
    $("#loveTable").innerHTML = `<tr><th>Dish</th><th>Restaurant</th><th>Mentions</th><th>Score</th><th>Pos</th><th>Neg</th><th>Category</th></tr>` +
      rel.map(d => `<tr><td>${esc(d.dish)}</td><td>${esc(short(d.restaurant))}</td><td class="n">${d.mentions}</td><td class="n">${signed(d.love_score)}</td><td class="n">${pct(d.pos_rate)}</td><td class="n">${pct(d.neg_rate)}</td><td>${CAT[d.category].name}</td></tr>`).join("");

    // recommendations
    const promote = ds.filter(d => d.category === "signature").sort((a, b) => b.love_score * Math.log(b.mentions + 1) - a.love_score * Math.log(a.mentions + 1)).slice(0, 4);
    const improve = ds.filter(d => d.category === "needs-improvement" || d.category === "polarising").sort((a, b) => b.neg_rate * Math.log(b.mentions + 1) - a.neg_rate * Math.log(a.mentions + 1)).slice(0, 4);
    const reco = (list, good) => list.length ? list.map(d => `<div class="reco-item"><span class="e">${pic(d.dish)}</span>
        <div><b>${esc(d.dish)}</b>${dashRest === "all" ? esc(short(d.restaurant)) + " · " : ""}${badge(d.category)}</div>
        <div class="r"><strong>${good ? pct(d.pos_rate) + " pos" : pct(d.neg_rate) + " neg"}</strong>${d.mentions} mentions</div>
        <button class="round-add" style="width:28px;height:28px;font-size:14px" aria-label="Open reviews" data-open="${esc(d.restaurant)}|${esc(d.dish)}">→</button></div>`).join("")
      : `<div class="muted" style="font-size:13px">None meet the thresholds yet.</div>`;
    $("#recoPromote").innerHTML = reco(promote, true);
    $("#recoImprove").innerHTML = reco(improve, false);

    // aspects
    const aspNames = Object.keys(RESTS[0].aspects);
    const asp = aspNames.map(a => {
      const src = dashRest === "all" ? RESTS : RESTS.filter(r => r.name === dashRest);
      const s = src.reduce((o, r) => ({ m: o.m + r.aspects[a].mentions, p: o.p + r.aspects[a].positive, n: o.n + r.aspects[a].negative }), { m: 0, p: 0, n: 0 });
      return { a, p: s.p, n: s.n, u: s.m - s.p - s.n, m: s.m };
    }).sort((x, y) => y.m - x.m);
    const stack = { stacked: true, grid, border: { display: false } };
    draw("aspectChart", {
      type: "bar",
      data: { labels: asp.map(x => x.a), datasets: [
        { label: "Positive", data: asp.map(x => x.p), backgroundColor: COL.pos },
        { label: "Neutral", data: asp.map(x => x.u), backgroundColor: COL.neu },
        { label: "Negative", data: asp.map(x => x.n), backgroundColor: COL.neg }].map(s => ({ ...s, borderColor: "#fff", borderWidth: { right: 2 }, borderSkipped: false, barThickness: 18 })) },
      options: { indexAxis: "y", maintainAspectRatio: false, scales: { x: stack, y: { stacked: true, grid: { display: false }, border: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.raw} reviews (${pct(c.raw / asp[c.dataIndex].m)})` } } } },
    });

    // star distribution
    const starKeys = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0"];
    const sc = starKeys.map(k => rv.filter(r => r.rating === +k).length);
    $("#starSub").textContent = `Reviews by star rating, ${dashRest === "all" ? "all restaurants" : dashRest}`;
    draw("starChart", {
      type: "bar",
      data: { labels: starKeys.map(k => k.replace(".0", "") + "★"), datasets: [{ data: sc, backgroundColor: COL.dark, borderRadius: 4, borderSkipped: "start", maxBarThickness: 26 }] },
      options: { maintainAspectRatio: false, scales: { y: { grid, border: { display: false } }, x: { grid: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => `${c.raw} reviews` } } } },
    });

    // words
    let words;
    if (dashRest === "all") {
      const m = {};
      RESTS.forEach(r => r.top_words.forEach(([w, n]) => m[w] = (m[w] || 0) + n));
      words = Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 30);
    } else words = RESTS.find(r => r.name === dashRest).top_words;
    const mx = words[0][1];
    $("#words").innerHTML = words.map(([w, n]) => `<span style="font-size:${12 + 16 * n / mx}px" title="${n} times">${esc(w)} <small class="muted">${n}</small></span>`).join("");
  }

  // static (all-restaurant) charts
  function renderStatic() {
    draw("sentChart", {
      type: "bar",
      data: { labels: RESTS.map(r => r.name), datasets: [["positive", "Positive", COL.pos], ["neutral", "Neutral", COL.neu], ["negative", "Negative", COL.neg]].map(([k, l, c]) => ({
        label: l, data: RESTS.map(r => (r.sentiment[k] || 0) / r.reviews * 100), raw: RESTS.map(r => r.sentiment[k] || 0),
        backgroundColor: c, borderColor: "#fff", borderWidth: { right: 2 }, borderSkipped: false, barThickness: 26 })) },
      options: { indexAxis: "y", maintainAspectRatio: false,
        scales: { x: { stacked: true, max: 100, grid, border: { display: false }, ticks: { callback: v => v + "%" } }, y: { stacked: true, grid: { display: false }, border: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${Math.round(c.raw)}% (${c.dataset.raw[c.dataIndex]} reviews)` } } } },
    });
    const f = D.funnel;
    draw("funnelChart", {
      type: "bar",
      data: { labels: f.map(s => s.step.replace(/^N\d /, "")), datasets: [{ data: f.map(s => s.remaining), backgroundColor: COL.sage, borderRadius: 4, borderSkipped: "start", barThickness: 18 }] },
      options: { indexAxis: "y", maintainAspectRatio: false,
        scales: { x: { min: Math.floor(f.at(-1).remaining / 100) * 100 - 100, grid, border: { display: false } }, y: { grid: { display: false }, border: { display: false } } },
        plugins: { tooltip: { callbacks: { label: c => `${c.raw} remaining (−${f[c.dataIndex].removed})` } } } },
    });
    const e = D.evaluation, m = e.confusion;
    $("#evalBox").innerHTML = `<table class="cm"><tr><th></th><th>Predicted +</th><th>Predicted −</th></tr>
      <tr><th>Stars +</th><td class="hit">${m.tp}</td><td class="miss">${m.fn}</td></tr>
      <tr><th>Stars −</th><td class="miss">${m.fp}</td><td class="hit">${m.tn}</td></tr></table>
      <div class="kpis" style="grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0 0">
        <div class="kpi" style="padding:12px 14px"><small>Accuracy</small><b style="font-size:22px">${pct(e.accuracy)}</b></div>
        <div class="kpi" style="padding:12px 14px"><small>F1 score</small><b style="font-size:22px">${e.f1.toFixed(2)}</b></div></div>
      <p style="font-size:12px;margin-top:10px">Measured on ${fmt(e.n)} reviews. Star ratings serve as weak labels, so this checks agreement rather than ground truth.</p>`;
  }

  document.querySelectorAll("[data-table]").forEach(b => b.onclick = () => {
    const t = $("#" + b.dataset.table); t.classList.toggle("open");
    b.textContent = t.classList.contains("open") ? "Hide table" : "Show as table";
  });

  // wait for Poppins so Chart.js measures axis labels with the real font
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { renderDash(); renderStatic(); });

  /* ---------------- reveal on scroll + active nav ---------------- */
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: .12 });
  document.querySelectorAll(".reveal").forEach(el => io.observe(el));
  const links = [...document.querySelectorAll("#navLinks a")];
  const secIo = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) links.forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id));
  }), { rootMargin: "-45% 0px -50% 0px" });
  ["home", "restaurants", "dashboard"].forEach(id => secIo.observe(document.getElementById(id)));
})();
