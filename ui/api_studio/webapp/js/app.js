// ── API Studio — main app shell ──────────────────────────────────────────
// Plain-JS Postman-style client. Persists everything to the local backend as
// a per-project bundle; the flow editor (flows.js) is a React Flow island.

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];

const S = {
  projects: [],
  name: null,
  bundle: null,
  dirty: false,
  active: null,        // { collId, reqId }
  activeFlowId: null,
  editEnvId: null,     // env being edited in Environments view
  sideTab: 'collections',
  view: 'request',
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs, ...kids) => {
  const n = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (k === 'class') n.className = attrs[k];
    else if (k === 'html') n.innerHTML = attrs[k];
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), attrs[k]);
    else n.setAttribute(k, attrs[k]);
  }
  kids.flat().forEach((c) => n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
  return n;
};
const uid = (p) => (p || 'id') + Date.now() + Math.floor(Math.random() * 1000);

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('show'), 1800);
}

function markDirty() {
  S.dirty = true;
  $('#saveState').textContent = 'Unsaved';
  $('#saveState').classList.add('dirty');
}
function markClean() {
  S.dirty = false;
  $('#saveState').textContent = 'Saved';
  $('#saveState').classList.remove('dirty');
}

// ── Bootstrap ────────────────────────────────────────────────────────────
async function init() {
  bindStaticEvents();
  S.projects = await API.listProjects();
  if (!S.projects.length) {
    await API.createProject('My First Project');
    S.projects = await API.listProjects();
  }
  await loadProject(S.projects[0].name);
  renderProjectSelect();
}

async function loadProject(name) {
  S.bundle = await API.loadProject(name);
  S.name = name;
  S.active = null;
  S.activeFlowId = null;
  S.editEnvId = (S.bundle.environments[0] || {}).id || null;
  // Ensure at least one collection exists.
  if (!S.bundle.collections.length) {
    S.bundle.collections.push({ id: uid('coll'), name: 'Default', requests: [] });
  }
  markClean();
  renderAll();
}

function renderAll() {
  renderProjectSelect();
  renderEnvSelect();
  renderTree();
  renderHistory();
  renderMethodSelect();
  renderRequest();
  renderEnvEditor();
  renderFlowToolbar();
}

// ── Top bar ──────────────────────────────────────────────────────────────
function renderProjectSelect() {
  const sel = $('#projectSelect');
  sel.innerHTML = '';
  S.projects.forEach((p) => sel.appendChild(el('option', { value: p.name }, p.name)));
  sel.value = S.name || '';
}

function renderEnvSelect() {
  const sel = $('#envSelect');
  sel.innerHTML = '';
  sel.appendChild(el('option', { value: '' }, 'No Environment'));
  S.bundle.environments.forEach((e) => sel.appendChild(el('option', { value: e.id }, e.name)));
  sel.value = S.bundle.meta.activeEnv || '';
}

function activeEnv() {
  return S.bundle.environments.find((e) => e.id === S.bundle.meta.activeEnv) || null;
}

// ── Sidebar: collections tree ────────────────────────────────────────────
function renderTree() {
  const tree = $('#tree');
  tree.innerHTML = '';
  if (!S.bundle.collections.length && !S.bundle.flows.length) {
    tree.appendChild(el('div', { class: 'empty' }, 'No collections yet'));
  }
  S.bundle.collections.forEach((coll) => {
    const head = el('div', { class: 'coll-head' },
      el('span', null, '📁'),
      el('span', null, coll.name),
      el('span', { class: 'del-x', title: 'Delete collection',
        onclick: (ev) => { ev.stopPropagation(); deleteCollection(coll.id); } }, '✕'));
    tree.appendChild(head);
    (coll.requests || []).forEach((req) => {
      const isActive = S.active && S.active.reqId === req.id;
      const item = el('div', {
        class: 'req-item' + (isActive ? ' active' : ''),
        onclick: () => selectRequest(coll.id, req.id),
      },
        el('span', { class: 'method-badge m-' + (req.method || 'GET') }, req.method || 'GET'),
        el('span', null, req.name || 'Untitled'),
        el('span', { class: 'del-x', title: 'Delete request',
          onclick: (ev) => { ev.stopPropagation(); deleteRequest(coll.id, req.id); } }, '✕'));
      tree.appendChild(item);
    });
  });
  if (S.bundle.flows.length) {
    tree.appendChild(el('div', { class: 'section-label' }, 'Flows'));
    S.bundle.flows.forEach((f) => {
      const item = el('div', {
        class: 'flow-item' + (S.activeFlowId === f.id ? ' active' : ''),
        onclick: () => selectFlow(f.id),
      },
        el('span', null, '🔀'),
        el('span', null, f.name || 'Flow'),
        el('span', { class: 'del-x', title: 'Delete flow',
          onclick: (ev) => { ev.stopPropagation(); deleteFlow(f.id); } }, '✕'));
      tree.appendChild(item);
    });
  }
}

