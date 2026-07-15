# API Studio — Implementation Reference

A Postman-style API client ("API Studio") embedded inside Terminal Browser. It
runs as a small **local web app** served by a **stdlib-only HTTP backend** and
displayed inside an embedded `BrowserWidget` tab. This document explains how it
is wired together so the feature can be maintained or extended later.

---

## 1. High-level architecture

```
┌─────────────────────────── Terminal Browser (PySide6 / Qt6) ───────────────────────────┐
│                                                                                          │
│  terminal_tabs.py                                                                        │
│   └─ tool "api"  ──▶  ui.api_studio.ensure_server()  ──▶  http://127.0.0.1:<port>/?token │
│                        (returns a token-scoped URL)                                       │
│   └─ BrowserWidget(is_api_studio=True), chrome hidden, navigate_to(url)                   │
│                                                                                          │
│                     ▲ HTTP (loopback only, token-gated)                                  │
│                     │                                                                    │
│  ui/api_studio/backend.py  (ThreadingHTTPServer, daemon thread, lazy singleton)          │
│   ├─ serves  webapp/  static files                                                       │
│   ├─ /api/projects (CRUD)   → mirrors to  ~/.terminal_browser/api_studio/projects/<name> │
│   └─ /api/proxy             → urllib outbound request (bypasses browser CORS)            │
│                                                                                          │
│  webapp/  (no build step — plain files)                                                  │
│   ├─ index.html                                                                          │
│   ├─ css/style.css                                                                       │
│   ├─ vendor/  react, react-dom, reactflow (UMD, vendored offline)                        │
│   └─ js/  api.js · app.js · flows.js                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why a local HTTP backend instead of `file://`?**
- `fetch()` / CORS and `ReactDOM.createRoot` behave correctly only from an
  `http://` origin.
- The backend also proxies outbound API calls so the in-page app is never
  blocked by CORS (same reason Postman uses a native agent).
- Projects persist to a real folder tree on disk.

---

## 2. Backend — `ui/api_studio/backend.py`

Stdlib only (no third-party deps). Key pieces:

| Concern | Implementation |
|---|---|
| Server | `ThreadingHTTPServer(("127.0.0.1", 0), _Handler)` — random free port, daemon thread |
| Lifecycle | Lazy singleton: `ensure_server()` starts once & returns URL; `stop_server()`; `base_url()` |
| Static files | `_serve_static()` — resolves under `WEBAPP_DIR`, blocks path traversal via `Path.resolve().relative_to()` |
| Data dir | `~/.terminal_browser/api_studio/projects/<name>/` |
| Content types | `_CONTENT_TYPES` map (html/js/css/json/svg/…) |

### Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/projects` | list project names |
| POST | `/api/projects` | create (409 if exists) |
| GET | `/api/projects/<name>` | load full bundle |
| PUT | `/api/projects/<name>` | save full bundle |
| DELETE | `/api/projects/<name>` | delete project folder |
| POST | `/api/proxy` | outbound HTTP via `urllib`; returns `{status, statusText, headers, body, timeMs, size, error}` |

### On-disk layout (a "bundle")
```
projects/<name>/
  project.json          # { name, created, updated, activeEnv }
  collections/*.json     # one file per collection
  environments/*.json    # one file per environment
  flows/*.json           # one file per flow
  history.json
```
`_save_bundle()` mirrors the in-memory bundle onto this tree (one file per
resource, named `<safe-id>.json`) and **deletes files removed in the UI**.
`_load_bundle()` reads it back.

### Gotchas (already fixed — keep them)
- **URL-decode path segments.** `_path_parts()` must `urllib.parse.unquote`
  each segment, otherwise a project named `Demo API` gets stored as
  `Demo%20API`.
- `_safe_name()` sanitises names to a single safe path segment.
- `_write_json()` writes to a `.tmp` then `os.replace()` for atomic saves.

---

## 3. Security — token-gated, loopback-only

The server binds to `127.0.0.1` so **no other machine on the network** can reach
it. To also block **other browsers/processes on the same machine** (which could
otherwise hit `http://127.0.0.1:<port>`), every request is gated by a
per-process secret token:

1. `ensure_server()` generates `_TOKEN = secrets.token_urlsafe(24)` on start and
   returns a **token-scoped URL**: `http://127.0.0.1:<port>/?token=<TOKEN>`.
2. Only the embedded API Studio tab is handed that URL.
3. `_Handler._authorized()` allows a request if **either**:
   - the `ast=<TOKEN>` cookie matches, **or**
   - the `?token=<TOKEN>` query matches (first navigation).
4. On first valid navigation the server pins the token to an
   **HttpOnly, SameSite=Strict cookie** (`_cookie_header()`), so all subsequent
   same-origin requests (static assets, `/api/*`, proxy) authenticate silently.
