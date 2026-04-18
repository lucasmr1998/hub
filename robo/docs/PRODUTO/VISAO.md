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

A jornada do consumidor atravessa **4 macro-fases** com 10 micro-estagios:

<div class="jrn-flow">
  <div class="jrn-group jrn-aquisicao">
    <div class="jrn-group-name">Aquisicao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">1</div><div class="jrn-t">Descoberta</div></div>
        <div class="jrn-m">Campanhas &middot; Indicacao</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">2</div><div class="jrn-t">Primeiro contato</div></div>
        <div class="jrn-m">Inbox &middot; Widget &middot; Cadastro</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">3</div><div class="jrn-t">Qualificacao</div></div>
        <div class="jrn-m">Atendimento &middot; Fluxos &middot; IA &middot; Viabilidade</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-conversao">
    <div class="jrn-group-name">Conversao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">4</div><div class="jrn-t">Atend. comercial</div></div>
        <div class="jrn-m">Inbox &middot; CRM &middot; Assistente</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">5</div><div class="jrn-t">Fechamento</div></div>
        <div class="jrn-m">CRM &middot; ERP (HubSoft / SGP / IXC / MK)</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">6</div><div class="jrn-t">Ativacao</div></div>
        <div class="jrn-m">Cliente &middot; Espelho do ERP</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-fidelizacao">
    <div class="jrn-group-name">Fidelizacao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">7</div><div class="jrn-t">Onboarding</div></div>
        <div class="jrn-m">Clube &middot; Automacoes &middot; Indicacao</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">8</div><div class="jrn-t">Relac. continuo</div></div>
        <div class="jrn-m">Inbox &middot; Suporte &middot; NPS &middot; Clube</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">9</div><div class="jrn-t">Retencao</div></div>
        <div class="jrn-m">CRM/Retencao &middot; Automacoes</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-expansao">
    <div class="jrn-group-name">Expansao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">10</div><div class="jrn-t">Indicacao / Upsell</div></div>
        <div class="jrn-m">Indicacao &middot; CRM &middot; Segmentos</div>
      </div>
    </div>
  </div>
</div>

Cada macro agrupa estagios detalhados. Os micro-estagios com os 5 campos (o que
acontece, como entra/sai, papel do Hubtrix, estado atual, metrica) estao mais
abaixo nesta secao.

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

Enquanto A2 e a jornada do **consumidor passando pelo funil do ISP**, A1 e a
jornada do **proprio ISP operando o Hubtrix** — do dia que descobre o produto
ate renovar ou cancelar. 4 macro-fases com 10 micro-estagios:

<div class="jrn-flow">
  <div class="jrn-group jrn-aquisicao">
    <div class="jrn-group-name">Contratacao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">1</div><div class="jrn-t">Descoberta e avaliacao</div></div>
        <div class="jrn-m">Site &middot; Materiais &middot; Indicacao</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">2</div><div class="jrn-t">Demo / trial</div></div>
        <div class="jrn-m">Tenant demo &middot; Discovery</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">3</div><div class="jrn-t">Fechamento</div></div>
        <div class="jrn-m">Contrato &middot; Pagamento &middot; Provisionamento</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-conversao">
    <div class="jrn-group-name">Ativacao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">4</div><div class="jrn-t">Provisionamento + config</div></div>
        <div class="jrn-m">Tenant &middot; Admin &middot; Branding</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">5</div><div class="jrn-t">Integracoes</div></div>
        <div class="jrn-m">ERP &middot; WhatsApp &middot; IA</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">6</div><div class="jrn-t">Onboarding do time</div></div>
        <div class="jrn-m">Treinamento &middot; Primeiros fluxos</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-fidelizacao">
    <div class="jrn-group-name">Operacao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">7</div><div class="jrn-t">Uso diario</div></div>
        <div class="jrn-m">Vendas &middot; CS &middot; Suporte</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">8</div><div class="jrn-t">Monitoramento</div></div>
        <div class="jrn-m">Dashboards &middot; Auditoria &middot; Alertas</div>
      </div>
    </div>
  </div>
  <div class="jrn-arrow">&rarr;</div>
  <div class="jrn-group jrn-expansao">
    <div class="jrn-group-name">Evolucao</div>
    <div class="jrn-cards">
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">9</div><div class="jrn-t">Expansao</div></div>
        <div class="jrn-m">Novos modulos &middot; Seats &middot; Canais</div>
      </div>
      <div class="jrn-card">
        <div class="jrn-head"><div class="jrn-n">10</div><div class="jrn-t">Renovacao ou churn</div></div>
        <div class="jrn-m">Recontratacao &middot; Saida</div>
      </div>
    </div>
  </div>
