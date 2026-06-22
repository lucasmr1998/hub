# Editor de Automação (ilha React, dev-only)

Editor visual estilo n8n do motor de automação. **React + @xyflow/react (React Flow) + Vite + TypeScript.** Roda só em dev por enquanto — nada vai pro deploy ainda.

O editor produz/consome o **mesmo JSON de grafo** que o runtime (`executar_fluxo`) roda. O Python não muda: o editor fala com o backend por 2 endpoints (`/automacao/api/nodes/` e `/automacao/api/testar-fluxo/`).

## Dois modos

### Modo uso (1 app só) — recomendado pra só usar o editor
O Django serve o bundle buildado como uma página normal. **Um endereço, um login, sem Vite.**
```bash
cd robo/dashboard_comercial/gerenciador_vendas/apps/automacao/editor
npm install      # primeira vez
npm run build    # gera apps/automacao/static/automacao_editor/{editor.js,editor.css}

cd ../../../      # gerenciador_vendas/
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```
Faça login em `http://localhost:8001/` e abra **`http://localhost:8001/automacao/editor/`**.
> Mudou o código do editor? Rode `npm run build` de novo pra atualizar o bundle servido.

### Modo dev da UI (2 portos) — pra desenvolver a tela com hot reload
```bash
# Terminal 1: Django (porta 8001), logado em http://localhost:8001/
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
# Terminal 2: Vite (porta 5173)
cd apps/automacao/editor && npm run dev
```
Abra `http://localhost:5173/`. O Vite faz proxy de `/automacao/api/*` pro Django (:8001) — same-origin, sem CORS, sessão de login compartilhada (cookie de `localhost`).

## Usar
- Clique nos blocos da paleta (esquerda) pra adicionar nós.
- Arraste das saídas (`sucesso`/`erro`) pra conectar.
- Selecione um nó pra editar **handle** (a identidade visível, usada em `{{nodes.<handle>}}`) e a **config** (JSON).
- **▶ Testar** roda o fluxo no backend e mostra o trace + variáveis.
- **Exportar JSON** baixa o grafo no formato do runtime.

## Build
```bash
npm run build   # gera dist/ (estático). O Django servirá isso quando formos publicar.
```

## Status / pendências
- **Dev-only.** Decisão de build no deploy (commitar `dist/` vs build no container EasyPanel) fica pra quando formos publicar.
- Config é editada como JSON cru por ora — formulários por tipo de nó vêm depois.
- CSRF do endpoint `testar-fluxo` está `csrf_exempt` (DEV-ONLY) — endurecer antes de qualquer deploy.
