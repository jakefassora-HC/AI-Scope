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

// ── System Map (Phase 3) ──────────────────────────────────────────────────────

// Tooltip element — created once, reused
var _mapTooltip = (function() {
  var el = document.createElement("div");
  el.className = "map-tooltip";
  document.body.appendChild(el);
  return el;
})();

// Navigate to a named tab by clicking its button
function activateTab(name) {
  var btn = document.querySelector("[data-tab='" + name + "']");
  if (btn) btn.click();
}

// Scroll the .file-row whose first-span title contains path (or basename) into view
function highlightRowByPath(path) {
  if (!path) return;
  var base = path.replace(/^.*\//, "");
  var rows = document.querySelectorAll(".file-row");
  var found = null;
  for (var i = 0; i < rows.length; i++) {
    var span = rows[i].querySelector("span");
    if (!span) continue;
    var t = span.getAttribute("title") || "";
    var txt = span.textContent || "";
    if (t.indexOf(path) !== -1 || txt.indexOf(base) !== -1) {
      found = rows[i];
      break;
    }
  }
  if (!found) return;
  found.scrollIntoView({ behavior: "smooth", block: "center" });
  found.classList.add("row-highlight");
  setTimeout(function() { found.classList.remove("row-highlight"); }, 1500);
}

var mapLoaded = false;
var _cy = null;

function loadMap() {
  if (typeof cytoscape === "undefined") {
    setTimeout(loadMap, 100);
    return;
  }
  // Register fcose layout extension (idempotent guard)
  if (window.cytoscapeFcose && !window._fcoseRegistered) {
    cytoscape.use(window.cytoscapeFcose);
    window._fcoseRegistered = true;
  }

  fetch("/api/graph").then(function(r) { return r.json(); }).then(function(data) {
    var canvas = document.getElementById("map-canvas");
    if (!canvas) return;

    // Empty state
    if (!data.nodes || data.nodes.length <= 1) {
      canvas.innerHTML =
        "<p style='text-align:center;padding:40px;color:var(--muted)'>" +
        "Map is empty. Create a project under <code>~/projects/</code> " +
        "or add a CLAUDE.md to populate it.</p>";
      return;
    }

    canvas.innerHTML = "";

    // Build cytoscape elements
    var elements = [];
    data.nodes.forEach(function(n) {
      var d = { id: n.id, label: n.label, type: n.type };
      var fields = ["path", "severity", "has_process", "branch", "dirty", "size_bytes",
                    "tokens_est", "age_days", "parent_repo_id", "attached_to_id", "cwd", "pid"];
      fields.forEach(function(f) {
        if (n[f] !== undefined && n[f] !== null) d[f] = n[f];
      });
      elements.push({ data: d });
    });
    data.edges.forEach(function(e) {
      var cls = e.style || "";
      elements.push({ data: { id: e.source + "->" + e.target, source: e.source, target: e.target }, classes: cls });
    });

    var layout = {
      name: "fcose",
      quality: "proof",
      animate: false,
      randomize: false,
      fit: true,
      padding: 30,
      nodeSeparation: 80,
      idealEdgeLength: 80,
      nodeRepulsion: 8000,
      gravity: 0.25,
      tile: true,
      tilingPaddingVertical: 10,
      tilingPaddingHorizontal: 10
    };

    _cy = cytoscape({
      container: canvas,
      elements: elements,
      style: [
        { selector: "node", style: {
            "label": "data(label)",
            "color": "#e6edf3",
            "background-color": "#21262d",
            "border-color": "#30363d",
            "border-width": 1,
            "font-size": "11px",
            "font-family": "ui-monospace, monospace",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "width": 28, "height": 28,
            "shape": "round-rectangle"
        }},
        { selector: 'node[type="home"]', style: {
            "background-color": "#58a6ff",
            "border-color": "#58a6ff",
            "width": 36, "height": 36,
            "font-size": "13px",
            "font-weight": "bold"
        }},
        { selector: 'node[type="config"]', style: {
            "shape": "round-rectangle",
            "background-color": "#161b22"
        }},
        { selector: 'node[type="repo"]', style: {
            "shape": "round-rectangle",
            "background-color": "#1f6feb33"
        }},
        { selector: 'node[type="worktree"]', style: {
            "shape": "round-rectangle",
            "background-color": "#21262d",
            "border-style": "dashed"
        }},
        { selector: 'node[type="process"]', style: {
            "shape": "ellipse",
            "background-color": "#3fb950",
            "border-color": "#3fb950"
        }},
        { selector: 'node[severity="HIGH"]', style: {
            "border-color": "#f85149",
            "border-width": 3
        }},
        { selector: 'node[severity="MED"]', style: {
            "border-color": "#d29922",
            "border-width": 3
        }},
        { selector: "node[?has_process]", style: {
            "overlay-color": "#3fb950",
            "overlay-padding": 4,
            "overlay-opacity": 0.2
        }},
        { selector: "edge", style: {
            "width": 1,
            "line-color": "#30363d",
            "target-arrow-color": "#30363d",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier"
        }},
        { selector: "edge.dashed", style: { "line-style": "dashed" }},
        { selector: "edge.process", style: {
            "line-color": "#3fb950",
            "target-arrow-color": "#3fb950",
            "line-style": "dotted"
        }}
      ],
      layout: layout
    });

    // Tooltip on hover
    _cy.on("mouseover", "node", function(evt) {
      var d = evt.target.data();
      var lines = [];
      if (d.type === "home") {
        lines.push("Home directory");
      } else if (d.type === "config") {
        lines.push(d.path || "");
        var parts = [];
        if (d.size_bytes !== undefined) parts.push(fmtBytes(d.size_bytes));
        if (d.tokens_est !== undefined) parts.push("~" + d.tokens_est + " tok");
        if (d.age_days !== undefined) parts.push(d.age_days + "d old");
        if (parts.length) lines.push(parts.join(" · "));
      } else if (d.type === "repo") {
        lines.push(d.path || "");
        var summary = [];
        if (d.branch) summary.push(d.branch);
        if (d.dirty) summary.push(d.dirty + " dirty");
        if (!d.dirty) summary.push("clean");
        lines.push(summary.join(", "));
      } else if (d.type === "worktree") {
        lines.push((d.path || "") + " (" + (d.branch || "") + ") (worktree)");
      } else if (d.type === "process") {
        lines.push("PID " + d.pid + " · cwd: " + d.cwd);
      } else {
        lines.push(d.label || d.id);
      }
      _mapTooltip.innerHTML = lines.map(function(l) {
        return "<div>" + l + "</div>";
      }).join("");
      _mapTooltip.style.display = "block";
      var oe = evt.originalEvent;
      _mapTooltip.style.left = (oe.pageX + 12) + "px";
      _mapTooltip.style.top  = (oe.pageY + 12) + "px";
    });

    _cy.on("mousemove", "node", function(evt) {
      var oe = evt.originalEvent;
      _mapTooltip.style.left = (oe.pageX + 12) + "px";
      _mapTooltip.style.top  = (oe.pageY + 12) + "px";
    });

    _cy.on("mouseout", "node", function() {
      _mapTooltip.style.display = "none";
    });

    // Click → navigate to matching tab
    _cy.on("tap", "node", function(evt) {
      var d = evt.target.data();
      if (d.type === "repo" || d.type === "worktree") {
        activateTab("git");
        setTimeout(function() { highlightRowByPath(d.path); }, 50);
      } else if (d.type === "config") {
        activateTab("context");
        setTimeout(function() { highlightRowByPath(d.path); }, 50);
      } else if (d.type === "process") {
        activateTab("processes");
      }
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
