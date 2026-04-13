# Sessao Intensiva — 11-12/04/2026

**Data:** 11 a 12 de abril de 2026
**Participantes:** Lucas (CEO) + Claude (Tech Lead / PM)
**Duracao:** Sessao longa (2 dias)

---

## Resumo

Sessao de alta produtividade com 28+ commits cobrindo notificacoes, CRM, editor de fluxos, integracoes, IA, branding e limpeza de codigo.

---

## Entregas Principais

### Modulo de Notificacoes (100% funcional)
- Models melhorados: campo `lida`, `data_lida`, `url_acao`, `icone`, `resposta_externa`
- 16 tipos de notificacao, 4 canais (sistema, email, whatsapp, webhook)
- Services centralizado: `criar_notificacao()`, `marcar_lida()`, `contar_nao_lidas()`
- 9 signals automaticos: lead novo, conversa recebida/transferida, mensagem recebida, tarefa atribuida, oportunidade movida, venda aprovada, ticket criado/respondido
- Frontend: badge real do backend, polling 15s, som via Web Audio API, marcar lida via API, sidebar com lista
- Documentacao: `16-NOTIFICACOES.md`

### Catalogo de Produtos/Servicos (CRM)
- Model `ProdutoServico` generico com `dados_erp` (JSONField) para campos do ERP
- Model `ItemOportunidade` (N:N com quantidade, valor, desconto)
- `OpcaoVencimentoCRM` com mapeamento ERP (`id_externo`, `dados_erp`)
- `valor_total_itens` e `recalcular_valor()` na OportunidadeVenda
- UI: tabela de produtos + chips de vencimento (redesign profissional)
- Unificacao: ProdutoServico como fonte unica, PlanoInternet vira legado

### Tool IA: Base de Conhecimento
- Tool `consultar_base_conhecimento` no engine do Agente IA
- Busca por titulo/tags (OR) + conteudo (AND) com stop words PT-BR
- Model `PerguntaSemResposta` com contagem de ocorrencias
- UI de gestao: filtros, metricas, botoes Criar Artigo/Resolver/Ignorar
- Testado no PostgreSQL local com dados reais

### Importacao de Leads CSV
- Upload com auto-deteccao de delimitador (`;` ou `,`) e encoding (UTF-8/Latin-1)
- Preview das primeiras 5 linhas + mapeamento visual de colunas
- Importacao em batch com relatorio (importados/duplicados/erros)
- Opcao de criar oportunidades no CRM automaticamente
- Botao "Importar CSV" na pagina de leads

### Validacao de Fluxo
- Funcao `_validar_fluxo()`: entrada, finalizacao, nos orfaos, IAs sem integracao
- Avisos como toasts ao salvar
- API toggle bloqueia ativacao com erros criticos
- Botao Ativar/Desativar no toolbar do editor

### Mensagens Interativas WhatsApp
- Botoes nativos (ate 3 opcoes) ou lista (4+ opcoes) via Uazapi
- Fallback para texto numerado se canal nao suporta
- Mensagem salva no inbox para historico

### Melhorias do Editor de Fluxos
- Preview do conteudo em cada nodo (titulo, modelo IA, etc.)
- Indicador de status (dot verde/amarelo/vermelho)
- Auto-save a cada 30 segundos
- Logs de execucao visual (painel lateral, nodos destacados em verde)

### Modos de Sincronizacao (Integracoes)
- Configuravel por feature: automatico / manual / desativado
- Signal e command checam modo antes de executar
- UI na tela de integracoes (selects por feature)
- Sem migration (usa JSONField existente)

### Renomear para Hubtrix
- Bot names: Aurora → Hubtrix, Aurora IA → Hubtrix IA
- Context processor, templates, admin, setup inicial
- Tela de login redesenhada com marca Hubtrix

### Limpeza e Organizacao
- Removidas pastas mortas: `crm/`, `integracoes/`, `vendas_web/` (60k linhas)
- Scripts movidos para pasta `scripts/`
- Removidos: `db.sqlite3` antigo, `.coverage`, `static` quebrado
- Funil por estagio filtrado por pipeline (fix)

---

## Decisoes Tecnicas

1. **ProdutoServico como fonte unica:** dados ISP-specific ficam em `dados_erp` (JSONField), nao em campos fixos. Agnostico de nicho.
2. **PlanoInternet mantido como legado:** FK opcional em ProdutoServico para retrocompatibilidade. Sera removido no futuro.
3. **Notificacoes sem WebSocket:** polling 15s e suficiente para o momento. WebSocket pode ser adicionado depois.
4. **Modos de sync sem migration:** usa `configuracoes_extras` (JSONField) existente. Default `automatico` e retrocompativel.
5. **Stop words na busca IA:** lista fixa de ~50 palavras PT-BR. Busca titulo/tags com OR, conteudo com AND.

---

## Tarefas Criadas

- **Assistente CRM via WhatsApp** (🔴 Alta) — agente IA operacional via numero dedicado. Doc: `17-ASSISTENTE_CRM.md`
- **Cron jobs de notificacoes** (🟢 Baixa) — tarefa_vencendo, sla_estourando, mencao_nota

---

## Tarefas Finalizadas (nesta sessao)

1. Recuperacao de senha (email + WhatsApp)
2. Validacao de oportunidade no fluxo
3. Notificacoes em tempo real
4. Tool IA: Base de Conhecimento
5. Produtos/Servicos no CRM
6. Importacao de leads CSV
7. Validacao de fluxo antes de ativar
8. Mensagens com botao Uazapi
9. Logs de execucao no editor
10. Melhorias visuais editor de fluxos
11. Renomear Aurora para Hubtrix
12. Unificar catalogo de produtos
13. CRM parceiro (movida de backlog)
14. Modulo marketing (movida de backlog)
15. Reguas de automacao (movida de backlog)
16. Aurora primeiro cliente (movida de backlog)
17. Deploy multi-tenancy (movida de backlog)
18. Modulo automacoes (movida de backlog)
19. Implementacao Aurora (movida de backlog)

---

## Estado do Backlog

- **15 pendentes** | **74 finalizadas**

---

## Proximos Passos

1. Implementar Assistente CRM via WhatsApp (prioridade alta)
2. Testar features no PostgreSQL local antes de deploy
3. Unificar completamente PlanoInternet → ProdutoServico (remover legado)
4. Considerar deploy das novas features em producao