</div>

---

#### Micro-estagios da jornada do ISP

## CONTRATACAO

### 1. Descoberta e avaliacao

**O que acontece:** Dono ou diretor do ISP descobre o Hubtrix — via indicacao de outro provedor (o canal mais forte no mercado brasileiro de ISPs), conteudo em redes sociais, busca organica, participacao em feira do setor, ou abordagem direta do time comercial. Visita o site, baixa material (one-pager, deck), consome cases de outros ISPs similares.

**Entra:** iniciativa de marketing do Hubtrix, indicacao de cliente, saida ativa do time de vendas, SEO.
**Sai:** ISP demonstra interesse genuino — agenda demo, pede trial, solicita proposta → estagio 2.

**Papel do Hubtrix:**
- Site comercial com apresentacao do produto, pricing, cases, request-a-demo
- Materiais de enablement (one-pager, deck, battle card): [OPERACIONAL/materiais/apresentacao/](OPERACIONAL/materiais/apresentacao/)
- Hubtrix operando o proprio funil (dogfooding): CRM interno, Inbox, automacoes pra nutricao de leads comerciais

**Estado atual:**
- ✅ Domínio `hubtrix.com.br` reservado
- ✅ Materiais comerciais (one-pager, deck, battle card, case anonimo, scripts de venda) em [OPERACIONAL/materiais/](OPERACIONAL/materiais/)
- ⚠️ Site comercial publico ainda nao lancado
- ❌ Tenant do proprio Hubtrix operando o funil comercial interno — provavelmente nao configurado com rigor
- ❌ Sem SEO estruturado, sem conteudo de topo de funil (blog, Youtube)
- ❌ Nenhum case publico divulgavel ate o momento

**Metrica:**
- MQLs (marketing qualified leads) por mes, por canal
- Custo por MQL
- % de MQLs que chegam no estagio 2

---

### 2. Demo / trial

**O que acontece:** ISP interessado entra em conversa de discovery com o time comercial. Assiste demo guiada dos modulos que importam pra ele (atendimento + CRM + clube geralmente), em ambiente com dados populados. Faz perguntas sobre: integracao com o ERP que ele usa hoje, customizacao, preco, prazo de implementacao, treinamento do time. Time comercial qualifica se e ICP.

**Entra:** MQL agendou conversa no estagio 1.
**Sai:**
- **Qualificado:** pronto pra contratar → envio de proposta → estagio 3
- **Nao-ICP:** tenant muito pequeno, fora do perfil; perde ou entra em nutricao
- **Timing errado:** quer mas nao agora; cadastrado em regua de followup de medio prazo
- **Perda ativa:** escolheu concorrente ou decidiu nao investir agora

**Papel do Hubtrix:**
- Tenant demo pre-populado com dados ficticios mostrando o produto em uso
- Management commands pra gerar dados de teste: `seed_inbox`, seeders do CS
- Documentacao publica no `/aurora-admin/docs/` pra ISPs tecnicos que querem validar arquitetura
- Scripts de discovery e demo: [OPERACIONAL/materiais/scripts_vendas/](OPERACIONAL/materiais/scripts_vendas/)

