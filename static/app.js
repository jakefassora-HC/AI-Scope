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

// ── System Map — D3 zoomable treemap ─────────────────────────────────────────

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
var _tmState = null; // {root, current, svg, w, h}

function _kindClass(d) {
  var kind = d.data.kind;
  if (kind === "phase") return "tm-phase-" + (d.data.status || "draft");
  return "tm-" + kind;
}

function _decorateClasses(d) {
  var classes = ["tm-rect", _kindClass(d)];
  if (d.data.has_process) classes.push("has-process");
  if (d.data.dirty) classes.push("is-dirty");
  if (d.data.severity === "HIGH") classes.push("sev-HIGH");
  else if (d.data.severity === "MED") classes.push("sev-MED");
  return classes.join(" ");
}

function _renderBreadcrumb(path, onClick) {
  var bc = document.getElementById("map-breadcrumb");
  bc.innerHTML = "";
  path.forEach(function(node, i) {
    if (i > 0) {
      var sep = document.createElement("span");
      sep.className = "sep"; sep.textContent = "›";
      bc.appendChild(sep);
    }
    var c = document.createElement("span");
    c.className = "crumb" + (i === path.length - 1 ? " current" : "");
    c.textContent = node.data.name;
    c.addEventListener("click", function() { onClick(node); });
    bc.appendChild(c);
  });
}

function _renderDetail(d) {
  var el = document.getElementById("map-detail");
  if (!d) { el.innerHTML = '<span style="color:var(--muted)">Click a tile to drill in. Click the background or breadcrumb to zoom out.</span>'; return; }
  var kind = d.data.kind;
  var html = '<div class="md-title">' + d.data.name + ' <span style="color:var(--muted);font-weight:400">· ' + kind + '</span></div>';
  var meta = [];
  if (kind === "repo" || kind === "worktree") {
    if (d.data.branch) meta.push("branch: <code>" + d.data.branch + "</code>");
    var status = [];
    if (d.data.dirty) status.push(d.data.dirty + " dirty");
    if (d.data.untracked) status.push(d.data.untracked + " untracked");
    if (d.data.ahead) status.push("↑" + d.data.ahead);
    if (d.data.behind) status.push("↓" + d.data.behind);
    meta.push(status.length ? status.join(", ") : '<span style="color:var(--green)">clean</span>');
    if (d.data.stale) meta.push('<span style="color:var(--amber)">STALE</span>');
    if (d.data.has_process) meta.push('<span style="color:#2ea043">● claude running</span>');
  } else if (kind === "file") {
    if (d.data.path) meta.push("<code>" + d.data.path + "</code>");
    meta.push(fmtBytes(d.data.size_bytes || 0));
    meta.push("~" + (d.data.tokens_est || 0).toLocaleString() + " tok");
    if (d.data.age_days !== undefined) meta.push(d.data.age_days + "d old");
  } else if (kind === "phase") {
    meta.push("status: <strong>" + d.data.status + "</strong>");
    if (d.data.path) meta.push("<code>" + d.data.path + "</code>");
  } else if (kind === "group" && d.data.percent !== undefined) {
    meta.push(d.data.completed_phases + "/" + d.data.total_phases + " phases");
    meta.push('<span class="md-progress"><span style="width:' + d.data.percent + '%"></span></span> ' + d.data.percent + "%");
    if (d.data.subtitle) meta.push(d.data.subtitle);
  } else if (kind === "region" && d.data.subtitle) {
    meta.push(d.data.subtitle);
  } else if (kind === "process") {
    meta.push("PID " + d.data.pid);
    if (d.data.cwd) meta.push("cwd: <code>" + d.data.cwd + "</code>");
  }
  if (d.data.severity) meta.push('<span style="color:var(--red)">' + d.data.severity + " severity</span>");
  if (meta.length) html += '<div class="md-meta">' + meta.map(function(m){ return "<span>" + m + "</span>"; }).join("") + "</div>";
  el.innerHTML = html;
}

function _statusDotColor(status) {
  return status === "complete" ? "#3fb950"
       : status === "iterating" ? "#58a6ff"
       : status === "planning" ? "#8957e5"
       : "#7d8590";
}

