# Relatório de Implementações — Robô de Vendas V2 (HubSoft)

**Data:** 07/07/2026
**Escopo:** Novo pipeline de Indicações, controle de acesso por perfil (RBAC),
notificações personalizadas, manual do usuário, central de mensagens configurável,
reengajamento por tempo de espera, retomada de atendimento, viabilidade por cidade
inteira e uma leva de correções de qualidade do fluxo conversacional.
**Ambiente:** PRODUÇÃO (HubSoft sem sandbox) — banco isolado `robovendas_v2`.
**Período coberto:** desde a rodada de 24/06/2026.

---

## Sumário executivo

Nesta fase o Robô V2 evoluiu de "ciclo de vendas automatizado" para uma **plataforma
comercial completa e configurável pela própria equipe**. Entregas principais:

1. **Pipeline de Indicações** operado por pessoas (funil manual ponta a ponta).
2. **Permissões por perfil (RBAC)** + **notificações personalizadas** por permissão.
3. **Manual do usuário** embutido (Central de Ajuda por perfil).
4. **Central de Mensagens do Robô** — a equipe edita os textos do WhatsApp sem deploy.
5. **Reengajamento por tempo de espera** (recontato escalonado).
6. **Retomada de atendimento** (continuar / recomeçar / outro CPF).
7. **Viabilidade por cidade inteira** + transbordo correto quando não há cobertura.
8. **Correções de qualidade** do fluxo (cliente inativo, endereço do novo serviço,
   menu de upgrade condicional, nome quebrado, confirmação vazia, "outro CPF").

Tudo validado ponta a ponta. **7 serviços** systemd do V2 ativos.

---

## 1. Pipeline de Indicações (operado por pessoas)

**Objetivo:** um funil 100% manual onde operadores cadastram indicações, completam os
dados, convertem em cliente e abrem atendimento/O.S.

**Entregue:**
- Novo tipo de pipeline **`indicacao`** com estágios próprios e **tags específicas**.
- Lead de indicação nasce com `canal_entrada='indicacao'` e guarda o **código do
  indicador** (`LeadProspecto.id_indicador`).
- Painel do operador em **modal centralizado** com as ações: criar lead, completar
  dados (formulário com **dia de vencimento em opções**, não digitado), **converter em
  cliente** (cria prospecto → cliente no HubSoft) e **abrir atendimento + O.S.**
- **Gate de contrato:** a abertura de atendimento/O.S. só libera quando o **status do
  contrato está "aceito"** (o próprio cliente aceita no app; o sistema **monitora**).
- Endpoints: `api_indicacao_criar`, `api_lead_editar`, `api_indicacao_converter`,
  `api_indicacao_agendar`, `api_indicacao_contrato_status`.

**Arquivos:** `crm/views.py`, `crm/models.py` (MensagemPipeline, choices),
`vendas_web/models.py` (id_indicador), migrations crm 0007–0010.

---

## 2. Permissões por perfil (RBAC) + Notificações personalizadas

**Objetivo:** controlar o que cada tipo de usuário vê e opera, e notificar cada um
conforme sua permissão.

**Entregue:**
- **5 perfis** (Administrador, Gerente, Operador, Vendedor, Auditor) com **matriz
  configurável** (catálogo de capacidades Ver/Operar) + **escopo de dados** (todos /
  pipeline / próprios). Tela em Administração → Perfis de Acesso.
- Enforcement: context processor (`cap` em todo template), decorator `@requer_cap`
  nas views/endpoints (403 para API, redirect para páginas), menu e abas de pipeline
  filtrados por permissão, escopo aplicado nas listas.
- **Notificações personalizadas** por permissão: novas entradas nos pipelines, marcos
  (conversão, O.S.), falhas (para gerentes) e atribuições (para o responsável).
  Reativada a criação de `Notificacao` (por-usuário) que já existia modelada.
- **Badges de contagem** por aba de pipeline (quantidade de oportunidades por funil).

**Arquivos:** `vendas_web/rbac.py`, `vendas_web/notificacoes_service.py`,
`vendas_web/models.py` (PerfilAcesso), `crm/views.py`, `crm/signals.py`,
migrations vendas_web 0060–0061.

---

## 3. Manual do usuário (Central de Ajuda)

