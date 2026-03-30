#!/usr/bin/env python3
"""
Gerador de Backlog Visual — AuroraISP
Lê os arquivos .md de tarefas e gera um kanban em HTML.

Uso: python scripts/gerar_backlog.py
Saída: exports/backlog.html
"""

import re
from pathlib import Path
from datetime import datetime
from html import escape

WORKSPACE = Path(__file__).parent.parent
TAREFAS_PATH = WORKSPACE / "docs" / "context" / "tarefas"
OUTPUT_PATH = WORKSPACE / "exports" / "backlog.html"

FOLDER_MAP = {
    "backlog": "pendente",
    "em_andamento": "em_andamento",
    "finalizadas": "finalizada",
}

STATUS_CONFIG = {
    "pendente":     {"label": "Pendente",      "color": "#f97316", "bg": "#fff7ed", "border": "#fed7aa"},
    "em_andamento": {"label": "Em andamento",  "color": "#3b82f6", "bg": "#eff6ff", "border": "#bfdbfe"},
    "finalizada":   {"label": "Finalizada",    "color": "#22c55e", "bg": "#f0fdf4", "border": "#bbf7d0"},
}


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_frontmatter(content):
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm = content[3:end].strip()
    body = content[end + 3:].strip()
    meta = {}
    for line in fm.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, body


def parse_checklist(body):
    tasks = []
    for line in body.split("\n"):
        m = re.match(r"\s*-\s*\[(x| )\]\s*(.*)", line, re.IGNORECASE)
        if m:
            tasks.append({"done": m.group(1).lower() == "x", "text": m.group(2).strip()})
    return tasks


