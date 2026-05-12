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