**Entregue:** Central de Ajuda embutida com **6 guias dinâmicos por perfil**
(Administrador, Gerente, Operador, Vendedor, Auditor e "Como o Robô Atende no
WhatsApp"), com passo a passo e UI/UX lúdica. O guia certo é sugerido conforme o
perfil RBAC do usuário logado.

**Arquivos:** `vendas_web/views_notificacoes_v2.py` (GUIAS),
`vendas_web/templates/vendas_web/ajuda/*.html`.

---

## 4. Central de Mensagens do Robô (personalização sem deploy)

**Objetivo:** a equipe editar tudo que o robô escreve no WhatsApp, direto na ferramenta.

**Entregue:**
- Nova aba **"Mensagens do Robô"** (Configurações), agrupada: boas-vindas & coleta,
  confirmações & respostas, menu, recontato, retomada.
- Modelo `MensagemRobo` (chave→texto) lido pelo engine com **cache + invalidação** —
  a alteração vale **na hora**, sem reiniciar serviço. **20 mensagens** já editáveis.
- **Confirmações/erros por pergunta** (msg_sucesso/msg_erro das regras) também
  editáveis na mesma aba.
- **Fallback seguro:** mensagem em branco faz o robô usar o texto padrão embutido —
  e, para a **confirmação de resposta**, **vazio agora significa "não enviar nada"**
  (antes mandava "Anotei!").
- Guardas: mensagens com opções (ex.: retomada) exigem manter os números 1/2/3.

**Arquivos:** `ia_validador/models.py` (MensagemRobo), `ia_validador/views.py`
(+ endpoint), `ia_validacao/src/regras/mensagens_client.py`,
`ia_validacao/src/onboarding.py`, `crm/views.py` + `crm/templates/crm/mensagens_robo.html`,
comando `seed_mensagens_robo`.

---

## 5. Reengajamento por tempo de espera (recontato)

**Problema:** quando o cliente não respondia, o atendimento era encerrado.

**Entregue:** endpoint **`POST /ia/recontato`**. Ao cair no "tempo de espera", em vez
de encerrar, o robô manda uma mensagem de reengajamento **escalonada** (diferente a
cada silêncio, personalizada com o 1º nome) para **fisgar** o cliente. Após 3
tentativas, manda **uma** despedida e **pausa em silêncio** (não fica em loop). O
contador zera sozinho quando o cliente volta a responder.

**Detalhe corrigido:** as mensagens são **sem emojis** (no canal viravam "?").

**Arquivos:** `ia_validacao/src/onboarding.py` (`decidir_recontato`),
`ia_validacao/src/app.py` (endpoint), `ia_validacao/src/regras/engine.py` (reset).

---

## 6. Retomada de atendimento (continuar / recomeçar / outro CPF)

**Problema:** um lead **a meio-cadastro** que reabria o atendimento caía direto na
próxima pergunta pendente, sem validar o CPF nem oferecer opção.

**Entregue:** um **gate de retomada** no fluxo determinístico (o que o Matrix usa).
Ao reabrir (saudação ou mensagem vazia) com cadastro em andamento, o robô pergunta:
**1) Continuar de onde paramos · 2) Recomeçar do início · 3) É para outro CPF** —
personalizado com o nome. Vale para leads em cadastro (`lead_novo` e
`processamento_manual`).

**Arquivos:** `ia_validacao/src/onboarding.py`, `ia_validacao/src/regras/engine.py`,
comando `seed_menu_retomada`.

---

## 7. Viabilidade por cidade inteira + transbordo correto

**Entregue:**
- **Todas as 55 cidades** de viabilidade marcadas **"atende cidade inteira"** — o robô
  vende para qualquer endereço dessas cidades (os bairros passam a ser informativos).
- **Consulta de viabilidade no fluxo:** ao **confirmar o endereço**, o robô cruza o
  CEP/cidade contra o cadastro de cobertura. Cidade fora da lista → **transborda** para
  atendimento.
- **Transbordo que realmente para o fluxo:** empresa (tipo de imóvel) e sem-viabilidade
  agora **mudam o status** do lead (como o menu "Atendimento"), então o robô **para**
  de pedir dados e transfere — antes mandava a mensagem mas continuava a coleta.