def get_section(body, name):
    m = re.search(rf"## {re.escape(name)}\n\n?(.*?)(?=\n## |\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_task_file(filepath, folder_status):
    content = filepath.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    checklist = parse_checklist(body)
    objective = get_section(body, "Objetivo")
    done_count = sum(1 for t in checklist if t["done"])
    status = "finalizada" if folder_status == "finalizada" else meta.get("status", folder_status)
    return {
        "name": meta.get("name", filepath.stem),
        "description": meta.get("description", ""),
        "status": status,
        "created": meta.get("criado_em", ""),
        "objective": objective,
        "checklist": checklist,
        "total": len(checklist),
        "done_count": done_count,
        "filename": filepath.name,
    }


def collect_tasks():
    tasks = []
    for folder, default_status in FOLDER_MAP.items():
        folder_path = TAREFAS_PATH / folder
        if folder_path.exists():
            for md_file in sorted(folder_path.glob("*.md")):
                if md_file.name.upper() not in ("TEMPLATE.MD",):
                    tasks.append(parse_task_file(md_file, default_status))
    return tasks


# ── HTML builders ─────────────────────────────────────────────────────────────

def progress_bar(done, total, color):
    pct = int((done / total) * 100) if total > 0 else 0
    return f"""
        <div class="progress-wrap">
          <div class="progress-bar" style="width:{pct}%;background:{color}"></div>
        </div>
        <span class="progress-label">{done}/{total} tarefas</span>"""


def checklist_html(items):
    if not items:
        return ""
    rows = ""
    for item in items:
        icon = "✓" if item["done"] else "○"
        cls = "item-done" if item["done"] else "item-pending"
        rows += f'<li class="{cls}"><span class="check-icon">{icon}</span>{escape(item["text"])}</li>\n'
    return f'<ul class="checklist">{rows}</ul>'


def card_html(task, idx):
    cfg = STATUS_CONFIG.get(task["status"], STATUS_CONFIG["pendente"])
    color = cfg["color"]
    total = task["total"]
    done = task["done_count"]
    pct = int((done / total) * 100) if total > 0 else 0

    desc = f'<p class="card-desc">{escape(task["description"])}</p>' if task["description"] else ""
    obj = f'<p class="card-obj">{escape(task["objective"])}</p>' if task["objective"] else ""
    date = f'<span class="card-date">Criado em {escape(task["created"])}</span>' if task["created"] else ""

    bar = ""
    if total > 0:
        bar = f"""
        <div class="progress-wrap">
          <div class="progress-bar" style="width:{pct}%;background:{color}"></div>
        </div>
        <div class="progress-meta">
          <span class="progress-label">{done}/{total} tarefas concluídas</span>
          <span class="progress-pct">{pct}%</span>
        </div>"""

    checklist = checklist_html(task["checklist"])
    detail_id = f"detail-{idx}"

    toggle = f'<button class="toggle-btn" onclick="toggle(\'{detail_id}\')">Ver tarefas ▾</button>' if checklist else ""

    return f"""
    <div class="card" style="border-left:3px solid {color}">
      <div class="card-header">
        <h3 class="card-title">{escape(task["name"])}</h3>
        {date}
      </div>
      {desc}
      {obj}
      {bar}
      {toggle}
      <div class="card-detail" id="{detail_id}">
        {checklist}
      </div>
    </div>"""


def column_html(status, tasks_in_col):
    cfg = STATUS_CONFIG[status]
    color = cfg["color"]
    bg = cfg["bg"]
    border = cfg["border"]
    label = cfg["label"]
    count = len(tasks_in_col)

    cards = "\n".join(card_html(t, f"{status}-{i}") for i, t in enumerate(tasks_in_col))
    empty = '<p class="empty">Nenhuma tarefa</p>' if not cards else ""

    return f"""
    <div class="column" style="background:{bg};border:1px solid {border}">
      <div class="column-header" style="border-bottom:2px solid {color}">
        <span class="column-title" style="color:{color}">{label}</span>
        <span class="badge" style="background:{color}">{count}</span>
      </div>
      <div class="cards">
        {cards}
        {empty}
      </div>
    </div>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def generate():
    tasks = collect_tasks()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    by_status = {s: [t for t in tasks if t["status"] == s] for s in STATUS_CONFIG}
    total_done = sum(1 for t in tasks if t["status"] == "finalizada")
    total_all = len(tasks)

    columns = "".join(column_html(s, by_status[s]) for s in STATUS_CONFIG)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Backlog — AuroraISP</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8fafc;
      color: #1e293b;
      min-height: 100vh;
    }}

    header {{
      background: #0f172a;
      color: #fff;
      padding: 20px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    header h1 {{ font-size: 1.25rem; font-weight: 700; letter-spacing: -0.02em; }}
    header h1 span {{ color: #818cf8; }}
    .header-meta {{ font-size: 0.75rem; color: #94a3b8; text-align: right; }}
    .header-meta strong {{ color: #e2e8f0; }}

    .summary {{
      background: #1e293b;
      padding: 12px 32px;
      display: flex;
      gap: 24px;
    }}
    .summary-item {{ font-size: 0.8rem; color: #94a3b8; }}
    .summary-item strong {{ color: #e2e8f0; }}

    main {{
      padding: 24px 32px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
      align-items: start;
    }}

    .column {{
      border-radius: 10px;
      overflow: hidden;
    }}

    .column-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
    }}
    .column-title {{ font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }}
    .badge {{
      color: #fff;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 99px;
    }}

    .cards {{ padding: 12px; display: flex; flex-direction: column; gap: 10px; }}

    .card {{
      background: #fff;
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }}

    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .card-title {{ font-size: 0.875rem; font-weight: 600; line-height: 1.3; }}
    .card-date {{ font-size: 0.7rem; color: #94a3b8; white-space: nowrap; }}
    .card-desc {{ font-size: 0.78rem; color: #64748b; margin-bottom: 8px; line-height: 1.45; }}
    .card-obj {{ font-size: 0.78rem; color: #475569; margin-bottom: 10px; line-height: 1.45; }}

    .progress-wrap {{
      height: 5px;
      background: #e2e8f0;
      border-radius: 99px;
      overflow: hidden;
      margin-bottom: 4px;
    }}
    .progress-bar {{ height: 100%; border-radius: 99px; transition: width 0.3s; }}
    .progress-meta {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
    .progress-label {{ font-size: 0.7rem; color: #64748b; }}
    .progress-pct {{ font-size: 0.7rem; color: #94a3b8; }}

    .toggle-btn {{
      background: none;
      border: 1px solid #e2e8f0;
      border-radius: 5px;
      padding: 4px 10px;
      font-size: 0.72rem;
      color: #64748b;
      cursor: pointer;
      margin-top: 2px;
      transition: all 0.15s;
    }}
    .toggle-btn:hover {{ background: #f1f5f9; border-color: #cbd5e1; }}

    .card-detail {{ display: none; margin-top: 10px; }}
    .card-detail.open {{ display: block; }}

    .checklist {{ list-style: none; display: flex; flex-direction: column; gap: 5px; }}
    .checklist li {{ display: flex; align-items: flex-start; gap: 7px; font-size: 0.775rem; line-height: 1.4; }}
    .check-icon {{ font-size: 0.7rem; margin-top: 2px; flex-shrink: 0; }}
    .item-done {{ color: #94a3b8; text-decoration: line-through; }}
    .item-done .check-icon {{ color: #22c55e; }}
    .item-pending {{ color: #374151; }}
    .item-pending .check-icon {{ color: #cbd5e1; }}

    .empty {{ font-size: 0.8rem; color: #94a3b8; text-align: center; padding: 24px 0; }}

    footer {{
      text-align: center;
      padding: 20px;
      font-size: 0.72rem;
      color: #94a3b8;
    }}

    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

<header>
  <h1>Backlog <span>AuroraISP</span></h1>
  <div class="header-meta">
    Gerado em {now}<br>
    <strong>{total_done} de {total_all} tarefas finalizadas</strong>
  </div>
</header>

<div class="summary">
  <div class="summary-item">Pendentes: <strong>{len(by_status["pendente"])}</strong></div>
  <div class="summary-item">Em andamento: <strong>{len(by_status["em_andamento"])}</strong></div>
  <div class="summary-item">Finalizadas: <strong>{len(by_status["finalizada"])}</strong></div>
  <div class="summary-item">Total: <strong>{total_all}</strong></div>
</div>

<main>
  {columns}
</main>

<footer>AuroraISP · Backlog gerado automaticamente a partir de docs/context/tarefas/</footer>

<script>
  function toggle(id) {{
    const el = document.getElementById(id);
    const btn = el.previousElementSibling;
    const open = el.classList.toggle('open');
    btn.textContent = open ? 'Ocultar tarefas ▴' : 'Ver tarefas ▾';
  }}
</script>

</body>
</html>"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Backlog gerado: {OUTPUT_PATH}")
    print(f"  {len(by_status['pendente'])} pendentes | {len(by_status['em_andamento'])} em andamento | {len(by_status['finalizada'])} finalizadas")


if __name__ == "__main__":
    generate()