function renderHistory() {
  const list = $('#historyList');
  list.innerHTML = '';
  const hist = S.bundle.history || [];
  if (!hist.length) { list.appendChild(el('div', { class: 'empty' }, 'No history')); return; }
  hist.slice().reverse().forEach((hr) => {
    const item = el('div', { class: 'req-item', onclick: () => loadFromHistory(hr) },
      el('span', { class: 'method-badge m-' + hr.method }, hr.method),
      el('span', null, (hr.url || '').slice(0, 40)));
    list.appendChild(item);
  });
}

// ── Collections / requests CRUD ──────────────────────────────────────────
function newRequest() {
  return {
    id: uid('req'), name: 'New Request', method: 'GET', url: '',
    params: [], headers: [],
    auth: { type: 'none', token: '', username: '', password: '', apikeyName: '', apikeyValue: '' },
    body: { mode: 'none', text: '', form: [] },
  };
}

function addCollection() {
  const name = prompt('Collection name:', 'New Collection');
  if (!name) return;
  S.bundle.collections.push({ id: uid('coll'), name, requests: [] });
  markDirty(); renderTree();
}

function deleteCollection(id) {
  if (!confirm('Delete this collection and its requests?')) return;
  S.bundle.collections = S.bundle.collections.filter((c) => c.id !== id);
  if (S.active && !getReq(S.active.collId, S.active.reqId)) S.active = null;
  markDirty(); renderTree(); renderRequest();
}

function addRequest() {
  if (!S.bundle.collections.length) addCollection();
  const coll = S.bundle.collections[0];
  const targetColl = S.active ? (getColl(S.active.collId) || coll) : coll;
  const req = newRequest();
  targetColl.requests.push(req);
  markDirty();
  selectRequest(targetColl.id, req.id);
}

function deleteRequest(collId, reqId) {
  const coll = getColl(collId);
  if (!coll) return;
  coll.requests = coll.requests.filter((r) => r.id !== reqId);
  if (S.active && S.active.reqId === reqId) S.active = null;
  markDirty(); renderTree(); renderRequest();
}

function getColl(id) { return S.bundle.collections.find((c) => c.id === id); }
function getReq(collId, reqId) {
  const c = getColl(collId);
  return c ? (c.requests || []).find((r) => r.id === reqId) : null;
}
function activeReq() { return S.active ? getReq(S.active.collId, S.active.reqId) : null; }

function selectRequest(collId, reqId) {
  S.active = { collId, reqId };
  switchView('request');
  renderTree();
  renderRequest();
}

// ── Request builder ──────────────────────────────────────────────────────
function renderMethodSelect() {
  const sel = $('#methodSelect');
  if (sel.children.length) return;
  METHODS.forEach((m) => sel.appendChild(el('option', { value: m }, m)));
}

function renderRequest() {
  const req = activeReq();
  const urlInput = $('#urlInput');
  const methodSel = $('#methodSelect');
  if (!req) {
    urlInput.value = '';
    methodSel.value = 'GET';
    renderKV($('#paramsTable'), [], () => {});
    renderKV($('#headersTable'), [], () => {});
    renderKV($('#formTable'), [], () => {});
    $('#bodyText').value = '';
    renderAuthFields({ type: 'none' });
    clearResponse();
    return;
  }
  methodSel.value = req.method || 'GET';
  urlInput.value = req.url || '';
  renderKV($('#paramsTable'), req.params, () => markDirty());
  renderKV($('#headersTable'), req.headers, () => markDirty());
  // Body
  const mode = (req.body && req.body.mode) || 'none';
  document.querySelectorAll('input[name=bodyMode]').forEach((r) => { r.checked = r.value === mode; });
  applyBodyMode(mode, false);
  $('#bodyText').value = (req.body && req.body.text) || '';
  renderKV($('#formTable'), (req.body && req.body.form) || [], () => markDirty());
  renderAuthFields(req.auth || { type: 'none' });
}