**Arquivos:** `ia_validacao/src/regras/engine.py`, `ia_validacao/src/onboarding.py`
(STATUS_ROTAS), dados `CidadeViabilidade`.

---

## 8. Correções de qualidade do fluxo

- **Cliente inativo → fluxo de já cadastrado:** CPF com cadastro inativo/cancelado é
  detectado (via banco espelho HubSoft) e segue o fluxo de cliente existente, podendo
  contratar normalmente.
- **Endereço do novo serviço:** usa o endereço **informado pelo cliente** (não o
  cadastral); cada O.S. no acompanhamento mostra o **endereço real** do seu serviço.
- **Menu de upgrade condicional:** a opção de upgrade só aparece para quem tem
  **serviço habilitado** (renumeração dinâmica das opções).
- **"Outro CPF" limpa tudo:** ao escolher "outro CPF", o robô **zera todos os dados**
  do cadastro anterior — antes, se o número já tinha cadastro completo, o robô achava
  "tudo preenchido" e transbordava indevidamente.
- **Nome quebrado na saudação:** primeiro nome é **higienizado** (ex.: "Thiago:" →
  "Thiago").
- **Pergunta pós-recontato:** quando o cliente responde a pergunta pendente após o
  recontato, a resposta é **aproveitada** (via `/validar`), sem re-perguntar.

**Arquivos:** `ia_validacao/src/onboarding.py`, `ia_validacao/src/regras/engine.py`,
`integracoes/services/hubsoft.py`, `posvenda_hubsoft/executores/novo_servico_api.py`,
`ia_validacao/src/menu_cliente.py`.

---

## Estado operacional

**Serviços systemd do V2 ativos (7):**
- `techub-robo-v2` — Django (porta 8104, /robo-v2)
- `techub-ia-v2` — engine FastAPI de conversa/validação (porta 8091)
- `techub-chatsim` — simulador/console de atendimento
- `techub-robo-v2-poll-novo-servico` — worker novo serviço (API interna)
- `techub-robo-v2-poll-upgrade` — worker upgrade (API interna)
- `techub-robo-v2-poll-conversao` — worker conversão prospecto→cliente (API interna)
- `techub-robo-v2-sync-status` — sync HubSoft + reconcilia CRM

**Números atuais (produção):**

| Item | Quantidade |
|---|---|
| Pipelines do CRM | **5** (aquisição, novo serviço, upgrade, atendimento, indicação) |
| Estágios de pipeline | **25** |
| Regras de automação de pipeline | **17** |
| Tags de classificação | **23** |
| Perfis de acesso (RBAC) | **5** |
| Regras de conversa (IA) | **34** ativas |
| Mensagens do robô editáveis | **20** |
| Cidades "atende cidade inteira" | **55 / 55** |

---

## Endpoints novos do engine (referência)

| Método / rota | Função |
|---|---|
| `POST /ia/recontato` | Reengajamento escalonado no tempo de espera |
| `GET /ia_validador/api/mensagens-robo/` | Mensagens configuráveis (o engine lê daqui) |
| `POST /admin/invalidar-cache/` | Recarrega regras **e** mensagens na hora |

## Comandos novos (referência)

| Comando | Função |
|---|---|
| `seed_menu_retomada` | Cria a regra do gate de retomada (continuar/recomeçar/outro CPF) |
| `seed_mensagens_robo` | Semeia as mensagens do robô (preserva edições da equipe) |
| `organizar_permissoes` | Semeia os 5 perfis de acesso padrão |

---

## Pendências / próximos passos sugeridos

- **Matrix (rota da resposta pós-recontato):** garantir que a resposta do cliente
  depois do recontato/pausa vá para o `/validar` da pergunta pendente (e não para o
  `/proximo-passo`), para aproveitar a resposta em vez de re-perguntar.
- **Central de Mensagens — 2ª leva:** trazer para a aba também os textos de
  **transbordo/encerramento** e do **menu** (hoje ainda fixos no código).
- **Padrão de cidade nova:** decidir se cidade recém-cadastrada nasce já como
  "atende cidade inteira" (hoje o padrão é restrito).
- **Painel de métricas de negócio** (volume, conversão, tempo médio por fluxo).
- **Limpeza dos dados de teste** no HubSoft e **decomissionamento do robô antigo**.