**Estado atual:**
- ✅ Multi-tenant permite tenant demo isolado
- ✅ Management commands populam dados realistas (seed_inbox, seed de CS/clube, etc.)
- ✅ Docs tecnicas publicas navegaveis em `/aurora-admin/docs/`
- ⚠️ Processo de demo e manual e depende de presenca do time comercial
- ❌ Trial self-service (ISP cria conta e testa sozinho) nao existe
- ❌ Sandbox publico isolado (sem precisar criar tenant) nao existe
- ❌ Demo guiada interativa (tour passo a passo dentro do produto) nao existe

**Metrica:**
- Taxa de conversao MQL → proposta (estagio 2 → 3)
- Duracao media do ciclo de demo (dias entre primeiro contato e proposta)
- Motivos de perda categorizados (preco, feature, timing, concorrente)

---

### 3. Fechamento

**O que acontece:** ISP aceita a proposta, assina contrato (digital ou fisico), faz primeiro pagamento (primeiro mes ou sinal de setup). Hubtrix provisiona o tenant, cria usuario admin inicial com senha temporaria, envia e-mail de boas-vindas com credenciais e link pro dashboard.

**Entra:** proposta aprovada pelo ISP no estagio 2.
**Sai:** tenant provisionado e admin com acesso → estagio 4 (Ativacao).

**Papel do Hubtrix:**
- Template de contrato SaaS em [OPERACIONAL/materiais/juridico/contrato_saas.md](OPERACIONAL/materiais/juridico/contrato_saas.md)
- Cobranca / gestao de assinatura (hoje externo — Stripe/ASAAS/similar)
- Criacao do tenant via painel `/aurora-admin/tenants/novo/`
- Criacao de `PerfilUsuario` admin do tenant com `senha_temporaria=True` (forca troca no 1o login)
- E-mail de boas-vindas com credenciais

**Estado atual:**
- ✅ Admin cria tenant via `/aurora-admin/`
- ✅ `PerfilUsuario.senha_temporaria` + middleware forcam troca de senha no primeiro login
- ✅ Templates de contrato (SaaS, politica de privacidade, termos) em [OPERACIONAL/materiais/juridico/](OPERACIONAL/materiais/juridico/)
- ❌ Integracao com gateway de pagamento nao existe
- ❌ Geracao automatica de contrato preenchido (CNPJ, plano escolhido, recorrencia, data) nao existe
- ❌ E-mail automatico de boas-vindas apos criacao do tenant nao dispara
- ❌ Gestao de assinatura dentro do Hubtrix (upgrade, downgrade, suspensao, cancelamento) nao existe — tudo manual no banco ou por pagamento externo
- ❌ Painel do cliente Hubtrix ver/gerenciar a propria assinatura nao existe

**Metrica:**
- Taxa de fechamento (propostas → contratos assinados)
- Ticket medio inicial
- Tempo medio entre proposta e pagamento (em dias)

---

## ATIVACAO

### 4. Provisionamento + configuracao inicial

**O que acontece:** Admin do ISP recebe credenciais, faz primeiro login no Hubtrix, e **troca a senha temporaria obrigatoriamente** (middleware bloqueia qualquer outra pagina ate trocar). Depois configura o tenant: dados da empresa, branding (cores, logo), nome comercial, cria as primeiras equipes internas (vendas, suporte, CS), convida os colaboradores, atribui permissoes por perfil.

**Entra:** tenant criado + admin com `senha_temporaria=True` no estagio 3.
**Sai:** tenant com dados basicos + equipe cadastrada + permissoes distribuidas → estagio 5.

**Papel do Hubtrix:**
- Middleware que forca troca de senha temporaria no primeiro acesso
- Painel `/configuracoes/empresa/` com dados da empresa e branding
- Gestao de usuarios: criar, editar, convidar, atribuir perfil
- Criacao de equipes (CRM + Inbox)
- Sistema de permissoes granulares
- Trilha de auditoria: [core/03-PERMISSOES.md](core/03-PERMISSOES.md)

