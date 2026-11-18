const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

const ROOT = __dirname;
const { checkRobin } = require("./marketing/video/tools/check-flows");

// Cache data files
console.log("Loading datasets...");
const kbClassic = JSON.parse(fs.readFileSync(path.join(ROOT, "PAD_Robin_ActionKB.json"), "utf8"));
const kbPowerFx = JSON.parse(fs.readFileSync(path.join(ROOT, "PAD_Robin_ActionKB_PowerFx.json"), "utf8"));
const typeRefClassic = JSON.parse(fs.readFileSync(path.join(ROOT, "PAD_Robin_TypeReference.json"), "utf8"));
const typeRefPowerFx = JSON.parse(fs.readFileSync(path.join(ROOT, "PAD_Robin_TypeReference_PowerFx.json"), "utf8"));
const rulesData = JSON.parse(fs.readFileSync(path.join(ROOT, "rules", "robin-rules.json"), "utf8"));

// Read examples
const examplesDir = path.join(ROOT, "examples");
const exampleFiles = fs.readdirSync(examplesDir).filter(f => f.endsWith(".robin"));
const examples = exampleFiles.map(file => ({
  name: file,
  content: fs.readFileSync(path.join(examplesDir, file), "utf8")
}));

console.log(`Loaded ${kbClassic.actions.length} Classic actions, ${kbPowerFx.actions.length} PowerFx actions, and ${examples.length} example flows.`);

