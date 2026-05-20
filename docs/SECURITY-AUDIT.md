# scope · Security Audit

**Date:** 2026-05-12
**Scope of review:** v2.6 (HEAD = `4b901a5`) — Flask backend, all `/api/*` routes, file scanners, frontend modal rendering.
**Method:** manual code review of every endpoint + every data sink. No external scanner used.
**Status:** ✅ All findings remediated in commit following this doc. 11 regression tests added.

---

## Threat model

scope is a **local-only** Flask app running on `127.0.0.1:8765`. It reads:
- `~/.claude/` config (auto-loaded files)
- `~/projects/` git repos
- Process info via psutil (own user only)
- Plan documents (`.md` / `.html`) for in-browser rendering

It must NOT:
- Be reachable from the network
- Allow reading secrets (SSH keys, `.env`, AWS creds, session transcripts)
- Render hostile content with script execution rights
- Permit any other process / website on the machine to extract data

---

## Findings

### 🔴 CRITICAL

#### C1. XSS in plan modal — markdown and HTML rendered without sanitization

**Where:** `static/app.js` `openPlan()` —
```js
if (d.ext === "md" && typeof marked !== "undefined") bodyEl.innerHTML = marked.parse(d.content);
else if (d.ext === "html" || d.ext === "htm") bodyEl.innerHTML = d.content;
```

`marked@12` does NOT sanitize HTML inside markdown by default — `<script>alert(1)</script>` inside a `.md` file executes when the modal opens. For `.html` files it is even more direct (raw `innerHTML` injection).

**Impact:** A `.md` or `.html` plan file containing JavaScript runs in the scope origin (`http://127.0.0.1:8765`). From there it can:
- Fetch any other `/api/*` endpoint and exfiltrate process info, file paths, plan contents
- Use the modal page to read every file the deny list otherwise blocks (via `/api/plan` chain — see C2)

**Vector:** Any process (AI agent, IDE plugin, malicious git hook, supply-chain dep) that can write a `.md` file under any planning-like folder can stage code execution in scope.

**Severity:** Critical — turns a read-only viewer into an arbitrary-data exfil channel.

---

#### C2. `/api/plan` bypasses the deny list

**Where:** `app.py` `api_plan()` —
```python
p = Path(raw).resolve()
if HOME.resolve() not in p.parents and p != HOME.resolve():
    return jsonify({"error": "outside HOME"}), 403
if not p.is_file():
    return jsonify({"error": "not a file"}), 404
if p.suffix.lower() not in (".md", ".html", ".htm", ".txt"):
    return jsonify({"error": "unsupported file type"}), 400
```

The HOME-only check is enforced, but the `is_excluded()` deny list (which blocks `.ssh/*`, `.aws/*`, `.env*`, `.claude/projects/*`, `.credentials.json`, `id_rsa*`, `*.pem`, `*.key`, `*.p12`, etc.) is **not called**.

**Impact:** A file like `~/.aws/notes.md`, `~/.ssh/README.md`, or `~/.claude/projects/<session>/some.md` would be served by `/api/plan` despite the explicit project-wide rule that these paths are off-limits. The session transcript exclusion is particularly load-bearing — bypassing it leaks every prompt the user has ever sent Claude Code.

**Vector:** Direct request: `GET /api/plan?path=/Users/x/.ssh/notes.md`.

**Severity:** Critical — defeats the security model documented in `README.md` and `PRD.md`.

---

### 🟠 HIGH

#### H1. DNS rebinding / cross-origin request

**Where:** `app.py` — no `Host` / `Origin` / `Referer` validation on any route.

Flask binds to `127.0.0.1` so direct external connections are refused. But the browser allows any page the user visits to make `XMLHttpRequest` / `fetch` to `localhost:8765` if:
- The malicious page resolves a domain it controls to `127.0.0.1` (DNS rebinding), bypassing same-origin policy
- The user has `localhost` CORS allowed in their browser (common in dev setups)

**Impact:** A drive-by website visited in any browser tab could exfiltrate the full output of `/api/treemap`, `/api/processes`, `/api/insights`, `/api/git`, `/api/config`, `/api/plan?path=…`. Combined with C1, it could plant a malicious markdown file and then render it.

**Severity:** High — full data exfil, no user interaction beyond visiting an attacker page.

---

#### H2. Flask debug mode is enabled in `app.py`

**Where:** `app.run(host="127.0.0.1", port=8765, debug=True)`

The Werkzeug debugger is exposed on every error. It is PIN-protected, but the PIN is derived from values readable by any local process on the machine (`uuid.getnode()`, `/proc/self/cgroup`, `~/.flask-debug-pin`). It can be brute-forced in seconds locally, and combined with H1 a malicious site could call `/console?__debugger__=yes&cmd=...` to execute arbitrary Python.

**Severity:** High — arbitrary code execution on the user's machine if any uncaught exception fires.

---

### 🟡 MEDIUM

#### M1. `redact()` is defined but never called

`scope/redact.py` has a regex bank that matches Anthropic / OpenAI / GitHub / AWS / Slack / JWT tokens. The module docstring claims it is invoked on every string heading to the browser. **It is not — `grep -rn "from scope.redact"` returns nothing.**

**Impact:** Any pasted token inside a CLAUDE.md, plan file, or repo metadata travels to the browser unfiltered. Combined with C1/H1, those tokens can be exfiltrated.

**Severity:** Medium — defense-in-depth was advertised; in practice absent.

---

#### M2. No `Cache-Control: no-store` on sensitive responses

`/api/plan`, `/api/processes`, `/api/git` responses are JSON. Browsers and intermediate proxies (rare on localhost, but extensions count) may cache them, persisting sensitive data longer than the session.

**Severity:** Medium — practical impact is small on localhost.

---

#### M3. `/api/processes` exposes full cmdline + cwd + open file paths

The endpoint returns every running `claude` process's full `cmdline`, working directory, and open `.md` / `.html` files. This is intentional for the UI but combined with H1 it leaks a lot.

**Severity:** Medium — bound by H1.

---

### 🟢 LOW / OK (notable non-issues)

- ✅ `subprocess.run(["git", ...])` everywhere uses list args; no `shell=True`. No command injection.
- ✅ `Path.resolve()` + ancestor check on `/api/browse` correctly handles `..` and symlinks.
- ✅ Bind address `127.0.0.1`, not `0.0.0.0`.
- ✅ Read-only — no endpoint writes the filesystem.
- ✅ Size cap (2 MB) on `/api/plan` prevents memory exhaustion.
- ✅ 2-second timeout on git subprocess calls prevents hang.
- ✅ Symlinks not followed in `file_browser.list_dir()`.

---

## Recommended fixes (priority order)

1. **C1:** Render plan modal inside a sandboxed iframe with `sandbox=""` (no `allow-scripts`). Eliminates JS execution for both .md and .html. Markdown render still works because the iframe runs in its own document with `srcdoc`.
2. **C2:** Call `scope.exclusions.is_excluded(p)` inside `api_plan()` before reading.
3. **H1:** Add a `before_request` hook validating `Host` is `127.0.0.1`, `localhost`, or `localhost:8765`. Reject everything else.
4. **H2:** Default `debug=False`; require `SCOPE_DEBUG=1` env var to opt in.
5. **M1:** Call `redact()` on plan content + any CLAUDE.md content path heading to the browser.
6. **M2:** Add `Cache-Control: no-store, private` to JSON responses.