5. Every verb (`do_GET/POST/PUT/DELETE`) rejects unauthorized requests with
   **403**. `stop_server()` clears `_TOKEN`.

Verified behaviour:
| Request | Result |
|---|---|
| no token, `GET /` | 403 |
| no token, `GET /api/projects` | 403 |
| `?token=<TOKEN>` | 200 (sets cookie) |
| correct cookie | 200 |
| wrong cookie | 403 |

---

## 4. Tab integration — `ui/terminal_tabs.py`

- Tool registered in `self._tools`: `("🛰  API Studio", "api")`.
- `_open_tool_tab(tool == 'api')`: calls `ensure_server()`, creates a
  `BrowserWidget`, sets `browser.is_api_studio = True`,
  `browser.set_chrome_visible(False)` (hides the nav toolbar — no URL bar /
  reload for this tab), sets the tab icon via `_make_api_icon()` (satellite/orbit
  glyph, teal `#4ec9b0` + blue `#6cb2ff`), then `navigate_to(url)`.
- **Save/restore:** in both tab-serialize blocks, a widget with
  `getattr(widget, 'is_api_studio', False)` is stored as `tab_type: 'api'`
  (not `'browser'`). Restore re-opens it via `_open_tool_tab(name, 'api')`,
  which starts a fresh server and gets a fresh token (state lives on disk, so
  nothing is lost).
- `ui/browser_widget.py` added `set_chrome_visible(visible)` (hides
  `self.nav_toolbar`) used to give API Studio a chrome-less embedded view.

---

## 5. Frontend — `webapp/`

No bundler / no JSX. Everything is plain files loaded via `<script>`.

### `js/api.js`
Thin `fetch` wrappers: `listProjects`, `getProject`, `createProject`,
`saveProject`, `deleteProject`, and `send(payload)` → `POST /api/proxy`.
All requests are same-origin, so the auth cookie is attached automatically.

### `js/app.js` — vanilla-JS app shell
- State `S` holds the loaded bundle; `markDirty()/markClean()` track unsaved
  edits; `saveProject()` syncs the current flow graph then PUTs the bundle.
- **Request builder**, **collections tree**, **environments** editor, **history**.
- Variable substitution: `resolveVars(str, map)` replaces `{{name}}` using
  `buildVarMap(extra)` (regex `/\{\{\s*([\w.$\-]+)\s*\}\}/g`).
- `buildRequestPayload(req, extraVars)` assembles method/url/params/headers/
  auth/body for the proxy.
- Data models:
  - request `{id,name,method,url,params[],headers[],auth{…},body{mode,text,form[]}}`
  - collection `{id,name,requests[]}`
  - environment `{id,name,variables[{key,value,enabled}]}`
  - **flow** `{id,name,nodes[],edges[],variables[]}`

### `js/flows.js` — React Flow "island"
- React + React Flow are **vendored offline** in `webapp/vendor/`
  (`react.production.min.js`, `react-dom.production.min.js`,
  `reactflow.umd.js` [global `ReactFlow`, component = `RF.default`],
  `reactflow.css`). Uses `React.createElement` (aliased `h`) — **no JSX**.
- Exposes an imperative controller `window.FlowEditor`:
  `mount, addRequestNode, addMockNode, addFunctionNode(kind), autoArrange,
  getGraph, setStatus, clearStatus, unmount`.
- `serialize()` persists node `type`, `position`, and data fields
  (`method,url,label,headers,body,ms,expr,max,count`) plus edges with
  `sourceHandle`.

---

## 6. Flow node types

| Node | `type` | Shape / handles | Data fields | Behaviour |
|---|---|---|---|---|
| Request | `request` | 1 in, 1 out | method,url,label,headers,body | HTTP call via proxy |
| Mock | `mock` | 1 out | label, body (JSON) | Emits canned JSON, no network |
| Start | `start` | 1 out | — | Flow entry point |
| End | `end` | 1 in | — | Stops that path |
| Wait | `wait` | 1 in, 1 out | ms | Pauses; **live countdown** |
| If / Else | `condition` | 1 in, 2 out (`true`/`false`) | expr | Branch on expression |
| While | `while` | 1 in, 2 out (`loop`/`done`) | label, expr, max | Loop while expr true (bounded by `max`) |
| For | `for` | 1 in, 2 out (`loop`/`done`) | label, count | Loop a fixed number of times |

- Branch edges carry a `sourceHandle` (`'true'`, `'false'`, `'loop'`, `'done'`)
  so the executor knows which path to follow.
- Loop nodes expose their counter downstream: `{{label.i}}` (0-based),
  `{{label.n}}` (1-based, For), `{{label.iteration}}`.

### Result chips (`metaRow` in flows.js, colours in style.css)
Each node shows a coloured result row after running:
- status (green `good` / red `bad`), time (yellow `n-m-time`), size (teal
  `n-m-size`), `mock` (purple), error (red).
