# Migração DS — Módulo Marketing — 20/04/2026

**Data:** 20/04/2026
**Participantes:** Lucas Rocha, Tech Lead, PM
**Duração:** sessão longa (múltiplas trocas)

---

## Contexto

Dando sequência ao plano de migração do Design System Hubtrix (`jazzy-giggling-wolf.md`), após concluir `comercial/leads` (Fase 2A) o escopo virou pro **módulo Marketing**. Inicialmente o usuário sugeriu a ordem Campanhas → Segmentos → E-mails → Automações. Durante a sessão, Automações foi tirado do escopo por envolver drawflow editor de ~830 linhas com particularidades próprias.

Marketing é o 2º módulo a ganhar o DS completo (o 1º foi Leads) e serviu pra amadurecer o padrão visual e descobrir gaps no DS.

---

## Principais pontos discutidos

### Templates migrados (7)
- **Campanhas** (1): `campanhas.html` — stat_cards, grid de campanhas, modal criar/editar, toasts.
- **Segmentos** (3, em `comercial/crm`): `segmentos_lista`, `segmento_criar`, `segmento_detalhe`. Inclui rule builder com preview live e modal de adicionar leads.
- **E-mails** (3): `lista`, `preview` (standalone), `editor` (editor drag-and-drop de 830 linhas).

### Bugs visuais resolvidos durante a migração
- Drop zone do editor email que fazia blocos ficarem lado-a-lado em vez de empilhados (flex só quando vazia).
- Botões de ação no canvas do editor sem contraste sobre fundos escuros (trocados pra fundo branco sólido + sombra forte + hover preenchido primary/danger).
- Block type badge ("CABEÇALHO") com pouco contraste — trocado pra fundo slate-900 sólido.
- Cards de segmento com alturas diferentes no grid — resolvido com `height: 100%` no `.entity-card` + wrapper `flex` + `flex: 1` no head.

### Discussão stat cards da lista de e-mails
Usuário questionou se os cards de inventário (total/ativos/rascunhos) poderiam trazer métricas mais interessantes (taxa de abertura, clique, bounce). Investigação revelou:
- Schema de tracking existe (`EnvioEmail` com aberto_em/clicado_em/bounce/erro + métodos `registrar_abertura/clique`).
- Mas **não há infra**: nenhum endpoint de pixel tracker, nenhum webhook de provider, nenhum código que dispare envio usando o módulo.
- Tabela `EnvioEmail` está praticamente vazia em prod.
Decidido: manter stat cards atuais até infra estar pronta.

### Tarefa aberta no backlog
[email_envio_tracking_19-04-2026.md](../tarefas/backlog/email_envio_tracking_19-04-2026.md) — Envio real + tracking de e-mails (marketing). Inclui: escolha de provider, service de envio, pixel tracker, redirect de cliques, webhook de bounces, fila, link de descadastro (LGPD).

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Remover Automações do escopo imediato de Marketing | Drawflow editor de ~830 linhas envolve outras complexidades; migrar em tarefa separada |
| Manter stat cards de inventário na lista de e-mails | Sem infra de envio/tracking, métricas reais retornariam zero |
| Abrir tarefa de infra envio+tracking antes de trocar KPIs | Evita implementar UI sem dado real |
| Editor de e-mail fica standalone (sem auto-migrar pro layout novo) | É app-like (3 colunas fixas, fullheight) — ganhos seriam mínimos vs risco |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Automações (5 templates) — `editor_fluxo`, `lista`, `dashboard`, `criar`, `historico` | Tech Lead — quando priorizar |
| Infra de envio + tracking de e-mails | Tech Lead — ver tarefa no backlog |

---

## Próximos passos

- [ ] Seguir pra próximo módulo — acordado: **CRM** (Fase 2B, 11 templates)
- [ ] Começar pela **pipeline.html** (tela mais vista, define padrão visual)
- [ ] Decidir se `retencao.html` (hoje em CRM) é CS e migra junto com CS
- [ ] Após CRM: Dashboard, depois Inbox (Fase 2C)
