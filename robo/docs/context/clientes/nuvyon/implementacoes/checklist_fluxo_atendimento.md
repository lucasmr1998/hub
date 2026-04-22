---
name: "Checklist de coleta — Fluxo de atendimento Nuvyon"
description: "Lista de informações a coletar com a Nuvyon pra parametrizar o fluxo Matrix que consome APIs Hubtrix. Complementa o checklist_onboarding e serve de input pro kickoff técnico."
---

# Checklist de coleta — Fluxo de atendimento Nuvyon

**Data:** 2026-04-21
**Contexto:** pra configurar o fluxo Matrix da Nuvyon replicando a estrutura do fluxo Megalink, precisamos coletar essas informações com o time deles. Este documento é o input pro kickoff técnico.

**Referência:** [fluxo_matrix_hubtrix.md](fluxo_matrix_hubtrix.md) (guia técnico do fluxo).

---

## 1. Identidade da empresa

- [ ] **Nome comercial exato** (ex: "Nuvyon Internet") — aparece nas mensagens pro cliente
- [ ] **Slug técnico** (ex: `nuvyon`) — usado em APIs, logs, chaves
- [ ] Logo em PNG/SVG alta resolução, fundo transparente
- [ ] Cores primária + secundária (hex)
- [ ] Site oficial

---

## 2. Planos de internet ofertados no fluxo

Pra cada plano que o fluxo deve ofertar:

- [ ] Nome comercial do plano (ex: "Fibra 620 Mega")
- [ ] Velocidade
- [ ] Preço mensal (com desconto e sem desconto, se aplicável)
- [ ] ID do plano no HubSoft/RP
- [ ] Benefícios inclusos (streaming, apps, fidelidade, etc.)
- [ ] Condição de promoção (validade, público-alvo)

**Exemplo Megalink:**
| Plano | ID HubSoft | Preço desc. | Preço cheio |
|---|---|---|---|
| 620MB | 1649 | R$ 99,90 | — |
| 1GB Turbo | 1648 | R$ 129,90 | — |

**Pergunta adicional:** a Nuvyon tem plano específico por perfil (ex: Megalink Energia)? Se sim, qual a regra de ofertar?

---

## 3. Dia de vencimento de fatura

O fluxo oferece ao cliente opções de dia de vencimento. Coletar:

- [ ] Quais dias estão habilitados no HubSoft da Nuvyon (ex: 1, 5, 10, 15, 20)
- [ ] **Mapeamento dia → ID** no HubSoft da Nuvyon:

| Dia | ID no HubSoft |
|---|---|
| _____ | _____ |
| _____ | _____ |

**Atenção:** esses IDs são específicos por tenant HubSoft, **não dá pra adivinhar**.

---

## 4. HubSoft e integração

- [ ] URL do HubSoft da Nuvyon
- [ ] Credenciais de API (client_id, client_secret ou usuário/senha)
- [ ] Usuário dedicado Hubtrix no HubSoft criado e com acesso API habilitado
- [ ] Usuário cadastrado como Vendedor no HubSoft (pra atribuição de contratos)
- [ ] **ID do vendedor padrão** — vai em `id_vendedor_rp` quando criar lead
- [ ] **ID de origem** (ex: código de "whatsapp" no cadastro HubSoft)
- [ ] **ID de origem de serviço**
- [ ] Ambiente de homologação HubSoft (se existir)
- [ ] Ponto focal técnico do HubSoft na Nuvyon

### 4.1 Validação de documentos

- [ ] O HubSoft da Nuvyon valida documentos automaticamente?
- [ ] Se sim: qual o critério? Quanto tempo demora em média?
- [ ] Se não: como vai ser o fallback? (validação manual por vendedor? pula a checagem?)
- [ ] Taxa esperada de rejeição de docs (pra dimensionar transbordos)

---

## 5. Matrix (sistema de atendimento da Nuvyon)

O Matrix é do cliente, não mexemos. Mas precisamos dos dados pra consumir as APIs dele dentro do fluxo:

- [ ] URL base da Matrix API (ex: `https://apimatrix.nuvyon.com.br`)
- [ ] Domínio de storage de imagens (ex: `https://nuvyon.matrixdobrasil.ai`)
- [ ] Acesso ao editor de fluxos (usuário Hubtrix com permissão de edição)
- [ ] Acesso ao emulador (pra testar antes de publicar)
- [ ] **ID tipo de atendimento "Instalação"** no Matrix deles
- [ ] **ID status inicial do atendimento**
- [ ] **ID usuário responsável padrão** (quem recebe os atendimentos automáticos)
- [ ] **ID tipo de OS "Instalação"**
- [ ] **Status inicial da OS** (string, ex: `pendente`)
- [ ] **Duração padrão da OS** (ex: `01:30:00`)
- [ ] Versão/variante do Matrix em uso
- [ ] Ponto focal técnico do Matrix