- Wait: live `⏳ N ms left` countdown (`n-m-wait`), then `✓ waited N ms`.
- While/For: `↻ loop k / max` (blue `n-m-loop`), then `✓ N loops`.

---

## 7. Flow execution engine — `runFlow()` in `app.js`

A graph interpreter (not a plain topological run) so it can branch and loop:

1. Sync the graph from `FlowEditor.getGraph()`; `clearStatus()`.
2. Seed `ctx` with flow variables (`{{key}}`).
3. **Entry** = Start node(s), else nodes with no incoming edge.
4. BFS work-queue; per node, run its action, then enqueue targets from the
   correct output handle:
   - `start` → follow out edges.
   - `end` → stop that path.
   - `wait` → `await` a timer, updating `{ wait: remaining }` every ~100 ms for
     the live countdown; then `{ waited: ms }`.
   - `condition` → `evalCondition(expr, ctx)`; follow `true`/`false` handle.
   - `while` → increment counter, expose `{{label.i}}`; if `iters < max` **and**
     expr true → follow `loop` else `done`.
   - `for` → if `iters < count` → follow `loop` (expose `{{label.i/.n}}`) else
     `done`.
   - `mock` → resolve body vars, record result, follow out edges.
   - `request` → parse `Key: Value` header lines, build payload, `API.send()`;
     on `error`/`>=400` mark node `err` and stop that path; else record result
     (JSON keys become `{{label.field}}`) and continue.
5. **`STEP_LIMIT = 1000`** guards against runaway loops.

### `evalCondition(expr, map)` — safe, no `eval()`
- Substitutes `{{…}}` first, then parses `left OP right` with
  `==, !=, >, <, >=, <=`, plus `contains`, plus bare truthiness.
- Numeric compare when both sides look numeric; otherwise string compare.
- Helpers: `fnUnquote()`, `fnCompare()`.

---

## 8. Canvas UX — grid, snapping, auto-arrange (`flows.js`)

- **Grid dots**: `<Background variant="dots" gap={GRID} size={1.5}>` (`GRID = 20`).
- **Snap to grid**: React Flow props `snapToGrid: true, snapGrid: [GRID, GRID]`.
- **Auto-arrange** (`ctrl.autoArrange`, toolbar `▤`):
  1. `computeLayers(nodes, edges)` — Kahn layering left-to-right, with a
     fallback pass so nodes inside loops/cycles still get a layer.
  2. Group nodes per layer; position columns left→right. **Column x advances by
     the actual/estimated width of the widest node in the previous column**
     (per-type `W` estimate or measured `n.width`), so wide request columns
     don't overlap the next.
  3. Within a column, stack rows using **each node's real/estimated height**
     (per-type `H` estimate or measured `n.height`) — prevents tall request
     nodes overlapping short End nodes.
  4. Snap every position to the grid, then `rfInstance.fitView()`.
  - `rfInstance` is captured via React Flow's `onInit`.

---

## 9. Seeded demo projects (on disk)

- **`Flow Demo`** — chained requests (`getUser → getPosts → getTodo`) showing
  `{{getUser.id}}` chaining.
- **`All Functions Demo`** — exercises every node type: Start → getUser →
  If/Else → (true) Wait → getPosts → While(×3 with a Mock tick) → End; the
  (else) branch → Mock fallback → End. Uses a flow variable `limit` and the
  while counter `{{loop.i}}`.

---

## 10. Dev / validation commands

```bash
# JS syntax check (no build step)
node --check ui/api_studio/webapp/js/flows.js
node --check ui/api_studio/webapp/js/app.js

# Backend compile check
python -m py_compile ui/api_studio/backend.py

# Run the app (filtered noise)
python main.py 2>&1 | grep -vE "DIAG|debug|js:|MediaEvent|ERROR:batching|gles2_cmd_decoder|shared_image_manager|DisplayCompositor|ssl_client_socket|backingstore|Back buffer|updateVideoFrame"
```

**Reloading JS/CSS changes:** the backend serves with `Cache-Control: no-store`,
but the API Studio tab has no reload button (chrome hidden), so **close and
reopen the API Studio tab** (or restart the app) to pick up edits.

---

## 11. Extending: how to add a new flow node

1. **`flows.js`** — write a `FooNode(props)` component (handles via
   `h(Handle, …)`), register it in `nodeTypes`, add a default in
   `addFunctionNode()`, and persist any new data fields in `serialize()`.
2. **`index.html`** — add a toolbar button in `#flowToolbar`.
3. **`app.js`** — wire the button in `bindStaticEvents()`, and add a branch in
   `runFlow()` for the new `type` (remember to `outFrom(id[, handle])` to follow
   the right edges).
4. **`style.css`** — add `.rf-node.fn-foo` + any result-chip classes.
5. Validate with `node --check`, then reopen the tab.
