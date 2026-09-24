/*
 * app.js — state, render, small SVG helpers.
 * One render(state) updates every view from state + window.APP_DATA.
 * No framework, no dependencies.
 */
(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // Data guard (copy deck: load error)
  // ---------------------------------------------------------------------
  var D = window.APP_DATA;
  if (!D) {
    document.getElementById("load-error").hidden = false;
    document.getElementById("app").style.display = "none";
    return;
  }

  var CORRIDORS = ["EDSA", "C5"];
  var $ = function (id) { return document.getElementById(id); };
  var SVG_NS = "http://www.w3.org/2000/svg";

  // ---------------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------------

  function el(tag, attrs, text) {
    var node = document.createElementNS(SVG_NS, tag);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (text != null) node.textContent = text;
    return node;
  }

  function fmtInt(n) { return Math.round(n).toLocaleString("en-US"); }

  function hourLabel(h) {
    var hh = h % 12 || 12;
    return hh + " " + (h < 12 ? "AM" : "PM");
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function longDate(iso) {
    var p = iso.split("-");
    return parseInt(p[2], 10) + " " + MONTHS[parseInt(p[1], 10) - 1] + " " + p[0];
  }

  // Tween a numeric text node over 350ms; snaps under reduced motion.
  var tweenState = new WeakMap();
  function tweenNumber(node, to, format) {
    var from = tweenState.has(node) ? tweenState.get(node) : to;
    tweenState.set(node, to);
    if (prefersReducedMotion() || from === to) {
      node.textContent = format(to);
      return;
    }
    if (node._raf) cancelAnimationFrame(node._raf);
    var start = performance.now();
    var dur = 350;
    function step(now) {
      var t = Math.min(1, (now - start) / dur);
      var eased = 1 - Math.pow(1 - t, 3);          // ease-out
      node.textContent = format(from + (to - from) * eased);
      if (t < 1) node._raf = requestAnimationFrame(step);
    }
    node._raf = requestAnimationFrame(step);
  }

  // ---------------------------------------------------------------------
  // State + URL hash  (#s=20&e=1.0&h=7 ; h omitted = all day)
  // ---------------------------------------------------------------------

  var state = {
    scenarioIndex: 0,   // 0..3 → baseline, +10%, +20%, +30%
    elasticity: 1.0,    // 0.8 | 1.0 | 1.2
    hour: null,         // null = all day, else 0..23
    playing: false
  };

  function scenario() { return D.scenarios[state.scenarioIndex]; }

  function eKey() { return state.elasticity.toFixed(1); }

  function entry(c) { return D.annual[c][eKey()][scenario().key]; }

  function entryFor(c, elasticityKey, scenarioKey) {
    return D.annual[c][elasticityKey][scenarioKey];
  }

  function rateFor(c) { return D.ratePer100k[c][eKey()][scenario().key]; }

  // Consistency rule (brief §5.4): hours = mean x hourShare; zones = hour x P(zone|hour)
  function hourlyExpected(c) {
    var m = entry(c).mean;
    return D.hourShare[c].map(function (s) { return m * s; });
  }

  function zoneHour(c) {
    return hourlyExpected(c).map(function (v, h) {
      return D.zoneGivenHour[c][h].map(function (p) { return v * p; });
    });
  }

  // Fixed axis per corridor: largest p95 across all scenarios and assumptions +5%.
  var AXIS_MAX = {};
  CORRIDORS.forEach(function (c) {
    var mx = 0;
    D.elasticities.forEach(function (e) {
      D.scenarios.forEach(function (s) {
        mx = Math.max(mx, D.annual[c][e.toFixed(1)][s.key].p95);
      });
    });
    AXIS_MAX[c] = mx * 1.05;   // never rescales with the scenario
  });

  function readHash() {
    var raw = location.hash.replace(/^#/, "");
    if (!raw) return;
    raw.split("&").forEach(function (pair) {
      var kv = pair.split("=");
      var k = kv[0], v = kv[1];
      if (k === "s") {
        var pct = Math.round(parseFloat(v));
        D.scenarios.forEach(function (s, i) {
          if (Math.round(s.change * 100) === pct) state.scenarioIndex = i;
        });
      } else if (k === "e") {
        var e = parseFloat(v);
        if ([0.8, 1.0, 1.2].some(function (x) { return Math.abs(x - e) < 1e-9; })) {
          state.elasticity = e;
        }
      } else if (k === "h") {
        var h = parseInt(v, 10);
        if (h >= 0 && h <= 23) state.hour = h;
      }
    });
  }

  function writeHash() {
    var parts = ["s=" + Math.round(scenario().change * 100),
                 "e=" + eKey()];
    if (state.hour != null) parts.push("h=" + state.hour);
    history.replaceState(null, "", "#" + parts.join("&"));
  }

  // ---------------------------------------------------------------------
  // Hero: vehicles, road slider, stops, live traffic line, sticky bar
  // ---------------------------------------------------------------------

  // Deterministic vehicle schedule: 13 slots, two lanes, 16–24s per pass.
  // Active count = round(10 x (1 + change)) → 10, 11, 12, 13.
  var VEHICLE_COUNT = 13;
  var vehicleNodes = [];

  function buildVehicles() {
    var lanes = [$("lane-top"), $("lane-bottom")];
    for (var i = 0; i < VEHICLE_COUNT; i++) {
      var lane = lanes[i % 2];
      var v = document.createElement("span");
      v.className = "vehicle";
      var dur = 16 + ((i * 7) % 9);                    // 16..24s, deterministic
      v.style.setProperty("--dur", dur + "s");
      v.style.setProperty("--delay", (-(i * dur) / VEHICLE_COUNT).toFixed(2) + "s");
      v.style.setProperty("--x", (4 + i * 7.3).toFixed(1) + "%");  // reduced-motion rest spot
      lane.appendChild(v);
      vehicleNodes.push(v);
    }
  }

  function activeVehicleCount() {
    return Math.round(10 * (1 + scenario().change));
  }

  function sliderValueText(idx) {
    if (idx === 0) return "Traffic at 2025 levels";
    return Math.round(D.scenarios[idx].change * 100) +
           " percent more traffic than 2025";
  }

  function renderHero() {
    var idx = state.scenarioIndex;
    var chg = scenario().change;

    // slider value, thumb plate position and label
    $("road-slider").value = String(idx);
    $("road-slider").setAttribute("aria-valuetext", sliderValueText(idx));
    $("thumb-plate").style.setProperty("--pct", String(idx / 3));
    $("thumb-value").textContent = scenario().label;

    // stops (hero row + sticky row)
    var stops = document.querySelectorAll(".stop-btn");
    for (var i = 0; i < stops.length; i++) {
      var on = Number(stops[i].dataset.stop) === idx;
      stops[i].classList.toggle("is-selected", on);
      stops[i].setAttribute("aria-pressed", on ? "true" : "false");
    }

    // vehicles: more traffic looks like more traffic
    var n = activeVehicleCount();
    vehicleNodes.forEach(function (v, i) {
      v.classList.toggle("is-hidden", i >= n);
    });

    // live line: AADT x (1 + change), whole vehicles
    $("tl-edsa").textContent = fmtInt(D.corridors.EDSA.aadt2025 * (1 + chg));
    $("tl-c5").textContent = fmtInt(D.corridors.C5.aadt2025 * (1 + chg));
  }

  function setScenario(idx) {
    if (idx === state.scenarioIndex) return;
    state.scenarioIndex = idx;
    render();
    writeHash();
  }

  function wireHero() {
    $("road-slider").addEventListener("input", function (ev) {
      setScenario(Number(ev.target.value));
    });

    var stops = document.querySelectorAll(".stop-btn");
    for (var i = 0; i < stops.length; i++) {
      stops[i].addEventListener("click", function (ev) {
        setScenario(Number(ev.currentTarget.dataset.stop));
      });
    }

    // sticky compact bar after the hero scrolls away
    var bar = $("sticky-bar");
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        bar.hidden = entries[0].isIntersecting;
      }, { rootMargin: "-80px 0px 0px 0px" });
      io.observe($("road-strip"));
    }

    // pause drifting vehicles when the tab is hidden
    document.addEventListener("visibilitychange", function () {
      document.documentElement.classList.toggle("tab-hidden", document.hidden);
      if (document.hidden && state.playing) stopPlay();
    });
  }

  // ---------------------------------------------------------------------
  // Copy link
  // ---------------------------------------------------------------------

  function wireCopyButtons() {
    var btns = document.querySelectorAll("[data-copy]");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", function (ev) {
        var btn = ev.currentTarget;
        var original = btn.textContent;
        function done(ok) {
          btn.textContent = ok ? "Link copied" : "Copy failed";
          setTimeout(function () { btn.textContent = original; }, 1600);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(location.href).then(
            function () { done(true); }, function () { done(false); });
        } else {
          try {
            var ta = document.createElement("textarea");
            ta.value = location.href;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
            done(true);
          } catch (e) { done(false); }
        }
      });
    }
  }

  // ---------------------------------------------------------------------
  // Meta: footer run details, validation badge, agreement, peak sentence
  // ---------------------------------------------------------------------

  function renderMeta() {
    var m = D.meta;
    $("footer-run").textContent =
      "Simulation run " + longDate(m.runDate) +
      " · " + m.runsPerScenario.toLocaleString("en-US") +
      " runs per scenario · seed " + m.seed;
    $("validation-badge").textContent =
      m.validation.passed + " of " + m.validation.total + " checks passed";
    $("agreement-pct").textContent = m.eventVsCountMaxDiffPct.toFixed(1);

    // auto-generated peak sentence, fixed by the hourly profile itself
    var parts = CORRIDORS.map(function (c) {
      var s = D.hourShare[c];
      var peak = s.indexOf(Math.max.apply(null, s));
      var top4 = s.slice().sort(function (a, b) { return b - a; })
                  .slice(0, 4).reduce(function (a, b) { return a + b; }, 0);
      return "<strong>" + c + "</strong> peaks at <strong>" + hourLabel(peak) +
             "</strong>; its four busiest hours hold <strong>" +
             (top4 * 100).toFixed(1) + "%</strong>";
    });
    $("peak-sentence").innerHTML =
      parts[0] + " of its reported crashes. " + parts[1] + ".";
  }

  // ---------------------------------------------------------------------
  // Corridor panels: fixed-axis range plot, sentences, delta, rate
  // ---------------------------------------------------------------------

  var RP_H = 72, RP_PAD = 10, RP_AXIS_Y = 46;
  var rpRefs = {};   // corridor → persistent SVG nodes (so the band can slide)
  var CORRIDOR_COLOR = { EDSA: "var(--edsa)", C5: "var(--c5)" };

  function buildRangePlot(c) {
    var host = $("rangeplot-" + c);
    host.textContent = "";
    var w = Math.max(240, host.clientWidth || 320);

    var svg = el("svg", { width: w, height: RP_H, role: "img" });
    svg.style.width = "100%";

    var axis = el("line", { class: "rp-axis", x1: RP_PAD, x2: w - RP_PAD,
                            y1: RP_AXIS_Y, y2: RP_AXIS_Y });
    var today = el("line", { class: "rp-today", x1: 0, x2: 0, y1: 16, y2: 56 });
    var todayLabel = el("text", { class: "rp-label", x: 0, y: 12,
                                  "text-anchor": "middle" }, "Today");
    var band = el("rect", { class: "band", x: 0, y: 30, width: 0, height: 12,
                            fill: CORRIDOR_COLOR[c], "fill-opacity": 0.25 });
    var meanTick = el("line", { class: "mean-tick", x1: 0, x2: 0, y1: 24, y2: RP_AXIS_Y,
                                stroke: CORRIDOR_COLOR[c], "stroke-width": 3 });
    var p05Label = el("text", { class: "rp-label", x: 0, y: 66, "text-anchor": "middle" });
    var p95Label = el("text", { class: "rp-label", x: 0, y: 66, "text-anchor": "middle" });

    [axis, today, todayLabel, band, meanTick, p05Label, p95Label]
      .forEach(function (n) { svg.appendChild(n); });
    host.appendChild(svg);

    rpRefs[c] = { svg: svg, band: band, meanTick: meanTick, today: today,
                  todayLabel: todayLabel, p05: p05Label, p95: p95Label,
                  w: w, max: AXIS_MAX[c] };
    updateRangePlot(c);
  }

  function rpX(c, v) {
    var r = rpRefs[c];
    return RP_PAD + (Math.min(v, r.max) / r.max) * (r.w - 2 * RP_PAD);
  }

  function updateRangePlot(c) {
    var r = rpRefs[c];
    if (!r) return;
    var e = entry(c);
    var todayMean = entryFor(c, eKey(), "baseline").mean;

    r.band.setAttribute("x", rpX(c, e.p05));
    r.band.setAttribute("width", Math.max(1, rpX(c, e.p95) - rpX(c, e.p05)));
    r.meanTick.setAttribute("x1", rpX(c, e.mean));
    r.meanTick.setAttribute("x2", rpX(c, e.mean));
    r.today.setAttribute("x1", rpX(c, todayMean));
    r.today.setAttribute("x2", rpX(c, todayMean));
    r.todayLabel.setAttribute("x", rpX(c, todayMean));
    r.p05.setAttribute("x", rpX(c, e.p05));
    r.p05.textContent = fmtInt(e.p05);
    r.p95.setAttribute("x", rpX(c, e.p95));
    r.p95.textContent = fmtInt(e.p95);

    // the fixed scale is part of the accessible summary
    r.svg.setAttribute("aria-label",
      c + " range plot, axis 0 to " + fmtInt(r.max) +
      ": average " + fmtInt(e.mean) +
      " reported crashes a year, 5th to 95th percentile " +
      fmtInt(e.p05) + " to " + fmtInt(e.p95) + ".");
  }

  function renderPanels() {
    CORRIDORS.forEach(function (c) {
      var e = entry(c);
      var base = entryFor(c, eKey(), "baseline").mean;

      tweenNumber($("big-" + c), e.mean, fmtInt);
      $("range-" + c).innerHTML =
        "In 9 of 10 simulated years, " + c + " had between <strong>" +
        fmtInt(e.p05) + "</strong> and <strong>" + fmtInt(e.p95) +
        "</strong> reported crashes.";

      var diff = Math.round(e.mean - base);
      $("delta-" + c).textContent =
        state.scenarioIndex === 0 ? "This is today's level."
                                  : fmtInt(Math.abs(diff)) + " more than today";

      $("rate-" + c).textContent = rateFor(c).toFixed(2);
      updateRangePlot(c);
    });

    // hidden equivalence table
    var rows = CORRIDORS.map(function (c) {
      var e = entry(c);
      return "<tr><th scope=\"row\">" + c + "</th><td>" + fmtInt(e.mean) +
             "</td><td>" + fmtInt(e.p05) + "</td><td>" + fmtInt(e.p95) + "</td></tr>";
    });
    $("table-panels").querySelector("tbody").innerHTML = rows.join("");
  }

  // ---------------------------------------------------------------------
  // Assumption selector (radiogroup) + help popover
  // ---------------------------------------------------------------------

  function renderAssumption() {
    var btns = $("assumption-group").querySelectorAll("[role=radio]");
    for (var i = 0; i < btns.length; i++) {
      var on = Math.abs(Number(btns[i].dataset.e) - state.elasticity) < 1e-9;
      btns[i].setAttribute("aria-checked", on ? "true" : "false");
      btns[i].tabIndex = on ? 0 : -1;
    }
  }

  function setElasticity(e) {
    if (Math.abs(e - state.elasticity) < 1e-9) return;
    state.elasticity = e;
    render();
    writeHash();
  }

  function wireAssumption() {
    var group = $("assumption-group");
    var btns = Array.prototype.slice.call(group.querySelectorAll("[role=radio]"));

    btns.forEach(function (btn, i) {
      btn.addEventListener("click", function () {
        setElasticity(Number(btn.dataset.e));
        var checked = group.querySelector('[aria-checked="true"]');
        if (checked) checked.focus();
      });
      btn.addEventListener("keydown", function (ev) {
        var d = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1
              : ev.key === "ArrowLeft"  || ev.key === "ArrowUp"   ? -1 : 0;
        if (!d) return;
        ev.preventDefault();
        var next = (i + d + btns.length) % btns.length;
        btns[next].focus();
        setElasticity(Number(btns[next].dataset.e));
      });
    });

    // "?" popover
    var help = $("assumption-help");
    var pop = $("assumption-popover");
    function closePop() {
      pop.hidden = true;
      help.setAttribute("aria-expanded", "false");
    }
    help.addEventListener("click", function () {
      var willOpen = pop.hidden;
      pop.hidden = !willOpen;
      help.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !pop.hidden) { closePop(); help.focus(); }
    });
    document.addEventListener("click", function (ev) {
      if (!pop.hidden && !pop.contains(ev.target) && ev.target !== help) closePop();
    });
  }

  // ---------------------------------------------------------------------
  // Hour chart (rebuilt each render; straight segments, direct labels)
  // ---------------------------------------------------------------------

  var TOP4 = {}, PEAK = {};
  CORRIDORS.forEach(function (c) {
    var s = D.hourShare[c];
    PEAK[c] = s.indexOf(Math.max.apply(null, s));
    TOP4[c] = s.map(function (v, i) { return [v, i]; })
               .sort(function (a, b) { return b[0] - a[0]; })
               .slice(0, 4).map(function (p) { return p[1]; });
  });

  var chartGeom = null;   // shared by render + pointer maths (1:1 pixel units)

  function chartHeight() { return window.innerWidth < 720 ? 240 : 320; }

  function niceMax(raw) {
    var mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var norm = raw / mag;
    var steps = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    for (var i = 0; i < steps.length; i++) {
      if (norm <= steps[i] + 1e-9) return steps[i] * mag;
    }
    return 10 * mag;
  }

  function renderHourChart() {
    var host = $("hourchart");
    var W = Math.max(240, host.clientWidth || 640);   // never upscale/downscale: 1:1 px keep text ≥15px
    var H = chartHeight();
    var L = 52, R = 64, T = 44, B = 34;

    var data = { EDSA: hourlyExpected("EDSA"), C5: hourlyExpected("C5") };
    var vmax = Math.max(
      Math.max.apply(null, data.EDSA),
      Math.max.apply(null, data.C5)
    );
    var yMax = niceMax(vmax * 1.08);
    var stepX = (W - L - R) / 23;

    function xOf(h) { return L + h * stepX; }
    function yOf(v) { return (H - B) - (v / yMax) * (H - B - T); }

    chartGeom = { W: W, H: H, L: L, R: R, T: T, B: B, stepX: stepX };

    host.textContent = "";
    var svg = el("svg", {
      width: W, height: H, role: "img",
      "aria-label": hourChartLabel(data)
    });
    svg.style.width = "100%";

    // gridlines + 3-tick y axis
    [0, yMax / 2, yMax].forEach(function (v) {
      var y = yOf(v);
      svg.appendChild(el("line", { class: "hc-grid", x1: L, x2: W - R, y1: y, y2: y }));
      svg.appendChild(el("text", { class: "hc-axis-text", x: L - 8, y: y + 5,
                                   "text-anchor": "end" }, fmtInt(v)));
    });

    // x tick labels: 12 AM, 6 AM, 12 PM, 6 PM, 12 AM (midnight = right edge).
    // On narrow charts the five labels collide, so fall back to three.
    var plotW = W - L - R;
    var ticks = plotW >= 300
      ? [[0, "12 AM", "start"], [6, "6 AM", "middle"], [12, "12 PM", "middle"],
         [18, "6 PM", "middle"], [23, "12 AM", "end"]]
      : [[0, "12 AM", "start"], [12, "12 PM", "middle"], [23, "12 AM", "end"]];
    ticks.forEach(function (t) {
      svg.appendChild(el("text", { class: "hc-axis-text", x: xOf(t[0]),
                                   y: H - B + 22, "text-anchor": t[2] }, t[1]));
    });

    // series: area fill 12% + straight-segment line + direct end label
    CORRIDORS.forEach(function (c) {
      var vals = data[c];
      var pts = vals.map(function (v, h) { return xOf(h) + "," + yOf(v); });
      var area = "M" + pts.join(" L") +
                 " L" + xOf(23) + "," + (H - B) + " L" + xOf(0) + "," + (H - B) + " Z";
      svg.appendChild(el("path", { d: area, fill: CORRIDOR_COLOR[c],
                                   "fill-opacity": 0.12, stroke: "none" }));
      svg.appendChild(el("polyline", { points: pts.join(" "), fill: "none",
                                       stroke: CORRIDOR_COLOR[c], "stroke-width": 2.5,
                                       "stroke-linejoin": "round" }));
      var labelColor = c === "EDSA" ? "var(--edsa-ink)" : "var(--c5-ink)";
      svg.appendChild(el("text", {
        class: "hc-end-label", x: xOf(23) + 8, y: yOf(vals[23]) + 5,
        fill: labelColor
      }, c));
    });

    // the four busiest hours of each corridor as filled dots
    CORRIDORS.forEach(function (c) {
      TOP4[c].forEach(function (h) {
        svg.appendChild(el("circle", {
          cx: xOf(h), cy: yOf(data[c][h]), r: 4.5,
          class: c === "EDSA" ? "hc-dot-edsa" : "hc-dot-c5"
        }));
      });
      // peak callout: "7 AM · 261"
      var p = PEAK[c];
      var cy = yOf(data[c][p]) - 14;
      if (cy < T - 26) cy = yOf(data[c][p]) + 24;
      svg.appendChild(el("text", {
        class: "hc-callout", x: xOf(p), y: cy, "text-anchor": "middle",
        stroke: "var(--paper)", "stroke-width": 3, "paint-order": "stroke"
      }, hourLabel(p) + " · " + fmtInt(data[c][p])));
    });

    // hour cursor
    if (state.hour != null) {
      svg.appendChild(el("line", { class: "hc-cursor", x1: xOf(state.hour),
                                   x2: xOf(state.hour), y1: T - 16, y2: H - B }));
    }

    host.appendChild(svg);

    // accessible equivalence table (hours sum to the headline mean)
    var rows = "";
    for (var h = 0; h < 24; h++) {
      rows += "<tr><th scope=\"row\">" + hourLabel(h) + "</th><td>" +
              data.EDSA[h].toFixed(1) + "</td><td>" +
              data.C5[h].toFixed(1) + "</td></tr>";
    }
    $("table-hourly").querySelector("tbody").innerHTML = rows;
  }

  function hourChartLabel(data) {
    var sel = state.hour == null ? "All day selected" : "Selected hour " + hourLabel(state.hour);
    return "Reported crashes by hour of day. EDSA peaks at " +
           hourLabel(PEAK.EDSA) + " with about " + fmtInt(data.EDSA[PEAK.EDSA]) +
           "; C5 peaks at " + hourLabel(PEAK.C5) + " with about " +
           fmtInt(data.C5[PEAK.C5]) + ". " + sel + ".";
  }

  // ---------------------------------------------------------------------
  // Hour controls: Play/Pause, All day, selected-time label, live region
  // ---------------------------------------------------------------------

  function selectedTimeText() {
    return state.hour == null ? "All day" : "Showing " + hourLabel(state.hour) + ".";
  }

  function renderHourControls() {
    var play = $("play-btn");
    play.textContent = state.playing ? "Pause" : "Play";
    play.setAttribute("aria-pressed", state.playing ? "true" : "false");

    var allday = $("allday-btn");
    allday.setAttribute("aria-pressed", state.hour == null ? "true" : "false");

    var txt = selectedTimeText();
    $("showing-label").textContent = txt;
    $("hour-live").textContent = txt;

    var host = $("hourchart");
    host.setAttribute("role", "slider");
    host.setAttribute("tabindex", "0");
    host.setAttribute("aria-label", "Hour of day");
    host.setAttribute("aria-valuemin", "0");
    host.setAttribute("aria-valuemax", "23");
    host.setAttribute("aria-valuenow", String(state.hour == null ? 0 : state.hour));
    host.setAttribute("aria-valuetext", state.hour == null ? "All day"
                                                           : hourLabel(state.hour));
  }

  var playTimer = null;

  function startPlay() {
    if (state.playing) return;
    state.playing = true;
    if (state.hour == null) { state.hour = 0; writeHash(); }
    playTimer = setInterval(function () {
      state.hour = (state.hour + 1) % 24;
      writeHash();
      renderHourChart();
      renderHourControls();
      renderMap();
    }, 650);
    renderHourControls();
    renderHourChart();
    renderMap();
  }

  function stopPlay() {
    if (!state.playing) return;
    state.playing = false;
    clearInterval(playTimer);
    playTimer = null;
    renderHourControls();
  }

  function setHour(h, userAction) {
    if (userAction) stopPlay();
    if (state.hour === h) return;
    state.hour = h;
    renderHourChart();
    renderHourControls();
    renderMap();
    writeHash();
  }

  function hourFromClientX(clientX) {
    var host = $("hourchart");
    var rect = host.getBoundingClientRect();
    if (!chartGeom) return state.hour == null ? 0 : state.hour;
    var x = clientX - rect.left;
    var h = Math.round((x - chartGeom.L) / chartGeom.stepX);
    return Math.max(0, Math.min(23, h));
  }

  function wireHourChart() {
    var host = $("hourchart");
    var dragging = false;

    host.addEventListener("pointerdown", function (ev) {
      dragging = true;
      if (host.setPointerCapture) host.setPointerCapture(ev.pointerId);
      setHour(hourFromClientX(ev.clientX), true);
      ev.preventDefault();
      host.focus();
    });
    host.addEventListener("pointermove", function (ev) {
      if (!dragging) return;
      setHour(hourFromClientX(ev.clientX), true);
    });
    host.addEventListener("pointerup", function () { dragging = false; });
    host.addEventListener("pointercancel", function () { dragging = false; });

    host.addEventListener("keydown", function (ev) {
      var cur = state.hour == null ? 0 : state.hour;
      var next = null;
      if (ev.key === "ArrowLeft" || ev.key === "ArrowDown") next = Math.max(0, cur - 1);
      else if (ev.key === "ArrowRight" || ev.key === "ArrowUp") next = Math.min(23, cur + 1);
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = 23;
      else if (ev.key === "PageUp") next = Math.min(23, cur + 6);
      else if (ev.key === "PageDown") next = Math.max(0, cur - 6);
      if (next == null) return;
      ev.preventDefault();
      setHour(next, true);
    });

    $("play-btn").addEventListener("click", function () {
      if (state.playing) stopPlay();
      else startPlay();
    });

    $("allday-btn").addEventListener("click", function () {
      stopPlay();
      setHour(null, false);
    });
  }

  // ---------------------------------------------------------------------
  // Zone map — schematic, no basemap. Equirectangular with cos(lat0).
  // Circles scale with the selected hour only; all-day = neutral size.
  // ---------------------------------------------------------------------

  var MAP_W = 420, MAP_H = 560, MAP_PAD = 32;
  var mapRefs = null;      // corridor → [ { circle, halo, p } ]

  function projectZones() {
    // fit all ten centroids into the viewBox with padding, north (lat) up
    var pts = [];
    CORRIDORS.forEach(function (c) {
      D.corridors[c].zones.forEach(function (z) { pts.push({ c: c, z: z }); });
    });
    var lat0 = pts.reduce(function (a, p) { return a + p.z.lat; }, 0) / pts.length;
    var k = Math.cos(lat0 * Math.PI / 180);
    pts.forEach(function (p) { p.x = p.z.lon * k; p.y = p.z.lat; });

    var xs = pts.map(function (p) { return p.x; });
    var ys = pts.map(function (p) { return p.y; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, ys), maxY = Math.max.apply(null, ys);
    var s = Math.min((MAP_W - 2 * MAP_PAD) / (maxX - minX),
                     (MAP_H - 2 * MAP_PAD) / (maxY - minY));
    var offX = (MAP_W - (maxX - minX) * s) / 2;
    var offY = (MAP_H - (maxY - minY) * s) / 2;

    var byCorridor = {};
    pts.forEach(function (p) {
      p.px = offX + (p.x - minX) * s;
      p.py = offY + (maxY - p.y) * s;      // flip: high latitude → top
      (byCorridor[p.c] = byCorridor[p.c] || []).push(p);
    });
    CORRIDORS.forEach(function (c) {          // zone 1 south → zone 5 north
      byCorridor[c].sort(function (a, b) { return a.z.n - b.z.n; });
    });
    return byCorridor;
  }

  function buildMap() {
    var host = $("zonemap");
    var tooltip = $("map-tooltip");
    var byCorridor = projectZones();

    var svg = el("svg", { viewBox: "0 0 " + MAP_W + " " + MAP_H,
                          role: "img", "aria-label": "" });
    svg.style.width = "100%";

    // subtle 5-line grid
    for (var i = 1; i <= 5; i++) {
      var gy = (MAP_H * i) / 6;
      svg.appendChild(el("line", { class: "zm-grid", x1: 0, x2: MAP_W, y1: gy, y2: gy }));
    }

    // north arrow
    svg.appendChild(el("line", { class: "zm-grid", x1: MAP_W - 34, x2: MAP_W - 34,
                                 y1: 66, y2: 38, stroke: "var(--ink-3)" }));
    svg.appendChild(el("polygon", {
      points: (MAP_W - 34) + ",32 " + (MAP_W - 38) + ",42 " + (MAP_W - 30) + ",42",
      fill: "var(--ink-3)"
    }));
    svg.appendChild(el("text", { class: "zm-label", x: MAP_W - 34, y: 88,
                                 "text-anchor": "middle" }, "N"));

    // south / north end labels
    svg.appendChild(el("text", { class: "zm-label", x: 6, y: MAP_H - 8 },
                       "Zone 1 (south)"));
    svg.appendChild(el("text", { class: "zm-label", x: 6, y: 26 }, "Zone 5 (north)"));

    mapRefs = {};

    CORRIDORS.forEach(function (c) {
      var pts = byCorridor[c];
      var d = pts.map(function (p) { return p.px + "," + p.py; }).join(" ");
      var dLane = pts.map(function (p) { return (p.px + 5) + "," + p.py; }).join(" ");
      svg.appendChild(el("polyline", { points: dLane, class: "zm-lane",
                                       stroke: CORRIDOR_COLOR[c] }));
      svg.appendChild(el("polyline", { points: d, class: "zm-road",
                                       stroke: CORRIDOR_COLOR[c] }));

      var refs = [];
      pts.forEach(function (p) {
        var halo = el("circle", { cx: p.px, cy: p.py, r: 14, class: "zm-halo",
                                  fill: CORRIDOR_COLOR[c], "fill-opacity": 0.25 });
        var circle = el("circle", { cx: p.px, cy: p.py, r: 12, class: "zm-circle",
                                    fill: CORRIDOR_COLOR[c], tabindex: "0", role: "img" });
        circle.addEventListener("mouseenter", function () { showTooltip(circle, p); });
        circle.addEventListener("mouseleave", hideTooltip);
        circle.addEventListener("focus", function () { showTooltip(circle, p); });
        circle.addEventListener("blur", hideTooltip);
        svg.appendChild(halo);
        svg.appendChild(circle);
        refs.push({ circle: circle, halo: halo, p: p, sentence: "" });
      });
      mapRefs[c] = refs;
    });

    host.insertBefore(svg, tooltip);
    mapRefs.svg = svg;
  }

  function zoneTimeLabel() {
    return state.hour == null ? "All day" : hourLabel(state.hour);
  }

  function zoneSentence(c, n, v) {
    var head = c + " Zone " + n + " · " + zoneTimeLabel() + " · ";
    if (state.hour == null) return head + "all-day totals are equal by construction";
    if (v < 1) return head + "fewer than 1 reported crashes a year";
    return head + "about " + fmtInt(v) + " reported crashes a year";
  }

  function renderMap() {
    if (!mapRefs) return;

    // maxValue is fixed while the hour changes: max cell across both
    // corridors, all hours, at the current scenario (brief §7.3)
    var maxV = 0;
    CORRIDORS.forEach(function (c) {
      zoneHour(c).forEach(function (row) {
        row.forEach(function (v) { if (v > maxV) maxV = v; });
      });
    });

    var rows = [];
    CORRIDORS.forEach(function (c) {
      var zh = zoneHour(c);
      mapRefs[c].forEach(function (ref, zi) {
        var v = state.hour == null ? null : zh[state.hour][zi];
        var r = v == null ? 12 : 6 + 22 * Math.sqrt(v / maxV);
        ref.circle.setAttribute("r", r.toFixed(2));
        ref.halo.setAttribute("r", (r + 8).toFixed(2));
        ref.sentence = zoneSentence(c, ref.p.z.n, v);
        ref.circle.setAttribute("aria-label", ref.sentence);
        rows.push("<tr><th scope=\"row\">" + c + "</th><td>Zone " +
                  ref.p.z.n + "</td><td>" +
                  (v == null ? "All day (equal by construction)"
                             : (v < 1 ? "fewer than 1" : v.toFixed(1))) +
                  "</td></tr>");
      });
    });
    $("table-map").querySelector("tbody").innerHTML = rows.join("");

    mapRefs.svg.setAttribute("aria-label",
      "Schematic map of five approximate zones on each corridor, drawn without " +
      "a basemap. " + selectedTimeText() +
      (state.hour == null
        ? " Circles are neutral because all-day totals are equal by construction."
        : " Circle sizes show reported crashes in each stretch at this hour."));
  }

  function showTooltip(circle, p) {
    var tip = $("map-tooltip");
    var refList = mapRefs[p.c];
    var ref = null;
    for (var i = 0; i < refList.length; i++) {
      if (refList[i].p === p) { ref = refList[i]; break; }
    }
    if (!ref) return;
    tip.textContent = ref.sentence;
    tip.hidden = false;

    var host = $("zonemap");
    var cr = circle.getBoundingClientRect();
    var hr = host.getBoundingClientRect();
    tip.style.left = (cr.left + cr.width / 2 - hr.left) + "px";
    tip.style.top = (cr.top - hr.top) + "px";
  }

  function hideTooltip() { $("map-tooltip").hidden = true; }

  // ---------------------------------------------------------------------
  // Single render(state): every view reads state + APP_DATA
  // ---------------------------------------------------------------------

  function render() {
    renderHero();
    renderAssumption();
    renderPanels();
    renderHourChart();
    renderHourControls();
    renderMap();
  }

  // ---------------------------------------------------------------------
  // Resize / font-load: rebuild the pixel-unit SVGs at their new widths
  // ---------------------------------------------------------------------

  function rebuildSizedSvgs() {
    buildRangePlot("EDSA");
    buildRangePlot("C5");
    renderHourChart();
  }

  function wireResize() {
    var t = null;
    window.addEventListener("resize", function () {
      clearTimeout(t);
      t = setTimeout(rebuildSizedSvgs, 150);
    });
    // web fonts change text metrics and sometimes container widths
    window.addEventListener("load", rebuildSizedSvgs);
  }

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------

  function init() {
    buildVehicles();
    readHash();
    renderMeta();
    buildRangePlot("EDSA");
    buildRangePlot("C5");
    buildMap();
    render();

    wireHero();
    wireAssumption();
    wireHourChart();
    wireCopyButtons();
    wireResize();
  }

  init();









})();
