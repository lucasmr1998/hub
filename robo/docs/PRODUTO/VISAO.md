# Visao do Produto — Hubtrix

**Status:** Em construcao (17/04/2026)
**Proposito:** Documento fundacional. Toda decisao de produto, marketing e roadmap deve se apoiar nele.

Este doc responde 4 perguntas, em ordem do concreto ao abstrato:

- **A. Jornada end-to-end** — quem passa pelo Hubtrix, em que ordem, em que estados
  - A2. Jornada do consumidor (cliente-do-cliente)
  - A1. Jornada do ISP usando o Hubtrix
- **B. Modelo mental do usuario** — como o operador do Hubtrix pensa no dia a dia
- **C. Como os modulos se conectam** — fluxo de dados e eventos entre as partes
- **D. Principios** — o que o Hubtrix E, o que NAO E

Cada secao e conversada, validada com o time e atualizada conforme o produto evolui.

---

## A. Jornada end-to-end

### A2. Jornada do consumidor (cliente-do-cliente)

> **Nota:** estagios 5-6 (Fechamento e Ativacao) usam a arquitetura de integracao
> com ERP definida em [secao C](#c-como-os-modulos-se-conectam) e [secao D](#d-principios-do-produto).

A jornada do consumidor atravessa **4 macro-fases**. Cada macro agrupa estagios
detalhados (ver secao de micro-estagios abaixo).

#### Aquisicao

Consumidor conhece o ISP e faz o primeiro contato. Hubtrix captura entradas vindas
de WhatsApp, site (widget) e telefone, reconhece de qual campanha o lead veio
(UTM, palavra-chave em mensagem), registra origem no historico do lead e aciona o
fluxo de qualificacao correto por canal.

*Promessa:* nenhum lead perdido, toda origem rastreada, canal certo sendo roteado
pro fluxo certo sem intervencao manual.

#### Conversao

Lead qualificado vira venda fechada. Bot visual pre-qualifica (nome, plano,
viabilidade, documentos); transfere pra humano quando atinge criterio. Vendedor
humano conduz negociacao no CRM (pipeline kanban, proposta, aceite de contrato).
Ao ganhar a oportunidade, dispatcher envia payload ao ERP configurado e o `Cliente`
nasce no espelho quando o ERP confirma o contrato.

*Promessa:* bot carrega o qualificavel, humano so entra onde agrega valor, venda
fecha sem re-digitar dados no ERP.

#### Fidelizacao

Cliente ativo passa a ser atendido no dia a dia: tickets de suporte ligados ao Inbox,
onboarding automatizado (primeiro mes), pesquisa de satisfacao, uso do Clube
(gamificacao, niveis, missoes, roleta) e resgate de beneficios com parceiros. Se da
sinais de churn (inadimplencia, queda no uso, reclamacao), sistema alerta o time de
retencao e aciona jornada de recuperacao antes do cancelamento.

*Promessa:* cliente engajado com o ISP, problemas resolvidos antes de virar churn,
valor percebido continuo apos a assinatura.

#### Expansao

Cliente satisfeito vira vetor de crescimento do ISP. Programa de indicacao
(member-get-member) com pagina publica personalizada e pontos ao indicador,
upsell de plano/SVA via CRM (alertas de upgrade), e campanhas segmentadas de
marketing acionadas por eventos (aniversario de contrato, liberacao de regiao).
Ciclo realimenta a fase de Aquisicao com leads de melhor qualidade.

*Promessa:* cliente ativo gera novo cliente ou paga mais; marketing opera sobre
dados reais do cliente, nao listas frias.

---

### Micro-estagios da jornada

Dez estagios detalhados, agrupados por macro-fase. Cada estagio responde 5 campos:
o que acontece, como entra e sai, papel do Hubtrix, estado atual, metrica.

---

## AQUISICAO

### 1. Descoberta

**O que acontece:** Pessoa toma conhecimento do provedor — ve anuncio (Google/Meta/TikTok), recebe indicacao de amigo, passa por ponto fisico, encontra por SEO ou boca a boca. **Ainda nao entrou em contato.** Esse estagio e largamente *fora* do Hubtrix: o ISP investe em midia, Hubtrix recebe o sinal so quando a pessoa vira primeiro contato (estagio 2).

**Entra:** investimento de midia do ISP, presenca fisica, referral organico, programa de indicacao ativo.
**Sai:** pessoa decide entrar em contato → estagio 2, carregando consigo: link UTM, codigo de indicacao, ou palavra-chave de campanha na mensagem.

**Papel do Hubtrix:**
- Cadastro de campanhas com palavra-chave, UTM, plataforma, orcamento: [marketing/campanhas.md](modulos/marketing/campanhas.md)
- Geracao de codigo de indicacao por membro + pagina publica personalizada: [cs/indicacoes.md](modulos/cs/indicacoes.md)

**Estado atual:**
- ✅ Cadastro de campanhas com 9 plataformas (google_ads, facebook_ads, instagram_ads, tiktok_ads, linkedin_ads, email, sms, whatsapp, outro), tipo_match (exato/parcial/regex), orcamento, periodo
- ✅ Programa de indicacao com pagina publica por `codigo_indicacao` do membro
- ⚠️ Sem integracao direta com Google Ads / Meta Ads — sync de campanhas e manual ou via N8N
- ❌ Sem dashboard de CAC por canal nesse estagio (so aparece apos conversao na secao 08-PRECIFICACAO do GTM)

**Metrica:** numero de **primeiros contatos** gerados no periodo, por canal. A saida deste estagio e o gatilho de entrada do estagio 2.

---

### 2. Primeiro contato

**O que acontece:** Consumidor **manda a primeira mensagem** — WhatsApp do ISP, widget do site, formulario de cadastro, ou liga no comercial. E o instante em que Hubtrix comeca a "ver" o consumidor.

**Entra:**
- Uazapi recebe WhatsApp → webhook inbound `/api/v1/n8n/inbox/mensagem-recebida/` → `services.receber_mensagem`
- Widget no site → POST publico `/api/public/widget/conversa/iniciar/` → `services.receber_mensagem_widget`
- Formulario de cadastro publico → cria Lead direto (sem passar pelo Inbox)
- Ligacao telefonica → vendedor registra Lead manualmente

**Sai:** Lead criado (novo ou reencontrado por telefone/email), Conversa criada no Inbox se e canal digital, signal `on_mensagem_recebida` dispara engine de atendimento → estagio 3.

**Papel do Hubtrix:**
- Recebimento e criacao de Conversa: [inbox/services.md](modulos/inbox/services.md)
- Signal conecta mensagem recebida ao engine de fluxos: [atendimento/integracao-inbox.md](modulos/atendimento/integracao-inbox.md)
- Landing publica de cadastro com multi-step + consulta CEP + upload de documentos: [comercial/cadastro.md](modulos/comercial/cadastro.md)
- Deteccao de campanha por palavra-chave na primeira mensagem (via N8N): [marketing/campanhas.md](modulos/marketing/campanhas.md)

**Estado atual:**
- ✅ WhatsApp via Uazapi integrado (provider pattern, Evolution disponivel)
- ✅ Widget JS 15KB embeddable com 3 abas (Inicio / Mensagens / FAQ) + FAQ integrado
- ✅ Cadastro publico com config completa (cores, campos obrigatorios, validacoes, contrato)
- ✅ Deteccao de campanha 100%/95%/90% de confianca (exato/parcial/regex)
- ✅ Normalizacao de telefone, deduplicacao de Lead por telefone/email
- ⚠️ Telefone/ligacao: vendedor cria lead manual; sem integracao com telefonia
- ❌ Sem captura nativa de Instagram DM / Facebook Messenger (tem que passar por N8N)
- ❌ Sem Telegram

**Metrica:**
- Tempo entre recepcao da mensagem e inicio do fluxo de qualificacao (alvo: <2s)
- % de mensagens que viram Lead com sucesso (alvo: >95%)
- % de Leads com campanha de origem rastreada (alvo: >60% — reconhece quem nao veio organico)

---

### 3. Qualificacao

**O que acontece:** Bot conversacional pergunta dados essenciais (nome, cidade, plano de interesse, CPF, viabilidade), verifica cobertura, apresenta planos disponiveis. Lead responde, abandona, ou e transferido pra humano quando atinge criterio configurado no fluxo (score, palavra-chave de compra, completude de dados).

**Entra:** Conversa com `modo_atendimento='bot'`, engine inicia fluxo visual vinculado ao canal (`CanalInbox.fluxo` ou fluxo default do tenant).
**Sai:**
- **Qualificado:** nodo `transferir_humano` muda `modo_atendimento` pra 'humano', distribui pra fila de vendas → estagio 4
- **Abandono temporario:** cron de recontato envia ate N mensagens de retomada; se lead volta, fluxo retoma de onde parou
- **Fora do perfil:** bot finaliza com motivo (fora_cobertura, sem_interesse, etc) → saida do funil
- **Timeout:** `tempo_limite_minutos` do fluxo estoura → finaliza como `tempo_limite`

**Papel do Hubtrix:**
- Engine de traversal do grafo, branches, validacao em cascata, IA integrada: [atendimento/engine.md](modulos/atendimento/engine.md)
- Fluxo visual configurado no editor Drawflow (11 tipos de nodos): [fluxos/nodos.md](modulos/fluxos/nodos.md)
- Viabilidade de cobertura por cidade/bairro/CEP: [comercial/viabilidade.md](modulos/comercial/viabilidade.md)
- Salvar respostas direto em campos do Lead via `salvar_em`: [atendimento/engine.md](modulos/atendimento/engine.md)
- Base de conhecimento nos fallbacks (KB consultada automaticamente quando IA falha): [fluxos/integracao-ia.md](modulos/fluxos/integracao-ia.md)
- Recontato automatico com tentativas configuraveis + mensagem IA opcional: [atendimento/recontato-automatico.md](modulos/atendimento/recontato-automatico.md)
- Sessoes observaveis em tempo real (fluxo ao vivo, logs passo a passo): [atendimento/sessoes.md](modulos/atendimento/sessoes.md)

**Estado atual:**
- ✅ 11 tipos de nodo (entrada, questao, condicao, acao, delay, finalizacao, transferir_humano, ia_classificador, ia_extrator, ia_respondedor, ia_agente)
- ✅ 4 providers IA (OpenAI, Anthropic, Groq, Google AI) com fallback cross-tenant
- ✅ Validacao em cascata (obrigatoria, opcoes, tipo, regex, IA, webhook)
- ✅ Extracao estruturada de dados via `ia_extrator` (salva no Lead ou variavel)
- ✅ Transferencia pra humano via nodo dedicado com fila de destino configuravel
- ✅ Recontato com tentativas, delays configuraveis, acao final (abandonar/transferir)
- ✅ Simulador embutido pra testar fluxo sem WhatsApp
- ⚠️ Dashboard de "funil do bot" (taxa de passagem nodo a nodo) nao existe; so log individual por sessao
- ⚠️ Sem benchmarks publicos de taxa de qualificacao/abandono — precisa cliente usar algumas semanas

**Metrica:**
- **Taxa de qualificacao:** % de Conversas que chegam no estagio 4 (transferidas pra humano com lead qualificado)
- **Tempo medio na qualificacao:** minutos entre primeira resposta do bot e transferencia
- **Taxa de abandono:** % de Conversas que param de responder durante o bot
- **Taxa de recontato bem-sucedido:** % de abandonos que voltam apos o recontato automatico

---

## CONVERSAO

### 4. Atendimento comercial

**O que acontece:** Vendedor humano assume a conversa apos o bot qualificar o lead. Conduz negociacao por WhatsApp (via Inbox) ou telefone; cria/completa oportunidade no CRM, adiciona itens (planos, produtos, SVAs), registra notas e tarefas de followup. Pode enviar proposta formal e coletar aceite de contrato.

**Entra:**
- `modo_atendimento='humano'` + conversa na fila do vendedor (auto via `distribuir_conversa` ou manual via `api_atribuir_responsavel`)
- OU oportunidade criada manualmente no CRM sem passar pelo bot (lead que ligou direto, indicacao, entrada via formulario)

**Sai:**
- **Ganho:** oportunidade movida pra estagio `is_final_ganho` → dispara estagio 5
- **Perda:** oportunidade movida pra `is_final_perdido` com `motivo_perda` e `concorrente_perdido` (se aplicavel)
- **Em aberto:** tarefa de followup agendada, oportunidade fica no pipeline aguardando

**Papel do Hubtrix:**
- Inbox com three-panel, conversa em tempo real, contexto do lead ao lado: [inbox/](modulos/inbox/)
- CRM kanban com drag-drop, oportunidade com itens, SLA por estagio: [comercial/crm/](modulos/comercial/crm/)
- Tarefas e notas vinculadas a oportunidade/lead: [comercial/crm/tarefas-notas.md](modulos/comercial/crm/tarefas-notas.md)
- Assistente CRM via WhatsApp (vendedor no celular, 15 tools): [assistente-crm/](modulos/assistente-crm/)
- Consulta HubSoft por CPF (cliente ja existe la?): [integracoes/01-HUBSOFT.md](integracoes/01-HUBSOFT.md)
- Auto-criacao de oportunidade quando lead qualifica: [comercial/crm/README.md](modulos/comercial/crm/README.md)

**Estado atual:**
- ✅ Inbox com fila por equipe, distribuicao automatica (round-robin/menor carga), respostas rapidas, etiquetas
- ✅ CRM com pipeline kanban drag-drop, itens com valores, SLA por estagio, motivo de perda
- ✅ Assistente WhatsApp com 15 tools (consultar_lead, mover_oportunidade, criar_nota, marcar_ganho, etc.)
- ✅ Criacao automatica de oportunidade via signal (score ≥ 7 ou `status_api='sucesso'`)
- ✅ Equipes de vendas com visibilidade controlada (vendedor ve so suas + nao atribuidas)
- ⚠️ Geracao de proposta formal em PDF nao e nativa — depende de template externo ou N8N
- ⚠️ Aceite de contrato via WhatsApp direto ainda manual (landing publica funciona)
- ❌ Sem forecast baseado em probabilidade do estagio

**Metrica:**
- Taxa de conversao (% de oportunidades no estagio 4 que chegam ao 5)
- Tempo medio no estagio (alerta se > SLA configurado)
- Valor medio de ticket

---

### 5. Fechamento

**O que acontece:** Cliente aceitou proposta. Oportunidade vai pra estagio `is_final_ganho` no CRM e dispara a integracao com o ERP configurado no tenant pra criar o contrato. Documentos do lead (selfie, doc frente/verso) ja deveriam estar coletados e validados nesse ponto.

**Entra:** oportunidade movida pra estagio ganho — manual pelo vendedor OU automatico via signal `verificar_conversao_historico` (quando `HistoricoContato.converteu_venda=True`)

**Sai:**
- **Sucesso:** ERP confirma criacao do contrato via webhook → `contrato_<erp>_id` preenchido na oportunidade → dispara estagio 6
- **Falha:** ERP rejeita (CPF duplicado, dados invalidos, endereco sem cobertura) → alerta no sistema, vendedor resolve e retenta

**Papel do Hubtrix:**
- Signal `on_oportunidade_movida` detecta transicao pra estagio ganho: [marketing/automacoes/signals.md](modulos/marketing/automacoes/signals.md)
- Dispatcher seleciona servico ERP por `tenant.erp_ativo`: [secao C acima](#c-como-os-modulos-se-conectam)
- Servico ERP especifico (hubsoft/sgp/ixc/mk) chama API do ERP ou dispara workflow N8N
- Webhook inbound `/webhook/<erp>/contrato/` recebe confirmacao e preenche `contrato_<erp>_id`: [comercial/crm/oportunidades.md](modulos/comercial/crm/oportunidades.md)
- Aceite digital com IP e timestamp (landing publica): [comercial/cadastro.md](modulos/comercial/cadastro.md)

**Estado atual:**
- ✅ Signal detecta mudanca pra estagio ganho
- ✅ Integracao HubSoft via N8N funcionando (criacao de cliente e contrato)
- ✅ Webhook de retorno preenche `contrato_hubsoft_id`
- ✅ Aceite digital com registro de IP
- ❌ Integracao SGP ainda nao implementada (proximo ERP prioritario)
- ❌ Integracao IXC/MK nao implementada
- ❌ Sem retry automatico ou fila de reenvio quando ERP falha
- ❌ Dashboard de integracoes ERP (quantas passaram, quantas falharam) inexistente

**Metrica:**
- Taxa de sucesso de integracao ERP (% de ganhos que viram contrato sem intervencao manual)
- Tempo entre "ganho" e "contrato criado no ERP" (alvo: < 10 min)
- Volume de retries manuais por semana

---

### 6. Ativacao

**O que acontece:** Contrato existe no ERP. Equipe tecnica do ISP agenda instalacao (se fibra), vai no endereco, instala equipamento, ativa o plano. Cliente passa a ter internet funcionando. No Hubtrix, o registro `Cliente` nasce no espelho do ERP e comeca a ser sincronizado.

**Entra:** webhook do ERP confirmando criacao do contrato; payload inclui dados do cliente ativo, plano, data de instalacao agendada.

**Sai:** cliente operacional, sync periodico do espelho inicia (Core 15min / Contratual 1h / Historico diario) → ciclo de Fidelizacao comeca.

**Papel do Hubtrix:**
- Cria novo model `Cliente` no espelho (ainda nao existe — ver [D.4](#d-principios-do-produto))
- Vincula `Cliente` a Oportunidade vencida e Lead original
- Inicia sync periodico via cron por tenant, respeitando camadas de frequencia: [secao C acima](#c-como-os-modulos-se-conectam)
- Notifica vendedor e equipe CS que cliente virou ativo
- Atualiza dashboard do CRM com status "cliente"

**Estado atual:**
- ⚠️ Model `Cliente` pendente — arquitetura definida na secao D, codigo nao escrito
- ⚠️ Sync em 3 camadas pendente — especificacao pronta, cron nao existe
- ✅ Webhook do HubSoft ja preenche `contrato_hubsoft_id` na oportunidade (proxy rudimentar de "cliente ativo")
- ❌ Dashboard "meus clientes ativos" vs "minhas oportunidades" nao existe
- ❌ Notificacao automatica pra CS quando cliente ativa nao existe
- ❌ Tracking de instalacao (agendada / em andamento / concluida) nao existe

**Metrica:**
- Tempo entre "contrato criado no ERP" e "primeiro sync do Cliente completo" (alvo: < 30 min)
- % de oportunidades ganhas que completam a ativacao (alguns cancelam antes de instalar)
- Taxa de sucesso da primeira sincronizacao

## FIDELIZACAO

### 7. Onboarding

**O que acontece:** Primeiros 30 dias do cliente. Recebe mensagem de boas-vindas, aprende a pagar, entra no Clube (cadastro + OTP + primeiro giro da roleta), descobre parceiros e cupons, recebe codigo pra indicar amigos. Objetivo: experiencia inicial positiva reduz churn nos primeiros 90 dias.

**Entra:** `Cliente` criado no espelho do ERP (estagio 6 completo), evento `cliente_criado` (ou `venda_aprovada`) dispara automacao de onboarding.
**Sai:** cliente operando normal, passado o periodo de adaptacao → estagio 8.

**Papel do Hubtrix:**
- Automacao dispara regua de boas-vindas (mensagens sequenciadas com delay): [marketing/automacoes/](modulos/marketing/automacoes/)
- Clube completo com gamificacao, roleta, missoes: [cs/clube/](modulos/cs/clube/)
- Cadastro de membro com OTP WhatsApp: [cs/clube/area-membro.md](modulos/cs/clube/area-membro.md)
- Parceiros + cupons com regras de resgate (pontos/nivel): [cs/parceiros.md](modulos/cs/parceiros.md)
- Indicacao com codigo automatico e pagina publica: [cs/indicacoes.md](modulos/cs/indicacoes.md)
- Carteirinha digital com regras de atribuicao: [cs/carteirinha.md](modulos/cs/carteirinha.md)

**Estado atual:**
- ✅ Clube completo: 10 models, RegraPontuacao, ExtratoPontuacao (ledger imutavel), niveis dinamicos, roleta com restricao geografica
- ✅ OTP WhatsApp via N8N (gerar codigo + enviar + validar + atribuir pontos)
- ✅ Parceiros + cupons com aprovacao, estoque, modalidade (gratuito/pontos/nivel)
- ✅ Programa de indicacao: codigo automatico, pagina publica personalizada, pontos ao converter
- ✅ Carteirinha digital com regras (por nivel/XP/cidade/todos)
- ⚠️ Evento `venda_aprovada` existe no model de automacao mas signal nao esta implementado — regua de boas-vindas precisa ser disparada manualmente hoje
- ⚠️ Nao tem evento `cliente_criado` ou `cliente_ativado` — depende do model `Cliente` ainda pendente (ver D.4)
- ❌ Dashboard de "saude do onboarding" (% que fez cadastro no Clube, primeiro giro, leu a regua) nao existe

**Metrica:**
- % de clientes novos que cadastraram no Clube em 7 dias
- % que fizeram primeiro giro na roleta
- % que completaram a regua de boas-vindas (respondeu ou interagiu com pelo menos N mensagens)

---

### 8. Relacionamento continuo

**O que acontece:** Cliente usa o servico. Abre ticket quando tem problema tecnico, responde pesquisa NPS, interage via WhatsApp, resgata cupons, acumula pontos. ISP envia comunicados pontuais (manutencao, novidades, campanhas). Estado estavel entre onboarding e ou retencao, ou recompra.

**Entra:** cliente operacional pos-onboarding.
**Sai:**
- Engajado e feliz → continua no estagio, alimenta estagio 10 com indicacoes/upsell
- Sinais de churn detectados → estagio 9 (Retencao)
- Cliente cancela direto → saida do funil

**Papel do Hubtrix:**
- Inbox recebe mensagens do cliente ativo (mesmos canais, vinculado a `Cliente` pos-venda): [inbox/](modulos/inbox/)
- Suporte: tickets com SLA por plano, timeline com comentarios, integracao com Inbox: [suporte/](modulos/suporte/)
- NPS: pesquisa de satisfacao (stub — models prontos, execucao pendente): [cs/nps.md](modulos/cs/nps.md)
- Clube: engajamento continuo (giros, missoes, indicacoes, resgates)
- Automacoes por evento (`mensagem_recebida`, `conversa_aberta`, `conversa_resolvida`, `cliente_aniversario`): [marketing/automacoes/](modulos/marketing/automacoes/)

**Estado atual:**
- ✅ Inbox multi-canal com fila, distribuicao, respostas rapidas, etiquetas, notas internas
- ✅ Suporte com 4 models, dashboard com KPIs, SLA breach destacado, integracao 1:1 com Inbox
- ✅ Clube engajamento continuo (roleta, missoes configuraveis, resgates, extrato)
- ✅ Automacoes com 14 eventos gatilho (signals + cron) e 8 tipos de acao
- ⚠️ NPS em stub: models ConfiguracaoNPS/PesquisaNPS existem; falta service de envio, cron periodico, views de dashboard
- ⚠️ Evento `cliente_aniversario` esta definido no model mas sem cron implementado
- ❌ Tracking de "ultimo uso" do servico (indicador de engajamento) — depende de dado do ERP via espelho
- ❌ Dashboard de saude por cliente consolidado (NPS + tickets + inadimplencia + uso) nao existe

**Metrica:**
- NPS medio do tenant (quando feature NPS rodar)
- Tickets abertos por cliente por mes
- % de clientes que resgatam cupons
- Engagement rate no Clube (giros/mes, missoes concluidas)

---

### 9. Retencao

**O que acontece:** Sistema detecta sinais de que cliente pode cancelar (contrato expirando, inadimplencia, downgrade, reclamacao recorrente, queda no uso). Cria AlertaRetencao classificado por nivel de risco. Time de CS age: liga, oferece beneficio, resolve o problema. Alvo: evitar churn antes que o cliente formalize o cancelamento.

**Entra:**
- Scanner automatico detecta sinal (contratos expirando no ERP, HistoricoContato com reclamacao, outros sinais do espelho)
- OU CS marca cliente como "em risco" manualmente

**Sai:**
- **Retido:** problema tratado → volta pro estagio 8
- **Churn confirmado:** cliente cancelou → saida do funil

**Papel do Hubtrix:**
- `AlertaRetencao` no CRM com 7 tipos e 4 niveis de risco: [comercial/crm/retencao.md](modulos/comercial/crm/retencao.md)
- Scanner automatico via `api_scanner_retencao`: [comercial/crm/retencao.md](modulos/comercial/crm/retencao.md)
- Fluxo de tratamento do alerta (novo → em_tratamento → resolvido/perdido)
- apps/cs/retencao/ como modulo dedicado de CS (stub): [cs/retencao.md](modulos/cs/retencao.md)
- Automacao pode disparar regua de reengajamento (evento `cliente_aniversario`, `lead_sem_contato` adaptavel)

**Estado atual:**
- ✅ `AlertaRetencao` com 7 tipos (contrato_expirando, inadimplencia, plano_downgradado, sem_uso, reclamacao, upgrade_disponivel, aniversario_contrato), 4 niveis de risco, score 0-100
- ✅ Scanner de contratos expirando (≤30d critico/90, ≤60 alto/70, ≤90 medio/50)
- ✅ Tela de gestao agrupada por nivel, acoes tratar/resolver
- ⚠️ apps/cs/retencao/ em stub (ScoreCliente, AlertaChurn, AcaoRetencao) — models criados, views/services pendentes
- ❌ Scanner so olha contratos expirando; outros sinais (inadimplencia ativa, uso baixo) dependem do espelho completo (estagio 6 pendente)
- ❌ Score de churn holistico combinando multiplos fatores (NPS + inadimplencia + uso + tickets) nao existe
- ❌ Jornada automatizada de retencao (regua de reengajamento por nivel de risco) nao configurada

**Metrica:**
- Taxa de retencao (% de alertas que viram resolvido vs perdido)
- Tempo medio ate tratar alerta critico (alvo: < 24h)
- Churn mensal por tenant

## EXPANSAO

### 10. Indicacao / Upsell / Expansao

**O que acontece:** Cliente satisfeito vira vetor de crescimento do ISP. Tres caminhos:

- **Indicacao** — cliente compartilha codigo pessoal com amigo/familiar; se converter, indicador ganha pontos no Clube
- **Upsell** — Hubtrix detecta oportunidade de upgrade de plano ou venda de SVA (servico adicional); vendedor ou automacao aborda
- **Expansao geografica** — cliente se muda pra outra cidade/endereco; se estiver na area de cobertura, gera novo contrato

**Entra:** cliente engajado no estagio 8, ou retido com sucesso no 9. Gatilho varia por caminho:

- Indicacao: iniciativa do cliente (entra na pagina publica, preenche dados do indicado)
- Upsell: alerta do CRM (`AlertaRetencao` tipo `upgrade_disponivel`) ou campanha segmentada
- Expansao: mudanca detectada no ERP (endereco) ou cliente avisa ativamente

**Sai:**
- **Indicacao convertida:** cria novo Lead → alimenta estagio 1/2 do ciclo (Aquisicao)
- **Upsell aceito:** nova `OportunidadeVenda` no CRM → estagio 4 (Atendimento comercial)
- **Expansao aceita:** novo contrato no ERP → estagio 5 (Fechamento)

**Papel do Hubtrix:**
- Indicacao: pagina publica por `codigo_indicacao`, `IndicacaoService.confirmar_conversao` credita pontos automaticamente: [cs/indicacoes.md](modulos/cs/indicacoes.md)
- Signal `indicacao_convertida` disponivel pra automacoes: [marketing/automacoes/signals.md](modulos/marketing/automacoes/signals.md)
- Alerta `upgrade_disponivel` no scanner de retencao: [comercial/crm/retencao.md](modulos/comercial/crm/retencao.md)
- Segmentos dinamicos do CRM pra campanhas de upsell segmentadas: [comercial/crm/segmentos.md](modulos/comercial/crm/segmentos.md)
- Disparo em massa por segmento como campanha de upsell/cross-sell: [marketing/segmentos.md](modulos/marketing/segmentos.md)

**Estado atual:**
- ✅ Indicacao: modelo completo, pagina publica personalizada, auto-credito de pontos via `GamificationService`
- ✅ Signal `indicacao_convertida` dispara evento pras automacoes
- ✅ Alerta `upgrade_disponivel` no scanner de retencao (identifica clientes com plano abaixo do disponivel)
- ✅ Segmentos dinamicos com rule builder + disparo em massa
- ✅ Automacoes com evento `disparo_segmento` (cron) — base pra campanhas recorrentes
- ⚠️ Upsell automatizado: infra existe, mas nao ha template pronto (cliente precisa configurar a regra)
- ❌ Dashboard de "top embaixadores" existe em CS/Indicacoes, mas sem alerta proativo pro time de CS premiar
- ❌ Cross-sell de SVAs: lista de produtos no CRM ok, mas sugestao automatica por perfil/uso do cliente nao existe
- ❌ Fluxo "cliente mudou de endereco" — nao detectado automaticamente, depende do espelho completo (estagio 6 pendente)
- ❌ ROI do programa de indicacao (valor gerado vs pontos distribuidos) nao e calculado

**Metrica:**
- Taxa de indicacao (indicacoes por cliente ativo por mes)
- Taxa de conversao de indicacao (% de indicacoes que viram venda)
- Upsell rate (% de clientes que aumentam ticket no ano)
- ROI do programa de indicacao (receita incremental / pontos distribuidos)
- % de recompra apos mudanca de endereco

### A1. Jornada do ISP usando o Hubtrix

> Pendente. Depois de A2.

---

## B. Modelo mental do usuario

> Pendente.

---

## C. Como os modulos se conectam

> Secao em construcao. Decisoes batidas ate agora:

### Integracao com ERPs

Hubtrix nao fala com um ERP "generico". Cada ERP tem seu proprio servico dedicado em `apps/integracoes/<erp>/`, com liberdade de modelar o ERP do jeito que ele e (sem interface comum forte que forca abstracao vazante).

**Topologia:**

```
Oportunidade ganha
    │
    ▼
Dispatcher por tenant.erp_ativo
    │
    ├─ hubsoft → apps/integracoes/hubsoft/  (pronto)
    ├─ sgp     → apps/integracoes/sgp/      (proximo)
    ├─ ixc     → apps/integracoes/ixc/      (futuro)
    └─ mk      → apps/integracoes/mk/       (futuro)
```

**Entrada (venda → ERP):** dispatcher encaminha payload normalizado ao servico correto; servico chama API do ERP pra criar cliente/contrato.

**Retorno (ERP → Hubtrix):**

- Webhook dedicado por ERP pra confirmacao pontual (ex: contrato criado, `contrato_<erp>_id` preenchido)
- Sync periodico em 3 camadas (ver abaixo) pra manter espelho atualizado

### Espelho do cliente ativo

Depois que a venda vira contrato no ERP, Hubtrix **mantem um espelho completo** dos dados do cliente. Espelho e **passivo**: ERP e a fonte da verdade, Hubtrix so le. Qualquer edicao de contrato/cobranca passa pelo ERP, nao pelo Hubtrix.

**Sync em 3 camadas com frequencias diferentes:**

| Camada | Conteudo | Frequencia | Justificativa |
|--------|----------|-------------|---------------|
| **Core** | Nome, contato, plano ativo, status, vencimento, inadimplencia | Cron 15min | Dashboard e alertas precisam de dado fresco |
| **Contratual** | Contratos, alteracoes de plano, mudanca de endereco | Cron 1h | Muda pouco, defasagem aceitavel |
| **Historico** | Faturas, tickets ERP, logs, consumo | Cron diario (noturno) ou on-demand | Volume alto, uso pontual |

**Regras de sync:**

- **Delta sync obrigatorio** — cada cron pega so o que mudou desde o ultimo
- **Primeira carga de tenant novo** e batch completo (pode levar horas)
- **Sem webhook primario** como caminho de sync — so webhooks pontuais em eventos criticos (contrato criado). Futuramente da pra adicionar webhook pra Core se defasagem de 15min virar problema.

### Modelo `Cliente` no Hubtrix

Novo model que surge dessa decisao: `Cliente` (distinto de `LeadProspecto`). Lead vira Cliente quando a venda fecha e o ERP confirma o contrato. Lead e "pre-venda"; Cliente e "pos-venda" espelhado do ERP.

---

## D. Principios do produto

> Secao em construcao. Principios batidos ate agora:

### 1. Hubtrix e front-office; ERP e back-office

Hubtrix cuida da jornada pre-venda (lead, atendimento, qualificacao, CRM, fechamento) e do relacionamento pos-venda (atendimento continuo, retencao, clube, indicacao). **Nao substitui o ERP** e nao assume funcoes de back-office (cobranca, provisionamento tecnico, contratacao fiscal). Hubtrix orquestra o que vem antes e ao lado do ERP.

### 2. Apos o contrato, a verdade vive no ERP

O ERP e fonte da verdade sobre o cliente ativo. Hubtrix espelha passivamente — le, exibe, analisa. Nao edita dados contratuais/fiscais fora do ERP. Quem quer mudar plano ou endereco passa pelo ERP; Hubtrix sincroniza o resultado.

### 3. Servico dedicado por ERP (sem abstracao universal)

ERPs sao muito diferentes entre si (HubSoft, SGP, IXC, MK, Voalle, ...). Forcar uma interface comum gera abstracoes vazantes e bugs sutis. Cada ERP ganha seu proprio modulo com liberdade de modelar do jeito que ele e. A "interface comum" fica so no ponto de entrada: "qual ERP este tenant usa? chama o servico correspondente."

### 4. Espelho completo, mas em camadas

Hubtrix espelha tudo do cliente ativo do ERP (contratual, faturas, tickets, historico). Mas sync e organizado em camadas: Core (15min), Contratual (1h), Historico (diario). Delta sync obrigatorio. Isso evita sobrecarga mantendo a promessa de dashboard rico sem depender de chamar o ERP toda hora.

### 5. Multi-tenant por natureza

Tudo no Hubtrix e multi-tenant. Nenhum dado vaza entre tenants. Isso e invariante, nao feature.