function renderKV(table, arr, onChange) {
  table.innerHTML = '';
  const rows = arr.slice();
  rows.push({ key: '', value: '', enabled: true, _new: true });
  rows.forEach((row, i) => {
    const tr = el('tr', null,
      el('td', { style: 'width:24px' }, el('input', {
        type: 'checkbox', ...(row.enabled === false ? {} : { checked: 'checked' }),
        onchange: (e) => { row.enabled = e.target.checked; commit(); },
      })),
      el('td', null, el('input', {
        type: 'text', value: row.key || '', placeholder: 'key',
        oninput: (e) => { row.key = e.target.value; commit(row); },
      })),
      el('td', null, el('input', {
        type: 'text', value: row.value || '', placeholder: 'value',
        oninput: (e) => { row.value = e.target.value; commit(row); },
      })),
      el('td', { style: 'width:24px' }, row._new ? '' : el('span', {
        class: 'del-row', title: 'Remove',
        onclick: () => { const idx = arr.indexOf(row); if (idx >= 0) arr.splice(idx, 1); renderKV(table, arr, onChange); onChange(); },
      }, '✕')));
    table.appendChild(tr);
  });
  function commit(row) {
    if (row && row._new && (row.key || row.value)) {
      delete row._new;
      arr.push(row);
      renderKV(table, arr, onChange);
    }
    onChange();
  }
}

function renderAuthFields(auth) {
  $('#authType').value = auth.type || 'none';
  const box = $('#authFields');
  box.innerHTML = '';
  const set = (k, v) => { const r = activeReq(); if (r) { r.auth = r.auth || {}; r.auth[k] = v; markDirty(); } };
  if (auth.type === 'bearer') {
    box.appendChild(el('input', { type: 'text', placeholder: 'Token', value: auth.token || '',
      oninput: (e) => set('token', e.target.value) }));
  } else if (auth.type === 'basic') {
    box.appendChild(el('input', { type: 'text', placeholder: 'Username', value: auth.username || '',
      oninput: (e) => set('username', e.target.value) }));
    box.appendChild(el('input', { type: 'text', placeholder: 'Password', value: auth.password || '',
      oninput: (e) => set('password', e.target.value) }));
  } else if (auth.type === 'apikey') {
    box.appendChild(el('input', { type: 'text', placeholder: 'Header name (e.g. X-API-Key)', value: auth.apikeyName || '',
      oninput: (e) => set('apikeyName', e.target.value) }));
    box.appendChild(el('input', { type: 'text', placeholder: 'Value', value: auth.apikeyValue || '',
      oninput: (e) => set('apikeyValue', e.target.value) }));
  }
}

function applyBodyMode(mode, dirty) {
  $('#bodyText').style.display = (mode === 'json' || mode === 'raw') ? 'block' : 'none';
  $('#formTable').style.display = (mode === 'form') ? 'table' : 'none';
  const req = activeReq();
  if (req && dirty) { req.body = req.body || {}; req.body.mode = mode; markDirty(); }
}

// ── Variable substitution ────────────────────────────────────────────────
function buildVarMap(extra) {
  const map = {};
  const env = activeEnv();
  if (env) (env.variables || []).forEach((v) => { if (v.enabled !== false && v.key) map[v.key] = v.value; });
  if (extra) Object.assign(map, extra);
  return map;
}
function resolveVars(str, map) {
  if (typeof str !== 'string') return str;
  return str.replace(/\{\{\s*([\w.$\-]+)\s*\}\}/g, (m, k) => (k in map ? map[k] : m));
}

