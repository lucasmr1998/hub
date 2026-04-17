#!/usr/bin/env python3
"""
Hub — AuroraISP
Gestor unificado de documentos e backlog.

Uso: python scripts/gerar_hub.py
Saida: exports/hub.html
"""

import json
import re
from pathlib import Path
from datetime import datetime

WORKSPACE   = Path(__file__).parent.parent
OUTPUT_PATH = WORKSPACE / "robo" / "exports" / "hub.html"

INCLUDE_ROOTS = [
    (WORKSPACE / "robo" / "docs",                "Documentacao"),
]
ROOT_FILES   = [WORKSPACE / "CLAUDE.md"]
IGNORE_FILES = {"TEMPLATE.MD"}
TAREFAS_PATH = WORKSPACE / "robo" / "docs" / "context" / "tarefas"


# ── Docs ──────────────────────────────────────────────────────────────────────

def read_md(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def doc_name(stem):
    return " ".join(w.capitalize() for w in stem.replace("-", " ").replace("_", " ").split())


def build_doc_node(path):
    if path.is_file():
        if path.suffix.lower() != ".md" or path.name.upper() in IGNORE_FILES:
            return None
        return {"t": "f", "n": doc_name(path.stem), "fn": path.name, "c": read_md(path)}
    if path.is_dir():
        dirs  = sorted(p for p in path.iterdir() if p.is_dir())
        files = sorted(p for p in path.iterdir() if p.is_file())
        ch = [x for x in (build_doc_node(i) for i in dirs + files) if x]
        return {"t": "d", "n": path.name, "ch": ch} if ch else None
    return None


def build_doc_tree():
    nodes = []
    for f in ROOT_FILES:
        if f.exists():
            n = build_doc_node(f)
            if n: nodes.append(n)
    for path, label in INCLUDE_ROOTS:
        if path.exists():
            n = build_doc_node(path)
            if n:
                n["n"] = label
                nodes.append(n)
    return nodes


# ── Tasks ─────────────────────────────────────────────────────────────────────

def parse_fm(content):
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    meta = {}
    for line in content[3:end].strip().split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, content[end+3:].strip()


def parse_checklist(body):
    items = []
    for line in body.split("\n"):
        m = re.match(r"\s*-\s*\[(x| )\]\s*(.*)", line, re.IGNORECASE)
        if m:
            items.append({"d": m.group(1).lower() == "x", "t": m.group(2).strip()})
    return items


def get_section(body, name):
    m = re.search(rf"## {re.escape(name)}\n\n?(.*?)(?=\n## |\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_task(filepath, folder_status):
    content = filepath.read_text(encoding="utf-8")
    meta, body = parse_fm(content)
    items = parse_checklist(body)
    done  = sum(1 for i in items if i["d"])
    status = "finalizada" if folder_status == "finalizada" else meta.get("status", folder_status)
    return {
        "name":    meta.get("name", filepath.stem),
        "desc":    meta.get("description", ""),
        "status":  status,
        "created": meta.get("criado_em", ""),
        "obj":     get_section(body, "Objetivo"),
        "items":   items,
        "total":   len(items),
        "done":    done,
    }


def collect_tasks():
    tasks = []
    for folder, default in [("backlog","pendente"), ("em_andamento","em_andamento"), ("finalizadas","finalizada")]:
        p = TAREFAS_PATH / folder
        if p.exists():
            for md in sorted(p.glob("*.md")):
                if md.name.upper() != "TEMPLATE.MD":
                    tasks.append(parse_task(md, default))
    return tasks


# ── HTML Template (raw string — use __PLACEHOLDERS__ for dynamic data) ────────

HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hub — AuroraISP</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {
      --sidebar-w: 280px;
      --nav-h: 54px;
      --accent: #818cf8;
      --sidebar-bg: #1e293b;
      --sidebar-hover: #2d3f55;
      --sidebar-active: #3b4f6b;
      --sidebar-text: #cbd5e1;
    }
    *, *::before, *::after { box-sizing: border-box; }
    body { overflow: hidden; background: #f1f5f9; }

    /* ── Navbar ── */
    #topnav {
      height: var(--nav-h);
      background: #0f172a;
      display: flex;
      align-items: center;
      padding: 0 20px;
      gap: 16px;
      border-bottom: 1px solid #1e293b;
      position: fixed; top: 0; left: 0; right: 0; z-index: 1000;
    }
    .brand { font-weight: 800; font-size: .95rem; color: #fff; white-space: nowrap; letter-spacing: -.02em; }
    .brand span { color: var(--accent); }
    .nav-pills .nav-link { font-size: .78rem; padding: 5px 14px; color: #94a3b8; border-radius: 99px; }
    .nav-pills .nav-link.active { background: var(--accent); color: #fff; }
    .nav-pills .nav-link:not(.active):hover { background: #1e293b; color: #e2e8f0; }
    #search-input {
      background: #1e293b; border: 1px solid #334155; color: #e2e8f0;
      border-radius: 8px; font-size: .78rem; padding: 5px 12px; width: 220px;
    }
    #search-input::placeholder { color: #64748b; }
    #search-input:focus { outline: none; border-color: var(--accent); box-shadow: none; }
    .nav-timestamp { font-size: .7rem; color: #475569; white-space: nowrap; margin-left: auto; }

    /* ── Layout ── */
    #app { display: flex; height: calc(100vh - var(--nav-h)); margin-top: var(--nav-h); }

    /* ── Sidebar with accordions ── */
    #sidebar {
      width: var(--sidebar-w); background: var(--sidebar-bg);
      overflow-y: auto; flex-shrink: 0;
      border-right: 1px solid #0f172a;
      padding: 6px 0 20px;
    }
    #sidebar::-webkit-scrollbar { width: 4px; }
    #sidebar::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

    .sb-section {
      font-size: .62rem; font-weight: 700; letter-spacing: .08em;
      color: #475569; text-transform: uppercase;
      padding: 14px 14px 6px; margin-top: 2px;
    }

    .sb-accordion {
      margin: 0 6px; border-radius: 6px; overflow: hidden; margin-bottom: 2px;
    }
    .sb-acc-header {
      display: flex; align-items: center; gap: 7px;
      padding: 7px 12px; cursor: pointer;
      font-size: .78rem; font-weight: 600; color: #e2e8f0;
      background: #263347; border-radius: 6px;
      user-select: none; transition: background .1s;
    }
    .sb-acc-header:hover { background: var(--sidebar-hover); }
    .sb-acc-header .sb-arrow { font-size: .55rem; color: #64748b; transition: transform .2s; margin-left: auto; }
    .sb-acc-header .sb-icon { color: #f59e0b; font-size: .75rem; }
    .sb-acc-header .sb-count { font-size: .62rem; color: #64748b; margin-left: 4px; }
    .sb-accordion.open .sb-acc-header { background: #334155; border-radius: 6px 6px 0 0; }
    .sb-accordion.open .sb-acc-header .sb-arrow { transform: rotate(90deg); }
    .sb-acc-body { display: none; background: #263347; border-radius: 0 0 6px 6px; padding: 2px 0 4px; }
    .sb-accordion.open .sb-acc-body { display: block; }

    .si {
      display: flex; align-items: center; gap: 7px;
      padding: 5px 14px 5px 24px; cursor: pointer;
      font-size: .75rem; color: var(--sidebar-text);
      border-radius: 4px; margin: 1px 6px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      user-select: none; transition: background .1s;
    }
    .si:hover { background: var(--sidebar-hover); }
    .si.active { background: var(--sidebar-active); color: #fff; }
    .si .si-icon { flex-shrink: 0; font-size: .7rem; color: #64748b; }
    .si.active .si-icon { color: var(--accent) !important; }

    /* non-accordion items (root files) */
    .si-root {
      padding-left: 14px;
      margin: 1px 6px;
    }

    /* ── Views ── */
    #view-docs    { flex: 1; display: flex; overflow: hidden; }
    #view-backlog { flex: 1; overflow-y: auto; display: none; }

    /* ── Doc panel ── */
    #doc-panel { flex: 1; overflow-y: auto; background: #f8fafc; }
    #breadcrumb {
      position: sticky; top: 0; z-index: 10;
      padding: 9px 32px; font-size: .75rem; color: #64748b;
      background: #fff; border-bottom: 1px solid #e2e8f0;
    }
    #breadcrumb i { margin-right: 6px; color: var(--accent); }
    #doc-content { padding: 36px 48px; max-width: 860px; }

    /* ── Summary / Welcome ── */
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .summary-card { background: #fff; border-radius: 10px; padding: 16px; border: 1px solid #e2e8f0; }
    .summary-card h3 { font-size: .72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }
    .summary-card .num { font-size: 1.5rem; font-weight: 800; color: #0f172a; }
    .summary-card .sub { font-size: .72rem; color: #94a3b8; }
    .summary-title { font-size: 1.3rem; font-weight: 800; color: #0f172a; margin-bottom: 6px; }
    .summary-sub { font-size: .85rem; color: #64748b; margin-bottom: 24px; }
    .summary-section { margin-bottom: 24px; }
    .summary-section h2 { font-size: .85rem; font-weight: 700; color: #334155; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
    .summary-section h2 i { color: var(--accent); }
    .doc-link { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 6px; cursor: pointer; font-size: .8rem; color: #334155; text-decoration: none; transition: all .1s; background: #fff; }
    .doc-link:hover { border-color: var(--accent); background: #f8f7ff; }
    .doc-link i { color: #94a3b8; font-size: .75rem; }

    /* ── Markdown ── */
    .md h1 { font-size: 1.55rem; font-weight: 800; color: #0f172a; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 2px solid #e2e8f0; }
    .md h2 { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-top: 32px; margin-bottom: 10px; }
    .md h3 { font-size: .925rem; font-weight: 700; color: #334155; margin-top: 22px; margin-bottom: 8px; }
    .md p  { font-size: .875rem; line-height: 1.75; color: #374151; margin-bottom: 12px; }
    .md ul, .md ol { padding-left: 22px; margin-bottom: 12px; }
    .md li { font-size: .875rem; line-height: 1.7; color: #374151; margin-bottom: 3px; }
    .md strong { font-weight: 700; color: #1e293b; }
    .md code { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 4px; padding: 1px 5px; font-size: .78rem; color: #be123c; font-family: "Fira Code", monospace; }
    .md pre { background: #1e293b; border-radius: 10px; padding: 18px 20px; overflow-x: auto; margin-bottom: 16px; }
    .md pre code { background: none; border: none; color: #e2e8f0; font-size: .78rem; padding: 0; }
    .md blockquote { border-left: 3px solid var(--accent); padding: 8px 16px; background: #f8fafc; margin-bottom: 12px; border-radius: 0 6px 6px 0; }
    .md blockquote p { margin: 0; color: #475569; font-size: .85rem; }
    .md hr { border: none; border-top: 1px solid #e2e8f0; margin: 28px 0; }
    .md a  { color: var(--accent); text-decoration: none; }
    .md a:hover { text-decoration: underline; }
    .md table { border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: .82rem; border-radius: 8px; overflow: hidden; }
    .md th { background: #f1f5f9; font-weight: 700; color: #1e293b; padding: 9px 14px; border: 1px solid #e2e8f0; text-align: left; }
    .md td { padding: 8px 14px; border: 1px solid #e2e8f0; color: #374151; vertical-align: top; }
    .md tr:nth-child(even) td { background: #fafafa; }
    .md input[type=checkbox] { margin-right: 6px; accent-color: var(--accent); }

    /* ── Backlog ── */
    #view-backlog { padding: 28px 24px; }
    .stat-card { background: #fff; border-radius: 14px; padding: 20px 22px; display: flex; align-items: center; gap: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.06); border: 1px solid #e2e8f0; }
    .stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; flex-shrink: 0; }
    .stat-num { font-size: 1.6rem; font-weight: 800; line-height: 1; color: #0f172a; }
    .stat-label { font-size: .75rem; color: #64748b; margin-top: 2px; }

    .kb-col { border-radius: 14px; overflow: hidden; border: 1px solid #e2e8f0; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
    .kb-header { padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f1f5f9; }
    .kb-title { font-weight: 700; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }
    .kb-body { padding: 12px; min-height: 80px; }

    .task-card { background: #fff; border-radius: 10px; border: 1px solid #e2e8f0; padding: 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.04); border-left-width: 3px !important; }
    .task-name { font-weight: 700; font-size: .82rem; color: #1e293b; line-height: 1.35; margin-bottom: 4px; }
    .task-desc { font-size: .75rem; color: #64748b; line-height: 1.45; margin-bottom: 10px; }
    .task-progress { height: 4px; background: #f1f5f9; border-radius: 99px; overflow: hidden; margin-bottom: 6px; }
    .task-progress-bar { height: 100%; border-radius: 99px; }
    .task-meta { display: flex; justify-content: space-between; align-items: center; }
    .task-count { font-size: .68rem; color: #94a3b8; }
    .task-toggle { font-size: .68rem; color: #94a3b8; background: none; border: 1px solid #e2e8f0; border-radius: 5px; padding: 2px 8px; cursor: pointer; }
    .task-toggle:hover { background: #f8fafc; }
    .task-checklist { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; display: none; }
    .task-checklist.open { display: block; }
    .ci { display: flex; align-items: flex-start; gap: 7px; font-size: .75rem; line-height: 1.45; margin-bottom: 4px; }
    .ci-done { color: #94a3b8; text-decoration: line-through; }
    .ci-icon { flex-shrink: 0; margin-top: 1px; font-size: .7rem; }
    .ci-done .ci-icon { color: #22c55e; }
    .ci-pend .ci-icon { color: #cbd5e1; }
    .kb-empty { text-align: center; padding: 32px 16px; color: #94a3b8; font-size: .8rem; }
  </style>
</head>
<body>

<!-- ── Navbar ── -->
<nav id="topnav">
  <div class="brand"><span>◆</span> Hub AuroraISP</div>
  <ul class="nav nav-pills ms-3">
    <li class="nav-item">
      <a class="nav-link active" id="btn-docs" href="#" onclick="showView('docs');return false;">
        <i class="bi bi-files me-1"></i>Documentos
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" id="btn-backlog" href="#" onclick="showView('backlog');return false;">
        <i class="bi bi-kanban me-1"></i>Backlog
      </a>
    </li>
  </ul>
  <div class="ms-3">
    <input id="search-input" type="text" placeholder="&#xe9d3; Buscar documento..." oninput="searchDocs(this.value)">
  </div>
  <div class="nav-timestamp"><i class="bi bi-clock me-1"></i>__NOW__</div>
</nav>

<!-- ── App ── -->
<div id="app">

  <!-- ── Sidebar ── -->
  <aside id="sidebar"></aside>

  <!-- ── Docs view ── -->
  <div id="view-docs">
    <div id="doc-panel">
      <div id="breadcrumb"><a href="#" onclick="goHome();return false;" style="text-decoration:none;color:#64748b;"><i class="bi bi-house-door"></i> Resumo</a> <span id="breadcrumb-text"></span></div>
      <div id="doc-content">
        <div id="doc-summary"></div>
      </div>
    </div>
  </div>

  <!-- ── Backlog view ── -->
  <div id="view-backlog">
    <!-- Stats and kanban rendered by JS -->
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
const TREE  = __TREE__;
const TASKS = __TASKS__;

// ── View switcher ──────────────────────────────────────────────────────────
function showView(v) {
  const isDocs = v === 'docs';
  document.getElementById('view-docs').style.display    = isDocs ? 'flex' : 'none';
  document.getElementById('view-backlog').style.display = isDocs ? 'none' : 'block';
  document.getElementById('sidebar').style.display      = isDocs ? 'block' : 'none';
  document.getElementById('search-input').style.display = isDocs ? 'block' : 'none';
  document.getElementById('btn-docs').classList.toggle('active', isDocs);
  document.getElementById('btn-backlog').classList.toggle('active', !isDocs);
}

// ── Sidebar with accordions ─────────────────────────────────────────────────
let allFiles = [];
let activeFileEl = null;

function countFiles(node) {
  if (node.t === 'f') return 1;
  return (node.ch || []).reduce((s, c) => s + countFiles(c), 0);
}

function buildTree(nodes, container, depth) {
  nodes.forEach(node => {
    if (node.t === 'd') {
      const fileCount = countFiles(node);
      const acc = document.createElement('div');
      acc.className = 'sb-accordion';

      const header = document.createElement('div');
      header.className = 'sb-acc-header';
      if (depth > 0) { header.style.paddingLeft = (12 + depth * 10) + 'px'; header.style.fontSize = '.74rem'; }
      header.innerHTML = `<i class="sb-icon bi bi-folder-fill"></i><span>${node.n}</span><span class="sb-count">(${fileCount})</span><i class="sb-arrow bi bi-chevron-right"></i>`;
      header.onclick = (e) => { e.preventDefault(); e.stopPropagation(); acc.classList.toggle('open'); return false; };

      const body = document.createElement('div');
      body.className = 'sb-acc-body';
      buildTree(node.ch || [], body, depth + 1);

      acc.appendChild(header);
      acc.appendChild(body);
      container.appendChild(acc);

    } else if (node.t === 'f') {
      const row = document.createElement('div');
      row.className = 'si' + (depth === 0 ? ' si-root' : '');
      row.innerHTML = `<i class="si-icon bi bi-file-earmark-text"></i><span>${node.n}</span>`;
      row.onclick = (e) => { e.stopPropagation(); openDoc(node, row); };
      container.appendChild(row);
      allFiles.push({ node, el: row });
    }
  });
}

function openDoc(node, el) {
  if (activeFileEl) activeFileEl.classList.remove('active');
  activeFileEl = el;
  el.classList.add('active');
  document.getElementById('breadcrumb-text').textContent = ' / ' + node.fn;
  const content = document.getElementById('doc-content');
  const html = marked.parse(node.c || '');
  content.innerHTML = `<div class="md">${html}</div>`;

  // render checkboxes
  content.querySelectorAll('li').forEach(li => {
    const t = li.childNodes[0];
    if (t && t.nodeType === 3) {
      const txt = t.textContent;
      if (/^\[( |x)\] /i.test(txt)) {
        const done = txt[1].toLowerCase() === 'x';
        const rest = txt.slice(4);
        li.innerHTML = `<input type="checkbox" ${done ? 'checked' : ''} disabled class="me-1">${rest}${li.innerHTML.replace(txt,'')}`;
      }
    }
  });

  // Transformar h2 em accordions
  convertH2ToAccordions(content.querySelector('.md'));

  document.getElementById('doc-panel').scrollTop = 0;
}

function convertH2ToAccordions(container) {
  if (!container) return;
  const children = Array.from(container.childNodes);
  const sections = [];
  let headerContent = []; // conteúdo antes do primeiro h2 (título, intro)
  let currentSection = null;

  children.forEach(child => {
    if (child.nodeType === 1 && child.tagName === 'H2') {
      if (currentSection) sections.push(currentSection);
      currentSection = { title: child.textContent, elements: [] };
    } else if (currentSection) {
      currentSection.elements.push(child);
    } else {
      headerContent.push(child);
    }
  });
  if (currentSection) sections.push(currentSection);

  // Se tem menos de 2 seções h2, não vale converter
  if (sections.length < 2) return;

  // Limpar container
  container.innerHTML = '';

  // Re-adicionar o conteúdo antes do primeiro h2 (título do doc)
  headerContent.forEach(el => container.appendChild(el));

  // Criar accordions
  sections.forEach((section, i) => {
    // Contar checkboxes na seção
    const tempDiv = document.createElement('div');
    section.elements.forEach(el => tempDiv.appendChild(el.cloneNode(true)));
    const allChecks = tempDiv.querySelectorAll('li');
    let totalChecks = 0, doneChecks = 0;
    allChecks.forEach(li => {
      const txt = li.textContent.trim();
      if (/^\[.\]/.test(txt) || li.querySelector('input[type=checkbox]')) {
        totalChecks++;
        if (/^\[x\]/i.test(txt) || (li.querySelector('input[type=checkbox]') && li.querySelector('input[type=checkbox]').checked)) {
          doneChecks++;
        }
      }
    });
    // Também contar via emojis de status nas tabelas
    const allTds = tempDiv.querySelectorAll('td');
    let statusDone = 0, statusTotal = 0;
    allTds.forEach(td => {
      const t = td.textContent.trim();
      if (t === '✅' || t.startsWith('✅')) { statusDone++; statusTotal++; }
      else if (t === '⏳' || t.startsWith('⏳') || t === '🟡' || t.startsWith('🟡') || t === '🔧' || t.startsWith('🔧')) { statusTotal++; }
    });
    if (statusTotal > totalChecks) { totalChecks = statusTotal; doneChecks = statusDone; }

    const allDone = totalChecks > 0 && doneChecks === totalChecks;
    const hasTasks = totalChecks > 0;
    const pending = totalChecks - doneChecks;

    // Badge de progresso
    let badge = '';
    if (allDone) {
      badge = `<span style="display:inline-flex;align-items:center;gap:4px;font-size:.68rem;font-weight:600;color:#16a34a;background:#dcfce7;padding:2px 8px;border-radius:99px;"><i class="bi bi-check-circle-fill"></i> Completo</span>`;
    } else if (hasTasks) {
      badge = `<span style="display:inline-flex;align-items:center;gap:4px;font-size:.68rem;font-weight:600;color:#d97706;background:#fef3c7;padding:2px 8px;border-radius:99px;"><i class="bi bi-clock"></i> ${pending} pendente${pending > 1 ? 's' : ''}</span>`;
    }

    const acc = document.createElement('div');
    acc.className = 'content-accordion';
    const borderColor = allDone ? '#bbf7d0' : '#e2e8f0';
    acc.style.cssText = `margin-bottom:8px; border:1px solid ${borderColor}; border-radius:10px; overflow:hidden; background:#fff;`;
    if (allDone) acc.style.borderLeftWidth = '3px';
    if (allDone) acc.style.borderLeftColor = '#22c55e';

    const header = document.createElement('div');
    const headerBg = allDone ? '#f0fdf4' : '#f8fafc';
    header.style.cssText = `padding:12px 16px; cursor:pointer; display:flex; align-items:center; gap:10px; font-weight:700; font-size:.9rem; color:#1e293b; background:${headerBg}; user-select:none; transition:background .1s;`;
    header.innerHTML = `<span style="flex:1;">${section.title}</span>${badge}<i class="bi bi-chevron-down" style="font-size:.7rem; color:#94a3b8; transition:transform .2s;"></i>`;

    const body = document.createElement('div');
    body.style.cssText = 'padding:0 16px 16px; display:none;';
    section.elements.forEach(el => body.appendChild(el));

    // Primeiro accordion aberto por padrão
    if (i === 0) {
      body.style.display = 'block';
      header.querySelector('i').style.transform = 'rotate(180deg)';
      header.style.background = '#fff';
    }

    header.onmouseenter = () => { if (body.style.display === 'none') header.style.background = '#f1f5f9'; };
    header.onmouseleave = () => { header.style.background = body.style.display === 'none' ? '#f8fafc' : '#fff'; };

    header.onclick = (e) => {
      e.stopPropagation();
      const open = body.style.display === 'none';
      body.style.display = open ? 'block' : 'none';
      header.querySelector('i').style.transform = open ? 'rotate(180deg)' : 'rotate(0)';
      header.style.background = open ? '#fff' : '#f8fafc';
    };

    acc.appendChild(header);
    acc.appendChild(body);
    container.appendChild(acc);
  });
}

function searchDocs(q) {
  q = q.toLowerCase().trim();
  // expand all folders while searching
  document.querySelectorAll('.sf-children').forEach(el => {
    el.parentElement.classList.toggle('sf-open', !!q);
    const icon = el.parentElement.querySelector('.si-icon');
    if (icon) icon.className = `si-icon bi ${q ? 'bi-folder2-open' : 'bi-folder-fill'}`;
  });
  allFiles.forEach(({ node, el }) => {
    const match = !q
      || node.n.toLowerCase().includes(q)
      || node.fn.toLowerCase().includes(q)
      || (node.c || '').toLowerCase().includes(q);
    el.style.display = match ? 'flex' : 'none';
  });
}

// ── Backlog ────────────────────────────────────────────────────────────────
const STATUS = {
  pendente:     { label: 'Pendente',     color: '#f97316', bg: '#fff7ed', icon: 'bi-clock-history',     statBg: '#fff7ed', statColor: '#f97316' },
  em_andamento: { label: 'Em andamento', color: '#3b82f6', bg: '#eff6ff', icon: 'bi-arrow-repeat',       statBg: '#eff6ff', statColor: '#3b82f6' },
  finalizada:   { label: 'Finalizada',   color: '#22c55e', bg: '#f0fdf4', icon: 'bi-check-circle',       statBg: '#f0fdf4', statColor: '#22c55e' },
};

function renderBacklog() {
  const wrap = document.getElementById('view-backlog');

  const byStatus = { pendente: [], em_andamento: [], finalizada: [] };
  TASKS.forEach(t => { if (byStatus[t.status]) byStatus[t.status].push(t); });
  const total = TASKS.length;

  // Stats
  const statsHtml = `
    <div class="row g-3 mb-4">
      ${['pendente','em_andamento','finalizada'].map(s => {
        const cfg = STATUS[s];
        const n = byStatus[s].length;
        return `
        <div class="col-sm-6 col-lg-3">
          <div class="stat-card">
            <div class="stat-icon" style="background:${cfg.statBg}">
              <i class="bi ${cfg.icon}" style="color:${cfg.statColor}"></i>
            </div>
            <div>
              <div class="stat-num">${n}</div>
              <div class="stat-label">${cfg.label}</div>
            </div>
          </div>
        </div>`;
      }).join('')}
      <div class="col-sm-6 col-lg-3">
        <div class="stat-card">
          <div class="stat-icon" style="background:#f1f5f9">
            <i class="bi bi-list-task" style="color:#64748b"></i>
          </div>
          <div>
            <div class="stat-num">${total}</div>
            <div class="stat-label">Total</div>
          </div>
        </div>
      </div>
    </div>`;

  // Kanban
  const colsHtml = `
    <div class="row g-3 align-items-start">
      ${['pendente','em_andamento','finalizada'].map(s => {
        const cfg = STATUS[s];
        const cards = byStatus[s].map((t, i) => taskCardHtml(t, s + i, cfg.color)).join('');
        const empty = !byStatus[s].length ? `<div class="kb-empty"><i class="bi bi-inbox mb-2 d-block" style="font-size:1.5rem;opacity:.3"></i>Nenhuma tarefa</div>` : '';
        return `
        <div class="col-lg-4">
          <div class="kb-col">
            <div class="kb-header" style="border-left: 4px solid ${cfg.color}; background: ${cfg.bg}">
              <span class="kb-title" style="color:${cfg.color}">${cfg.label}</span>
              <span class="badge rounded-pill text-white" style="background:${cfg.color}">${byStatus[s].length}</span>
            </div>
            <div class="kb-body">${cards}${empty}</div>
          </div>
        </div>`;
      }).join('')}
    </div>`;

  wrap.innerHTML = statsHtml + colsHtml;
}

function taskCardHtml(t, uid, color) {
  const pct = t.total > 0 ? Math.round((t.done / t.total) * 100) : 0;
  const date = t.created ? `<span style="font-size:.68rem;color:#94a3b8">${t.created}</span>` : '';
  const desc = t.desc ? `<div class="task-desc">${esc(t.desc)}</div>` : '';
  const progressHtml = t.total > 0 ? `
    <div class="task-progress"><div class="task-progress-bar" style="width:${pct}%;background:${color}"></div></div>
    <div class="task-meta">
      <span class="task-count">${t.done}/${t.total} tarefas &bull; ${pct}%</span>
      <button class="task-toggle" onclick="toggleChecklist('cl-${uid}',this)">Ver tarefas</button>
    </div>` : '';

  const checklistItems = t.items.map(item => {
    const cls = item.d ? 'ci ci-done' : 'ci ci-pend';
    const icon = item.d ? 'bi-check-circle-fill text-success' : 'bi-circle text-secondary';
    return `<div class="${cls}"><i class="ci-icon bi ${icon}"></i><span>${esc(item.t)}</span></div>`;
  }).join('');

  const checklist = t.items.length ? `<div class="task-checklist" id="cl-${uid}">${checklistItems}</div>` : '';

  return `
  <div class="task-card" style="border-left-color:${color}">
    <div class="d-flex justify-content-between align-items-start mb-1">
      <div class="task-name">${esc(t.name)}</div>
      ${date}
    </div>
    ${desc}
    ${progressHtml}
    ${checklist}
  </div>`;
}

function toggleChecklist(id, btn) {
  const el = document.getElementById(id);
  const open = el.classList.toggle('open');
  btn.textContent = open ? 'Ocultar' : 'Ver tarefas';
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Summary ─────────────────────────────────────────────────────────────────
function renderSummary() {
  const totalDocs = allFiles.length;
  const totalTasks = TASKS.length;
  const doneTasks = TASKS.filter(t => t.status === 'finalizada').length;
  const pendTasks = TASKS.filter(t => t.status === 'pendente').length;

  // Agrupar docs por pasta de primeiro nível
  const folders = {};
  TREE.forEach(node => {
    if (node.t === 'd') {
      folders[node.n] = countFiles(node);
    }
  });

  // Encontrar docs do GTM
  let gtmFiles = [];
  function findGtm(nodes, path) {
    nodes.forEach(n => {
      if (n.t === 'd' && n.n === 'GTM') {
        (n.ch || []).forEach(f => { if (f.t === 'f') gtmFiles.push(f); });
      } else if (n.t === 'd') {
        findGtm(n.ch || [], path + '/' + n.n);
      }
    });
  }
  findGtm(TREE, '');

  const gtmHtml = gtmFiles.map(f =>
    `<div class="doc-link" onclick="openDocByName('${f.fn}')"><i class="bi bi-file-earmark-text"></i>${f.n}</div>`
  ).join('');

  // Tarefas recentes (finalizadas)
  const recentDone = TASKS.filter(t => t.status === 'finalizada').slice(0, 5);
  const recentPend = TASKS.filter(t => t.status === 'pendente').slice(0, 5);

  const doneHtml = recentDone.map(t =>
    `<div class="doc-link" style="border-left:3px solid #22c55e;"><i class="bi bi-check-circle-fill" style="color:#22c55e;"></i>${esc(t.name)}</div>`
  ).join('');

  const pendHtml = recentPend.map(t =>
    `<div class="doc-link" style="border-left:3px solid #f97316;"><i class="bi bi-clock" style="color:#f97316;"></i>${esc(t.name)}</div>`
  ).join('');

  document.getElementById('doc-summary').innerHTML = `
    <div class="summary-title">Hub AuroraISP</div>
    <div class="summary-sub">Gestor de documentos, backlog e estrategia. Gerado em __NOW__.</div>

    <div class="summary-grid">
      <div class="summary-card">
        <h3>Documentos</h3>
        <div class="num">${totalDocs}</div>
        <div class="sub">${Object.keys(folders).join(', ')}</div>
      </div>
      <div class="summary-card">
        <h3>Tarefas</h3>
        <div class="num">${totalTasks}</div>
        <div class="sub">${doneTasks} finalizadas, ${pendTasks} pendentes</div>
      </div>
      <div class="summary-card">
        <h3>Progresso</h3>
        <div class="num">${totalTasks > 0 ? Math.round((doneTasks/totalTasks)*100) : 0}%</div>
        <div class="sub">do backlog concluido</div>
      </div>
    </div>

    <div class="summary-section">
      <h2><i class="bi bi-rocket-takeoff"></i> GTM (Go-to-Market)</h2>
      ${gtmHtml || '<div class="doc-link"><i class="bi bi-info-circle"></i>Nenhum documento GTM encontrado</div>'}
    </div>

    <div class="summary-section">
      <h2><i class="bi bi-check2-square"></i> Finalizadas recentes</h2>
      ${doneHtml || '<div style="font-size:.8rem;color:#94a3b8;">Nenhuma tarefa finalizada</div>'}
    </div>

    <div class="summary-section">
      <h2><i class="bi bi-clock-history"></i> Pendentes</h2>
      ${pendHtml || '<div style="font-size:.8rem;color:#94a3b8;">Nenhuma tarefa pendente</div>'}
    </div>
  `;
}

function goHome() {
  if (activeFileEl) activeFileEl.classList.remove('active');
  activeFileEl = null;
  document.getElementById('breadcrumb-text').textContent = '';
  document.getElementById('doc-content').innerHTML = '<div id="doc-summary"></div>';
  renderSummary();
  document.getElementById('doc-panel').scrollTop = 0;
}

function openDocByName(filename) {
  const found = allFiles.find(f => f.node.fn === filename);
  if (found) {
    // Abrir os accordions pai
    let el = found.el;
    while (el) {
      if (el.classList && el.classList.contains('sb-accordion')) el.classList.add('open');
      el = el.parentElement;
    }
    openDoc(found.node, found.el);
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
buildTree(TREE, document.getElementById('sidebar'), 0);
renderBacklog();
renderSummary();
</script>
</body>
</html>"""


def generate():
    doc_tree = build_doc_tree()
    tasks    = collect_tasks()
    now      = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Escapar </script> dentro do JSON para não quebrar o <script> tag
    tree_json  = json.dumps(doc_tree, ensure_ascii=False).replace("</script>", "<\\/script>")
    tasks_json = json.dumps(tasks,    ensure_ascii=False).replace("</script>", "<\\/script>")

    html = (HTML
        .replace("__TREE__",  tree_json)
        .replace("__TASKS__", tasks_json)
        .replace("__NOW__",   now))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    by_status = {}
    for t in tasks:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    print(f"Hub gerado: {OUTPUT_PATH}")
    print(f"  Docs: {sum(1 for _ in WORKSPACE.rglob('*.md'))} arquivos")
    print(f"  Backlog: {by_status.get('pendente',0)} pendentes | {by_status.get('em_andamento',0)} em andamento | {by_status.get('finalizada',0)} finalizadas")


if __name__ == "__main__":
    generate()
