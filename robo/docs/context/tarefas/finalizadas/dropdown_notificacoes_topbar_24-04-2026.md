---
name: "Dropdown de notificacoes recentes no sino do topbar"
description: "Hoje o sino linka pra configuracoes/notificacoes. Melhoria: dropdown inline com ultimas 10 notificacoes + marcar como lida + link 'ver todas'"
prioridade: "🟢 Baixa"
responsavel: "Tech Lead"
---

# Dropdown de notificacoes topbar — 24/04/2026

**Data:** 24/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟢 Baixa
**Status:** ✅ Cancelado — 30/04/2026
**Motivo:** Decisão de produto: sino já abre a página de notificações diretamente. Dropdown inline deixou de ser necessário — a página cobre o caso de uso com mais contexto.

---

## Descrição

Hoje o sino no topbar (apos fix 24/04) eh um link direto pra `/configuracoes/notificacoes/`. UX ideal: dropdown inline que abre ao clicar, mostrando ultimas 10 notificacoes nao-lidas, com:

- Titulo + mensagem + timestamp
- Icone por tipo
- Click numa notificacao: marca como lida + segue `url_acao`
- Botao "marcar todas como lidas"
- Link "ver todas" no rodape -> pagina completa

## Infra existente

- API ja disponivel: `GET /api/notificacoes/listar/?nao_lidas_only=true&limite=10`
- API marcar lida: `POST /api/notificacoes/<id>/lida/`
- API marcar todas: `POST /api/notificacoes/marcar-todas-lidas/`
- Polling ja existe em `layout_app.html` (badge do sino atualiza a cada 15s)

## Proposta

### Template
Adicionar em `templates/partials/topbar.html`:

```html
<div class="app-topbar-bell-wrap">
  <button class="app-topbar-bell-btn" onclick="toggleNotifPanel()">
    <i class="bi bi-bell"></i>
    <span class="app-topbar-bell-dot" id="notificationBadge" hidden></span>
  </button>
  <div class="app-topbar-notif-panel" id="notifPanel" hidden>
    <header>Notificacoes <button onclick="marcarTodasLidas()">Marcar todas</button></header>
    <div id="notifList"><!-- preenchido via JS --></div>
    <footer><a href="{% url 'notificacoes:configuracoes_notificacoes' %}">Ver todas</a></footer>
  </div>
</div>
```

### JS (em layout_app.html)

```javascript
function toggleNotifPanel() { ... fetch API, render lista ... }
function marcarLida(id) { ... }
function marcarTodasLidas() { ... }
```

### Seguir padrao do flyout de sidebar
Ja existe pattern de flyout em `layout_app.html`. Reaproveitar CSS.

## Criterios de aceite

- [ ] Clique no sino abre/fecha panel
- [ ] Lista carrega via API (10 notif nao-lidas)
- [ ] Click em notificacao: marca como lida (badge -1) e redireciona pra url_acao
- [ ] Marcar todas funciona + fecha panel
- [ ] Fora do panel clica -> fecha
- [ ] ESC fecha
- [ ] Responsivo (mobile colapsa pra tela cheia?)

## Referencia

- Fix anterior (sino nao clicavel): commit apos 24/04/2026 em topbar.html