// ── Build & send ─────────────────────────────────────────────────────────
function buildRequestPayload(req, extraVars) {
  const map = buildVarMap(extraVars);
  let url = resolveVars(req.url || '', map);
  // Query params.
  const qs = (req.params || []).filter((p) => p.enabled !== false && p.key)
    .map((p) => encodeURIComponent(resolveVars(p.key, map)) + '=' + encodeURIComponent(resolveVars(p.value || '', map)));
  if (qs.length) url += (url.includes('?') ? '&' : '?') + qs.join('&');

  const headers = {};
  (req.headers || []).forEach((hd) => {
    if (hd.enabled !== false && hd.key) headers[resolveVars(hd.key, map)] = resolveVars(hd.value || '', map);
  });
  // Auth.
  const a = req.auth || {};
  if (a.type === 'bearer' && a.token) headers['Authorization'] = 'Bearer ' + resolveVars(a.token, map);
  else if (a.type === 'basic') headers['Authorization'] = 'Basic ' + btoa(resolveVars(a.username || '', map) + ':' + resolveVars(a.password || '', map));
  else if (a.type === 'apikey' && a.apikeyName) headers[a.apikeyName] = resolveVars(a.apikeyValue || '', map);

  // Body.
  let body = null;
  const bm = (req.body && req.body.mode) || 'none';
  if (bm === 'json') {
    body = resolveVars(req.body.text || '', map);
    if (!headers['Content-Type']) headers['Content-Type'] = 'application/json';
  } else if (bm === 'raw') {
    body = resolveVars(req.body.text || '', map);
  } else if (bm === 'form') {
    body = (req.body.form || []).filter((f) => f.enabled !== false && f.key)
      .map((f) => encodeURIComponent(resolveVars(f.key, map)) + '=' + encodeURIComponent(resolveVars(f.value || '', map)))
      .join('&');
    if (!headers['Content-Type']) headers['Content-Type'] = 'application/x-www-form-urlencoded';
  }
  return { method: req.method || 'GET', url, headers, body };
}

async function sendRequest() {
  const req = activeReq();
  if (!req) { toast('Select a request first'); return; }
  const payload = buildRequestPayload(req);
  if (!payload.url) { toast('Enter a URL'); return; }
  $('#respStatus').textContent = 'Sending…';
  $('#respStatus').className = 'resp-status';
  const res = await API.send(payload);
  renderResponse(res);
  // Record history.
  S.bundle.history = S.bundle.history || [];
  S.bundle.history.push({ method: payload.method, url: payload.url, at: Date.now(),
    status: res.status, snapshot: JSON.parse(JSON.stringify(req)) });
  if (S.bundle.history.length > 100) S.bundle.history.shift();
  renderHistory();
  markDirty();
}

function renderResponse(res) {
  const st = $('#respStatus');
  if (res.error) {
    st.textContent = 'Error';
    st.className = 'resp-status err';
    $('#respTime').textContent = '';
    $('#respSize').textContent = '';
    $('#respBody').textContent = res.error;
    $('#respHeaders').textContent = '';
    return;
  }
  st.textContent = res.status + ' ' + (res.statusText || '');
  st.className = 'resp-status ' + (res.status < 400 ? 'ok' : 'err');
  $('#respTime').textContent = (res.timeMs != null ? res.timeMs + ' ms' : '');
  $('#respSize').textContent = (res.size != null ? formatBytes(res.size) : '');
  const body = res.body || '';
  let pretty = body;
  try { pretty = JSON.stringify(JSON.parse(body), null, 2); } catch (e) {}
  $('#respBody').innerHTML = highlightJson(pretty);
  $('#respHeaders').innerHTML = Object.entries(res.headers || {})
    .map(([k, v]) => '<span class="json-key">' + escapeHtml(k) + '</span>: ' + escapeHtml(String(v))).join('\n');
  return { status: res.status, body };
}

function clearResponse() {
  $('#respStatus').textContent = '';
  $('#respTime').textContent = '';
  $('#respSize').textContent = '';
  $('#respBody').textContent = '';
  $('#respHeaders').textContent = '';
}

function loadFromHistory(hr) {
  if (!hr.snapshot) return;
  // Drop into the first collection as a scratch request.
  const coll = S.bundle.collections[0];
  const req = JSON.parse(JSON.stringify(hr.snapshot));
  req.id = uid('req');
  req.name = (req.name || 'Request') + ' (history)';
  coll.requests.push(req);
  markDirty();
  selectRequest(coll.id, req.id);
}

// ── Environments ─────────────────────────────────────────────────────────
function renderEnvEditor() {
  const sel = $('#envEditSelect');
  sel.innerHTML = '';
  S.bundle.environments.forEach((e) => sel.appendChild(el('option', { value: e.id }, e.name)));
  if (S.editEnvId && !S.bundle.environments.find((e) => e.id === S.editEnvId)) S.editEnvId = null;
  if (!S.editEnvId && S.bundle.environments.length) S.editEnvId = S.bundle.environments[0].id;
  sel.value = S.editEnvId || '';
  const env = S.bundle.environments.find((e) => e.id === S.editEnvId);
  renderKV($('#envTable'), env ? env.variables : [], () => markDirty());
}

function addEnvironment() {
  const name = prompt('Environment name:', 'New Env');
  if (!name) return;
  const env = { id: uid('env'), name, variables: [] };
  S.bundle.environments.push(env);
  S.editEnvId = env.id;
  markDirty();
  renderEnvSelect(); renderEnvEditor();
}