**Estado atual:**
- ✅ Middleware de senha temporaria ativo
- ✅ Painel de empresa com branding (cores, logo, nome)
- ✅ Gestao de usuarios com perfil e permissoes granulares
- ✅ Equipes com lideres, cor, membros
- ✅ Auditoria de acoes em `LogSistema` (quem fez o que, quando)
- ⚠️ Wizard de onboarding do admin ("proximos passos", checklist) nao existe
- ❌ E-mail de convite pra novos usuarios (com link de primeiro acesso) nao dispara automatico
- ❌ Import em massa de colaboradores via CSV nao existe
- ❌ Copia de configuracao de outro tenant (template) nao existe

**Metrica:**
- Tempo entre provisionamento e primeira configuracao completa (alvo: < 24h)
- % de admins que completam branding + equipe no primeiro dia
- % de tenants que ficam > 7 dias sem nenhum usuario alem do admin inicial (sinal de churn precoce)

---

### 5. Integracoes

**O que acontece:** Admin configura as integracoes externas que o Hubtrix precisa pra operar na pratica:

- **ERP** (HubSoft agora; SGP/IXC/MK futuros) — pra envio de contratos fechados e espelho de clientes ativos
- **WhatsApp** (Uazapi ou Evolution) — pro bot e Inbox receberem/enviarem mensagens
- **IA** (OpenAI / Anthropic / Groq / Google AI) — pros nodos IA nos fluxos de atendimento
- **N8N** (opcional) — workflows customizados

Testa cada uma, valida que esta funcionando. Configura webhooks do lado dos providers apontando pras URLs do tenant.

**Entra:** tenant configurado no estagio 4.
**Sai:** integracoes ativas e testadas → estagio 6.

**Papel do Hubtrix:**
- Painel de integracoes `/configuracoes/integracoes/`
- Encriptacao de API keys com Fernet (chave em env var)
- Providers WhatsApp com interface comum: [integracoes/02-INTEGRACOES.md](integracoes/02-INTEGRACOES.md)
- Providers IA via `apps/integracoes/providers/`
- Integracao HubSoft especifica: [integracoes/01-HUBSOFT.md](integracoes/01-HUBSOFT.md)
- Webhook URLs fornecidas pra cada integracao configurar no lado do provider

