(function () {
  "use strict";

  var DATA = null, CURRENT = null, chart = null;
  var sortKey = "score", sortDir = -1;

  var C = { pos: "#2f7d54", neu: "#b58421", neg: "#b1372f", accent: "#1f5d8c", grey: "#8d8a82", line: "#e2dfd7" };

  var $ = function (id) { return document.getElementById(id); };
  var pct = function (a, b) { return b ? Math.round((a / b) * 100) : 0; };
  var esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  };

  // Cache-buster: without it the browser serves a stale dashboard.json after you
  // re-run build_slice.py, so the page silently shows the previous run's numbers.
  fetch("data/dashboard.json?v=" + Date.now())
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (d) { DATA = d; init(); })
    .catch(function (e) {
      $("cards").innerHTML =
        '<div class="panel"><h2>Could not load data</h2><p class="hint">' +
        esc(e.message) +
        '. This page reads <code>data/dashboard.json</code> with fetch, which browsers block on <code>file://</code>. ' +
        'Serve it instead: <code>python -m http.server 8000</code> from this folder, then open ' +
        '<code>http://localhost:8000</code>.</p></div>';
    });

  function init() {
    renderCards();
    renderFunnel();
    $("genStamp").textContent = "Generated " + DATA.generated_utc + " UTC from " + DATA.source;
    $("methodStamp").textContent = "Sentiment: " + DATA.sentiment_method +
      " · minimum " + DATA.min_mentions + " mentions to rank";
    $("backBtn").addEventListener("click", showLanding);
    $("modalClose").addEventListener("click", closeModal);
    $("modal").addEventListener("click", function (e) { if (e.target === $("modal")) closeModal(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });

    $("upBtn").addEventListener("click", doUpload);

    Array.prototype.forEach.call(document.querySelectorAll("th.sortable"), function (th) {
      th.addEventListener("click", function () {
        var k = th.getAttribute("data-k");
        if (sortKey === k) { sortDir = -sortDir; } else { sortKey = k; sortDir = -1; }
        renderDishTable();
      });
    });
  }

  function status(msg, kind) {
    var el = $("upStatus");
    el.className = "up-status" + (kind ? " " + kind : "");
    el.innerHTML = msg;
    el.classList.remove("hidden");
  }

  function doUpload() {
    var name = $("upName").value.trim();
    var file = $("upFile").files[0];
    if (!name) { status("Enter a restaurant name first.", "err"); return; }
    if (!file) { status("Choose a CSV file first.", "err"); return; }

    var fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);

    $("upBtn").disabled = true;
    status("Reading the file and running the model on every review …");

    fetch("api/analyze", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        $("upBtn").disabled = false;
        if (!res.ok) { status(esc(res.j.error || "Something went wrong."), "err"); return; }

        var rest = res.j.restaurant;
        DATA.restaurants = DATA.restaurants.filter(function (x) { return x.id !== rest.id; });
        DATA.restaurants.unshift(rest);
        renderCards();

        if (!rest.dishes_ranked) {
          status("Analysed " + res.j.rows_read + " reviews in " + res.j.seconds +
            "s, but no dish reached " + DATA.min_mentions +
            " mentions, so nothing could be ranked. Try a bigger file.", "err");
        } else {
          status("Analysed <b>" + res.j.rows_read + "</b> reviews in " + res.j.seconds +
            "s and found <b>" + rest.dishes_ranked + "</b> dishes. " +
            "Opening " + esc(rest.name) + " …", "ok");
          setTimeout(function () { showDetail(rest.id); }, 700);
        }
      })
      .catch(function () {
        $("upBtn").disabled = false;
        status("Could not reach the analysis server. The site must be started with " +
          "<code>python app.py</code> for uploads to work.", "err");
      });
  }

  function renderCards() {
    $("cards").innerHTML = DATA.restaurants.map(function (r) {
      var s = r.sentiment, t = r.review_count;
      var badge = r.uploaded
        ? '<div class="card-tag">yours</div>'
        : '<div class="card-rate">' + esc(r.rate || "n/a") + "</div>";
      return '<div class="card' + (r.uploaded ? " mine" : "") + '" data-id="' + r.id + '">' +
        '<div class="card-top"><div><h3>' + esc(r.name) + '</h3>' +
        '<div class="card-cui">' + esc(r.cuisines || "uploaded by you") + '</div></div>' +
        badge + '</div>' +
        '<div class="split-mini">' +
          bar(s.positive, t, C.pos) + bar(s.neutral, t, C.neu) + bar(s.negative, t, C.neg) +
        '</div>' +
        '<div class="card-stats">' +
          stat(t, "reviews") +
          stat(pct(s.positive, t) + "%", "positive") +
          stat(r.dishes_ranked, "dishes ranked") +
        '</div></div>';
    }).join("");

    Array.prototype.forEach.call(document.querySelectorAll(".card"), function (el) {
      el.addEventListener("click", function () { showDetail(el.getAttribute("data-id")); });
    });
  }

  function bar(n, t, col) {
    return '<span style="width:' + (t ? (n / t) * 100 : 0) + '%;background:' + col + '"></span>';
  }
  function stat(n, l) {
    return '<div class="card-stat"><span class="n">' + n + '</span><span class="l">' + l + '</span></div>';
  }

  function renderFunnel() {
    var q = DATA.quality || {};
    var n = function (k) { return q[k] || 0; };
    var base = n("input_reviews") + n("dropped_duplicate") || 1;
    var rows = [
      ["Duplicates removed", n("dropped_duplicate"), C.neg],
      ["Reviews in sample", n("input_reviews"), C.grey],
      ["Too short, dropped", n("dropped_too_short"), C.neg],
      ["Passed cleaning", n("after_cleaning"), C.grey],
      ["Mention a dish", n("with_dish_mention"), C.accent],
      ["No dish mentioned", n("no_dish_mention"), C.neu]
    ].filter(function (r) { return r[1] > 0; });

    $("funnel").innerHTML = rows.map(function (r) {
      return '<div class="frow"><span class="fl">' + r[0] + "</span>" +
        '<span class="fb"><span style="width:' + Math.min((r[1] / base) * 100, 100) +
        "%;background:" + r[2] + '"></span></span>' +
        '<span class="fn">' + r[1].toLocaleString() + "</span></div>";
    }).join("");
  }

  function showLanding() {
    $("detail").classList.add("hidden");
    $("landing").classList.remove("hidden");
    $("backBtn").classList.add("hidden");
    window.scrollTo(0, 0);
  }

  function showDetail(id) {
    CURRENT = DATA.restaurants.filter(function (r) { return r.id === id; })[0];
    if (!CURRENT) return;
    var r = CURRENT, s = r.sentiment, t = r.review_count;

    $("landing").classList.add("hidden");
    $("detail").classList.remove("hidden");
    $("backBtn").classList.remove("hidden");

    $("rName").textContent = r.name;
    $("rMeta").textContent = r.uploaded
      ? "Uploaded by you  ·  analysed live by the model"
      : [r.cuisines, r.rest_type, r.location].filter(Boolean).join("  ·  ");
    $("rAddr").textContent = r.address || "";
    if (r.uploaded) {
      $("rRate").textContent = Math.round(r.positive_rate * 100) + "%";
      $("rVotes").textContent = "of reviews were positive";
    } else {
      $("rRate").textContent = r.rate || "n/a";
      $("rVotes").textContent = r.votes.toLocaleString() + " votes on the platform";
    }

    var dropTotal = 0;
    var dc = (r.dropped && r.dropped.counts) || {};
    Object.keys(dc).forEach(function (k) { dropTotal += dc[k]; });

    $("rKpis").innerHTML =
      kpi(t.toLocaleString(), "Reviews analysed") +
      kpi(pct(s.positive, t) + "%", "Positive") +
      kpi(r.dishes_ranked, "Dishes ranked") +
      (r.uploaded
        ? kpi(dropTotal.toLocaleString(), "Comments not used")
        : kpi(r.approx_cost || "n/a", "Cost for two"));

    $("rSplit").innerHTML =
      seg(s.positive, t, "seg-pos", "Positive") +
      seg(s.neutral, t, "seg-neu", "Neutral") +
      seg(s.negative, t, "seg-neg", "Negative");

    var liked = r.dish_liked || [];
    $("zomatoPanel").classList.toggle("hidden", liked.length === 0);
    $("rDishLiked").innerHTML = liked.map(function (d) {
      return '<span class="chip">' + esc(d) + "</span>";
    }).join("");

    var minM = r.min_mentions || DATA.min_mentions || 1;
    var hint = "Share of comments about each dish that were positive.";
    if (minM > 1) {
      hint += " Only dishes mentioned at least " + minM + " times are shown.";
    } else {
      hint += " Every dish mentioned is shown, so check the comment count — " +
        "a dish with one or two comments is a hint, not a verdict.";
    }
    if (r.discovered_dishes && r.discovered_dishes.length) {
      hint += " Dish names in this file were learned from the reviews themselves: " +
        esc(r.discovered_dishes.slice(0, 8).join(", ")) +
        (r.discovered_dishes.length > 8 ? " and more." : ".");
    }
    $("dishHint").innerHTML = hint;

    renderDishTable();
    renderDishChart();
    renderDropped();
    window.scrollTo(0, 0);
  }

  function kpi(n, l) {
    return '<div class="kpi"><span class="l">' + l + '</span><span class="n">' + n + "</span></div>";
  }
  function seg(n, t, cls, label) {
    var w = t ? (n / t) * 100 : 0;
    if (w < 0.5) return "";
    return '<div class="' + cls + '" style="width:' + w + '%">' +
      (w > 11 ? label + " " + Math.round(w) + "%" : "") + "</div>";
  }

  var DROP_INFO = {
    duplicate: ["Duplicate", "The same comment appears more than once in the dataset. Counting it twice would inflate the dish's rating.", C.neg],
    too_short: ["Too short", "Under 20 characters. Too little text to judge which dish is meant, or whether it is good or bad.", C.neu],
    no_dish: ["No dish named", "A real comment, but about delivery, service or price. It still counts toward the restaurant's overall rating above — just not toward any dish.", C.accent],
    no_rating: ["No star rating", "The entry had no rating attached, so there was nothing to learn from.", C.grey]
  };

  function renderDropped() {
    var dr = CURRENT.dropped || { counts: {}, samples: {} };
    var keys = Object.keys(dr.counts).filter(function (k) { return dr.counts[k] > 0; });
    keys.sort(function (a, b) { return dr.counts[b] - dr.counts[a]; });

    if (!keys.length) {
      $("dropFilters").innerHTML = "";
      $("dropList").innerHTML = '<p class="hint">Nothing was dropped for this restaurant.</p>';
      return;
    }

    $("dropFilters").innerHTML = keys.map(function (k, i) {
      return '<button class="filt' + (i === 0 ? " on" : "") + '" data-d="' + k + '">' +
        DROP_INFO[k][0] + " " + dr.counts[k].toLocaleString() + "</button>";
    }).join("");

    function draw(k) {
      var info = DROP_INFO[k] || [k, "", C.grey];
      var shown = (dr.samples[k] || []);
      var total = dr.counts[k];
      var html = '<div class="drop-why" style="border-color:' + info[2] + '">' +
        '<div class="drop-why-t" style="color:' + info[2] + '">Why these were set aside</div>' +
        "<p>" + info[1] + "</p></div>";
      html += '<p class="modal-sub">Showing ' + shown.length + " of " +
        total.toLocaleString() + "</p>";
      html += shown.map(function (t) {
        return '<div class="drop-item">' + esc(t) + "</div>";
      }).join("");
      $("dropList").innerHTML = html;
    }
    draw(keys[0]);

    Array.prototype.forEach.call($("dropFilters").querySelectorAll(".filt"), function (b) {
      b.addEventListener("click", function () {
        Array.prototype.forEach.call($("dropFilters").querySelectorAll(".filt"),
          function (o) { o.classList.remove("on"); });
        b.classList.add("on");
        draw(b.getAttribute("data-d"));
      });
    });
  }

  function ratingColour(rate) {
    if (rate >= 0.6) return { bg: "#e4f0e9", fg: C.pos };
    if (rate <= 0.35) return { bg: "#f8e6e5", fg: C.neg };
    return { bg: "#f7f0de", fg: "#8a6416" };
  }

  function renderDishTable() {
    if (!CURRENT) return;
    var ds = CURRENT.dishes.slice();
    $("noDishes").classList.toggle("hidden", ds.length > 0);

    ds.sort(function (a, b) {
      var x = a[sortKey], y = b[sortKey];
      if (typeof x === "string") return sortDir * x.localeCompare(y);
      return sortDir * (x - y);
    });

    $("dishBody").innerHTML = ds.map(function (d, i) {
      var c = ratingColour(d.positive_rate);
      return '<tr data-i="' + i + '">' +
        '<td class="dish-name">' + esc(d.dish) + "</td>" +
        '<td class="num">' + d.mentions + "</td>" +
        '<td class="num" style="color:' + C.pos + '">' + d.positive + "</td>" +
        '<td class="num" style="color:' + C.neg + '">' + d.negative + "</td>" +
        '<td class="num"><span class="score-pill" style="background:' + c.bg + ";color:" + c.fg + '">' +
        Math.round(d.positive_rate * 100) + "%</span></td></tr>";
    }).join("");

    Array.prototype.forEach.call($("dishBody").querySelectorAll("tr"), function (tr) {
      tr.addEventListener("click", function () { openModal(ds[+tr.getAttribute("data-i")]); });
    });
  }

  function openModal(d) {
    $("modalTitle").textContent = d.dish;
    var all = d.comments || [];
    var label = { positive: "Good", negative: "Bad", neutral: "Mixed" };

    var html = '<p class="modal-sub">' +
      Math.round(d.positive_rate * 100) + "% liked &middot; " +
      d.mentions + " comments &middot; " +
      '<span style="color:' + C.pos + '">' + d.positive + " good</span>, " +
      '<span style="color:' + C.neg + '">' + d.negative + " bad</span>" +
      (d.neutral ? ", " + d.neutral + " mixed" : "") + "</p>";

    if (!all.length) {
      html += '<p class="hint">No comments stored for this dish.</p>';
      $("modalBody").innerHTML = html;
      $("modal").classList.remove("hidden");
      return;
    }

    html += '<div class="filters">' +
      '<button class="filt on" data-f="all">All ' + all.length + "</button>" +
      '<button class="filt" data-f="positive">Good ' + d.positive + "</button>" +
      '<button class="filt" data-f="negative">Bad ' + d.negative + "</button>" +
      (d.neutral ? '<button class="filt" data-f="neutral">Mixed ' + d.neutral + "</button>" : "") +
      "</div><div id='commentList'></div>";
    $("modalBody").innerHTML = html;

    function draw(f) {
      $("commentList").innerHTML = all
        .filter(function (q) { return f === "all" || q.label === f; })
        .map(function (q) {
          var cls = q.label === "positive" ? "pos" : q.label === "negative" ? "neg" : "neu";
          return '<div class="quote ' + cls + '">' +
            '<div class="quote-label">' + (label[q.label] || q.label) + "</div>" +
            "<p>" + esc(q.text) + "</p></div>";
        }).join("");
    }
    draw("all");

    Array.prototype.forEach.call($("modalBody").querySelectorAll(".filt"), function (b) {
      b.addEventListener("click", function () {
        Array.prototype.forEach.call($("modalBody").querySelectorAll(".filt"),
          function (o) { o.classList.remove("on"); });
        b.classList.add("on");
        draw(b.getAttribute("data-f"));
        $("modalBody").parentNode.scrollTop = 0;
      });
    });
    $("modal").classList.remove("hidden");
  }
  function closeModal() { $("modal").classList.add("hidden"); }

  function renderDishChart() {
    var ds = CURRENT.dishes.slice()
      .sort(function (a, b) { return b.positive_rate - a.positive_rate; });
    if (chart) { chart.destroy(); chart = null; }
    if (!ds.length) return;

    var wrap = document.getElementById("dishChart").parentNode;
    wrap.style.height = Math.max(ds.length * 34 + 70, 220) + "px";

    chart = new Chart($("dishChart"), {
      type: "bar",
      data: {
        labels: ds.map(function (d) { return d.dish; }),
        datasets: [{
          data: ds.map(function (d) { return Math.round(d.positive_rate * 100); }),
          backgroundColor: ds.map(function (d) { return ratingColour(d.positive_rate).fg; }),
          borderRadius: 3,
          barThickness: 18
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { right: 34 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (i) {
                var d = ds[i.dataIndex];
                return i.raw + "% liked  (" + d.positive + " good, " + d.negative +
                  " bad of " + d.mentions + ")";
              }
            }
          }
        },
        scales: {
          x: {
            min: 0, max: 100,
            title: { display: true, text: "% of comments that were positive", color: C.grey, font: { size: 11 } },
            ticks: { color: C.grey, font: { size: 11 }, callback: function (v) { return v + "%"; } },
            grid: { color: C.line, drawTicks: false }
          },
          y: {
            ticks: { color: "#23221f", font: { size: 12 } },
            grid: { display: false }
          }
        }
      },
      plugins: [{
        id: "valueLabels",
        afterDatasetsDraw: function (ch) {
          var ctx = ch.ctx;
          ctx.save();
          ctx.font = "11px Segoe UI, sans-serif";
          ctx.fillStyle = "#5f5d57";
          ctx.textBaseline = "middle";
          ch.getDatasetMeta(0).data.forEach(function (bar, i) {
            ctx.fillText(ds[i].mentions + " comments", bar.x + 8, bar.y);
          });
          ctx.restore();
        }
      }]
    });
  }
})();