function deleteEnvironment() {
  if (!S.editEnvId) return;
  if (!confirm('Delete this environment?')) return;
  S.bundle.environments = S.bundle.environments.filter((e) => e.id !== S.editEnvId);
  if (S.bundle.meta.activeEnv === S.editEnvId) S.bundle.meta.activeEnv = null;
  S.editEnvId = null;
  markDirty();
  renderEnvSelect(); renderEnvEditor();
}

// ── Flows ────────────────────────────────────────────────────────────────
function addFlow() {
  const name = prompt('Flow name:', 'New Flow');
  if (!name) return;
  const flow = { id: uid('flow'), name, nodes: [], edges: [] };
  S.bundle.flows.push(flow);
  markDirty();
  renderTree();
  selectFlow(flow.id);
}

function deleteFlow(id) {
  if (!confirm('Delete this flow?')) return;
  S.bundle.flows = S.bundle.flows.filter((f) => f.id !== id);
  if (S.activeFlowId === id) { S.activeFlowId = null; window.FlowEditor.unmount(); }
  markDirty(); renderTree(); renderFlowToolbar();
}

function activeFlow() { return S.bundle.flows.find((f) => f.id === S.activeFlowId); }

function selectFlow(id) {
  S.activeFlowId = id;
  switchView('flows');
  renderTree();
  renderFlowToolbar();
  const flow = activeFlow();
  if (flow) {
    window.FlowEditor.mount($('#flowCanvas'), flow, (graph) => {
      const f = activeFlow();
      if (f) { f.nodes = graph.nodes; f.edges = graph.edges; markDirty(); }
    });
  }
}

function renderFlowToolbar() {
  const flow = activeFlow();
  $('#flowName').textContent = flow ? flow.name : 'No flow selected';
  renderFlowVars();
}

function renderFlowVars() {
  const flow = activeFlow();
  const table = $('#flowVarsTable');
  if (!flow) { table.innerHTML = ''; return; }
  flow.variables = flow.variables || [];
  renderKV(table, flow.variables, () => markDirty());
}

// ── Flow condition evaluation ────────────────────────────────────────────
function fnUnquote(s) {
  s = String(s == null ? '' : s).trim();
  if (s.length >= 2 && ((s[0] === '"' && s[s.length - 1] === '"') ||
                        (s[0] === "'" && s[s.length - 1] === "'"))) return s.slice(1, -1);
  return s;
}

function fnCompare(l, r, op) {
  const lu = fnUnquote(l), ru = fnUnquote(r);
  const numeric = /^-?\d*\.?\d+$/.test(lu.trim()) && /^-?\d*\.?\d+$/.test(ru.trim());
  const a = numeric ? parseFloat(lu) : lu;
  const b = numeric ? parseFloat(ru) : ru;
  switch (op) {
    case '==': return a === b;
    case '!=': return a !== b;
    case '>': return a > b;
    case '<': return a < b;
    case '>=': return a >= b;
    case '<=': return a <= b;
    default: return false;
  }
}

// Evaluate a flow condition like "{{getUser.id}} == 1" against the context.
// Supports ==, !=, >, <, >=, <=, "contains", and bare truthiness. No eval().
function evalCondition(expr, map) {
  const s = resolveVars(String(expr || ''), map).trim();
  if (!s) return false;
  for (const op of ['>=', '<=', '==', '!=', '>', '<']) {
    const i = s.indexOf(op);
    if (i > 0) return fnCompare(s.slice(0, i), s.slice(i + op.length), op);
  }
  const m = s.match(/^(.*)\s+contains\s+(.*)$/i);
  if (m) return String(fnUnquote(m[1])).indexOf(fnUnquote(m[2])) >= 0;
  const v = fnUnquote(s).toLowerCase();
  return !(v === '' || v === 'false' || v === '0' || v === 'null' || v === 'undefined');
}

