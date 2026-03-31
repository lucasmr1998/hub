# Melhorias Frontend — Rob-Vendas

> Registro de todas as otimizacoes de performance e padronizacao UX/design aplicadas.
> Data: 24/03/2026

---

## Performance

### 1. Polling de notificacoes unificado
**Antes:** Duas funcoes (`updateBadge` + `checkPendingNotifications`) faziam 2 requests ao mesmo endpoint `/api/notificacoes/listar/` a cada 30 segundos = 4 requests/minuto desnecessarios.

**Depois:** Uma unica funcao `pollNotifications()` faz 1 request a cada 30s, atualizando badge E mostrando toasts no mesmo callback.

**Arquivo:** `base.html`

### 2. Chart.js removido do carregamento global
**Antes:** `chart.min.js` (~150KB) carregava em TODAS as paginas via `base.html`, mesmo que so o Dashboard usasse graficos (e usa canvas nativo, nao Chart.js).

**Depois:** Removido do `base.html`. Paginas que precisam (relatorios, analise) carregam via CDN no proprio `{% block extra_js %}`.

**Arquivo:** `base.html`

### 3. SPA cleanup de intervals/timeouts
**Antes:** Ao navegar entre paginas via SPA, event listeners e `setInterval` acumulavam — cada visita ao Dashboard adicionava um novo polling de 30s sem limpar o anterior.

**Depois:** Sistema de cleanup global: `window._pageIntervals` e `window._pageTimeouts` sao limpos antes de cada navegacao SPA. Paginas registram seus intervals nesse array.

**Arquivos:** `base.html` (navigateTo), `new_dash.html` (registra interval)

---

## UX/Design

### 4. Menu reorganizado
**Topbar (modulos):**
- Dashboard | Comercial | Marketing | Relatorios

**Sidebar muda conforme modulo:**
- Dashboard: Visao Geral
- Comercial: Vendas, Cadastro
- Marketing: Leads, Campanhas
- Relatorios: Visao Geral, Conversoes, Atendimentos
- Configuracoes (via menu perfil): Painel, Usuarios, Planos, Vencimentos, Cadastro, Campanhas, Fluxos, Questoes, Recontato, Notificacoes

**Perfil unificado:** Sino + Avatar + Nome em bloco unico na topbar

**Arquivo:** `base.html`

### 5. Tabelas padronizadas
**Antes:** Tabela de Leads e Vendas tinham estilos completamente diferentes (avatares, badges, paginacao, filtros).

**Depois:**
- Nomes truncados com ellipsis + tooltip (`.truncate`, `.cell-main`, `.cell-sub`)
- Sem avatares coloridos — nome direto com 2 primeiros nomes
- Badges unificados via `statusBadge()` usando `.badge-success/.badge-warning/.badge-danger`
- Data compacta `DD/MM HH:MM` com tooltip do ano
- Icones de acao uniformes (`.row-action`) com hover que destaca no hover da linha
- Paginacao identica: `Anterior | 1 2 3 | Proximo` centralizado
- Filtros identicos: `.filter-card` + `.filter-toggle` + `.filter-body` + `.filter-row`

**Arquivos:** `leads.html`, `vendas.html`

### 6. CSS consolidado no design system
**Movido para `dashboard.css` (global):**
- `.filter-card`, `.filter-toggle`, `.filter-body`, `.filter-row` — filtros
- `.stat-icon-card` — stat cards com icone
- `.pagination` — paginacao
- `.truncate`, `.truncate-2` — truncamento de texto
- `.avatar-sm`, `.avatar-md` — avatares
- `.skeleton` — loading skeleton
- `.cell-main`, `.cell-sub` — conteudo de celulas
- `.row-action`, `.row-action.whatsapp`, `.row-action.danger` — botoes de acao
- `.empty-state` — estados vazios
- Colunas de tabela: `.col-id`, `.col-name`, `.col-contact`, `.col-value`, `.col-origin`, `.col-status`, `.col-date`, `.col-actions`

**Removido CSS duplicado de:** `leads.html`, `vendas.html`

### 7. Stat cards com icones
**Antes:** Leads tinha stat cards centralizados sem icones, Vendas tinha com icones e gradientes.

**Depois:** Ambos usam o mesmo padrao — icone colorido a esquerda + label uppercase + valor grande.

### 8. Vendas — coluna Valor unificada
Coluna "Valor" removida como coluna separada. Valor agora aparece como subtexto na coluna "Servico/Plano".

### 9. Dashboard labels corrigidas
**Antes:** "LEADS (TOTAL)", "LEADS (HOJE)", "PLANOS ATIVOS", "BANNERS ATIVOS" — nao refletiam dados reais.

**Depois:** "ATENDIMENTOS", "LEADS", "PROSPECTOS", "CLIENTES" — correspondem aos dados da API.

### 10. Loading skeleton no Dashboard
**Antes:** Spinner generico bloqueando tela.

**Depois:** 4 skeleton cards + 2 blocos pulsando que simulam o layout real enquanto carrega.

### 11. Hover de tabela melhorado
Icones de acao ganham fundo branco e cor mais escura no hover da linha, mantendo visibilidade.

---

## Problemas conhecidos (pendentes)

| Problema | Prioridade |
|----------|-----------|
| Stat cards: Dashboard usa 32px valor, Leads/Vendas usam 24px | Baixa |
| Vendas: ~30 inline styles hardcoded restantes nos modais | Baixa |
| Relatorios/Analise: ainda usam CSS inline antigo (override global atenua) | Media |
| Configuracoes (planos, campanhas, questoes, etc.): CSS inline extenso | Baixa |
| Mobile: breakpoints inconsistentes entre paginas | Media |
| Modais: Leads usa `.modal-overlay`, Vendas usa `.modal` | Baixa |

---

## Arquivos modificados

| Arquivo | Mudancas |
|---------|----------|
| `static/vendas_web/css/dashboard.css` | Design system completo, filtros, paginacao, stat cards, truncation, skeleton, avatares, overrides |
| `templates/vendas_web/base.html` | Topbar, sidebar por modulo, perfil unificado, SPA cleanup, polling unificado |
| `templates/vendas_web/new_dash.html` | Labels corrigidas, skeleton loading, interval com cleanup |
| `templates/vendas_web/leads.html` | Tabela padronizada, truncation, badges unificados, paginacao |
| `templates/vendas_web/vendas.html` | Tabela padronizada, filtros, sem avatar, valor unificado, acoes em icones |
| `templates/vendas_web/configuracoes/index.html` | Cards com design system |
| `templates/vendas_web/configuracoes/usuarios.html` | Tabela com design system |
| `templates/vendas_web/configuracoes/fluxos.html` | Reescrito com design system |
| `templates/vendas_web/configuracoes/recontato.html` | Reescrito com design system |
| `templates/vendas_web/login.html` | Cores atualizadas |