---

## 6. Aurora/N8N (instância dedicada Nuvyon)

Decisão tomada: Nuvyon terá instância Aurora própria.

- [ ] URL do webhook Aurora da Nuvyon
- [ ] Quem provisiona a instância (nós ou eles)?
- [ ] Quem mantém (nós ou eles)?
- [ ] Base geográfica calibrada (cidades atendidas pela Nuvyon carregadas)?
- [ ] Regras de classificação (`isAClient`, `hasCancelledService`, `needsReception`) validadas no contexto deles?

---

## 7. Horário comercial e transbordo

- [ ] Horário de atendimento (seg-sex, sáb, dom)
- [ ] Mensagem padrão fora do horário
- [ ] **Filas/serviços de transbordo no Matrix** — quando o bot transborda, quem pega?
  - Serviço de "consultor comercial"
  - Serviço de "atendimento técnico"
  - Serviço de "suporte"
  - Outros?
- [ ] Tempo máximo de inatividade antes de finalizar atendimento (ex: 5 min)
- [ ] Quantidade de tentativas inválidas antes de transbordar (ex: 3)

---

## 8. Mensagens da marca (texto do fluxo)

Textos que precisam ser adaptados do Megalink pra Nuvyon:

- [ ] Saudação inicial (hoje: "Oi! Que bom ter você aqui na Megalink Internet 🚀")
- [ ] Descrição de cada plano (copy persuasivo de vendas)
- [ ] Mensagem de confirmação de dados
- [ ] Mensagem de sucesso na finalização ("Seja bem-vindo(a)...")
- [ ] Mensagem de transferência pra humano
- [ ] Link alternativo de contratação pelo site (se existir)
- [ ] Texto do boleto proporcional (hoje: explicação sobre cobrança proporcional)
- [ ] Fidelidade: 12 meses? Outro valor?

---

## 9. Canais de entrada

- [ ] Número(s) de WhatsApp oficiais
- [ ] Provider WhatsApp (Uazapi / Evolution / Meta Cloud / Twilio)
- [ ] Tem widget no site? Qual URL?
- [ ] Tem Instagram DM, Facebook Messenger, Telegram?
- [ ] Tem ligação telefônica? Como registra lead por telefone?

---

## 10. Validação interna (antes do go-live)

- [ ] Fluxo exportado do Megalink + adaptado pra Nuvyon no Matrix
- [ ] Tenant Nuvyon criado no aurora-admin
- [ ] `IntegracaoAPI` criada + token gerado
- [ ] Endpoint `/api/leads/tags/` implementado no Hubtrix (dívida técnica registrada)
- [ ] Header `Authorization: Bearer` adicionado em todos os nós de API Hubtrix
- [ ] Variáveis globais do fluxo preenchidas com os valores coletados
- [ ] Teste 1: criar lead via telefone de teste, passar por todas URAs, confirmar criação no Hubtrix
- [ ] Teste 2: envio de imagens → confirmar registro em `ImagemLeadProspecto`
- [ ] Teste 3: polling HubSoft → confirmar retorno correto
- [ ] Teste 4: agendamento de instalação → confirmar OS criada no Matrix
- [ ] Dry run com funcionário interno da Nuvyon fazendo papel de cliente

---

## 11. Pós go-live

- [ ] Quem monitora as primeiras 48h
- [ ] Canal de comunicação pra bugs/ajustes (Slack, WhatsApp, e-mail)
- [ ] Cadência de acompanhamento nas primeiras 4 semanas
- [ ] Critério de "estabilizado" (ex: zero bug crítico por 7 dias corridos)

---

## Resumo de pendências técnicas do Hubtrix (nossa dívida)

Pra Nuvyon ligar o fluxo, temos que resolver:

1. **Criar endpoint `POST /api/leads/tags/`** em `apps/comercial/leads/views.py`
   - Aceitar `{ lead_id, tags_add: [], tags_remove: [] }`
   - Validar tenant via decorator `api_token_required`
   - Atualizar campo de tags do `LeadProspecto`
2. **Validar que todos os 6 endpoints existentes aceitam campos extras** que o fluxo manda sem reclamar (já que o `registrar_lead_api` filtra pelo `_model_field_names`, isso está ok — confirmar)
3. **Documentar no `/configuracoes/integracoes/`** como gerar token de API no tenant (UI precisa deixar isso claro)