// Execute a flow: traverse from the Start node, following edges, honouring
// wait / if-else / while control-flow nodes and chaining outputs downstream.
async function runFlow() {
  const flow = activeFlow();
  if (!flow) { toast('Select a flow'); return; }
  const graph = window.FlowEditor.getGraph();
  flow.nodes = graph.nodes; flow.edges = graph.edges;
  window.FlowEditor.clearStatus();
  // Mark every node as "waiting" up front so each shows a status badge.
  graph.nodes.forEach((n) => window.FlowEditor.setStatus(n.id, 'waiting'));

  const nodes = graph.nodes;
  const edges = graph.edges;
  const byId = {};
  nodes.forEach((n) => { byId[n.id] = n; });

  // Outgoing edges from a node, optionally filtered by a source handle id.
  const outFrom = (id, handle) => edges.filter((e) =>
    e.source === id && (handle == null || (e.sourceHandle || null) === handle));

  const ctx = {};   // label.key -> value, for downstream {{...}}
  // Seed flow-level variables so they are usable as {{key}} in any node.
  (flow.variables || []).forEach((v) => { if (v.enabled !== false && v.key) ctx[v.key] = v.value; });

  const recordResult = (label, bodyText, statusVal) => {
    ctx[label + '.body'] = bodyText || '';
    ctx[label + '.status'] = String(statusVal != null ? statusVal : '');
    try {
      const j = JSON.parse(bodyText);
      if (j && typeof j === 'object') {
        Object.keys(j).forEach((k) => {
          ctx[label + '.' + k] = typeof j[k] === 'object' ? JSON.stringify(j[k]) : String(j[k]);
        });
      }
    } catch (e) {}
  };

  // Entry points: explicit Start node(s), else nodes with no incoming edges.
  const indeg = {};
  nodes.forEach((n) => { indeg[n.id] = 0; });
  edges.forEach((e) => { indeg[e.target] = (indeg[e.target] || 0) + 1; });
  let entries = nodes.filter((n) => (n.type || 'request') === 'start').map((n) => n.id);
  if (!entries.length) entries = nodes.filter((n) => !indeg[n.id]).map((n) => n.id);

  const iters = {};             // per-while-node iteration counters
  const STEP_LIMIT = 1000;      // guard against runaway loops
  let steps = 0;
  const queue = entries.slice();

  while (queue.length) {
    if (++steps > STEP_LIMIT) { toast('Flow stopped: step limit reached'); break; }
    const id = queue.shift();
    const node = byId[id];
    if (!node) continue;
    const type = node.type || 'request';
    const label = (node.data && node.data.label) || id;

    if (type === 'start') { outFrom(id).forEach((e) => queue.push(e.target)); continue; }

    if (type === 'end') { window.FlowEditor.setStatus(id, 'ok', { status: 'end' }); continue; }

    if (type === 'wait') {
      const ms = Math.max(0, parseInt(node.data.ms, 10) || 0);
      const start = Date.now();
      window.FlowEditor.setStatus(id, 'running', { wait: ms });
      await new Promise((resolve) => {
        const tick = () => {
          const remaining = ms - (Date.now() - start);
          if (remaining <= 0) { resolve(); return; }
          window.FlowEditor.setStatus(id, 'running', { wait: remaining });
          setTimeout(tick, Math.min(100, remaining));
        };
        setTimeout(tick, Math.min(100, ms || 1));
      });
      window.FlowEditor.setStatus(id, 'ok', { waited: ms });
      outFrom(id).forEach((e) => queue.push(e.target));
      continue;
    }

    if (type === 'condition') {
      window.FlowEditor.setStatus(id, 'running');
      const pass = evalCondition(node.data.expr || '', buildVarMap(ctx));
      window.FlowEditor.setStatus(id, pass ? 'ok' : 'err', { status: pass ? 'true' : 'else' });
      outFrom(id, pass ? 'true' : 'false').forEach((e) => queue.push(e.target));
      continue;
    }

    if (type === 'while') {
      iters[id] = iters[id] || 0;
      // Expose the loop counter so conditions can reference it.
      ctx[label + '.i'] = iters[id];
      ctx[label + '.iteration'] = iters[id];
      const max = parseInt(node.data.max, 10) || 10;
      const pass = iters[id] < max && evalCondition(node.data.expr || '', buildVarMap(ctx));
      if (pass) {
        iters[id] += 1;
        window.FlowEditor.setStatus(id, 'running', { loop: iters[id], max: max });
        outFrom(id, 'loop').forEach((e) => queue.push(e.target));
      } else {
        window.FlowEditor.setStatus(id, 'ok', { done: iters[id] });
        outFrom(id, 'done').forEach((e) => queue.push(e.target));
      }
      continue;
    }

    if (type === 'for') {
      iters[id] = iters[id] || 0;
      const count = Math.max(0, parseInt(node.data.count, 10) || 0);
      if (iters[id] < count) {
        iters[id] += 1;
        // Expose the loop counter (0-based .i, 1-based .n) to the body.
        ctx[label + '.i'] = iters[id] - 1;
        ctx[label + '.n'] = iters[id];
        ctx[label + '.iteration'] = iters[id];
        window.FlowEditor.setStatus(id, 'running', { loop: iters[id], max: count });
        outFrom(id, 'loop').forEach((e) => queue.push(e.target));
      } else {
        window.FlowEditor.setStatus(id, 'ok', { done: iters[id] });
        outFrom(id, 'done').forEach((e) => queue.push(e.target));
      }
      continue;
    }

    // Mock nodes emit their (variable-substituted) JSON without a network call.
    if (type === 'mock') {
      window.FlowEditor.setStatus(id, 'running');
      const mockBody = resolveVars(node.data.body || '', buildVarMap(ctx));
      recordResult(label, mockBody, 200);
      window.FlowEditor.setStatus(id, 'ok', { status: 200, mock: true, size: (mockBody || '').length });
      outFrom(id).forEach((e) => queue.push(e.target));
      continue;
    }

    // Request node.
    window.FlowEditor.setStatus(id, 'running');
    // Parse "Key: Value" lines into a header array for this node.
    const headerArr = (node.data.headers || '').split('\n').map((line) => {
      const idx = line.indexOf(':');
      if (idx < 0) return null;
      return { key: line.slice(0, idx).trim(), value: line.slice(idx + 1).trim(), enabled: true };
    }).filter((x) => x && x.key);
    const hasBody = (node.data.body || '').trim().length > 0;
    const pseudo = {
      method: node.data.method || 'GET', url: node.data.url || '',
      params: [], headers: headerArr, auth: { type: 'none' },
      body: hasBody ? { mode: 'json', text: node.data.body } : { mode: 'none' },
    };
    const payload = buildRequestPayload(pseudo, ctx);
    const res = await API.send(payload);
    if (res.error || (res.status && res.status >= 400)) {
      window.FlowEditor.setStatus(id, 'err', { error: res.error || ('HTTP ' + res.status) });
      toast('Flow stopped at "' + label + '"');
      continue;   // stop this path; other branches keep running
    }
    recordResult(label, res.body, res.status);
    window.FlowEditor.setStatus(id, 'ok', { status: res.status, time: res.timeMs, size: res.size });
    outFrom(id).forEach((e) => queue.push(e.target));
  }
  markDirty();
}

