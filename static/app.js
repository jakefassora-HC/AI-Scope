"use strict";

function fmtBytes(bytes) {
  if (bytes === 0) return "0 B";
  var k = 1024;
  var sizes = ["B", "KB", "MB", "GB"];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 10) / 10 + " " + sizes[i];
}

var browserPath = null;

function fmtUptime(sec) {
  if (sec < 60) return sec + "s";
  if (sec < 3600) return Math.floor(sec / 60) + "m";
  if (sec < 86400) return Math.floor(sec / 3600) + "h";
  return Math.floor(sec / 86400) + "d";
}

function loadBrowse(path) {
  fetch("/api/browse?path=" + encodeURIComponent(path)).then(function(r) {
    if (r.status === 403) return r.json().then(function(d) { throw new Error(d.error); });
    return r.json();
  }).then(function(d) {
    browserPath = d.path;
    document.getElementById("browser-current").textContent = d.path;
    var ul = document.createElement("div");
    var parent = d.path.replace(/\/[^/]+$/, "");
    if (parent && parent !== d.path) {
      var up = document.createElement("div");
      up.className = "file-row"; up.style.cursor = "pointer";
      up.innerHTML = "<span>📁 ../ (up)</span><span></span><span></span><span></span>";
      up.addEventListener("click", function() { loadBrowse(parent); });
      ul.appendChild(up);
    }
    d.items.forEach(function(it) {
      var row = document.createElement("div");
      row.className = "file-row";
      if (it.is_dir) {
        row.style.cursor = "pointer";
        row.addEventListener("click", function() { loadBrowse(it.path); });
      }
      row.innerHTML =
        "<span>" + (it.is_dir ? "📁 " : "📄 ") + it.name + "</span>" +
        "<span></span>" +
        "<span>" + (it.is_dir ? "" : fmtBytes(it.size_bytes)) + "</span>" +
        "<span>" + it.modified_iso.slice(0, 10) + "</span>";
      ul.appendChild(row);
    });
    var container = document.getElementById("browser-list");
    container.innerHTML = ""; container.appendChild(ul);
  }).catch(function(err) {
    document.getElementById("browser-list").textContent = "Error: " + err.message;
  });
}

function loadProcesses() {
  fetch("/api/processes").then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById("processes-list");
    if (!d.processes.length) {
      container.innerHTML = "<p style='color:var(--muted)'>No claude processes running.</p>";
      return;
    }
    container.innerHTML = "";
    d.processes.forEach(function(p) {
      var row = document.createElement("div");
      row.className = "file-row";
      row.innerHTML =
        "<span>PID " + p.pid + "</span>" +
        "<span>" + p.cwd + "</span>" +
        "<span></span>" +
        "<span>up " + fmtUptime(p.uptime_sec) + "</span>";
      container.appendChild(row);
    });
  });
}

// Lazy-load tabs the first time they are opened
document.querySelector("[data-tab='browser']").addEventListener("click", function() {
  if (browserPath === null) loadBrowse(window.HOME_PATH || "/Users/jakefassora");
});
document.querySelector("[data-tab='processes']").addEventListener("click", loadProcesses);

// Tab switching
document.querySelectorAll(".tab").forEach(function(btn) {
  btn.addEventListener("click", function() {
    var name = btn.dataset.tab;
    document.querySelectorAll(".tab").forEach(function(t) { t.classList.remove("active"); });
    document.querySelectorAll(".tab-panel").forEach(function(p) { p.classList.remove("active"); });
    btn.classList.add("active");
    document.getElementById("tab-" + name).classList.add("active");
  });
});

function fmtBytes(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / (1024 * 1024)).toFixed(1) + " MB";
}

