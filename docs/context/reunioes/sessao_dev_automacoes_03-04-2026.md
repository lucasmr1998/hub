# Sessão Dev: Automações, Filtros CRM, Segmentos e Ajustes — 03/04/2026

**Data:** 03/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / CTO / CPO / QA)
**Duração:** ~4 horas

---

## Contexto

Continuação do desenvolvimento. Foco em filtros do CRM, reorganização de segmentos para Marketing, refatoração completa do módulo de Automações com editor visual, e evolução dos testes.

---

## Principais pontos discutidos

- Filtros no CRM (pipeline, oportunidades, tarefas) precisavam ser colapsáveis no padrão "Filtros >"
- Segmentos devem pertencer ao Marketing, não ao Comercial
- Segmentos precisam de página dedicada com regras dinâmicas e preview em tempo real
- Signal para atualizar segmentos automaticamente quando lead muda
- Automações é o módulo mais importante do Marketing
- Fluxos condicionais (if/else entre ações) são necessários
- Editor visual tipo N8N/Zapier (Drawflow)
- Segmentos como fonte de dados para disparo em massa
- Timeline de automações na ficha do lead
- Controles robustos (rate limit, cooldown, deduplicação)
- Logs claros por lead e por regra
- PostgreSQL local configurado (aurora_dev)
- Migração de dados SQLite → PostgreSQL para Aurora HQ

---

## O que foi implementado

### CRM
- Filtros colapsáveis (padrão "Filtros >") no Pipeline, Oportunidades e Tarefas
- Filtros por responsável, tag, valor no Pipeline
- Filtros por estágio, responsável, tag nas Oportunidades
- Filtros por tipo, responsável, prioridade nas Tarefas
- Dropdown de seleção de pipeline no título (substitui tabs)
- Troca de pipeline via AJAX sem reload da página
- Superuser vê tarefas de todos

### Segmentos
- Movidos do CRM para Marketing (URLs /marketing/segmentos/)
- Página dedicada de criação/edição (substituiu modal)
- Builder de regras dinâmicas (campo + operador + valor)
- Preview em tempo real (mostra leads que atendem as regras)
- Signal automático: lead criado/atualizado avalia segmentos dinâmicos
- Service extraído para `apps/comercial/crm/services/segmentos.py`

### Automações (refatoração completa)
- 4 novos models: NodoFluxo, ConexaoNodo, ExecucaoPendente, ControleExecucao
- Engine dual-mode: legacy linear + BFS em grafo visual
- Branching if/else entre ações
- Delays reais via ExecucaoPendente + cron
- Management command `executar_automacoes_cron`
- Editor visual Drawflow (drag & drop, paleta de nós, painel de config)
- Dashboard central com KPIs, gráfico 30 dias, erros
- Timeline de automações na ficha do lead
- Integração com segmentos (lead_entrou_segmento, disparo em massa)
- Controles: max_execucoes_por_lead, cooldown_horas
- 60 testes passando
- Documentação completa em docs/PRODUTO/05-AUTOMACOES.md

### Infraestrutura
- PostgreSQL 18 instalado localmente
- Banco aurora_dev criado
- settings_local_pg.py configurado
- Migração SQLite → PostgreSQL do tenant Aurora HQ (CRM, equipes, tags, config)

### Testes
- Evoluiu de 291 para 756+ testes
- Cobertura de 40% para 57%
- Documentação de testes em docs/PRODUTO/04-TESTES.md

### Outros ajustes
- Removido "Aurora" do menu topbar
- Removido "Cadastro" do menu Comercial
- Removido "Estatísticas do Sistema" das configurações
- CS renomeado para "Customer Success"
- Membros renomeado para "Clientes" no CS
- Indicações movida para primeira posição em Fidelização
- Retenção removida temporariamente do menu
- Cores de segmentos padronizadas com sistema
- Erro `vendas_web_leadprospecto` no admin corrigido
- Admin Aurora: páginas Produto, Docs e Backlog adicionadas
- Contrato Grupo Magister gerado (MD + PDF)

---

## Próximos passos

- [ ] Testar editor visual Drawflow com feedback do Lucas
- [ ] Módulo de Suporte (atendimentos + tickets)
- [ ] Feedback e ajustes no CRM e Automações