// ── View / tab switching ─────────────────────────────────────────────────
function switchView(view) {
  S.view = view;
  document.querySelectorAll('.view-tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
}

function bindStaticEvents() {
  // Top bar.
  $('#projectSelect').addEventListener('change', (e) => confirmSwitchProject(e.target.value));
  $('#newProjectBtn').addEventListener('click', createProjectPrompt);
  $('#deleteProjectBtn').addEventListener('click', deleteCurrentProject);
  $('#envSelect').addEventListener('change', (e) => { S.bundle.meta.activeEnv = e.target.value || null; markDirty(); });
  $('#saveBtn').addEventListener('click', saveProject);

  // View tabs.
  document.querySelectorAll('.view-tab').forEach((t) =>
    t.addEventListener('click', () => switchView(t.dataset.view)));

  // Sidebar tabs.
  document.querySelectorAll('.side-tab').forEach((t) => t.addEventListener('click', () => {
    document.querySelectorAll('.side-tab').forEach((x) => x.classList.toggle('active', x === t));
    S.sideTab = t.dataset.side;
    $('#tree').style.display = S.sideTab === 'collections' ? 'block' : 'none';
    $('#historyList').style.display = S.sideTab === 'history' ? 'block' : 'none';
  }));
  $('#addCollectionBtn').addEventListener('click', addCollection);
  $('#addRequestBtn').addEventListener('click', addRequest);
  $('#addFlowBtn').addEventListener('click', addFlow);

  // Request builder.
  $('#methodSelect').addEventListener('change', (e) => { const r = activeReq(); if (r) { r.method = e.target.value; markDirty(); renderTree(); } });
  $('#urlInput').addEventListener('input', (e) => { const r = activeReq(); if (r) { r.url = e.target.value; markDirty(); } });
  $('#sendBtn').addEventListener('click', sendRequest);
  document.querySelectorAll('.req-tab').forEach((t) => t.addEventListener('click', () => {
    document.querySelectorAll('.req-tab').forEach((x) => x.classList.toggle('active', x === t));
    document.querySelectorAll('.req-panel').forEach((p) => p.classList.toggle('active', p.dataset.panel === t.dataset.tab));
  }));
  document.querySelectorAll('.resp-tab').forEach((t) => t.addEventListener('click', () => {
    document.querySelectorAll('.resp-tab').forEach((x) => x.classList.toggle('active', x === t));
    $('#respBody').style.display = t.dataset.rtab === 'body' ? 'block' : 'none';
    $('#respHeaders').style.display = t.dataset.rtab === 'headers' ? 'block' : 'none';
  }));
  $('#authType').addEventListener('change', (e) => { const r = activeReq(); if (r) { r.auth = r.auth || {}; r.auth.type = e.target.value; markDirty(); renderAuthFields(r.auth); } });
  document.querySelectorAll('input[name=bodyMode]').forEach((r) =>
    r.addEventListener('change', (e) => applyBodyMode(e.target.value, true)));
  $('#bodyText').addEventListener('input', (e) => { const r = activeReq(); if (r) { r.body = r.body || {}; r.body.text = e.target.value; markDirty(); } });

  // Flows.
  $('#addRequestNodeBtn').addEventListener('click', () => window.FlowEditor.addRequestNode());
  $('#addMockNodeBtn').addEventListener('click', () => window.FlowEditor.addMockNode());
  $('#addStartNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('start'));
  $('#addEndNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('end'));
  $('#addWaitNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('wait'));
  $('#addConditionNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('condition'));
  $('#addWhileNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('while'));
  $('#addForNodeBtn').addEventListener('click', () => window.FlowEditor.addFunctionNode('for'));
  $('#autoArrangeBtn').addEventListener('click', () => window.FlowEditor.autoArrange());
  $('#flowVarsBtn').addEventListener('click', () => {
    const p = $('#flowVarsPanel');
    p.style.display = p.style.display === 'none' ? 'block' : 'none';
  });
  $('#runFlowBtn').addEventListener('click', runFlow);

  // Environments.
  $('#addEnvBtn').addEventListener('click', addEnvironment);
  $('#delEnvBtn').addEventListener('click', deleteEnvironment);
  $('#envEditSelect').addEventListener('change', (e) => { S.editEnvId = e.target.value; renderEnvEditor(); });

  // Save shortcut.
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); saveProject(); }
  });
}

// ── Project management ───────────────────────────────────────────────────
async function saveProject() {
  if (!S.name) return;
  // Sync current flow graph before saving.
  const flow = activeFlow();
  if (flow && window.FlowEditor.getGraph) {
    const g = window.FlowEditor.getGraph();
    flow.nodes = g.nodes; flow.edges = g.edges;
  }
  await API.saveProject(S.name, S.bundle);
  S.projects = await API.listProjects();
  renderProjectSelect();
  markClean();
  toast('Saved');
}

async function confirmSwitchProject(name) {
  if (name === S.name) return;
  if (S.dirty && !confirm('Discard unsaved changes and switch project?')) {
    renderProjectSelect();
    return;
  }
  window.FlowEditor.unmount();
  await loadProject(name);
}

async function createProjectPrompt() {
  const name = prompt('New project name:', 'New Project');
  if (!name) return;
  const res = await API.createProject(name);
  if (res.error) { toast(res.error); return; }
  S.projects = await API.listProjects();
  window.FlowEditor.unmount();
  await loadProject(name);
}

async function deleteCurrentProject() {
  if (!S.name) return;
  if (!confirm('Delete project "' + S.name + '" and all its data?')) return;
  await API.deleteProject(S.name);
  S.projects = await API.listProjects();
  if (!S.projects.length) { await API.createProject('My First Project'); S.projects = await API.listProjects(); }
  window.FlowEditor.unmount();
  await loadProject(S.projects[0].name);
}

// ── Helpers ──────────────────────────────────────────────────────────────
function formatBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1024 / 1024).toFixed(2) + ' MB';
}
function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function highlightJson(s) {
  const esc = escapeHtml(s);
  return esc.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (m) => {
      let cls = 'json-num';
      if (/^"/.test(m)) cls = /:$/.test(m) ? 'json-key' : 'json-str';
      else if (/true|false/.test(m)) cls = 'json-bool';
      else if (/null/.test(m)) cls = 'json-null';
      return '<span class="' + cls + '">' + m + '</span>';
    });
}

document.addEventListener('DOMContentLoaded', init);
