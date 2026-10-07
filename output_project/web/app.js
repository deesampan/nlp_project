/* ResRec front-end, shared by both pages (see <body data-page>):
     home        index.html       the three restaurant cards
     restaurant  restaurant.html  one restaurant: summary, menu, reviews per dish
   Everything is read from window.RESREC_DATA (data.js, written by run_pipeline.py). */
(() => {
  const D = window.RESREC_DATA;
  const $ = (s, el = document) => el.querySelector(s);
  if (!D) {
    $("main").innerHTML = '<p class="empty">data.js not found. Run <code>python run_pipeline.py</code> first.</p>';
    return;
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = n => n.toLocaleString("en-US");
  const pct = x => Math.round(x * 100) + "%";
  const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const stars = n => "★".repeat(Math.round(n)) + "☆".repeat(5 - Math.round(n));
  const MIN = D.thresholds.min_opinions;   // a dish is ranked once this many reviews take a side on it
  const IMAGES = D.images || {};

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
  // real photo when the pipeline has one for this dish, emoji otherwise
  const pic = (d, lazy = true) => IMAGES[d] ? `<img src="${IMAGES[d]}" alt=""${lazy ? ' loading="lazy"' : ""}>` : `<span class="emo">${emoji(d)}</span>`;
  const plate = (d, size = "") => `<span class="plate ${size}${IMAGES[d] ? " has-img" : ""}" aria-hidden="true">${pic(d)}</span>`;

  // a restaurant's dishes, the ones with most opinions first
  const dishesOf = name => D.dishes.filter(d => d.restaurant === name).sort((a, b) => b.opinions - a.opinions || b.positive - a.positive);
  // each restaurant's picture: its most mentioned dish with a photo that an earlier restaurant isn't already using
  const COVER = {};
  const used = new Set();
  for (const r of D.restaurants) {
    const ds = dishesOf(r.name);
    const d = ds.find(x => IMAGES[x.dish] && !used.has(IMAGES[x.dish])) || ds.find(x => IMAGES[x.dish]) || ds[0];
    if (IMAGES[d.dish]) used.add(IMAGES[d.dish]);
    COVER[r.name] = d.dish;
  }

  // plain-language labels; "steady" and "low-data" dishes get none
  const TAG = { "signature": "★ Customers love it", "needs-improvement": "! Needs work", "polarising": "⇅ Mixed opinions" };
  const tag = d => TAG[d.category] ? `<span class="tag ${d.category}">${TAG[d.category]}</span>` : "";

  // liked vs didn't like; reviews that only name the dish are not part of the bar
  function bar(d) {
    const tip = d.opinions ? `${d.positive} liked it · ${d.negative} didn't like it` : "No opinions yet";
    return `<span class="bar" role="img" aria-label="${tip}" title="${tip}">
      ${d.positive ? `<i class="pos" style="flex:${d.positive}"></i>` : ""}${d.negative ? `<i class="neg" style="flex:${d.negative}"></i>` : ""}
    </span>`;
  }

  if (document.body.dataset.page === "home") home(); else restaurant();

  /* ---------------- home: three restaurant cards ---------------- */
  function home() {
    $("#total").textContent = fmt(D.restaurants.reduce((a, r) => a + r.reviews, 0));
    $("#cards").innerHTML = D.restaurants.map(r => {
      return `<a class="rest-card" href="restaurant.html?r=${slug(r.name)}">
        ${plate(COVER[r.name])}
        <span class="rest-body">
          <span class="rest-name">${esc(r.name)}</span>
          <span class="rest-meta">${esc(r.location)} · ${esc(r.cuisines)}</span>
          <span class="rest-foot">
            <span><b>${pct(r.sentiment.positive / r.reviews)}</b> positive reviews<br>${fmt(r.reviews)} reviews read</span>
            <span class="arrow" aria-hidden="true">→</span>
          </span>
        </span>
      </a>`;
    }).join("");
  }

  /* ---------------- restaurant: summary, menu, reviews ---------------- */
  function restaurant() {
    const key = new URLSearchParams(location.search).get("r");
    const r = D.restaurants.find(x => slug(x.name) === key);
    if (!r) {
      $("main").innerHTML = '<a class="back" href="index.html">← All restaurants</a><p class="empty">Restaurant not found.</p>';
      return;
    }
    document.title = `${r.name} · ResRec`;

    const all = dishesOf(r.name);
    const rated = all.filter(d => d.opinions >= MIN);   // enough opinions to judge
    const rare = all.filter(d => d.opinions < MIN);
    const share = (d, k) => d.opinions ? d[k] / d.opinions : 0;   // share of the reviews that took a side
    const best = [...rated].sort((a, b) => share(b, "positive") - share(a, "positive") || b.opinions - a.opinions)[0];
    const worst = [...rated].sort((a, b) => share(b, "negative") - share(a, "negative") || b.opinions - a.opinions)[0];

    $("#head").innerHTML = `
      <div class="hero-copy">
        <h1>${esc(r.name)}</h1>
        <p>${esc(r.location)} · ${esc(r.rest_type)}</p>
        <p>${esc(r.cuisines)} · ₹${esc(r.cost_for_two)} for two · <span class="star">★</span> ${esc(r.zomato_rate)} on Zomato</p>
      </div>
      <div class="deco" aria-hidden="true">${pic(COVER[r.name], false)}</div>`;

    const tiles = [
      { k: "Reviews read", v: fmt(r.reviews), s: "customer reviews on Zomato" },
      { k: "Positive reviews", v: pct(r.sentiment.positive / r.reviews), s: `${fmt(r.sentiment.positive)} of ${fmt(r.reviews)} reviews` },
    ];
    if (best) tiles.push({ k: "Most loved dish", v: best.dish, s: `${best.positive} of ${best.opinions} liked it`, d: best });
    if (worst && worst.negative) tiles.push({ k: "Most criticised dish", v: worst.dish, s: `${worst.negative} of ${worst.opinions} didn't like it`, d: worst });
    $("#stats").innerHTML = tiles.map(t => t.d
      ? `<button class="stat dish" data-dish="${esc(t.d.dish)}"><small>${t.k}</small><b>${esc(t.v)}</b><span>${t.s}</span></button>`
      : `<div class="stat"><small>${t.k}</small><b>${esc(t.v)}</b><span>${t.s}</span></div>`).join("");

    // menu lists: most liked first (share of opinions that liked it), ties go to the dish with more opinions
    const byLiked = (a, b) => share(b, "positive") - share(a, "positive") || b.opinions - a.opinions || a.dish.localeCompare(b.dish);
    const row = d => `<li><button class="dish-row" data-dish="${esc(d.dish)}">
        ${plate(d.dish, "row")}
        <span class="row-name"><b>${esc(d.dish)}</b>${tag(d)}</span>
        ${bar(d)}
        <span class="row-score">${d.opinions ? `<b>${pct(share(d, "positive"))}</b><small>${d.positive} of ${d.opinions} liked it</small>` : `<b>–</b><small>no opinions yet</small>`}</span>
        <span class="chev" aria-hidden="true">›</span>
      </button></li>`;

    $("#menu").innerHTML = rated.sort(byLiked).map(row).join("") || `<li class="empty">No dish has ${MIN} or more opinions.</li>`;
    if (rare.length) {
      $("#rareNote").textContent = `These dishes have fewer than ${MIN} opinions, so there is too little to judge them yet.`;
      $("#rare").innerHTML = rare.sort(byLiked).map(row).join("");
      $("#rareBlock").hidden = false;
    }

    /* ---- reviews the cleaning step left out (removed.js, written by src/export_removed.py) ---- */
    const REASON = { N1: "Empty", N2: "Duplicate", N3: "Too short", N4: "Not English" };
    const reasonOf = x => REASON[x.reason.slice(0, 2)] || x.reason;
    const gone = (window.RESREC_REMOVED || []).filter(x => x.restaurant === r.name);
    const counts = {};
    gone.forEach(x => counts[reasonOf(x)] = (counts[reasonOf(x)] || 0) + 1);
    const reasons = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);   // most common reason first
    const goneSummary = reasons.map(k => `${counts[k]} ${k.toLowerCase()}`).join(", ");
    const LEFT_OUT = gone.length ? `${gone.length} reviews were left out before analysis (${goneSummary}), so they are not counted here. They are listed at the bottom of the page.` : "";
    if (gone.length) {
      $("#leftOutNote").textContent = `These ${gone.length} reviews were not analysed: ${goneSummary}.`;
      $("#leftOut").innerHTML = [...gone].sort((a, b) => reasons.indexOf(reasonOf(a)) - reasons.indexOf(reasonOf(b)) || a.id - b.id).map(x => {
        // empty reviews have no cleaned text: say what was there instead
        const text = x.clean ? esc(x.clean)
          : `<em>${/\S/.test(x.raw.replace(/^\s*RATED\s*/, "")) ? "Only emoji or broken characters" : "No text"}</em>`;
        return `<li><span class="tag reason">${reasonOf(x)}</span>
          <span class="stars" ${x.rating ? `aria-label="${x.rating} out of 5 stars">${stars(x.rating)}` : ">"}</span>
          <span class="left-out-text">${text}</span></li>`;
      }).join("");
      $("#leftOutBlock").hidden = false;
    }

    /* ---- dish dialog: every review that mentions the dish ---- */
    const BY_ID = new Map(D.reviews.map(x => [x.id, x]));
    const VOTE = { positive: "Liked it", negative: "Didn't like it" };
    const PER = 10, PER_UNCLEAR = 3;
    const dlg = $("#dish");
    let cur = null;

    // highlight every mention of the dish in the review text, coloured by that mention's opinion
    function reviewText(rv, name) {
      let out = "", pos = 0;
      for (const m of rv.dishes.filter(x => x.dish === name).sort((a, b) => a.start - b.start)) {
        if (m.start < pos) continue;
        out += esc(rv.clean.slice(pos, m.start)) + `<mark class="${m.label}">${esc(rv.clean.slice(m.start, m.end))}</mark>`;
        pos = m.end;
      }
      return out + esc(rv.clean.slice(pos));
    }

    function openDish(name) {
      const d = all.find(x => x.dish === name);
      if (!d) return;
      // a review's vote is its last mention of the dish that takes a side, the same rule the pipeline counts with
      // (src/sentiment.py vote); "neutral" is left only when no mention takes a side
      const rows = d.review_ids.map(id => BY_ID.get(id)).filter(Boolean).map(rv => {
        const ms = rv.dishes.filter(x => x.dish === name).reverse();
        return { rv, vote: (ms.find(x => x.label !== "neutral") || ms[0]).label };
      });
      cur = { d, rows, filter: "all", shown: PER, shownUnclear: PER_UNCLEAR };
      $("#dishPlate").innerHTML = plate(d.dish, "sm");
      $("#dishName").textContent = d.dish;
      $("#dishLiked").innerHTML = d.opinions ? `<b>${d.positive} of ${d.opinions}</b> liked it` : "No opinions yet";
      $("#dishBar").innerHTML = bar(d);
      renderReviews();
      if (!dlg.open) dlg.showModal();
      dlg.scrollTop = 0;
    }

    function renderReviews() {
      const { d, rows, filter, shown, shownUnclear } = cur;
      $("#dishTabs").innerHTML = [["all", "All", d.opinions], ["positive", "Liked it", d.positive], ["negative", "Didn't like it", d.negative]]
        .map(([k, l, n]) => `<button class="chip ${filter === k ? "active" : ""}" data-filter="${k}" ${n ? "" : "disabled"}>${l} <small>${n}</small></button>`).join("")
        + `<p class="left-out">${LEFT_OUT}</p>`;
      const card = ({ rv, vote }) => `<article class="review">
          <div class="review-head">${VOTE[vote] ? `<span class="vote ${vote}">${VOTE[vote]}</span>` : ""}<span class="stars" aria-label="${rv.rating} out of 5 stars">${stars(rv.rating)}</span></div>
          <p>${reviewText(rv, d.dish)}</p>
        </article>`;
      const more = (left, key) => left > 0 ? `<button class="link more" data-more="${key}">Show more (${left} left)</button>` : "";
      const list = rows.filter(x => x.vote !== "neutral" && (filter === "all" || x.vote === filter));
      // reviews that name the dish without taking a side: kept apart at the very bottom, never counted
      const unclear = rows.filter(x => x.vote === "neutral");
      $("#dishReviews").innerHTML = list.slice(0, shown).map(card).join("") + more(list.length - shown, "shown")
        + (unclear.length ? `<section class="no-opinion">
            <h3>Mentioned, no opinion given <small>${unclear.length}</small></h3>
            <p>These reviews name the dish without saying whether it was good or bad, so they are not counted above.</p>
            ${unclear.slice(0, shownUnclear).map(card).join("")}${more(unclear.length - shownUnclear, "shownUnclear")}
          </section>` : "");
    }

    $("#dishTabs").addEventListener("click", e => {
      const b = e.target.closest("[data-filter]"); if (!b) return;
      Object.assign(cur, { filter: b.dataset.filter, shown: PER, shownUnclear: PER_UNCLEAR });
      renderReviews();
    });
    $("#dishReviews").addEventListener("click", e => {
      const b = e.target.closest("[data-more]"); if (!b) return;
      cur[b.dataset.more] += PER;
      renderReviews();
    });
    $("#dishClose").onclick = () => dlg.close();
    dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });   // click on the backdrop
    document.addEventListener("click", e => {
      const b = e.target.closest("[data-dish]");
      if (b) openDish(b.dataset.dish);
    });
  }
})();