function _zoomTo(node) {
  var s = _tmState;
  if (!s) return;
  s.current = node;
  _drawTreemap();
  _renderDetail(null);
}

function _drawTreemap() {
  var s = _tmState;
  var canvas = document.getElementById("map-canvas");
  var rect = canvas.getBoundingClientRect();
  var w = rect.width, h = rect.height;
  s.w = w; s.h = h;

  // Build a sub-hierarchy rooted at current
  var current = s.current;
  // d3.treemap operates on a hierarchy; rebuild from current node's data so values re-sum scoped
  var sub = d3.hierarchy(current.data)
    .sum(function(d) { return d.children ? 0 : (d.value || 1); })
    .sort(function(a, b) { return (b.value || 0) - (a.value || 0); });

  d3.treemap()
    .size([w, h])
    .paddingTop(function(d) { return d.depth === 0 ? 28 : (d.children ? 22 : 2); })
    .paddingInner(4)
    .paddingOuter(4)
    .round(true)(sub);

  // Build breadcrumb path from root down to current
  var path = [];
  var n = current;
  while (n) { path.unshift(n); n = n.parent; }
  _renderBreadcrumb(path, _zoomTo);

  // Render
  var svg = s.svg;
  svg.selectAll("*").remove();

  // Root title bar
  svg.append("text")
    .attr("class", "tm-label tm-region-title")
    .attr("x", 12).attr("y", 19)
    .attr("fill", "#7d8590")
    .text(current.data.name + (current.data.subtitle ? "  ·  " + current.data.subtitle : ""));

  var descendants = sub.descendants().filter(function(d) { return d.depth > 0; });

  var g = svg.selectAll("g.tm-cell")
    .data(descendants, function(d) { return d.data.path || d.data.name + ":" + d.depth; })
    .enter().append("g")
    .attr("class", function(d) { return "tm-cell" + (d.children ? "" : " tm-leaf"); })
    .attr("transform", function(d) { return "translate(" + d.x0 + "," + d.y0 + ")"; });

  g.append("rect")
    .attr("class", _decorateClasses)
    .attr("width", function(d) { return Math.max(0, d.x1 - d.x0); })
    .attr("height", function(d) { return Math.max(0, d.y1 - d.y0); });

  // Title for branches (regions/repos/groups): top-left, monospace
  g.filter(function(d) { return d.children; }).each(function(d) {
    var gw = d.x1 - d.x0, gh = d.y1 - d.y0;
    if (gw < 50 || gh < 20) return;
    var sel = d3.select(this);
    sel.append("text")
      .attr("class", "tm-label tm-title")
      .attr("x", 8).attr("y", 14)
      .text(d.data.name);
    // subtitle: branch info, percent, etc.
    var sub = null;
    if (d.data.kind === "repo" || d.data.kind === "worktree") {
      var bits = [];
      if (d.data.branch) bits.push(d.data.branch);
      if (d.data.dirty) bits.push(d.data.dirty + "Δ");
      if (d.data.ahead) bits.push("↑" + d.data.ahead);
      if (d.data.behind) bits.push("↓" + d.data.behind);
      sub = bits.join(" · ");
    } else if (d.data.kind === "group" && d.data.percent !== undefined) {
      sub = d.data.completed_phases + "/" + d.data.total_phases + " · " + d.data.percent + "%";
    } else if (d.data.subtitle) {
      sub = d.data.subtitle;
    }
    if (sub && gw > 80) {
      sel.append("text")
        .attr("class", "tm-label tm-sub")
        .attr("x", gw - 8).attr("y", 14)
        .attr("text-anchor", "end")
        .text(sub);
    }
    // running-process pulse dot
    if (d.data.has_process) {
      sel.append("circle")
        .attr("class", "tm-status-dot")
        .attr("cx", gw - 10).attr("cy", gh - 10)
        .attr("r", 4)
        .attr("fill", "#2ea043")
        .style("filter", "drop-shadow(0 0 4px #2ea043)");
    }
  });

  // Leaf labels
  g.filter(function(d) { return !d.children; }).each(function(d) {
    var gw = d.x1 - d.x0, gh = d.y1 - d.y0;
    if (gw < 30 || gh < 14) return;
    var sel = d3.select(this);
    // truncate label to fit
    var label = d.data.name;
    var maxChars = Math.floor(gw / 7);
    if (label.length > maxChars) label = label.slice(0, Math.max(0, maxChars - 1)) + "…";
    sel.append("text")
      .attr("class", "tm-label tm-leaf-label")
      .attr("x", 6).attr("y", 14)
      .text(label);
    // phase status dot
    if (d.data.kind === "phase" && gw > 50 && gh > 22) {
      sel.append("circle")
        .attr("class", "tm-status-dot")
        .attr("cx", gw - 8).attr("cy", 10)
        .attr("r", 3.5)
        .attr("fill", _statusDotColor(d.data.status));
    }
  });

  // Interaction
  g.on("mouseover", function(event, d) {
      var t = d.data.name;
      if (d.data.kind === "file") t += " · " + fmtBytes(d.data.size_bytes || 0) + " · ~" + (d.data.tokens_est || 0) + " tok";
      else if (d.data.kind === "phase") t += " · " + d.data.status;
      else if (d.data.path) t += " · " + d.data.path;
      _mapTooltip.textContent = t;
      _mapTooltip.style.display = "block";
    })
    .on("mousemove", function(event) {
      _mapTooltip.style.left = (event.pageX + 12) + "px";
      _mapTooltip.style.top = (event.pageY + 12) + "px";
    })
    .on("mouseout", function() { _mapTooltip.style.display = "none"; })
    .on("click", function(event, d) {
      event.stopPropagation();
      _renderDetail(d);
      // drill in: only branches with children
      if (d.children && d.children.length) {
        // find the equivalent node in the master root by data identity (path or chain)
        var target = _findInRoot(s.root, d);
        if (target) _zoomTo(target);
      } else if (d.data.kind === "file" && d.data.path) {
        activateTab("context");
      } else if (d.data.kind === "process") {
        activateTab("processes");
      }
    });

  svg.on("click", function() {
    // zoom out one level on background click
    if (s.current.parent) _zoomTo(s.current.parent);
  });
}

