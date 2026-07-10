# Sessão 08 a 10/07/2026 — Relatório executivo, resumos diários e blindagem HubSoft (Nuvyon)

## Contexto

Continuação do foco em relatórios pra Nuvyon. A Gabi definiu o Relatório Executivo como prioridade e foi pedindo incrementos ao longo dos dias; em paralelo, casos de suporte (Misael, Walace, Rita, Jefferson) revelaram e fecharam buracos na sincronização com o HubSoft.

## Entregas

### Painel da Gabi (dash #15) — 18 widgets, todos com ícone "?" explicativo

- Relatório executivo completo: receita (R$ 10.198), ticket médio (R$ 105, sem zeros), conversão geral (19,6%), conversão por canal, consultora líder, leads parados (7d+), leads sem atendimento (sem responsável), instalações pendentes (HubSoft, com true-up), pior gargalo do funil, vendas por canal.
- Pedidos extras da Gabi: leads por cidade, vendas por cidade (transform `normalizar_cidade` unifica grafias), funil de viabilidade (leads → Endereço Validado → vendas; estágio como proxy porque a consulta formal não carimba o lead — instrumentação do endpoint N8N registrada como melhoria).
- Filtros globais de Período e Fonte em tudo; rastreamento Meta Ads responde "origem pré-WhatsApp".

### Resumos diários WhatsApp (divididos em dois a pedido da Gabi)

- Geral (`resumo_diario_comercial`): sem o ranking; com link "Ver e atribuir" nas sem responsável.
- Vendedoras (`resumo_diario_vendedoras`): 1 linha por pessoa (+recebeu · fechou · perdeu com "Sem retorno" · carteira com paradas). Formato compacto aprovado em preview.
- Infra comum: cron horário #19 + gate de horário da preferência (8h Gabi) + dedup por dia. **Cron DESATIVADO aguardando aprovação final** (ativação = tipo vendedoras + preferência Gabi + religar #19).

### Blindagem HubSoft (casos da semana)

- Retry em 2 fases plano×cidade corrigido de verdade (detecção movida pro except; wrapper levanta exceção em erro lógico — mocks anteriores validaram o comportamento errado).
- Email + origens obrigatórios no modal (casos Misael/Walace: cadastro salvo sem email não sincronizava e ninguém via).
- Criador vira responsável default na criação manual + filtro "Sem responsável" + backfill das órfãs.
- Valor do lead autopreenchido pelo preço típico do plano + backfill das 22 vendas sem receita (valores reais do HubSoft por CPF/telefone).
- **Caso Jefferson/Itu (deadlock)**: HubSoft valida o plano ARMAZENADO contra a cidade em toda edição; plano de unidade errada gravado trava o prospecto. Prevenção em 3 camadas: dropdown de planos filtra pelo CEP (catálogo real do HubSoft), seleção inválida limpa com aviso, save bloqueado com fail-open.

## Decisões

1. Resumo de vendedoras separado do geral, diário (dia anterior), formato 1 linha.
2. "Sem retorno" = motivo declarado pela vendedora no card (verificado: 100% manual).
3. Funil de viabilidade usa estágio Endereço Validado como proxy até instrumentarmos o endpoint N8N.
4. Cron dos resumos só liga com aprovação explícita do Lucas.
5. Tarefa #172 (sync incremental do prospecto) segue pendente — 3 casos em 2 dias reforçam a prioridade.

## Pendências (10/07 fim do dia)

- Ativação dos 2 resumos (tipo + preferência Gabi + religar cron #19 + fix plural "1 paradas").
- Jefferson: time trocar o plano pra unidade Meganet no card (alertas #4108 param).
- CAC: decidir campo manual vs API Meta Ads.
- Cron diário do true-up de instalações (w#74 degrada sem ele).
- Tarefa #172 sync incremental; instrumentar endpoint N8N de viabilidade; automatizar import do CSV Meta Ads.
- E-mail boas-vindas v2 no Paper: construído, falta revisão final.
