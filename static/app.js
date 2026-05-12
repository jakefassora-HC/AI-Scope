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

var STATUS_COLOR = { complete: "#3fb950", iterating: "#58a6ff", planning: "#8957e5", draft: "#7d8590" };
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
      if (k === "phase") return STATUS_COLOR[d.data.status] || "#7d8590";
      if (k === "plan") {
        var s = d.data.phase_status; if (s) return STATUS_COLOR[s] || "#7d8590";
        return d.data.ext === "html" ? "#ffa657" : "#58a6ff";
      }
      if (d.data.has_process) return "#2ea043";
      if (d.data.severity === "HIGH") return "#f85149";
      if (d.data.dirty) return "#d29922";
      return KIND_COLOR[k] || "#21262d";
    })
    .attr("fill-opacity", function(d){ return d.children ? 0.35 : 0.85; })
    .on("click", function(event, d){
      event.stopPropagation();
      if (!d.children && d.data.kind === "plan" && d.data.path) {
        openPlan(d.data.path, d.data.rel || d.data.name); return;
      }
      if (focus !== d) zoom(d);
    })
    .on("mouseover", function(e, d){
      var parts = ["<b>" + d.data.name + "</b> · " + (d.data.kind || "")];
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
    .attr("fill-opacity", function(d){ return arcVisible(d.current) ? (d.children ? 0.6 : 0.88) : 0; })
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
    if (d.data.kind === "phase") return STATUS_COLOR[d.data.status] || "#7d8590";
    if (d.data.kind === "plan") return STATUS_COLOR[d.data.phase_status || "draft"];
    if (d.data.has_process) return "#2ea043";
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
      .attr("fill-opacity", function(d){ return arcVisible(d.target) ? (d.children ? 0.6 : 0.88) : 0; })
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

function loadMap() {
  if (typeof d3 === "undefined") { setTimeout(loadMap, 100); return; }
  var canvas = document.getElementById("map-canvas");
  canvas.textContent = "Loading…";
  fetch("/api/treemap").then(function(r){ return r.json(); }).then(function(data){
    _mapData = data;
    _renderMap();
  }).catch(function(err){
    canvas.textContent = "Error loading map: " + err.message;
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

// Lazy-load on first tab open
document.querySelector("[data-tab='map']").addEventListener("click", function(){
  if (!mapLoaded) { loadMap(); mapLoaded = true; }
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