**Estado atual:**
- ✅ Painel CRUD de integracoes
- ✅ Encriptacao de API keys / tokens via Fernet
- ✅ Providers WhatsApp (Uazapi, Evolution)
- ✅ Providers IA (4 providers) com fallback cross-tenant para Assistente CRM
- ✅ HubSoft com cliente HTTP + webhook inbound `/webhook/hubsoft/contrato/`
- ⚠️ Teste de conexao por integracao (botao "Testar") inconsistente entre providers
- ⚠️ Erros de integracao sao opacos (token errado → atendimento nao dispara, mas diagnostico e manual via logs)
- ❌ SGP / IXC / MK ainda nao implementados (ver [secao C](#c-como-os-modulos-se-conectam))
- ❌ Wizard guiado "primeira integracao" passo a passo nao existe
- ❌ Health check consolidado (painel mostrando status de todas as integracoes do tenant) nao existe

**Metrica:**
- % de tenants com ERP + WhatsApp + IA configurados no primeiro dia
- Taxa de falha nos testes de conexao iniciais
- Tempo medio pra primeira integracao funcional

---

### 6. Onboarding do time

**O que acontece:** Admin chama os colaboradores do ISP pra comecar a usar o Hubtrix no dia a dia. Pode acontecer via treinamento ao vivo conduzido pelo time comercial/CS do Hubtrix, videos, documentacao, ou o ISP se vira sozinho. Criam os primeiros fluxos de atendimento (aproveitando templates ou do zero), testam o simulador, configuram o primeiro canal de Inbox, fazem o primeiro atendimento real.

**Entra:** tenant com integracoes ativas no estagio 5.
**Sai:** equipe operacional, primeiros atendimentos reais acontecendo → estagio 7 (Uso diario).

**Papel do Hubtrix:**
- Editor visual de fluxos com simulador embutido: [modulos/fluxos/editor-visual.md](modulos/fluxos/editor-visual.md)
- Materiais de treinamento de parceiro (5 modulos): [OPERACIONAL/materiais/treinamento_parceiro/](OPERACIONAL/materiais/treinamento_parceiro/)
- Docs publicas por modulo em `/aurora-admin/docs/`
- Simulador de atendimento pra testar fluxo sem WhatsApp real: [modulos/atendimento/simulador.md](modulos/atendimento/simulador.md)
- Management commands de seed de dados pra explorar produto com exemplos realistas

**Estado atual:**
- ✅ Editor visual de fluxos (11 tipos de nodos, Drawflow) com simulador embutido
- ✅ Materiais de treinamento completos (5 modulos: visao geral, comercial, marketing/CS, precificacao/ROI, objecoes/fechamento)
- ✅ Docs publicas navegaveis com accordion e busca
- ✅ Seeders de dados (seed_inbox e equivalentes)
- ⚠️ Fluxos-template pre-configurados existem como seeder, mas UX pra "clonar template" dentro do painel nao esta claro
- ❌ Tour interativo guiado dentro do produto ("seu primeiro fluxo em 5 min") nao existe
- ❌ Videos de treinamento embutidos no painel do admin nao existem
- ❌ Checklist visual de onboarding ("seu tenant esta 80% pronto, faltam X passos") nao existe
- ❌ Certificacao do time (comprovacao de que colaboradores concluiram treinamento) nao existe

**Metrica:**
- Tempo entre integracao ativa e primeiro atendimento real (alvo: < 7 dias)
- % de tenants que completam onboarding em < 30 dias
- % de tenants que abandonam na ativacao (contratou mas nunca comecou a usar — metrica de churn precoce)
- Numero de fluxos criados no primeiro mes

---

## OPERACAO

### 7. Uso diario

**O que acontece:** Dia a dia da equipe do ISP dentro do Hubtrix. Vendedor abre o painel pela manha, ve tarefas pendentes no CRM, pega conversas novas no Inbox (transferidas pelo bot ou redirecionadas da fila), faz follow-ups, move oportunidades no pipeline, fecha contratos. Time de CS atende tickets de suporte, monitora NPS, gerencia o Clube (roleta, pontos, cupons, indicacoes). Marketing configura automacoes e segmentos. Em paralelo, o bot esta rodando atendendo novos leads no WhatsApp (A2).

**Entra:** tenant operacional pos-onboarding (estagio 6).
**Sai:** operacao estavel; cicla em paralelo com Monitoramento (estagio 8) e eventualmente dispara Evolucao (estagio 9).

**Papel do Hubtrix:**
- CRM com pipeline kanban, oportunidades, tarefas, notas: [comercial/crm/](modulos/comercial/crm/)
- Inbox three-panel multi-canal: [inbox/](modulos/inbox/)
- Assistente CRM via WhatsApp pra operar pelo celular: [assistente-crm/](modulos/assistente-crm/)
- Engine de atendimento rodando em background: [atendimento/](modulos/atendimento/)
- Automacoes processando signals e cron: [marketing/automacoes/](modulos/marketing/automacoes/)
- Clube operando (giros, resgates, indicacoes): [cs/clube/](modulos/cs/clube/)
- Suporte recebendo tickets: [suporte/](modulos/suporte/)
- Integracao com ERP sincronizando cliente ativo (apos implementacao do espelho em C)

**Estado atual:**
- ✅ Todos os modulos funcionais e em uso (comercial, inbox, atendimento, automacoes, cs, suporte)
- ✅ Assistente CRM via WhatsApp com 15 tools
- ✅ Auditoria completa (LogSistema) de quem fez o que
- ✅ Permissoes granulares garantindo que cada funcao ve o que deve
- ⚠️ Espelho do cliente ativo pos-venda ainda pendente (secao C)
- ⚠️ Mobile experience limitada fora do Assistente (painel web nao foi otimizado pra mobile)
- ❌ Dashboard "home do tenant" unificado (KPIs de todos os modulos numa tela) nao existe
- ❌ "Modo foco" do vendedor (abrir e ja ter tudo pra trabalhar — proxima tarefa, proxima conversa, proxima oportunidade a avancar) nao existe — o vendedor precisa navegar modulo por modulo

**Metrica:**
- DAU / MAU por tenant
- Tempo medio de sessao por tipo de usuario (vendedor / CS / admin)
- Acoes por usuario por dia (conversas, oportunidades, tarefas concluidas)
- Taxa de uso por modulo (% de tenants que usam Inbox / CRM / Clube / automacoes)
- Numero de tenants com "atividade zero" em 7 dias (sinal de churn iminente)

---

### 8. Monitoramento e administracao

**O que acontece:** Admin do ISP monitora a saude geral da operacao — funil de vendas, NPS, tickets abertos, SLA, uso do Clube, qualidade do atendimento pelo bot. Ajusta configuracoes (pipelines, estagios, SLAs, regras de automacao, equipes, permissoes). Audita acoes do time. Adiciona/remove colaboradores. Decide mudancas que eventualmente viram Evolucao (estagio 9).

**Entra:** operacao diaria em curso (estagio 7).
**Sai:** ajustes configurados voltam pra operacao OU dispara um pedido de expansao/mudanca → estagio 9.

**Papel do Hubtrix:**
- Dashboards por modulo: [comercial/crm/](modulos/comercial/crm/) (pipeline, desempenho, metas, retencao), [inbox/interface.md](modulos/inbox/interface.md), [suporte/](modulos/suporte/), [cs/clube/](modulos/cs/clube/)
- Configuracoes por area (CRM, Inbox, cadastro, cs/clube, automacoes, integracoes)
- Auditoria `LogSistema` por categoria: [core/03-PERMISSOES.md](core/03-PERMISSOES.md)
- Gestao de usuarios, equipes e permissoes granulares
- Relatorios exportaveis (CSV em varios modulos)

**Estado atual:**
- ✅ Dashboards por modulo (pipeline, desempenho, metas, retencao, inbox, suporte, clube)
- ✅ LogSistema por categoria (auth, crm, inbox, suporte, cs, marketing, config, admin, integracao, sistema)
- ✅ Gestao de usuarios + equipes + permissoes granulares
- ✅ Exportacao CSV em varios modulos
- ⚠️ Dashboard unificado do tenant (KPIs agregados de todos os modulos) nao existe
- ⚠️ Alertas automaticos pro admin (SLA sistemico em breach, falha em integracao, lead parado ha > N dias) limitados ou inexistentes
- ❌ Insights acionaveis ("30% dos seus leads ficaram sem resposta nos ultimos 7 dias — abra essa conversa") nao existem
- ❌ Exportacao consolidada em PDF pra stakeholders (diretor, socio) nao existe
- ❌ Benchmarking contra outros tenants (de forma anonima) nao existe
- ❌ Health score do tenant ("voce esta usando 60% do potencial — eis onde ganhar os 40%") nao existe

**Metrica:**
- Frequencia com que admin acessa dashboards por semana
- Numero de configuracoes ajustadas por mes (sinal de operacao ativa vs passiva)
- Tempo medio entre alerta critico e acao tomada
- % de admins que visualizam dashboard semanalmente (engajamento de nivel executivo)

---

## EVOLUCAO

### 9. Expansao

**O que acontece:** Apos alguns meses operando, o ISP quer crescer o uso do Hubtrix. Quatro vetores possiveis:

- **Novos modulos:** comecou no starter com Inbox+CRM, agora quer CS (Clube), Marketing (automacoes) ou Suporte
- **Mais seats:** time cresceu, precisa de mais usuarios
- **Novos canais:** comecou so WhatsApp, agora quer widget no site, Instagram, Telegram
- **Upgrade de plano:** sobe de Starter → Pro pra liberar features bloqueadas (automacoes, assistente IA, clube completo)

**Entra:** operacao diaria estavel (estagios 7-8), ISP identifica oportunidade ou necessidade de crescer.
**Sai:**
- Novo modulo ou feature ativado → volta pra operacao (estagio 7)
- Contrato ampliado → pode precisar de ativacao de integracao extra (estagio 5)

**Papel do Hubtrix:**
- Sistema de planos + `FeaturePlano` (gate por plano): [core/03-PERMISSOES.md](core/03-PERMISSOES.md)
- Aurora Admin habilita/desabilita modulos por tenant: `/aurora-admin/tenants/<id>/`
- Gateway de pagamento pra upgrade self-service (pendente — ver insight D)
- CS do Hubtrix consultivo pra planejar expansao
- Dados de uso apontando oportunidades ("voce atendeu 500 conversas mes passado — plano Pro libera automacao que economizaria N horas")

**Estado atual:**
- ✅ Sistema de planos + `FeaturePlano` funcional
- ✅ Aurora Admin libera/bloqueia modulos por tenant
- ⚠️ Ativacao de novo modulo e manual (operador Hubtrix libera — nao e self-service)
- ❌ Self-service de upgrade de plano nao existe (precisa contactar o time)
- ❌ Upsell proativo baseado em uso nao existe
- ❌ Dashboard "o que voce esta deixando de usar no seu plano" (features disponiveis mas subutilizadas) nao existe
- ❌ Billing / cobranca do novo modulo integrada (ver [gestao_assinatura_interna](../context/tarefas/backlog/gestao_assinatura_interna_17-04-2026.md))

**Metrica:**
- Taxa de expansao (% de tenants que expandem no primeiro ano)
- Ticket medio por tenant (crescimento)
- **Net Revenue Retention (NRR)** — receita que cresce no mesmo cliente; alvo > 110% pra SaaS saudavel
- Tempo medio entre contratacao e primeira expansao

---

### 10. Renovacao ou churn

**O que acontece:** Fim do ciclo contratual (anual ou mensal conforme plano). ISP decide renovar ou cancelar. Sinais de churn idealmente foram detectados cedo (baixa adocao, tickets nao resolvidos, NPS baixo) pra que CS do Hubtrix agisse antes. Se renova, ciclo reinicia com possivel expansao; se cancela, executa offboarding (export de dados, encerra tenant).

**Entra:** aproximacao do fim do periodo contratual OU sinais precoces de churn.
**Sai:**
- **Renovacao:** ciclo reinicia (pode combinar com expansao)
- **Churn:** offboarding, tenant encerrado, dados exportados

**Papel do Hubtrix:**
- Health score de tenants (para time Hubtrix identificar risco)
- CS do Hubtrix monitora e age preventivamente
- Processo de offboarding com export LGPD-compliant
- NPS do proprio Hubtrix com tenants (feedback dos ISPs)
- Regua automatizada de retencao pro tenant ativo quando sinal de churn

**Estado atual:**
- ⚠️ Monitoramento de health dos tenants e manual — nao existe dashboard automatico pro time Hubtrix
- ❌ Health score automatizado dos tenants (combinando uso, NPS, tickets, adesao) nao existe
- ❌ NPS dos tenants (pesquisa do Hubtrix com os ISPs) nao existe
- ❌ Regua automatizada de reengajamento de tenant em risco nao existe
- ❌ Offboarding formalizado: export de dados do tenant, encerramento tecnico, retencao legal de contratos, LGPD — nao formalizado
- ❌ Benchmarking interno ("tenant X usa 40% do que tenants de mesmo porte usam") nao existe
- ❌ Saida do usuario (admin Hubtrix cancelando um tenant) nao tem fluxo claro no sistema

**Metrica:**
- **Taxa de renovacao** (alvo: > 90% no B2B SaaS nicho)
- **Churn rate mensal / anual**
- **Net Revenue Retention** (já citado no 9)
- Motivos de churn categorizados (preco / produto / operacional / concorrente / fim de negocio)
- Tempo medio entre primeiro sinal de churn e acao do CS do Hubtrix
- % de tenants cujo offboarding e concluido corretamente (dados exportados, docs mantidos)

---

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

## Insights e lacunas estrategicas

> Observacoes que surgem durante o detalhamento das jornadas e que merecem
> virar acao. Cada item com link pra tarefa no backlog (se aplicavel).

### De A1 — Contratacao

**Contratacao e a fase mais imatura do Hubtrix** — 9 `❌` entre os 3 estagios iniciais. Foco historico foi o produto pro cliente final (A2), nao a operacao comercial do proprio Hubtrix. As lacunas especificas ja estao listadas no "Estado atual" de cada estagio. As 3 acoes derivadas:

| Insight | Acao | Backlog |
|---------|------|---------|
| Site comercial publico nao existe | Criar site Hubtrix com SEO e request-a-demo | [site_comercial_hubtrix_17-04-2026.md](../context/tarefas/backlog/site_comercial_hubtrix_17-04-2026.md) |
| Hubtrix nao usa o proprio produto pra gerenciar seu funil B2B | Dogfooding do funil interno | [dogfooding_funil_interno_17-04-2026.md](../context/tarefas/backlog/dogfooding_funil_interno_17-04-2026.md) |
| Gestao de assinatura (cobranca, upgrade, suspensao) fora do Hubtrix | Modulo proprio de assinatura | [gestao_assinatura_interna_17-04-2026.md](../context/tarefas/backlog/gestao_assinatura_interna_17-04-2026.md) |

### De A1 — Operacao

| Insight | Acao | Backlog |
|---------|------|---------|
| Todos os perfis veem todos os dashboards (UX ruim + problema de permissao). Admin precisa percorrer 5+ modulos pra avaliar saude do tenant. Sem insights proativos | Home personalizada por perfil + dashboard unificado do admin + insights acionaveis | [home_personalizada_por_perfil_17-04-2026.md](../context/tarefas/backlog/home_personalizada_por_perfil_17-04-2026.md) |

### De A1 — Evolucao

| Insight | Acao | Backlog |
|---------|------|---------|
| Time Hubtrix nao tem ferramentas pra operar a propria base de tenants com maturidade (health score / NPS / self-service de upgrade / offboarding LGPD) | Modulo de operacao interna do Hubtrix — 4 capacidades agrupadas | [operacao_interna_hubtrix_17-04-2026.md](../context/tarefas/backlog/operacao_interna_hubtrix_17-04-2026.md) |

### De A2 — Jornada do consumidor

A2 mostrou 5 padroes transversais que aparecem em multiplos estagios:

| Insight | Acao | Backlog |
|---------|------|---------|
| Analytics/dashboards faltantes em quase todo estagio (funil do bot, integracoes ERP, saude do onboarding, ROI de indicacao, saude por cliente) | Projeto de dashboards e observabilidade da jornada | [dashboards_jornada_consumidor_17-04-2026.md](../context/tarefas/backlog/dashboards_jornada_consumidor_17-04-2026.md) |
| Canais de captura limitados — so WhatsApp e widget nativamente; Instagram DM, Messenger, Telegram, telefonia sao gaps | Expansao de canais inbound | [expansao_canais_inbound_17-04-2026.md](../context/tarefas/backlog/expansao_canais_inbound_17-04-2026.md) |
| Infra de fluxo/regua/segmento pronta, mas cliente sempre comeca do zero — onboarding lento e muito trabalho manual | Biblioteca de templates prontos (fluxos + reguas + segmentos) | [biblioteca_templates_17-04-2026.md](../context/tarefas/backlog/biblioteca_templates_17-04-2026.md) |
| Integracao ERP sem retry, fila ou monitoramento — falha fica invisivel ate cliente reclamar | Resiliencia em integracoes ERP (retry, fila, dashboard) | [resiliencia_integracoes_erp_17-04-2026.md](../context/tarefas/backlog/resiliencia_integracoes_erp_17-04-2026.md) |
| Model `Cliente` pendente bloqueia varios estagios pos-venda (6-10) | Ja documentado na secao C/D (arquitetura batida, falta implementacao) | — |

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