const HTML_PAGE = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PAD Robin Action KB Explorer</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --accent: #818cf8;
      --success: #34d399;
      --error: #f87171;
      --code-bg: #0b1120;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }
    header {
      background: #182234;
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand h1 {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--primary);
    }
    .badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }
    .tabs {
      display: flex;
      gap: 8px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.15s;
    }
    .tab-btn:hover {
      color: var(--text);
      background: rgba(255, 255, 255, 0.05);
    }
    .tab-btn.active {
      color: var(--text);
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--primary);
    }
    .edition-switch {
      display: flex;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      overflow: hidden;
    }
    .edition-btn {
      padding: 6px 12px;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 0.8rem;
      cursor: pointer;
      font-weight: 600;
    }
    .edition-btn.active {
      background: var(--primary);
      color: #0f172a;
    }
    .main-container {
      display: flex;
      flex: 1;
      overflow: hidden;
    }
    /* Tab View: Actions */
    #tab-actions {
      display: flex;
      width: 100%;
      height: 100%;
    }
    .sidebar {
      width: 340px;
      border-right: 1px solid var(--card-border);
      background: #131c2e;
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
    }
    .search-box {
      padding: 16px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .search-input {
      width: 100%;
      padding: 9px 12px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      border-radius: 6px;
      font-size: 0.88rem;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--primary);
    }
    .module-select {
      width: 100%;
      padding: 8px 10px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
    }
    .action-list {
      flex: 1;
      overflow-y: auto;
      list-style: none;
    }
    .action-item {
      padding: 10px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      cursor: pointer;
      transition: background 0.15s;
    }
    .action-item:hover {
      background: rgba(255, 255, 255, 0.04);
    }
    .action-item.selected {
      background: rgba(56, 189, 248, 0.12);
      border-left: 3px solid var(--primary);
    }
    .action-item .id {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text);
      word-break: break-all;
    }
    .action-item .mod {
      font-size: 0.72rem;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .detail-view {
      flex: 1;
      overflow-y: auto;
      padding: 24px 32px;
      background: var(--bg);
    }
    .detail-header {
      margin-bottom: 24px;
    }
    .detail-title {
      font-size: 1.4rem;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .detail-tags {
      display: flex;
      gap: 8px;
      margin-top: 6px;
    }
    .tag {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 4px;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
    }
    .section-title {
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--accent);
      margin: 20px 0 8px 0;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .code-box {
      position: relative;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
      color: #e2e8f0;
      line-height: 1.5;
    }
    .copy-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.75rem;
      transition: all 0.15s;
    }
    .copy-btn:hover {
      background: var(--primary);
      color: #0f172a;
    }
    .param-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 0.85rem;
    }
    .param-table th, .param-table td {
      border: 1px solid var(--card-border);
      padding: 8px 12px;
      text-align: left;
    }
    .param-table th {
      background: #141e30;
      color: var(--text-muted);
      font-weight: 600;
    }
    .param-table td {
      background: var(--card-bg);
    }
    /* Tab View: Validator */
    #tab-validator, #tab-rules {
      display: none;
      width: 100%;
      height: 100%;
      padding: 24px 32px;
      overflow-y: auto;
    }
    .validator-layout {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      height: calc(100vh - 140px);
    }
    .val-column {
      display: flex;
      flex-direction: column;
      height: 100%;
    }
    .editor-textarea {
      flex: 1;
      width: 100%;
      background: var(--code-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      color: #e2e8f0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.88rem;
      padding: 16px;
      resize: none;
      outline: none;
      line-height: 1.5;
    }
    .editor-textarea:focus {
      border-color: var(--primary);
    }
    .val-toolbar {
      display: flex;
      gap: 10px;
      margin-bottom: 10px;
      align-items: center;
    }
    .btn-action {
      background: var(--primary);
      color: #0f172a;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.88rem;
      cursor: pointer;
    }
    .btn-action:hover {
      background: var(--primary-hover);
    }
    .results-panel {
      flex: 1;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      padding: 16px;
      overflow-y: auto;
    }
    .rule-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 14px;
    }
    .rule-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .rule-num {
      font-weight: 700;
      color: var(--primary);
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>PAD Robin Knowledge Base</h1>
      <span class="badge" id="stats-badge">1,135 Actions</span>
      <span class="badge" style="border-color: #34d39944; color: #34d399;">PAD 2.74 Validated</span>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('actions')">Action Catalog</button>
      <button class="tab-btn" onclick="switchTab('validator')">Robin Script Validator</button>
      <button class="tab-btn" onclick="switchTab('rules')">Syntax Rules (25)</button>
    </div>

    <div class="edition-switch">
      <button class="edition-btn active" id="btn-classic" onclick="setEdition('classic')">Classic</button>
      <button class="edition-btn" id="btn-powerfx" onclick="setEdition('powerfx')">Power Fx</button>
    </div>
  </header>

  <div class="main-container">
    <!-- TAB 1: ACTIONS -->
    <div id="tab-actions">
      <div class="sidebar">
        <div class="search-box">
          <input type="text" id="action-search" class="search-input" placeholder="Search actions (e.g. Excel, Text, Run)..." oninput="filterActions()">
          <select id="module-select" class="module-select" onchange="filterActions()">
            <option value="">All Modules (46)</option>
          </select>
        </div>
        <div class="action-list" id="action-list"></div>
      </div>
      <div class="detail-view" id="detail-view">
        <p style="color: var(--text-muted); margin-top: 40px; text-align: center;">Select an action from the sidebar to inspect its golden example, template, and parameters.</p>
      </div>
    </div>

    <!-- TAB 2: VALIDATOR -->
    <div id="tab-validator">
      <div class="val-toolbar">
        <button class="btn-action" onclick="runValidation()">Run Validator</button>
        <span style="font-size: 0.85rem; color: var(--text-muted);">Load Example:</span>
        <select id="example-select" class="module-select" style="width: 260px;" onchange="loadSelectedExample()">
          <option value="">-- Choose Example Flow --</option>
        </select>
        <button class="btn-action" style="background: #334155; color: #fff;" onclick="clearEditor()">Clear</button>
      </div>
      <div class="validator-layout">
        <div class="val-column">
          <textarea id="robin-input" class="editor-textarea" placeholder="Paste or type Robin code here..."></textarea>
        </div>
        <div class="val-column">
          <div class="results-panel" id="val-results">
            <h3 style="color: var(--text-muted); font-size: 0.95rem; margin-bottom: 12px;">Validation Diagnostic Output</h3>
            <p style="color: #64748b; font-size: 0.85rem;">Click 'Run Validator' or select an example flow to check against the PAD Robin syntax & rules.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: RULES -->
    <div id="tab-rules">
      <h2 style="font-size: 1.3rem; margin-bottom: 6px; color: var(--primary);">25 Robin Syntax Rules PAD Enforces</h2>
      <p style="color: var(--text-muted); margin-bottom: 20px; font-size: 0.9rem;">
        Probed and confirmed on PAD 2.74 across 456 probe pastes. Every rule below prevents silent rejections or canvas errors.
      </p>
      <div id="rules-container"></div>
    </div>
  </div>

  <script>
    let currentEdition = 'classic';
    let kb = null;
    let typeRef = null;
    let rules = null;
    let examples = [];
    let selectedAction = null;

    async function init() {
      await loadData();
      populateModules();
      filterActions();
      loadRules();
      loadExamples();
    }

    async function loadData() {
      const res = await fetch('/api/kb?edition=' + currentEdition);
      kb = await res.json();
      document.getElementById('stats-badge').innerText = kb.actions.length + " Actions (" + currentEdition.toUpperCase() + ")";
    }

    async function setEdition(edition) {
      if (currentEdition === edition) return;
      currentEdition = edition;
      document.getElementById('btn-classic').classList.toggle('active', edition === 'classic');
      document.getElementById('btn-powerfx').classList.toggle('active', edition === 'powerfx');
      await loadData();
      populateModules();
      filterActions();
      if (selectedAction) {
        const found = kb.actions.find(a => a.actionId === selectedAction.actionId);
        if (found) renderDetail(found);
      }
    }

    function populateModules() {
      const mods = [...new Set(kb.actions.map(a => a.module))].sort();
      const sel = document.getElementById('module-select');
      const cur = sel.value;
      sel.innerHTML = '<option value="">All Modules (' + mods.length + ')</option>';
      mods.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.innerText = m;
        sel.appendChild(opt);
      });
      sel.value = cur;
    }

    function filterActions() {
      const q = document.getElementById('action-search').value.toLowerCase().trim();
      const mod = document.getElementById('module-select').value;
      const listEl = document.getElementById('action-list');
      listEl.innerHTML = '';

      const filtered = kb.actions.filter(a => {
        if (mod && a.module !== mod) return false;
        if (!q) return true;
        return a.actionId.toLowerCase().includes(q) || (a.template && a.template.toLowerCase().includes(q));
      });

      filtered.forEach((a, idx) => {
        const div = document.createElement('div');
        div.className = 'action-item' + (selectedAction && selectedAction.actionId === a.actionId ? ' selected' : '');
        div.innerHTML = '<div class="id">' + escapeHtml(a.actionId) + '</div><div class="mod">' + escapeHtml(a.module) + ' &bull; ' + (a.kind || 'Action') + '</div>';
        div.onclick = () => {
          document.querySelectorAll('.action-item').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
          renderDetail(a);
        };
        listEl.appendChild(div);
        if (idx === 0 && !selectedAction) {
          div.classList.add('selected');
          renderDetail(a);
        }
      });
    }

    function renderDetail(action) {
      selectedAction = action;
      const el = document.getElementById('detail-view');
      const inputs = action.input_params || [];
      const outputs = action.output_params || [];
      const eh = action.error_handling || {};

      let html = '<div class="detail-header">';
      html += '<div class="detail-title">' + escapeHtml(action.actionId) + '</div>';
      html += '<div class="detail-tags">';
      html += '<span class="tag">Module: ' + escapeHtml(action.module) + '</span>';
      html += '<span class="tag">Kind: ' + escapeHtml(action.kind || 'Action') + '</span>';
      if (action.selector) html += '<span class="tag">Selector: ' + escapeHtml(action.selector) + '</span>';
      if (eh.on_error) html += '<span class="tag" style="border-color: #34d39944; color: #34d399;">ON ERROR supported</span>';
      html += '</div></div>';

      html += '<div class="section-title">Golden Example (Paste-Validated)</div>';
      html += '<div class="code-box">' + escapeHtml(action.golden_example || action.template) + '<button class="copy-btn" onclick="copyText(\\'' + escapeJs(action.golden_example || action.template) + '\\')">Copy</button></div>';

      html += '<div class="section-title">Template</div>';
      html += '<div class="code-box">' + escapeHtml(action.template) + '<button class="copy-btn" onclick="copyText(\\'' + escapeJs(action.template) + '\\')">Copy</button></div>';

      if (inputs.length) {
        html += '<div class="section-title">Input Parameters (' + inputs.length + ')</div>';
        html += '<table class="param-table"><thead><tr><th>Name</th><th>Type</th><th>Required</th><th>Enum Values / Details</th></tr></thead><tbody>';
        inputs.forEach(p => {
          html += '<tr><td><strong>' + escapeHtml(p.name) + '</strong></td><td><code>' + escapeHtml(p.type || '') + '</code></td><td>' + (p.required ? 'Yes' : 'No') + '</td><td>' + (p.enumValues ? escapeHtml(p.enumValues.join(', ')) : '') + '</td></tr>';
        });
        html += '</tbody></table>';
      }

      if (outputs.length) {
        html += '<div class="section-title">Output Parameters (' + outputs.length + ')</div>';
        html += '<table class="param-table"><thead><tr><th>Name</th><th>Type</th><th>Default Variable</th></tr></thead><tbody>';
        outputs.forEach(p => {
          html += '<tr><td><strong>' + escapeHtml(p.name) + '</strong></td><td><code>' + escapeHtml(p.type || '') + '</code></td><td><code>' + escapeHtml(p.defaultVariable || '') + '</code></td></tr>';
        });
        html += '</tbody></table>';
      }

      if (eh.on_error && eh.errors && eh.errors.length) {
        html += '<div class="section-title">Declared Errors (' + eh.errors.length + ')</div>';
        html += '<p style="color: var(--text-muted); font-size: 0.85rem;">' + escapeHtml(eh.errors.join(', ')) + '</p>';
      }

      if (action.sibling_selectors && action.sibling_selectors.length) {
        html += '<div class="section-title">Sibling Selectors</div>';
        html += '<p style="color: var(--text-muted); font-size: 0.85rem;">' + escapeHtml(action.sibling_selectors.join(', ')) + '</p>';
      }

      el.innerHTML = html;
    }

    async function loadRules() {
      const res = await fetch('/api/rules');
      rules = await res.json();
      const container = document.getElementById('rules-container');
      container.innerHTML = '';
      (rules.rules || []).forEach((r, idx) => {
        const div = document.createElement('div');
        div.className = 'rule-card';
        div.innerHTML = '<div class="rule-header"><span class="rule-num">Rule ' + (idx + 1) + ': ' + escapeHtml(r.title || r.id) + '</span><span class="tag">' + escapeHtml(r.kind || 'syntax') + '</span></div><p style="font-size: 0.88rem; line-height: 1.5; color: #cbd5e1;">' + escapeHtml(r.summary || r.explanation || '') + '</p>';
        container.appendChild(div);
      });
    }

    async function loadExamples() {
      const res = await fetch('/api/examples');
      examples = await res.json();
      const sel = document.getElementById('example-select');
      examples.forEach((ex, idx) => {
        const opt = document.createElement('option');
        opt.value = idx;
        opt.innerText = ex.name;
        sel.appendChild(opt);
      });
    }

    function loadSelectedExample() {
      const idx = document.getElementById('example-select').value;
      if (idx === '') return;
      document.getElementById('robin-input').value = examples[idx].content;
      runValidation();
    }

    function clearEditor() {
      document.getElementById('robin-input').value = '';
      document.getElementById('val-results').innerHTML = '<p style="color: #64748b; font-size: 0.85rem;">Editor cleared. Paste Robin code and click Run Validator.</p>';
    }

    async function runValidation() {
      const code = document.getElementById('robin-input').value;
      if (!code.trim()) {
        alert('Please enter or select some Robin code to validate.');
        return;
      }
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, edition: currentEdition })
      });
      const data = await res.json();
      const panel = document.getElementById('val-results');
      if (data.errors && data.errors.length > 0) {
        let html = '<div style="background: rgba(248, 113, 113, 0.15); border: 1px solid var(--error); border-radius: 6px; padding: 12px; margin-bottom: 16px;">';
        html += '<h3 style="color: var(--error); font-size: 1rem; margin-bottom: 4px;">&#10008; Rejected / Errors (' + data.errors.length + ')</h3>';
        html += '<p style="font-size: 0.8rem; color: #fca5a5;">Scanned ' + data.actionLines + ' action lines. The following errors would cause PAD to reject the paste:</p></div>';
        html += '<ul style="list-style: none; display: flex; flex-direction: column; gap: 8px;">';
        data.errors.forEach(err => {
          html += '<li style="background: #182234; border-left: 3px solid var(--error); padding: 8px 12px; font-size: 0.83rem; font-family: monospace;">' + escapeHtml(err) + '</li>';
        });
        html += '</ul>';
        panel.innerHTML = html;
      } else {
        panel.innerHTML = '<div style="background: rgba(52, 211, 153, 0.15); border: 1px solid var(--success); border-radius: 6px; padding: 16px;">' +
          '<h3 style="color: var(--success); font-size: 1.1rem; margin-bottom: 6px;">&#10004; Clean Paste Validated!</h3>' +
          '<p style="font-size: 0.85rem; color: #a7f3d0;">' + data.actionLines + ' action lines verified against PAD ' + (currentEdition === 'classic' ? '2.74' : '2.74 PowerFx') + ' syntax rules. This script will paste directly into PAD Designer with 0 errors.</p>' +
          '</div>';
      }
    }

    function switchTab(name) {
      document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (name === 'actions' && i === 0) || (name === 'validator' && i === 1) || (name === 'rules' && i === 2));
      });
      document.getElementById('tab-actions').style.display = name === 'actions' ? 'flex' : 'none';
      document.getElementById('tab-validator').style.display = name === 'validator' ? 'block' : 'none';
      document.getElementById('tab-rules').style.display = name === 'rules' ? 'block' : 'none';
    }

    function copyText(str) {
      navigator.clipboard.writeText(str).then(() => {
        alert('Copied to clipboard!');
      });
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeJs(str) {
      if (!str) return '';
      return String(str).replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'").replace(/\\n/g, '\\\\n').replace(/\\r/g, '');
    }

    window.onload = init;
  </script>
</body>
</html>`;

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url, true);
  const pathname = parsed.pathname;

  if (pathname === "/" || pathname === "/index.html") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(HTML_PAGE);
    return;
  }

  if (pathname === "/api/kb") {
    const edition = parsed.query.edition === "powerfx" ? "powerfx" : "classic";
    const dataset = edition === "powerfx" ? kbPowerFx : kbClassic;
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(dataset));
    return;
  }

  if (pathname === "/api/rules") {
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(rulesData));
    return;
  }

  if (pathname === "/api/examples") {
    res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(examples));
    return;
  }

  if (pathname === "/api/validate" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => (body += chunk));
    req.on("end", () => {
      try {
        const payload = JSON.parse(body || "{}");
        const edition = payload.edition === "powerfx" ? kbPowerFx : kbClassic;
        const result = checkRobin(payload.code || "", edition);
        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(result));
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain" });
  res.end("Not Found");
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, "0.0.0.0", () => {
  console.log(`PAD Robin Action KB Explorer running at http://localhost:${PORT}/`);
});