function renderFileRows(container, files, isAuto) {
  container.innerHTML = "";
  if (!files.length) { container.textContent = "(none found)"; return; }
  files.sort(function(a, b) { return b.tokens_est - a.tokens_est; });
  files.forEach(function(f) {
    var row = document.createElement("div");
    row.className = "file-row";
    row.innerHTML =
      "<span title=\"" + f.path + "\">" + f.path.replace(/^.*\/(\.claude|projects)\//, "$1/") + "</span>" +
      "<span class=\"badge " + (isAuto ? "auto" : "ondemand") + "\">" +
        (isAuto ? "AUTO" : "ON-DEMAND") + "</span>" +
      "<span>" + fmtBytes(f.size_bytes) + "</span>" +
      "<span>~" + f.tokens_est.toLocaleString() + " tok</span>";
    container.appendChild(row);
  });
}

function renderBudget(autoTokens) {
  var el = document.getElementById("budget");
  var pct = Math.min(100, Math.round((autoTokens / 25000) * 100));
  el.innerHTML =
    "<div class=\"budget\">~" + autoTokens.toLocaleString() + " tokens</div>" +
    "<div class=\"budget-caption\">loaded on every turn — about " + pct +
    "% of a typical response budget</div>";
}

function loadAll() {
  fetch("/api/config").then(function(r) { return r.json(); }).then(function(d) {
    renderFileRows(document.getElementById("claude-dir"), d.claude_dir, true);
    renderFileRows(document.getElementById("project-md"), d.project_claude_md, true);
    var autoTokens = d.claude_dir.reduce(function(s, f) { return s + f.tokens_est; }, 0) +
                     d.project_claude_md.reduce(function(s, f) { return s + f.tokens_est; }, 0);
    renderBudget(autoTokens);
  });
}

document.getElementById("refresh").addEventListener("click", loadAll);
loadAll();

function renderRepos(container, repos) {
  container.innerHTML = "";
  if (!repos.length) { container.textContent = "(none)"; return; }
  repos.sort(function(a, b) { return b.age_days - a.age_days; });
  repos.forEach(function(r) {
    var row = document.createElement("div");
    row.className = "file-row";
    var summary = [];
    if (r.dirty) summary.push(r.dirty + " dirty");
    if (r.untracked) summary.push(r.untracked + " untracked");
    if (r.ahead) summary.push("↑" + r.ahead);
    if (r.behind) summary.push("↓" + r.behind);
    if (r.stash_count) summary.push(r.stash_count + " stash");
    if (!summary.length) summary.push("clean");
    var stalenessBadge = r.stale
      ? "<span class=\"badge auto\">STALE</span>"
      : "<span class=\"badge ondemand\">OK</span>";
    row.innerHTML =
      "<span title=\"" + r.path + "\">" + r.path.replace(/^.*\//, "") +
        " <code>" + r.branch + "</code></span>" +
      stalenessBadge +
      "<span>" + summary.join(", ") + "</span>" +
      "<span>" + r.age_days + "d ago</span>";
    container.appendChild(row);
  });
}

function loadGit() {
  fetch("/api/git").then(function(r) { return r.json(); }).then(function(d) {
    renderRepos(document.getElementById("git-projects"), d.projects);
    renderRepos(document.getElementById("git-worktrees"), d.worktrees);
  });
}

document.querySelector("[data-tab='git']").addEventListener("click", loadGit);

function renderInsights() {
  fetch("/api/insights").then(function(r) { return r.json(); }).then(function(d) {
    var body = document.getElementById("insights-body");
    if (!d.findings.length) {
      body.innerHTML = "<p style='color:var(--green)'>✓ No issues found.</p>";
      return;
    }
    body.innerHTML = "";
    d.findings.forEach(function(f) {
      var row = document.createElement("div");
      row.className = "file-row";
      var color = f.severity === "HIGH" ? "auto" : "ondemand";
      row.innerHTML =
        "<span>" + f.message + "</span>" +
        "<span class=\"badge " + color + "\">" + f.severity + "</span>" +
        "<span></span>" +
        "<span>" + f.rule + "</span>";
      body.appendChild(row);
    });
  });
}

// Re-run on initial load + on refresh
var originalLoadAll = loadAll;
loadAll = function() { originalLoadAll(); renderInsights(); };
renderInsights();

// Cheat-sheet collapse toggle (persists across reloads)
(function() {
  var toggle = document.getElementById("cheatsheet-toggle");
  var body = document.getElementById("cheatsheet-body");
  if (!toggle || !body) return;
  var KEY = "scope.cheatsheet.collapsed";
  function apply(collapsed) {
    body.classList.toggle("collapsed", collapsed);
    toggle.textContent = collapsed ? "Show" : "Hide";
    toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }
  apply(localStorage.getItem(KEY) === "1");
  toggle.addEventListener("click", function() {
    var nowCollapsed = !body.classList.contains("collapsed");
    localStorage.setItem(KEY, nowCollapsed ? "1" : "0");
    apply(nowCollapsed);
  });
})();

// ── System Map — D3 circle packing + sunburst (toggle) ──────────────────────

var _mapTooltip = (function() {
  var el = document.createElement("div");
  el.className = "map-tooltip";
  document.body.appendChild(el);
  return el;
})();

function activateTab(name) {
  var btn = document.querySelector("[data-tab='" + name + "']");
  if (btn) btn.click();
}

var mapLoaded = false;
var _mapData = null;
var _mapView = "circles";

// 3-status taxonomy (KISS): done / active / idle
// done   = green  (handled, no action needed)
// active = blue   (claude working OR recent commits)
// idle   = amber  (needs your attention — drafted but not shipped)
var STATUS_COLOR = { done: "#3fb950", active: "#58a6ff", idle: "#d29922" };
// claude is currently editing a file → orange glow on top of status color
var ACTIVE_EDIT_COLOR = "#ffa657";
// HIGH severity overlay
var HIGH_COLOR = "#f85149";
var KIND_COLOR = {
  root: "#0d1117", region: "#1c2230", repo: "#2d6cdf", worktree: "#1f6feb",
  group: "#3b3654", plan: "#7d8590", phase: "#3fb950", process: "#2ea043",
  file: "#7d8590", placeholder: "#21262d"
};

function _showTip(html, e) {
  _mapTooltip.innerHTML = html;
  _mapTooltip.style.display = "block";
  _mapTooltip.style.left = (e.pageX + 12) + "px";
  _mapTooltip.style.top = (e.pageY + 12) + "px";
}
function _hideTip() { _mapTooltip.style.display = "none"; }

// Plan viewer modal
function openPlan(path, name) {
  var titleEl = document.getElementById("plan-modal-title");
  var bodyEl = document.getElementById("plan-modal-body");
  titleEl.textContent = name || path;
  bodyEl.innerHTML = "<p style='color:var(--muted)'>Loading…</p>";
  document.getElementById("plan-modal-bg").classList.add("open");
  fetch("/api/plan?path=" + encodeURIComponent(path)).then(function(r){return r.json();}).then(function(d){
    if (d.error) { bodyEl.innerHTML = "<p style='color:var(--red)'>" + d.error + "</p>"; return; }
    if (d.ext === "md" && typeof marked !== "undefined") bodyEl.innerHTML = marked.parse(d.content);
    else if (d.ext === "html" || d.ext === "htm") bodyEl.innerHTML = d.content;
    else bodyEl.innerHTML = "<pre>" + d.content.replace(/</g, "&lt;") + "</pre>";
  });
}
function closePlanModal() {
  document.getElementById("plan-modal-bg").classList.remove("open");
}
document.getElementById("plan-modal-bg").addEventListener("click", closePlanModal);
document.addEventListener("keydown", function(e){ if (e.key === "Escape") closePlanModal(); });

// ── Circle packing ──────────────────────────────────────────────────────────
function renderCircles(data) {
  var stage = document.getElementById("map-canvas");
  stage.innerHTML = "";
  var rect = stage.getBoundingClientRect();
  var W = rect.width, H = rect.height;
  if (W < 50) return;
  var D = Math.min(W, H);

  var root = d3.hierarchy(data)
    .sum(function(d){ return d.children ? 0 : (d.value || 1); })
    .sort(function(a,b){ return (b.value||0) - (a.value||0); });
  d3.pack().size([D, D]).padding(4)(root);

  var svg = d3.select(stage).append("svg")
    .attr("viewBox", -D/2 + " " + -D/2 + " " + D + " " + D)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("background", "#06080c");

  var focus = root, view;

  var node = svg.append("g").selectAll("g")
    .data(root.descendants().slice(1))
    .join("g").attr("class", "cp-node");

  node.append("circle")
    .attr("fill", function(d){
      var k = d.data.kind;
      if (k === "plan" && d.data.claude_active) return ACTIVE_EDIT_COLOR;
      if (k === "phase") return STATUS_COLOR[d.data.status] || STATUS_COLOR.idle;
      if (k === "plan") {
        var s = d.data.phase_status; if (s) return STATUS_COLOR[s] || STATUS_COLOR.idle;
        return d.data.ext === "html" ? ACTIVE_EDIT_COLOR : STATUS_COLOR.active;
      }
      if (d.data.has_process) return "#2ea043";
      if (d.data.severity === "HIGH") return HIGH_COLOR;
      if (d.data.dirty) return STATUS_COLOR.idle;
      return KIND_COLOR[k] || "#21262d";
    })
    .attr("stroke", function(d){ return d.data.claude_active ? ACTIVE_EDIT_COLOR : null; })
    .attr("stroke-width", function(d){ return d.data.claude_active ? 2 : 0; })
    .style("filter", function(d){ return d.data.claude_active ? "drop-shadow(0 0 6px " + ACTIVE_EDIT_COLOR + ")" : null; })
    .attr("fill-opacity", function(d){
      // Branches: a touch translucent so children read; leaves: full strength
      if (!d.children) return 0.92;
      // idle phases stay fully visible (we want them to grab attention)
      if (d.data.kind === "phase" && d.data.status === "idle") return 0.75;
      return d.data.kind === "phase" ? 0.7 : 0.55;
    })
    .on("click", function(event, d){
      event.stopPropagation();
      if (!d.children && d.data.kind === "plan" && d.data.path) {
        openPlan(d.data.path, d.data.rel || d.data.name); return;
      }
      if (focus !== d) zoom(d);
    })
    .on("mouseover", function(e, d){
      var parts = ["<b>" + d.data.name + "</b> · " + (d.data.kind || "")];
      if (d.data.claude_active) parts.push("<span style='color:#ffa657'>● claude editing</span>");
      if (d.data.status) parts.push(d.data.status);
      if (d.data.phase_status) parts.push(d.data.phase_status);
      if (d.data.branch) parts.push("branch: " + d.data.branch);
      if (d.data.rel) parts.push(d.data.rel);
      _showTip(parts.join(" · "), e);
    })
    .on("mousemove", function(e){ _mapTooltip.style.left = (e.pageX+12)+"px"; _mapTooltip.style.top = (e.pageY+12)+"px"; })
    .on("mouseout", _hideTip);

  var label = svg.append("g").style("pointer-events", "none").selectAll("text")
    .data(root.descendants().slice(1))
    .join("text")
    .attr("class", function(d){ return "cp-label" + (d.depth > 2 ? " dim" : ""); })
    .style("fill-opacity", function(d){ return labelVisible(d, root) ? 1 : 0; })
    .style("display", function(d){ return labelVisible(d, root) ? "inline" : "none"; })
    .text(function(d){ return fitLabel(d.data.name, d.r); });

  var centerName = svg.append("text").attr("text-anchor", "middle").attr("dy", "-0.4em")
    .style("font", "600 14px ui-monospace, monospace").style("fill", "#7d8590").style("pointer-events", "none");
  var centerHint = svg.append("text").attr("text-anchor", "middle").attr("dy", "1em")
    .style("font", "10px ui-monospace, monospace").style("fill", "#7d8590").style("pointer-events", "none");

  svg.on("click", function(){ zoom(focus.parent || root); });
  zoomTo([root.x, root.y, root.r * 2]);

  function labelVisible(d, f) {
    if (d.parent !== f) return false;
    if (!d.children) return d.r > 14;
    return d.r > 24;
  }
  function fitLabel(name, r) {
    var max = Math.max(3, Math.floor(r / 4));
    return name.length > max ? name.slice(0, Math.max(2, max - 1)) + "…" : name;
  }
  function zoomTo(v) {
    var k = D / v[2]; view = v;
    node.attr("transform", function(d){ return "translate(" + (d.x - v[0]) * k + "," + (d.y - v[1]) * k + ")"; });
    label.attr("transform", function(d){ return "translate(" + (d.x - v[0]) * k + "," + (d.y - v[1]) * k + ")"; });
    node.select("circle").attr("r", function(d){ return d.r * k; });
    label.style("font-size", function(d){ return Math.max(9, Math.min(16, d.r * k / 4)) + "px"; });
  }
  function zoom(d) {
    focus = d;
    centerName.text(focus === root ? "" : focus.data.name);
    centerHint.text(focus === root ? "" : "click background to zoom out");
    var tr = svg.transition().duration(650)
      .tween("zoom", function(){ var i = d3.interpolateZoom(view, [focus.x, focus.y, focus.r * 2]); return function(t){ zoomTo(i(t)); }; });
    label.transition(tr)
      .style("fill-opacity", function(d2){ return labelVisible(d2, focus) ? 1 : 0; })
      .on("start", function(d2){ if (labelVisible(d2, focus)) this.style.display = "inline"; })
      .on("end", function(d2){ if (!labelVisible(d2, focus)) this.style.display = "none"; });
  }
}

// ── Sunburst ────────────────────────────────────────────────────────────────
function renderSunburst(data) {
  var stage = document.getElementById("map-canvas");
  stage.innerHTML = "";
  var rect = stage.getBoundingClientRect();
  var W = rect.width, H = rect.height;
  if (W < 50) return;
  var VISIBLE_DEPTH = 3;
  var radius = Math.min(W, H) / 2 - 20;
  var ringR = radius / (VISIBLE_DEPTH + 1);

  var root = d3.hierarchy(data)
    .sum(function(d){ return d.children ? 0 : (d.value || 1); })
    .sort(function(a,b){ return (b.value||0) - (a.value||0); });
  d3.partition().size([2 * Math.PI, root.height + 1])(root);
  root.each(function(d){ d.current = d; });

  var arc = d3.arc()
    .startAngle(function(d){ return d.x0; }).endAngle(function(d){ return d.x1; })
    .padAngle(function(d){ return Math.min((d.x1 - d.x0) / 2, 0.004); })
    .padRadius(radius * 1.5)
    .innerRadius(function(d){ return d.y0 * ringR; })
    .outerRadius(function(d){ return Math.max(d.y0 * ringR, d.y1 * ringR - 1.5); });

  var svg = d3.select(stage).append("svg")
    .attr("viewBox", (-W/2) + " " + (-H/2) + " " + W + " " + H)
    .attr("preserveAspectRatio", "xMidYMid meet")
    .style("background", "#06080c");

  var path = svg.append("g").selectAll("path")
    .data(root.descendants().slice(1))
    .join("path")
    .attr("class", "sb-arc")
    .attr("fill", arcColor)
    .attr("fill-opacity", function(d){
      if (!arcVisible(d.current)) return 0;
      if (!d.children) return 0.95;                       // leaves: vibrant
      if (d.data.kind === "phase") return 0.85;           // phases: prominent so status reads at a glance
      return 0.65;                                         // other branches (regions/repos/groups)
    })
    .attr("pointer-events", function(d){ return arcVisible(d.current) ? "auto" : "none"; })
    .attr("d", function(d){ return arc(d.current); })
    .on("click", clicked)
    .on("mouseover", function(e, d){
      var parts = ["<b>" + d.data.name + "</b> · " + d.data.kind];
      if (d.data.status) parts.push(d.data.status);
      if (d.data.phase_status) parts.push(d.data.phase_status);
      _showTip(parts.join(" · "), e);
    })
    .on("mousemove", function(e){ _mapTooltip.style.left = (e.pageX+12)+"px"; _mapTooltip.style.top = (e.pageY+12)+"px"; })
    .on("mouseout", _hideTip);

  var label = svg.append("g").style("pointer-events", "none").selectAll("text")
    .data(root.descendants().slice(1))
    .join("text")
    .attr("class", "sb-label").attr("dy", "0.35em")
    .attr("fill-opacity", function(d){ return +labelVisible(d.current); })
    .attr("transform", function(d){ return labelTransform(d.current); })
    .text(function(d){ return fitArcLabel(d, d.current); });

  var center = svg.append("circle").datum(root)
    .attr("r", ringR * 0.95)
    .attr("fill", "#0d1117").attr("stroke", "#30363d")
    .attr("pointer-events", "all").style("cursor", "pointer")
    .on("click", clicked);
  var centerName = svg.append("text").attr("text-anchor", "middle").attr("dy", "-0.3em")
    .attr("fill", "#e6edf3").style("font", "600 14px ui-monospace, monospace")
    .style("pointer-events", "none").text("~");
  var centerHint = svg.append("text").attr("text-anchor", "middle").attr("dy", "1.1em")
    .attr("fill", "#7d8590").style("font", "10px ui-monospace, monospace")
    .style("pointer-events", "none").text("scope");

  function arcColor(d) {
    if (d.data.kind === "plan" && d.data.claude_active) return ACTIVE_EDIT_COLOR;
    if (d.data.kind === "phase") return STATUS_COLOR[d.data.status] || STATUS_COLOR.idle;
    if (d.data.kind === "plan") return STATUS_COLOR[d.data.phase_status || "idle"];
    if (d.data.has_process) return "#2ea043";
    if (d.data.severity === "HIGH") return HIGH_COLOR;
    if (d.data.dirty) return STATUS_COLOR.idle;
    return KIND_COLOR[d.data.kind] || "#3a3f4b";
  }

  function clicked(event, p) {
    if (!p.children && p.data.kind === "plan" && p.data.path) {
      openPlan(p.data.path, p.data.rel || p.data.name); return;
    }
    if (event) event.stopPropagation();
    center.datum(p.parent || root);
    centerName.text(p === root ? "~" : p.data.name);
    centerHint.text(p === root ? "scope" : "click center to zoom out");
    root.each(function(d){
      d.target = {
        x0: Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
        x1: Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
        y0: Math.max(0, d.y0 - p.depth),
        y1: Math.max(0, d.y1 - p.depth)
      };
    });
    var tr = svg.transition().duration(650);
    path.transition(tr)
      .tween("data", function(d){ var i = d3.interpolate(d.current, d.target); return function(t){ d.current = i(t); }; })
      .filter(function(d){ return +this.getAttribute("fill-opacity") || arcVisible(d.target); })
      .attr("fill-opacity", function(d){
        if (!arcVisible(d.target)) return 0;
        if (!d.children) return 0.95;
        if (d.data.kind === "phase") return 0.85;
        return 0.65;
      })
      .attr("pointer-events", function(d){ return arcVisible(d.target) ? "auto" : "none"; })
      .attrTween("d", function(d){ return function(){ return arc(d.current); }; });
    label.transition(tr)
      .filter(function(d){ return +this.getAttribute("fill-opacity") || labelVisible(d.target); })
      .attr("fill-opacity", function(d){ return +labelVisible(d.target); })
      .attrTween("transform", function(d){ return function(){ return labelTransform(d.current); }; })
      .on("end", function(d){ d3.select(this).text(fitArcLabel(d, d.target)); });
  }
  function arcVisible(d){ return d.y1 > 0 && d.y1 <= VISIBLE_DEPTH + 1 && d.y0 >= 1 && d.x1 > d.x0; }
  function labelVisible(d) {
    if (!arcVisible(d)) return false;
    var arcLen = (d.x1 - d.x0) * ((d.y0 + d.y1) / 2) * ringR;
    var thick = (d.y1 - d.y0) * ringR;
    return arcLen > 36 && thick > 12;
  }
  function labelTransform(d) {
    var x = (d.x0 + d.x1) / 2 * 180 / Math.PI;
    var y = (d.y0 + d.y1) / 2 * ringR;
    return "rotate(" + (x - 90) + ") translate(" + y + ",0) rotate(" + (x < 180 ? 0 : 180) + ")";
  }
  function fitArcLabel(d, projected) {
    var arcLen = (projected.x1 - projected.x0) * ((projected.y0 + projected.y1) / 2) * ringR;
    var max = Math.max(3, Math.floor(arcLen / 6.2));
    var name = d.data.name || "";
    return name.length > max ? name.slice(0, Math.max(2, max - 1)) + "…" : name;
  }
}

// ── Dispatcher / view toggle ────────────────────────────────────────────────
function _renderMap() {
  if (!_mapData) return;
  if (_mapView === "sunburst") renderSunburst(_mapData);
  else renderCircles(_mapData);
}

var _mapTreeRefreshId = null;
var _mapActivityRefreshId = null;
var _MAP_TREE_REFRESH_MS = 30000;
var _MAP_ACTIVITY_REFRESH_MS = 1000;

function loadMap(silent) {
  if (typeof d3 === "undefined") { setTimeout(loadMap, 100); return; }
  var canvas = document.getElementById("map-canvas");
  if (!silent) canvas.textContent = "Loading…";
  fetch("/api/treemap").then(function(r){ return r.json(); }).then(function(data){
    var changed = !_mapData || JSON.stringify(data) !== JSON.stringify(_mapData);
    _mapData = data;
    if (changed) _renderMap();
    _updateRefreshIndicator("tree");
  }).catch(function(err){
    if (!silent) canvas.textContent = "Error loading map: " + err.message;
  });
}

function _updateRefreshIndicator(kind) {
  var el = document.getElementById("map-refresh-indicator");
  if (!el) return;
  var now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  if (kind === "tree") {
    el.dataset.lastTree = now;
  }
  var act = el.dataset.lastActivity || "—";
  var tree = el.dataset.lastTree || now;
  el.textContent = "● " + act + " · ↻ " + tree;
}

function _mapTabActive() {
  return document.getElementById("tab-map").classList.contains("active") && !document.hidden;
}

// ── Activity overlay: 1Hz poll, mutates existing SVG attrs only ─────────────
function _applyActivityOverlay(activity) {
  if (!activity) return;
  var openSet = {};
  (activity.processes || []).forEach(function(p){
    (p.open_plans || []).forEach(function(path){ openSet[path] = true; });
  });
  var recentSet = {};
  (activity.recent_mtimes || []).forEach(function(r){ recentSet[r.path] = r.mtime; });

  // Mutate the cached _mapData in place so subsequent re-renders preserve state
  function walk(node) {
    if (!node) return;
    if (node.kind === "plan" && node.path) {
      node.claude_active = !!openSet[node.path];
      node.recently_modified = !!recentSet[node.path];
    }
    if (node.children) node.children.forEach(walk);
  }
  if (_mapData) walk(_mapData);

  // Direct SVG attribute updates (no layout pass, zoom state preserved)
  // Circle packing nodes
  d3.selectAll(".cp-node").each(function(d) {
    if (!d || d.data.kind !== "plan") return;
    var active = !!openSet[d.data.path];
    var recent = !!recentSet[d.data.path];
    d.data.claude_active = active;
    d.data.recently_modified = recent;
    var sel = d3.select(this).select("circle");
    if (active) {
      sel.attr("stroke", "#ffa657").attr("stroke-width", 2)
        .style("filter", "drop-shadow(0 0 8px #ffa657)")
        .attr("fill", "#ffa657");
    } else if (recent) {
      sel.attr("stroke", "#58a6ff").attr("stroke-width", 1.5)
        .style("filter", "drop-shadow(0 0 4px #58a6ff)");
    } else {
      sel.attr("stroke", null).attr("stroke-width", 0).style("filter", null);
    }
  });

  // Sunburst arcs
  d3.selectAll(".sb-arc").each(function(d){
    if (!d || d.data.kind !== "plan") return;
    var active = !!openSet[d.data.path];
    d.data.claude_active = active;
    if (active) {
      d3.select(this).attr("fill", "#ffa657");
    }
  });

  // Update activity indicator
  var el = document.getElementById("map-refresh-indicator");
  if (el) {
    el.dataset.lastActivity = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    _updateRefreshIndicator();
  }
}

function _pollActivity() {
  if (!_mapTabActive()) return;
  fetch("/api/activity").then(function(r){ return r.json(); }).then(_applyActivityOverlay)
    .catch(function(){ /* silent */ });
}

function _startMapAutoRefresh() {
  if (!_mapTreeRefreshId) {
    _mapTreeRefreshId = setInterval(function(){
      if (_mapTabActive()) loadMap(true);
    }, _MAP_TREE_REFRESH_MS);
  }
  if (!_mapActivityRefreshId) {
    _mapActivityRefreshId = setInterval(_pollActivity, _MAP_ACTIVITY_REFRESH_MS);
  }
  _pollActivity();  // fire one immediately so the user sees activity right away
}

// ── Plan search ─────────────────────────────────────────────────────────────
function _collectPlanLeaves(node, repo, out) {
  if (!node) return;
  if (node.kind === "repo" || node.kind === "worktree") repo = node.name;
  if (node.kind === "plan" && node.path) {
    out.push({
      name: node.name, path: node.path, ext: node.ext || "md",
      phase: node.phase || null, phase_status: node.phase_status || null,
      claude_active: !!node.claude_active, repo: repo || ""
    });
  }
  if (node.children) node.children.forEach(function(c){ _collectPlanLeaves(c, repo, out); });
}

function _renderSearchResults(query) {
  var el = document.getElementById("map-search-results");
  if (!_mapData || !query || query.length < 2) {
    el.hidden = true; el.innerHTML = ""; return;
  }
  var all = [];
  _collectPlanLeaves(_mapData, null, all);
  var q = query.toLowerCase();
  var matches = all.filter(function(p){
    return p.name.toLowerCase().indexOf(q) !== -1 ||
           (p.repo && p.repo.toLowerCase().indexOf(q) !== -1) ||
           (p.phase && p.phase.toLowerCase().indexOf(q) !== -1);
  });
  // sort: claude_active first, then by repo+name
  matches.sort(function(a,b){
    if (a.claude_active !== b.claude_active) return a.claude_active ? -1 : 1;
    return (a.repo + a.name).localeCompare(b.repo + b.name);
  });
  el.hidden = false;
  if (!matches.length) {
    el.innerHTML = '<div class="sr-empty">No plan files match "' + q + '"</div>';
    return;
  }
  function highlight(s) {
    var idx = s.toLowerCase().indexOf(q);
    if (idx === -1) return s;
    return s.slice(0, idx) + "<b>" + s.slice(idx, idx + q.length) + "</b>" + s.slice(idx + q.length);
  }
  el.innerHTML = matches.slice(0, 50).map(function(p){
    var status = p.phase_status || "none";
    return '<div class="sr-row" data-path="' + encodeURIComponent(p.path) + '" data-name="' + p.name + '">' +
      '<span class="sr-status ' + status + '"></span>' +
      '<span class="sr-name">' + highlight(p.name) +
        (p.phase ? ' <span class="sr-repo">· ' + p.phase + '</span>' : '') +
      '</span>' +
      '<span class="sr-repo">' + p.repo + '</span>' +
      (p.claude_active ? '<span class="sr-active">● editing</span>' : '<span class="sr-ext ' + p.ext + '">' + p.ext.toUpperCase() + '</span>') +
    '</div>';
  }).join("");
  el.querySelectorAll(".sr-row").forEach(function(row){
    row.addEventListener("click", function(){
      openPlan(decodeURIComponent(row.dataset.path), row.dataset.name);
    });
  });
}

// View toggle buttons
document.querySelectorAll(".map-view-btn").forEach(function(btn){
  btn.addEventListener("click", function(){
    document.querySelectorAll(".map-view-btn").forEach(function(b){ b.classList.remove("active"); });
    btn.classList.add("active");
    _mapView = btn.dataset.view;
    _renderMap();
  });
});

// Search wiring (debounced)
(function(){
  var input = document.getElementById("map-search");
  if (!input) return;
  var to;
  input.addEventListener("input", function(){
    clearTimeout(to);
    to = setTimeout(function(){ _renderSearchResults(input.value.trim()); }, 120);
  });
  input.addEventListener("keydown", function(e){
    if (e.key === "Escape") { input.value = ""; _renderSearchResults(""); input.blur(); }
  });
})();

// Lazy-load on first tab open + start auto-refresh
document.querySelector("[data-tab='map']").addEventListener("click", function(){
  if (!mapLoaded) { loadMap(); mapLoaded = true; }
  _startMapAutoRefresh();
});

// Resize
var _mapResizeTO;
window.addEventListener("resize", function(){
  clearTimeout(_mapResizeTO);
  _mapResizeTO = setTimeout(function(){
    if (_mapData && document.getElementById("tab-map").classList.contains("active")) _renderMap();
  }, 150);
});

// Refresh integration
var _origLoadAll2 = loadAll;
loadAll = function(){
  _origLoadAll2();
  if (document.getElementById("tab-map").classList.contains("active")) {
    mapLoaded = false;
    loadMap();
    mapLoaded = true;
  }
};
