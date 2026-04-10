# Sessao 10/04/2026 (Parte 2) — Fixes, Testes, Dashboard, Permissoes

**Participantes:** Lucas (CEO), Claude (Tech Lead / PM)

---

## Entregas

### 1. Debug e Fix da Extracao IA
- Problema: classificacao e extracao eram chamadas separadas. "Me explique o curso de direito" era classificado como `curso_invalido` mesmo extraindo "Direito"
- Solucao: para `classificar_extrair`, extrai primeiro. Depois faz uma classificacao unica baseada no prompt completo
- Resultado: todas as variacoes de resposta ("me interessa X", "quero saber sobre X", etc) agora sao aceitas

### 2. Fix do IA Respondedor
- Problema: na primeira execucao, usava `_ultima_mensagem` do nodo anterior como input (ex: "Nota do Enem" ia como pergunta pra IA de valores)
- Solucao: primeira execucao envia "Apresente as informacoes conforme instruido" em vez da mensagem do usuario
- Variavel `mensagem_usuario` inicializada como `None` para evitar `UnboundLocalError`

### 3. Melhorias no Fluxo FATEPI
- Saudacao separada do nome (nodo espera_resposta=False)
- Mensagens pendentes acumuladas no engine e concatenadas na proxima pausa
- Branching por forma de ingresso: ENEM (pede foto), Prova Online (envia link), Transferencia (humano)
- Retencao antes de despedida com finalizacao propria
- Mover matriculado → finalizacao (score 10) em vez de transferir_humano
- "Como conheceu" movido para apos PIX
- Prompt de curso melhorado para aceitar frases naturais

### 4. Dashboard Inbox Reformulado
- KPIs tempo real: No Bot, Na Fila, Em Atendimento, Resolvidas Hoje, Total Hoje, Espera na Fila
- Painel de Agentes: avatar com dot de status, conversas ativas/capacidade
- Painel de Filas: aguardando, atendendo, agentes online, dentro/fora horario
- Grafico volume 30 dias + por canal + ranking agentes
- Agentes filtrados por equipes do tenant (corrigido vazamento cross-tenant)

### 5. Status Online/Offline dos Agentes
- Toggle no topbar: dot sobreposto no avatar, dropdown ao clicar
- API `POST /sistema/api/agente/status/`
- Auto-offline: middleware atualiza `ultimo_status_em` a cada request, marca offline apos 30min sem atividade
- Indicador visual no inbox: dot colorido ao lado do nome do agente nas conversas

### 6. Permissoes Corrigidas
- Marketing removido do topbar para vendedores (era `perm.acesso_comercial` que liberava)
- `comercial.ver_desempenho` adicionado ao perfil Vendedor
- Ranking de vendedores filtrado por perfil (Vendedor/Supervisor/Gerente) em vez de todos usuarios
- Agentes de outros tenants removidos da equipe FATEPI

### 7. Vinculo Automatico Agente → Oportunidade
- Quando agente e atribuido a conversa, automaticamente vira responsavel da oportunidade mais recente sem responsavel
- Funciona em: distribuicao automatica, atribuicao manual, auto-atribuicao ao responder, transferencia
- Funcao `_vincular_agente_oportunidade()` em services.py

### 8. Padronizacao Visual
- Headers padronizados (fundo branco, border-radius, padding) em:
  - Suporte: sessoes, base conhecimento
  - Marketing: automacoes (lista, dashboard, criar, historico), emails, campanhas
  - CRM: desempenho, tarefas, configuracoes, equipes, metas
  - Segmentos, Landing Page (cadastro e clube)
  - Fluxos de atendimento (cards redesenhados estilo segmentos)
- Topbar: fix do highlight duplo Dashboard/Suporte
- Grafico inbox: container com altura fixa (corrigido bug infinito)

### 9. CRM
- Botao "Nova Oportunidade" no pipeline com modal (nome, telefone, titulo, valor, responsavel)
- API `POST /crm/oportunidades/criar/`
- Dashboard: "Prospectos" renomeado para "Oportunidades", dados do CRM em vez de HubSoft
- Fix `data_criacao` → `data_cadastro` na API ultimas conversoes

### 10. Contas FATEPI
- 5 contas criadas: 2 Admin (NTI, Direcao) + 3 Vendedor (Anne, Italo, Marisa)
- Senha: Fatepi@2026
- Vendedores na equipe Comercial FATEPI como agentes do inbox
- 8 segmentos criados (Leads Quentes, Novos, Inativos, por curso, por canal, VIPs)

### 11. Limpeza
- Conversas orfas fechadas automaticamente
- Leads de teste removidos
- Agentes de outro tenant removidos

---

## Arquivos Modificados

### Engine
- `atendimento/engine.py` — fix classificar_extrair (extrai primeiro), respondedor primeira execucao, mensagens pendentes, branch questao sem IA

### Views
- `inbox/views.py` — dashboard reformulado, agentes filtrados por equipe tenant
- `crm/views.py` — api_criar_oportunidade, ranking vendedores por perfil
- `dashboard/views.py` — oportunidades CRM, fix data_cadastro
- `sistema/views.py` — api_agente_status
- `suporte/views.py` — fixes seguranca + features

### Models/Services
- `inbox/services.py` — _vincular_agente_oportunidade
- `inbox/distribution.py` — vincular agente na distribuicao
- `sistema/middleware.py` — auto-offline por inatividade
- `sistema/context_processors.py` — agente_status no context

### Templates (15+)
- `sistema/base.html` — topbar status toggle, fix Marketing vendedor, fix highlight
- `inbox/dashboard_inbox.html` — reformulado completo
- `inbox/inbox.html` — agentes_status_json
- `inbox/static/inbox/js/inbox.js` — status dots
- `crm/pipeline.html` — botao + modal nova oportunidade
- `crm/desempenho.html`, `tarefas_lista.html`, `configuracoes_crm.html`, `equipes.html`, `metas.html` — headers
- `crm/segmentos_lista.html` — header
- `marketing/*` — 6 templates headers
- `suporte/*` — dashboard, tickets, base conhecimento
- `atendimento/fluxos.html` — cards redesenhados
- `cadastro/cadastro.html` — header landing page

---

## Pendencias
- Auto-layout no editor de fluxos (organizar nos automaticamente)
- Testar fluxo FATEPI via WhatsApp com numero limpo
- Configurar crons em producao (executar_recontato, verificar_sla, executar_pendentes)
- Deploy