function _findInRoot(root, target) {
  // Match by (name + depth chain) since data refs differ between rebuilt hierarchies
  var chain = [];
  var n = target;
  while (n) { chain.unshift(n.data.name); n = n.parent; }
  var cur = root;
  // chain[0] is root name; descend matching by name
  for (var i = 1; i < chain.length; i++) {
    if (!cur.children) return null;
    var found = null;
    for (var j = 0; j < cur.children.length; j++) {
      if (cur.children[j].data.name === chain[i]) { found = cur.children[j]; break; }
    }
    if (!found) return null;
    cur = found;
  }
  return cur;
}

function loadMap() {
  if (typeof d3 === "undefined") { setTimeout(loadMap, 100); return; }
  fetch("/api/treemap").then(function(r) { return r.json(); }).then(function(data) {
    var canvas = document.getElementById("map-canvas");
    if (!canvas) return;
    canvas.innerHTML = "";

    var root = d3.hierarchy(data)
      .sum(function(d) { return d.children ? 0 : (d.value || 1); })
      .sort(function(a, b) { return (b.value || 0) - (a.value || 0); });

    var svg = d3.select(canvas).append("svg")
      .attr("preserveAspectRatio", "xMidYMid meet");

    _tmState = { root: root, current: root, svg: svg };
    _drawTreemap();
    _renderDetail(null);

    // Re-render on window resize
    var _resizeTO;
    window.addEventListener("resize", function() {
      clearTimeout(_resizeTO);
      _resizeTO = setTimeout(function() {
        if (_tmState) _drawTreemap();
      }, 150);
    });
  }).catch(function(err) {
    var canvas = document.getElementById("map-canvas");
    if (canvas) canvas.textContent = "Error loading map: " + err.message;
  });
}

// Lazy-load map on first click
document.querySelector("[data-tab='map']").addEventListener("click", function() {
  if (!mapLoaded) { loadMap(); mapLoaded = true; }
});

// Refresh integration: reload map if it's the active tab
var _origLoadAll2 = loadAll;
loadAll = function() {
  _origLoadAll2();
  var mapPanel = document.getElementById("tab-map");
  if (mapPanel && mapPanel.classList.contains("active")) {
    mapLoaded = false;
    loadMap();
    mapLoaded = true;
  }
};
