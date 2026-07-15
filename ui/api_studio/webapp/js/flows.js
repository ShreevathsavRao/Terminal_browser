// Visual flow editor built on React Flow (vendored UMD build).
// Exposes a small imperative controller (window.FlowEditor) so the plain-JS
// app shell can mount a flow, add nodes, run it, and read the graph back.
(function () {
  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const RF = window.ReactFlow;
  if (!React || !ReactDOM || !RF) {
    console.error('React Flow vendor bundle failed to load');
    return;
  }
  const h = React.createElement;
  const RFComp = RF.default || RF.ReactFlow;
  const { Background, Controls, MiniMap, Handle, Position,
          BaseEdge, useReactFlow, MarkerType,
          applyNodeChanges, applyEdgeChanges, addEdge } = RF;

  // Module-scoped handle to the mounted editor's imperative API.
  let ctrl = null;
  let onChangeCb = null;
  let rfInstance = null;   // React Flow instance (for fitView after arrange)

  const GRID = 20;         // snap grid size (px)

  // Compute a left-to-right layer index for every node (Kahn layering with a
  // fallback pass so nodes inside loops/cycles still get placed).
  function computeLayers(nodes, edges) {
    const adj = {};
    const indeg = {};
    nodes.forEach((n) => { adj[n.id] = []; indeg[n.id] = 0; });
    edges.forEach((e) => {
      if (adj[e.source]) adj[e.source].push(e.target);
      if (indeg[e.target] != null) indeg[e.target] += 1;
    });
    const layer = {};
    nodes.forEach((n) => { layer[n.id] = 0; });
    const local = Object.assign({}, indeg);
    const seen = new Set();
    const q = nodes.filter((n) => indeg[n.id] === 0).map((n) => n.id);
    q.forEach((id) => seen.add(id));
    while (q.length) {
      const id = q.shift();
      (adj[id] || []).forEach((t) => {
        if (layer[t] < layer[id] + 1) layer[t] = layer[id] + 1;
        local[t] -= 1;
        if (local[t] <= 0 && !seen.has(t)) { seen.add(t); q.push(t); }
      });
    }
    // Nodes left unplaced (cycles) sit just after their deepest predecessor.
    nodes.forEach((n) => {
      if (seen.has(n.id)) return;
      let mx = -1;
      edges.forEach((e) => {
        if (e.target === n.id && seen.has(e.source)) mx = Math.max(mx, layer[e.source]);
      });
      layer[n.id] = mx + 1;
      seen.add(n.id);
    });
    return layer;
  }

  // ── Grid A* router ────────────────────────────────────────────────────────
  // Routes edges on a coarse GRID lattice so that every grid cell is used by at
  // most one path (and never by a node), giving fully non-overlapping paths.
  function MinHeap() { this.a = []; }
  MinHeap.prototype.push = function (node, pri) {
    const a = this.a; a.push({ node: node, pri: pri }); let i = a.length - 1;
    while (i > 0) { const p = (i - 1) >> 1; if (a[p].pri <= a[i].pri) break; const t = a[p]; a[p] = a[i]; a[i] = t; i = p; }
  };
  MinHeap.prototype.pop = function () {
    const a = this.a; const top = a[0]; const last = a.pop();
    if (a.length) {
      a[0] = last; let i = 0;
      for (;;) {
        let l = 2 * i + 1, r = l + 1, s = i;
        if (l < a.length && a[l].pri < a[s].pri) s = l;
        if (r < a.length && a[r].pri < a[s].pri) s = r;
        if (s === i) break; const t = a[s]; a[s] = a[i]; a[i] = t; i = s;
      }
    }
    return top.node;
  };
  MinHeap.prototype.empty = function () { return this.a.length === 0; };

  // A* on a cols×rows grid. blocked/reserved are Uint8Array(cols*rows). The
  // start (sI) and goal (gI) cells are always traversable even if occupied.
  // Returns an array of {c,r} cells, or null if no path exists.
  function astarGrid(cols, rows, blocked, reserved, s, g) {
    const N = cols * rows;
    const idx = (c, r) => r * cols + c;
    const gScore = new Float64Array(N); gScore.fill(Infinity);
    const came = new Int32Array(N); came.fill(-1);
    const dirTo = new Int8Array(N); dirTo.fill(-1);
    const closed = new Uint8Array(N);
    const sI = idx(s.c, s.r), gI = idx(g.c, g.r);
    if (s.c < 0 || s.c >= cols || s.r < 0 || s.r >= rows) return null;
    if (g.c < 0 || g.c >= cols || g.r < 0 || g.r >= rows) return null;
    const heur = (c, r) => Math.abs(c - g.c) + Math.abs(r - g.r);
    const heap = new MinHeap();
    gScore[sI] = 0; heap.push(sI, heur(s.c, s.r));
    const dc = [1, -1, 0, 0], dr = [0, 0, 1, -1];
    while (!heap.empty()) {
      const cur = heap.pop();
      if (cur === gI) break;
      if (closed[cur]) continue;
      closed[cur] = 1;
      const cc = cur % cols, cr = (cur - cc) / cols;
      for (let d = 0; d < 4; d++) {
        const nc = cc + dc[d], nr = cr + dr[d];
        if (nc < 0 || nc >= cols || nr < 0 || nr >= rows) continue;
        const ni = idx(nc, nr);
        if (closed[ni]) continue;
        if (ni !== gI && ni !== sI && (blocked[ni] || reserved[ni])) continue;
        let step = 1;
        if (dirTo[cur] !== -1 && dirTo[cur] !== d) step += 4; // penalise turns
        const tentative = gScore[cur] + step;
        if (tentative < gScore[ni]) {
          gScore[ni] = tentative; came[ni] = cur; dirTo[ni] = d;
          heap.push(ni, tentative + heur(nc, nr));
        }
      }
    }
    if (gI !== sI && came[gI] === -1) return null;
    const path = []; let c = gI;
    while (c !== -1) { const cc = c % cols, cr = (c - cc) / cols; path.push({ c: cc, r: cr }); if (c === sI) break; c = came[c]; }
    path.reverse();
    return path;
  }

  function fmtBytes(n) {
    if (n == null) return '';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1024 / 1024).toFixed(2) + ' MB';
  }

  // Render the coloured result row (status / time / size) shown under a node.
  function metaRow(r) {
    if (!r || typeof r !== 'object') return null;
    if (r.error) return h('div', { className: 'n-meta' },
      h('span', { className: 'n-m-err' }, String(r.error)));
    // Wait-node live countdown.
    if (r.wait != null) return h('div', { className: 'n-meta' },
      h('span', { className: 'n-m-wait' }, '⏳ ' + Math.ceil(r.wait) + ' ms left'));
    if (r.waited != null) return h('div', { className: 'n-meta' },
      h('span', { className: 'n-m-status good' }, '✓ waited ' + r.waited + ' ms'));
    // Loop nodes (while / for) live iteration count.
    if (r.loop != null) return h('div', { className: 'n-meta' },
      h('span', { className: 'n-m-loop' }, '↻ loop ' + r.loop + (r.max ? ' / ' + r.max : '')));
    if (r.done != null) return h('div', { className: 'n-meta' },
      h('span', { className: 'n-m-status good' }, '✓ ' + r.done + ' loops'));
    const kids = [h('span', {
      key: 's',
      className: 'n-m-status ' + (r.status < 400 ? 'good' : 'bad'),
    }, String(r.status != null ? r.status : ''))];
    if (r.time != null) kids.push(h('span', { key: 't', className: 'n-m-time' }, r.time + ' ms'));
    if (r.size != null) kids.push(h('span', { key: 'z', className: 'n-m-size' }, fmtBytes(r.size)));
    if (r.mock) kids.push(h('span', { key: 'm', className: 'n-m-mock' }, 'mock'));
    return h('div', { className: 'n-meta' }, kids);
  }

  // Small status pill shown next to a node's name: waiting/running/success/failed.
  function statusBadge(status) {
    const map = {
      waiting: ['waiting', 'Waiting'],
      running: ['running', 'Running'],
      ok: ['ok', 'Success'],
      err: ['err', 'Failed'],
    };
    const m = map[status];
    if (!m) return null;
    return h('span', { className: 'n-status-badge ' + m[0] },
      h('span', { className: 'n-sb-dot' }),
      h('span', { className: 'n-sb-label' }, m[1]));
  }

  function RequestNode(props) {
    const d = props.data || {};
    const cls = 'rf-node' + (d.status ? ' ' + d.status : '');
    return h('div', { className: cls },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-method m-' + (d.method || 'GET') }, (d.method || 'GET') + '  ' + (d.label || 'Request')),
        statusBadge(d.status),
        h('span', {
          className: 'n-close', title: 'Remove node',
          onClick: (e) => { e.stopPropagation(); ctrl && ctrl.deleteNode(props.id); },
        }, '✕')),
      h('select', {
        value: d.method || 'GET',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { method: e.target.value }),
      }, ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => h('option', { key: m, value: m }, m))),
      h('input', {
        type: 'text', value: d.url || '', placeholder: 'https://...',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { url: e.target.value }),
      }),
      h('input', {
        type: 'text', value: d.label || '', placeholder: 'node name',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { label: e.target.value }),
      }),
      h('div', { className: 'n-section' }, 'Headers  (Key: Value per line)'),
      h('textarea', {
        className: 'n-headers', value: d.headers || '',
        placeholder: 'Content-Type: application/json',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { headers: e.target.value }),
      }),
      h('div', { className: 'n-section' }, 'Body'),
      h('textarea', {
        className: 'n-body', value: d.body || '',
        placeholder: '{ "key": "value" }',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { body: e.target.value }),
      }),
      metaRow(d.result),
      h(Handle, { type: 'source', position: Position.Right })
    );
  }

  function MockNode(props) {
    const d = props.data || {};
    const cls = 'rf-node mock-node' + (d.status ? ' ' + d.status : '');
    return h('div', { className: cls },
      h('div', { className: 'n-head' },
        h('span', { className: 'n-method n-mock' }, 'MOCK  ' + (d.label || 'Mock')),
        statusBadge(d.status),
        h('span', {
          className: 'n-close', title: 'Remove node',
          onClick: (e) => { e.stopPropagation(); ctrl && ctrl.deleteNode(props.id); },
        }, '✕')),
      h('input', {
        type: 'text', value: d.label || '', placeholder: 'mock name',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { label: e.target.value }),
      }),
      h('textarea', {
        className: 'n-mock-body', value: d.body || '', placeholder: '{ "id": 1 }',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { body: e.target.value }),
      }),
      metaRow(d.result),
      h(Handle, { type: 'source', position: Position.Right })
    );
  }

  // Small close (✕) button shared by the function nodes.
  function closeBtn(id) {
    return h('span', {
      className: 'n-close', title: 'Remove node',
      onClick: (e) => { e.stopPropagation(); ctrl && ctrl.deleteNode(id); },
    }, '✕');
  }

  function StartNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-start' + (d.status ? ' ' + d.status : '') },
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '▶  Start'),
        statusBadge(d.status),
        closeBtn(props.id)),
      h(Handle, { type: 'source', position: Position.Right })
    );
  }

  function EndNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-end' + (d.status ? ' ' + d.status : '') },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '■  End'),
        statusBadge(d.status),
        closeBtn(props.id))
    );
  }

  function WaitNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-wait' + (d.status ? ' ' + d.status : '') },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '⏱  Wait'),
        statusBadge(d.status),
        closeBtn(props.id)),
      h('div', { className: 'n-fn-row' },
        h('input', {
          type: 'number', min: '0', value: d.ms != null ? d.ms : 1000,
          onChange: (e) => ctrl && ctrl.updateNode(props.id, { ms: e.target.value }),
        }),
        h('span', { className: 'n-unit' }, 'ms')),
      metaRow(d.result),
      h(Handle, { type: 'source', position: Position.Right })
    );
  }

  function ConditionNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-cond' + (d.status ? ' ' + d.status : '') },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '◆  If / Else'),
        statusBadge(d.status),
        closeBtn(props.id)),
      h('input', {
        type: 'text', value: d.expr || '', placeholder: '{{getUser.id}} == 1',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { expr: e.target.value }),
      }),
      metaRow(d.result),
      h('div', { className: 'n-branch n-branch-true' }, 'true ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'true', style: { top: '68%' } }),
      h('div', { className: 'n-branch n-branch-false' }, 'else ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'false', style: { top: '86%' } })
    );
  }

  function WhileNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-while' + (d.status ? ' ' + d.status : '') },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '↻  While'),
        statusBadge(d.status),
        closeBtn(props.id)),
      h('input', {
        type: 'text', value: d.label || '', placeholder: 'loop name (for {{name.i}})',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { label: e.target.value }),
      }),
      h('input', {
        type: 'text', value: d.expr || '', placeholder: '{{i}} < 5',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { expr: e.target.value }),
      }),
      h('div', { className: 'n-fn-row' },
        h('span', { className: 'n-unit' }, 'max'),
        h('input', {
          type: 'number', min: '1', value: d.max != null ? d.max : 10,
          onChange: (e) => ctrl && ctrl.updateNode(props.id, { max: e.target.value }),
        })),
      metaRow(d.result),
      h('div', { className: 'n-branch n-branch-true' }, 'loop ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'loop', style: { top: '70%' } }),
      h('div', { className: 'n-branch n-branch-false' }, 'done ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'done', style: { top: '88%' } })
    );
  }

  function ForNode(props) {
    const d = props.data || {};
    return h('div', { className: 'rf-node fn-node fn-for' + (d.status ? ' ' + d.status : '') },
      h(Handle, { type: 'target', position: Position.Left }),
      h('div', { className: 'n-head' },
        h('span', { className: 'n-fn-title' }, '⟳  For'),
        statusBadge(d.status),
        closeBtn(props.id)),
      h('input', {
        type: 'text', value: d.label || '', placeholder: 'loop name (for {{name.i}})',
        onChange: (e) => ctrl && ctrl.updateNode(props.id, { label: e.target.value }),
      }),
      h('div', { className: 'n-fn-row' },
        h('span', { className: 'n-unit' }, 'count'),
        h('input', {
          type: 'number', min: '1', value: d.count != null ? d.count : 3,
          onChange: (e) => ctrl && ctrl.updateNode(props.id, { count: e.target.value }),
        })),
      metaRow(d.result),
      h('div', { className: 'n-branch n-branch-true' }, 'loop ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'loop', style: { top: '70%' } }),
      h('div', { className: 'n-branch n-branch-false' }, 'done ▸'),
      h(Handle, { type: 'source', position: Position.Right, id: 'done', style: { top: '88%' } })
    );
  }

  const nodeTypes = {
    request: RequestNode, mock: MockNode,
    start: StartNode, end: EndNode, wait: WaitNode,
    condition: ConditionNode, while: WhileNode, for: ForNode,
  };

  // ── Editable, grid-snapping connection edge ───────────────────────────
  // Routes source → user-placed waypoints → target. Double-click the edge to
  // drop a waypoint; drag a waypoint (snaps to the grid) to shape the path;
  // double-click a waypoint to remove it.
  function orthoPath(sx, sy, tx, ty, wps) {
    // No waypoints: simple horizontal-vertical-horizontal through a mid channel
    // so the edge exits the right side and enters the left side squarely.
    if (!wps || !wps.length) {
      const mx = Math.round((sx + tx) / 2 / GRID) * GRID;
      return 'M ' + sx + ' ' + sy + ' L ' + mx + ' ' + sy
        + ' L ' + mx + ' ' + ty + ' L ' + tx + ' ' + ty;
    }
    // Pass through EVERY waypoint exactly (so the draggable dots always sit on
    // the drawn line), turning only at right angles.
    let d = 'M ' + sx + ' ' + sy;
    let cy = sy;
    wps.forEach((p) => {
      d += ' L ' + p.x + ' ' + cy;   // horizontal into the channel
      d += ' L ' + p.x + ' ' + p.y;  // vertical along the channel
      cy = p.y;
    });
    // Enter the target squarely from the left (real target Y).
    d += ' L ' + wps[wps.length - 1].x + ' ' + ty;
    d += ' L ' + tx + ' ' + ty;
    return d;
  }

  function EditableEdge(props) {
    const { id, sourceX, sourceY, targetX, targetY, data, markerEnd, style, selected } = props;
    const rf = useReactFlow();
    const [hover, setHover] = React.useState(false);
    const [drag, setDrag] = React.useState(false);
    const pts = (data && data.points) || [];
    const full = [{ x: sourceX, y: sourceY }].concat(pts, [{ x: targetX, y: targetY }]);
    // Build a purely orthogonal (right-angle) path: exit the source to the
    // right, travel through the waypoint channels, then enter the target from
    // the left. Because we always turn at 90° using the REAL handle coords,
    // no segment can ever cut diagonally across a node.
    const d = orthoPath(sourceX, sourceY, targetX, targetY, pts);

    const toFlow = (evt) => (rf.screenToFlowPosition || rf.project)
      .call(rf, { x: evt.clientX, y: evt.clientY });
    const snap = (v) => Math.round(v / GRID) * GRID;
    const commit = (next) => rf.setEdges((es) => es.map((e) => e.id === id
      ? Object.assign({}, e, { data: Object.assign({}, e.data, { points: next }) }) : e));

    const startDrag = (idx) => (evt) => {
      evt.stopPropagation(); evt.preventDefault();
      setDrag(true);
      const move = (ev) => {
        const p = toFlow(ev);
        const next = pts.slice();
        next[idx] = { x: snap(p.x), y: snap(p.y) };
        commit(next);
      };
      const up = () => {
        setDrag(false);
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    };

    const addWaypoint = (evt) => {
      evt.stopPropagation();
      const p = toFlow(evt);
      let bestI = 0, bestD = Infinity;
      for (let i = 0; i < full.length - 1; i++) {
        const a = full[i], b = full[i + 1];
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const dd = (mx - p.x) * (mx - p.x) + (my - p.y) * (my - p.y);
        if (dd < bestD) { bestD = dd; bestI = i; }
      }
      const next = pts.slice();
      next.splice(bestI, 0, { x: snap(p.x), y: snap(p.y) });
      commit(next);
    };

    const removeWaypoint = (idx) => (evt) => {
      evt.stopPropagation(); evt.preventDefault();
      const next = pts.slice(); next.splice(idx, 1); commit(next);
    };

    const show = hover || selected || drag;

    return h(React.Fragment, null,
      h(BaseEdge, { id: id, path: d, markerEnd: markerEnd, style: style }),
      h('path', {
        d: d, fill: 'none', stroke: 'transparent', strokeWidth: 18,
        className: 'nopan', style: { cursor: 'pointer', pointerEvents: 'stroke' },
        onMouseEnter: () => setHover(true),
        onMouseLeave: () => setHover(false),
        onDoubleClick: addWaypoint,
      }),
      show ? pts.map((p, i) => h('circle', {
        key: 'wp' + i, cx: p.x, cy: p.y, r: 6, className: 'edge-waypoint nopan',
        onMouseEnter: () => setHover(true), onMouseLeave: () => setHover(false),
        onPointerDown: startDrag(i), onDoubleClick: removeWaypoint(i),
      })) : null
    );
  }

  const edgeTypes = { editable: EditableEdge };

  function Editor(props) {
    const [nodes, setNodes] = React.useState(props.initialNodes || []);
    const [edges, setEdges] = React.useState(props.initialEdges || []);

    // Undo/redo history (snapshots of {nodes, edges}).
    const rootRef = React.useRef(null);
    const past = React.useRef([]);
    const future = React.useRef([]);
    const applying = React.useRef(false);   // guard while restoring a snapshot
    const histTimer = React.useRef(null);
    const lastStable = React.useRef({ nodes: props.initialNodes || [], edges: props.initialEdges || [] });
    const firstRun = React.useRef(true);

    const onNodesChange = React.useCallback(
      (chs) => setNodes((ns) => applyNodeChanges(chs, ns)), []);
    const onEdgesChange = React.useCallback(
      (chs) => setEdges((es) => applyEdgeChanges(chs, es)), []);
    const onConnect = React.useCallback(
      (c) => setEdges((es) => addEdge(
        Object.assign({}, c, { type: 'editable', animated: true, data: { points: [] } }), es)), []);

    // Publish the imperative controller once mounted.
    React.useEffect(() => {
      ctrl = {
        addNode(node) { setNodes((ns) => ns.concat([node])); },
        deleteNode(id) {
          setNodes((ns) => ns.filter((n) => n.id !== id));
          setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
        },
        updateNode(id, patch) {
          setNodes((ns) => ns.map((n) => n.id === id
            ? Object.assign({}, n, { data: Object.assign({}, n.data, patch) }) : n));
        },
        setStatus(id, status, result) {
          setNodes((ns) => ns.map((n) => n.id === id
            ? Object.assign({}, n, { data: Object.assign({}, n.data, { status, result: result || '' }) }) : n));
        },
        clearStatus() {
          setNodes((ns) => ns.map((n) =>
            Object.assign({}, n, { data: Object.assign({}, n.data, { status: '', result: '' }) })));
        },
        autoArrange() {
          const es = edgesRef.current;
          const ns = nodesRef.current;
          const layer = computeLayers(ns, es);
          const byId = {};
          ns.forEach((n) => { byId[n.id] = n; });
          const byLayer = {};
          ns.forEach((n) => {
            const L = layer[n.id] || 0;
            (byLayer[L] = byLayer[L] || []).push(n);
          });
          // Use measured size when available, else estimate per node type so
          // tall request nodes don't overlap short ones.
          const H = { request: 380, mock: 220, condition: 160, while: 210, for: 210, wait: 140, start: 80, end: 80 };
          const W = { request: 400, mock: 250, condition: 220, while: 250, for: 250, wait: 200, start: 170, end: 170 };
          // Prefer the REAL measured size so handle rows match exactly (the
          // node is rendered at this height, with its handle at the centre);
          // fall back to a per-type estimate only when unmeasured.
          const estH = (n) => (n.height || (n.__rf && n.__rf.height) || H[n.type] || 150);
          const estW = (n) => (n.width || (n.__rf && n.__rf.width) || W[n.type] || 200);
          const HGAP = 140, VGAP = 64;
          const snap = (v) => Math.round(v / GRID) * GRID;
          const layers = Object.keys(byLayer).map(Number).sort((a, b) => a - b);

          // --- Crossing reduction: order nodes within each layer by the
          // barycentre of their neighbours in the adjacent layer, sweeping
          // forward then backward a few passes so connected nodes line up. ---
          const pred = {}, succ = {};
          es.forEach((e) => {
            (succ[e.source] = succ[e.source] || []).push(e.target);
            (pred[e.target] = pred[e.target] || []).push(e.source);
          });
          const orderIndex = {};
          const reindex = () => layers.forEach((L) =>
            byLayer[L].forEach((n, i) => { orderIndex[n.id] = i; }));
          reindex();
          const bary = (n, neigh) => {
            const arr = (neigh[n.id] || []).filter((id) => orderIndex[id] != null);
            if (!arr.length) return null;
            return arr.reduce((s, id) => s + orderIndex[id], 0) / arr.length;
          };
          for (let it = 0; it < 6; it++) {
            const forward = it % 2 === 0;
            const seq = forward ? layers.slice(1) : layers.slice(0, -1).reverse();
            const neigh = forward ? pred : succ;
            seq.forEach((L) => {
              const keyed = byLayer[L].map((n, i) => {
                const b = bary(n, neigh);
                return { n, k: b == null ? orderIndex[n.id] : b, i };
              });
              keyed.sort((a, b) => (a.k - b.k) || (a.i - b.i));
              byLayer[L] = keyed.map((o) => o.n);
              reindex();
            });
          }

          // --- Placement: columns left→right, each column vertically centred.
          // Each node's vertical CENTRE is snapped to the grid so its (centred)
          // connection handles land exactly on grid points. ---
          const colHeight = {};
          layers.forEach((L) => {
            colHeight[L] = byLayer[L].reduce((s, n) => s + estH(n) + VGAP, -VGAP);
          });
          const maxH = Math.max(0, ...layers.map((L) => colHeight[L]));
          const pos = {};        // node id -> top-left {x,y}
          const centerY = {};    // node id -> grid-snapped handle Y
          const colX = {};       // layer -> grid-snapped left x
          const colW = {};       // layer -> column width
          let x = 60;
          layers.forEach((L) => {
            const col = byLayer[L];
            const cx = snap(x);
            colX[L] = cx;
            let y = 40 + (maxH - colHeight[L]) / 2, w = 0;
            col.forEach((n) => {
              const nh = estH(n);
              const cy = snap(y + nh / 2);   // snap the handle row to the grid
              pos[n.id] = { x: cx, y: cy - nh / 2 };
              centerY[n.id] = cy;
              y += nh + VGAP;
              w = Math.max(w, estW(n));
            });
            colW[L] = w;
            x += w + HGAP;
          });

          // --- Grid A* edge routing: every path owns the grid cells it uses,
          // so no two paths (and no path/node) ever share a grid dot. Cells
          // covered by nodes are blocked; each routed edge reserves its cells
          // so later edges must find a different lane. ---
          const frac = (hid) => hid === 'true' ? 0.68 : hid === 'loop' ? 0.70
            : hid === 'false' ? 0.86 : hid === 'done' ? 0.88 : 0.5;
          const srcPt = (e) => {
            const n = byId[e.source];
            return { x: pos[n.id].x + estW(n), y: Math.round(pos[n.id].y + frac(e.sourceHandle) * estH(n)) };
          };
          const tgtPt = (e) => ({ x: pos[e.target].x, y: centerY[e.target] });
          const routes = {};

          // Build the routing lattice covering all nodes plus a margin.
          const cell = GRID, MARGIN = 8;
          let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
          ns.forEach((n) => {
            const p = pos[n.id]; if (!p) return;
            minX = Math.min(minX, p.x); minY = Math.min(minY, p.y);
            maxX = Math.max(maxX, p.x + estW(n)); maxY = Math.max(maxY, p.y + estH(n));
          });
          if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 0; maxY = 0; }
          const ox = Math.floor(minX / cell) - MARGIN;
          const oy = Math.floor(minY / cell) - MARGIN;
          const cols = Math.ceil(maxX / cell) - ox + MARGIN;
          const rows = Math.ceil(maxY / cell) - oy + MARGIN;
          const cidx = (c, r) => r * cols + c;
          const blocked = new Uint8Array(cols * rows);
          const reserved = new Uint8Array(cols * rows);
          // Block node cells plus a 1-cell clearance ring so paths never hug a
          // node's border.
          const CLR = 1;
          ns.forEach((n) => {
            const p = pos[n.id]; if (!p) return;
            const c0 = Math.floor(p.x / cell) - ox - CLR, c1 = Math.ceil((p.x + estW(n)) / cell) - ox + CLR;
            const r0 = Math.floor(p.y / cell) - oy - CLR, r1 = Math.ceil((p.y + estH(n)) / cell) - oy + CLR;
            for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++)
              if (c >= 0 && c < cols && r >= 0 && r < rows) blocked[cidx(c, r)] = 1;
          });
          const toCell = (x, y) => ({ c: Math.round(x / cell) - ox, r: Math.round(y / cell) - oy });
          const toFlowXY = (c, r) => ({ x: (c + ox) * cell, y: (r + oy) * cell });

          // Route shorter edges first so simple adjacent links claim direct
          // lanes and longer edges detour around them.
          const ordered = es.filter((e) => byId[e.source] && byId[e.target]).slice().sort((a, b) => {
            const da = Math.abs(srcPt(a).x - tgtPt(a).x) + Math.abs(srcPt(a).y - tgtPt(a).y);
            const db = Math.abs(srcPt(b).x - tgtPt(b).x) + Math.abs(srcPt(b).y - tgtPt(b).y);
            return da - db;
          });
          es.forEach((e) => { if (!byId[e.source] || !byId[e.target]) routes[e.id] = []; });

          ordered.forEach((e) => {
            const sp = srcPt(e), tp = tgtPt(e);
            const s = toCell(sp.x + cell * (CLR + 1), sp.y);   // clear of the source ring
            const g = toCell(tp.x - cell * (CLR + 1), tp.y);   // clear of the target ring
            const path = astarGrid(cols, rows, blocked, reserved, s, g);
            if (!path) {
              // Fallback: a single mid-gap channel (may overlap when congested).
              const chX = snap((sp.x + tp.x) / 2);
              routes[e.id] = [{ x: chX, y: sp.y }, { x: chX, y: tp.y }];
              return;
            }
            // Reserve every interior cell so no other path can reuse it. The
            // first/last cells sit next to a node handle and may be shared by
            // sibling edges converging on the same handle.
            for (let i = 1; i < path.length - 1; i++) reserved[cidx(path[i].c, path[i].r)] = 1;
            // Keep only corner cells (where the path changes direction).
            const corners = [];
            for (let i = 0; i < path.length; i++) {
              if (i === 0 || i === path.length - 1) { corners.push(path[i]); continue; }
              const a = path[i - 1], b = path[i], c = path[i + 1];
              if ((a.c !== c.c) && (a.r !== c.r)) corners.push(b); // a real turn
            }
            // Store only the INTERIOR corners. orthoPath draws the source-exit
            // and target-entry stubs from the REAL handle coordinates, so the
            // path never travels to an estimated handle row and then doubles
            // back (which produced the "down then back up" jog).
            routes[e.id] = corners.slice(1, corners.length - 1).map((p) => toFlowXY(p.c, p.r));
          });

          setNodes((cur) => cur.map((n) =>
            Object.assign({}, n, { position: pos[n.id] || n.position })));
          setEdges((cur) => cur.map((e) => Object.assign({}, e, {
            type: 'editable',
            data: Object.assign({}, e.data, { points: routes[e.id] || [] }),
          })));
          setTimeout(() => {
            try { rfInstance && rfInstance.fitView({ padding: 0.2, duration: 300 }); } catch (e) {}
          }, 60);
        },
        getGraph() { return serialize(nodesRef.current, edgesRef.current); },
        undo() {
          if (!past.current.length) return;
          if (histTimer.current) { clearTimeout(histTimer.current); histTimer.current = null; }
          const prev = past.current.pop();
          future.current.push({ nodes: nodesRef.current, edges: edgesRef.current });
          applying.current = true;
          lastStable.current = prev;
          setNodes(prev.nodes);
          setEdges(prev.edges);
        },
        redo() {
          if (!future.current.length) return;
          if (histTimer.current) { clearTimeout(histTimer.current); histTimer.current = null; }
          const next = future.current.pop();
          past.current.push({ nodes: nodesRef.current, edges: edgesRef.current });
          applying.current = true;
          lastStable.current = next;
          setNodes(next.nodes);
          setEdges(next.edges);
        },
      };

      // Keyboard shortcuts: Cmd/Ctrl+Z = undo, Cmd+Shift+Z / Ctrl+Y = redo.
      const onKey = (e) => {
        if (!(e.metaKey || e.ctrlKey)) return;
        const t = e.target, tag = t && t.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
        if (rootRef.current && rootRef.current.offsetParent === null) return;   // flow tab hidden
        const k = (e.key || '').toLowerCase();
        if (k === 'z' && !e.shiftKey) { e.preventDefault(); ctrl && ctrl.undo(); }
        else if ((k === 'z' && e.shiftKey) || k === 'y') { e.preventDefault(); ctrl && ctrl.redo(); }
      };
      window.addEventListener('keydown', onKey);
      return () => { window.removeEventListener('keydown', onKey); ctrl = null; };
    }, []);

    // Keep refs so getGraph reads the latest state.
    const nodesRef = React.useRef(nodes);
    const edgesRef = React.useRef(edges);
    nodesRef.current = nodes;
    edgesRef.current = edges;

    // Record history (debounced) so drags/edits collapse into one undo step.
    React.useEffect(() => {
      if (firstRun.current) { firstRun.current = false; lastStable.current = { nodes, edges }; return; }
      if (applying.current) { applying.current = false; lastStable.current = { nodes, edges }; return; }
      if (histTimer.current) clearTimeout(histTimer.current);
      histTimer.current = setTimeout(() => {
        past.current.push(lastStable.current);
        if (past.current.length > 100) past.current.shift();
        future.current = [];
        lastStable.current = { nodes, edges };
      }, 350);
    }, [nodes, edges]);

    // Notify the app whenever the graph changes so it can mark unsaved.
    React.useEffect(() => {
      if (onChangeCb) onChangeCb(serialize(nodes, edges));
    }, [nodes, edges]);

    return h('div', { ref: rootRef, style: { width: '100%', height: '100%' } },
      h(RFComp, {
        nodes, edges, onNodesChange, onEdgesChange, onConnect,
        nodeTypes, edgeTypes, fitView: true, proOptions: { hideAttribution: true },
        snapToGrid: true, snapGrid: [GRID, GRID], zoomOnDoubleClick: false,
        defaultEdgeOptions: {
          type: 'editable',
          markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#8a8a8a' },
          style: { stroke: '#8a8a8a', strokeWidth: 2 },
        },
        onInit: (inst) => { rfInstance = inst; },
      },
        h(Background, { variant: 'dots', color: '#3a3a3a', gap: GRID, size: 1.5 }),
        h(Controls, null),
        h(MiniMap, { pannable: true, zoomable: true,
          style: { background: '#252526' }, maskColor: 'rgba(0,0,0,0.6)' })
      )
    );
  }

  function serialize(nodes, edges) {
    return {
      nodes: (nodes || []).map((n) => ({
        id: n.id, type: n.type || 'request', position: n.position,
        data: {
          method: (n.data && n.data.method) || 'GET',
          url: (n.data && n.data.url) || '',
          label: (n.data && n.data.label) || '',
          headers: (n.data && n.data.headers) || '',
          body: (n.data && n.data.body) || '',
          ms: (n.data && n.data.ms != null) ? n.data.ms : undefined,
          expr: (n.data && n.data.expr) || '',
          max: (n.data && n.data.max != null) ? n.data.max : undefined,
          count: (n.data && n.data.count != null) ? n.data.count : undefined,
        },
      })),
      edges: (edges || []).map((e) => ({
        id: e.id, source: e.source, target: e.target,
        sourceHandle: e.sourceHandle || null,
        points: (e.data && e.data.points) || [],
      })),
    };
  }

  let root = null;

  // ── Public imperative API used by app.js ──────────────────────────────
  window.FlowEditor = {
    mount(container, flow, onChange) {
      onChangeCb = onChange || null;
      const initialNodes = ((flow && flow.nodes) || []).map((n) => ({
        id: n.id, type: n.type || 'request', position: n.position || { x: 60, y: 60 },
        data: Object.assign({ method: 'GET', url: '', label: '', headers: '', body: '' }, n.data || {}),
      }));
      const initialEdges = ((flow && flow.edges) || []).map((e) =>
        Object.assign({}, e, {
          type: 'editable', animated: true,
          data: { points: (e.data && e.data.points) || e.points || [] },
        }));
      if (root) { try { root.unmount(); } catch (e) {} root = null; }
      root = ReactDOM.createRoot(container);
      root.render(h(Editor, { initialNodes, initialEdges }));
    },
    addRequestNode() {
      if (!ctrl) return;
      const id = 'n' + Date.now();
      ctrl.addNode({
        id, type: 'request',
        position: { x: 80 + Math.random() * 240, y: 60 + Math.random() * 200 },
        data: { method: 'GET', url: '', label: 'Request', status: '', result: '' },
      });
    },
    addMockNode() {
      if (!ctrl) return;
      const id = 'm' + Date.now();
      ctrl.addNode({
        id, type: 'mock',
        position: { x: 80 + Math.random() * 240, y: 60 + Math.random() * 200 },
        data: { label: 'Mock', body: '{\n  "id": 1\n}', status: '', result: '' },
      });
    },
    addFunctionNode(kind) {
      if (!ctrl) return;
      const defaults = {
        start: { prefix: 's', data: {} },
        end: { prefix: 'e', data: {} },
        wait: { prefix: 'w', data: { ms: 1000 } },
        condition: { prefix: 'c', data: { expr: '' } },
        while: { prefix: 'l', data: { expr: '', max: 10 } },
        for: { prefix: 'f', data: { label: 'for', count: 3 } },
      };
      const cfg = defaults[kind];
      if (!cfg) return;
      const id = cfg.prefix + Date.now();
      ctrl.addNode({
        id, type: kind,
        position: { x: 80 + Math.random() * 240, y: 60 + Math.random() * 200 },
        data: Object.assign({ status: '', result: '' }, cfg.data),
      });
    },
    getGraph() { return ctrl ? ctrl.getGraph() : { nodes: [], edges: [] }; },
    setStatus(id, status, result) { if (ctrl) ctrl.setStatus(id, status, result); },
    clearStatus() { if (ctrl) ctrl.clearStatus(); },
    autoArrange() { if (ctrl) ctrl.autoArrange(); },
    undo() { if (ctrl) ctrl.undo(); },
    redo() { if (ctrl) ctrl.redo(); },
    unmount() {
      if (root) { try { root.unmount(); } catch (e) {} root = null; }
      ctrl = null; onChangeCb = null; rfInstance = null;
    },
  };
})();
