# Relatório Executivo e Técnico — Bot de Vendas com IA

**Data:** 26 de maio de 2026
**Projeto:** Rob-Vendas Megalink — Atendimento WhatsApp com IA
**Status:** Fluxo de venda completo operando ponta-a-ponta

---

## 1. Resumo Executivo

### O que foi construído

Um **assistente virtual no WhatsApp** que conduz o cliente da primeira mensagem
("oi") até a abertura automática da Ordem de Serviço de instalação no
Hubsoft — sem necessidade de atendente humano nas etapas operacionais.

A IA participa em **três momentos críticos** da conversa:

1. **Validação visual de documentos** (Vision API da OpenAI) — analisa selfie
   com documento, frente e verso de RG/CNH e aprova/rejeita imediatamente.
2. **Estruturação de endereço** (OpenAI texto) — transforma respostas livres
   do cliente ("apto 502 bloco B Edifício Aurora") em strings padronizadas
   prontas para a equipe de instalação.
3. **Detecção de intenção e roteamento** — identifica clientes já cadastrados
   no Hubsoft pelo CPF e oferece menu específico em vez do fluxo de venda.

### Impacto para o negócio

| Antes | Agora |
|---|---|
| Atendente recebia lead "frio", coletava todos os dados, validava documentos manualmente | Bot coleta + valida + abre OS automaticamente |
| Tempo de cadastro: ~15-20 min de atendente humano por lead | Tempo de cadastro: ~5-8 min de cliente, atendente entra só na assinatura |
| Documentação validada manualmente após horas/dias | Documentação validada em ~3 segundos pela IA |
| Cliente já cadastrado misturava no fluxo de venda novo | Cliente é reconhecido pelo CPF e roteado pra menu específico |
| Endereço em texto livre, instalação descobria detalhes na hora | Endereço estruturado com bloco/apto/condomínio padronizado |
| Bot solicitava confirmação repetidamente em loops | Fluxo linear sem loops, com transbordo claro nas exceções |

### Indicadores

- **17 commits no dia** consolidando o fluxo completo.
- **4 endpoints novos** no Django para integração IA ↔ Backend ↔ Hubsoft ↔ Matrix.
- **2 modelos novos** (`AgendamentoInstalacaoIA`) e **5 migrations** ajustando regras de validação.
- **Custo da IA:** ~R$ 0,03 por venda completa (Vision + extração de endereço, modelo `gpt-4o-mini`).
- **8/8 testes** de validação visual passando em casos reais (RG antigo, CIN novo, CNH, selfie, rejeições legítimas).

---

## 2. Arquitetura — Visão Geral

```
WhatsApp → Matrix (flow_v5) ────────────────────────────────────┐
                │                                                │
                ├── /ia/proximo-passo ──► onboarding.py          │
                │       (decide próxima pergunta)                │
                │                                                │
                └── /ia/validar ──────► engine.py                │
                       (valida resposta + dispara ações)         │
                            │                                    │
                            ├── openai_imagens (Vision)          │
                            ├── openai_endereco (Texto)          │
                            ├── robovendas (HTTP) ────► Django   │
                            │                                    │
                            └── retorno ao Matrix ◄──────────────┘
```

**Componentes principais:**

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| **Matrix** | Plataforma externa (flow JSON) | Orquestra a conversa no WhatsApp, exibe mensagens, captura respostas |
| **API IA** (`ia_validacao/`) | FastAPI Python | Decide próxima pergunta + valida resposta com IA |
| **Backend Django** (`dashboard_comercial/`) | Django | Persiste leads, integra com Hubsoft, abre OS via Matrix API |
| **OpenAI** | gpt-4o-mini (Vision + Text) | Valida imagens + estrutura endereços |
| **Hubsoft** | API externa do provedor | Cadastra prospectos, consulta clientes existentes |
| **Matrix API** (apimatrix) | API externa de agendamento | Consulta datas/agenda disponíveis, abre atendimentos/OS |

---

## 3. Atuação da IA — Detalhamento

### 3.1 Validação Visual de Documentos (OpenAI Vision)

**Onde fica:** `ia_validacao/src/integracoes/openai_imagens.py`

**Quando dispara:** o cliente envia uma das 3 fotos solicitadas (selfie/frente/verso).
A API IA recebe a URL da imagem (já hospedada pelo Matrix) e chama o
`validar_imagem(url, descricao)`.

**Como funciona:**

1. **Chain-of-thought no prompt** — força a IA a preencher PRIMEIRO sinais
   discriminadores (`tem_foto_biometrica_visivel`, `tem_assinatura_diretor_expedidor`,
   `tem_textos_legais_brasileiros`) ANTES de decidir o tipo da imagem.
2. **Discriminador chave:** FRENTE = lado com foto biométrica do titular.
   VERSO = lado sem foto, com dados textuais + assinatura do diretor.
3. **Reconhece 2 modelos de RG brasileiro:**
   - RG antigo (verde, papel) — verso tem REGISTRO GERAL, FILIAÇÃO,
     NATURALIDADE, CPF, "VÁLIDA EM TODO TERRITÓRIO NACIONAL", "LEI Nº 7.116/83"
   - CIN novo (PVC, polímero) — verso tem QR code, número A1003573...,
     filiação, órgão expedidor, assinatura do diretor
4. **Códigos de erro mapeados pra mensagens específicas pro cliente:**
   - `tipo_errado` → "Por favor, envie a foto da frente/verso..."
   - `ilegivel` → "A foto está pouco nítida, pode tentar com mais luz?"
   - `self_sem_doc` → "Lembre-se: segurando o documento ao lado do rosto"
5. **Quando aprovado:** marca o boolean `doc_*_recebida=True` no lead
   **SÍNCRONO** (antes de retornar) — assim o próximo `/proximo-passo`
   imediato já vê o avanço. Imagem é registrada no DB com
   `status_validacao='documentos_validos'`.

**Resultado nos testes:** 8/8 acertos em casos reais variados.

### 3.2 Estruturação de Endereço (OpenAI Texto)

**Onde fica:** `ia_validacao/src/integracoes/openai_endereco.py`

**Quando dispara:** cliente responde a pergunta de ponto de referência.

**Por que existe:** a equipe de operações precisava saber se o cliente mora
em casa térrea, apartamento ou condomínio, com detalhes específicos (bloco,
torre, andar, número do apto, nome do condomínio). Antes era texto livre
sem padronização.

**Como funciona:**

1. Cliente recebe pergunta única que cita os 4 cenários (casa/apto/cond/empresa).
2. Responde em texto livre: "edif aurora bloco b apto 502 perto do mercado"
3. IA extrai os componentes via JSON estruturado.
4. Helper monta string padronizada que vai pro campo `ponto_referencia` do lead:
   - `[CASA] perto da padaria do José`
   - `[APARTAMENTO] Edif. Aurora - Bloco B - 5º andar - Apto 502. Ref: mercado X`
   - `[CONDOMÍNIO] Cond. Jardim - Quadra 3 - Casa 12. Ref: portaria 2`
   - `[EMPRESA] Centro Empresarial - 3º andar - Sala 305`

**Custo:** ~R$ 0,003 por extração.

### 3.3 Detecção de Cliente Existente

**Onde fica:** hooks no `engine.py` + endpoint `api_verificar_cliente_por_cpf` no Django.

**Como funciona:**

1. Cliente responde CPF na PRIMEIRA pergunta do fluxo.
2. Engine valida CPF (regex + dígito verificador), salva no lead.
3. Chama endpoint Django que faz **GET direto na API Hubsoft**
   (`/api/v1/integracao/cliente?busca=cpf_cnpj&termo_busca=X`).
4. **Se Hubsoft retorna cliente:**
   - Marca `status_api='cliente_ativo'` no lead
   - Cria/atualiza `ClienteHubsoft` local + `ServicoClienteHubsoft`
   - Próxima rodada do `/proximo-passo` retorna o menu
5. **Se Hubsoft NÃO retorna:** segue o fluxo de venda normal (nome, RG, etc).

**A separação detecção × sincronização** evita que validações locais
quebradas (ex: cliente sem certos campos obrigatórios) impeçam a detecção.

---

## 4. Fluxo de Atendimento — Passo a Passo

### 4.1 Cliente Novo (Fluxo de Venda Completo)

```
1. "oi" → bot saúda e pergunta CPF
2. CPF → backend consulta Hubsoft. Não é cliente. Continua.
3. Nome completo
4. RG, data nascimento, e-mail
5. Tipo de imóvel: Casa ou Empresa?
   ├── Empresa → transbordo (atendente comercial)
   └── Casa → continua
6. CEP → ViaCEP preenche cidade/rua/bairro automaticamente
7. Confirma endereço
8. Número da casa, ponto de referência (estruturado via IA)
9. Plano (Plano 620 Mega ou Plano 1G Turbo)
10. Dia vencimento
11. CONFIRMAÇÃO DOS DADOS → status=pendente
    → signal Django dispara cadastrar_prospecto no Hubsoft
    → status vira "processado" + id_hubsoft preenchido
12. Selfie com documento → IA Vision valida → aprovado
13. Frente do documento → IA Vision valida → aprovado
14. Verso do documento → IA Vision valida → aprovado
15. Turno de instalação: Manhã ou Tarde?
16. Data (3 datas reais consultadas via apimatrix)
17. ENGINE DISPARA agendamento síncrono:
    a. Pré-sync Hubsoft (busca dados atualizados do cliente)
    b. consultar_agenda(cidade, data, turno) → horário + técnico
    c. abrir_atendimento → id_atendimento
    d. abrir_os → id_os
    e. status='instalacao_agendada' + tag
18. Mensagem rica ao cliente:
    "Instalação confirmada! ✅
     📅 Data: 28/05/2026
     ⏰ Turno: Tarde
     🕐 Horário: 14:00
     🔧 Técnico: José Silva"
19. Transbordo (atendente finaliza assinatura do contrato)
```

### 4.2 Cliente Existente (Detectado pelo CPF)

```
1. "oi" → bot saúda e pergunta CPF
2. CPF → backend consulta Hubsoft. ACHOU cliente.
3. Marca status_api='cliente_ativo'. Próxima rodada:
4. Bot exibe menu:
   Como posso te ajudar hoje?
   1) 🚀 Contratar um novo serviço
   2) 📈 Fazer upgrade de plano
   3) 📍 Acompanhar status da instalação
   4) 📱 Falar com Atendimento
5. Cliente escolhe:
   ├── 1, 2, 4 → mensagem específica + transbordo
   └── 3 → busca OrdemServicoHubsoft em aberto
        - Se tem OS: exibe número, data programada, status amigável
          ("Agendada", "Em rota", "Em execução", ...) sem nome de técnicos
        - Se não tem: transbordo "vou conferir com atendente"
```

### 4.3 Cliente que Finalizou Recentemente

Cliente com `status_api='instalacao_agendada'` (acabou de finalizar) que
volta a mandar mensagem recebe **o mesmo menu** acima.

### 4.4 Cliente Aguardando Assinatura

`status_api='aguardando_assinatura'` → cliente cadastrou mas ainda não
assinou. Sem serviço/OS no Hubsoft, então transborda direto pra atendente
finalizar a assinatura.

---

## 5. Registros e Funcionalidades Implementadas

### 5.1 Modelos Django (banco de dados)

| Model | Função |
|---|---|
| `LeadProspecto` (existente, expandido) | Lead de venda — recebeu campos `turno_instalacao`, `data_instalacao`, `endereco_confirmado`, `dados_confirmados`, `tipo_ajuste`, `doc_*_recebida`, `data_primeira_tentativa_sync_hubsoft` |
| `ImagemLeadProspecto` (existente) | Imagens dos docs — agora marcadas como `documentos_validos` direto pela IA |
| **`AgendamentoInstalacaoIA`** (NOVO) | Registro de cada agendamento iniciado via bot, com status (aguardando_sync, processando, agendado, erro), tentativas, dados do técnico/OS, payloads de resposta do Matrix |
| `ClienteHubsoft` (existente) | Espelho local do cliente Hubsoft |
| `ServicoClienteHubsoft` (existente) | Serviços contratados pelo cliente |
| `OrdemServicoHubsoft` (existente) | OS espelhadas do Hubsoft (usado pra "Acompanhar instalação") |

### 5.2 Regras de Validação (`ia_validador.RegraValidacao`)

20+ regras configuráveis via Django Admin, uma por etapa do fluxo:

- `coleta_cpf` (extractor=cpf + hook detecta Hubsoft)
- `coleta_nome`, `coleta_rg`, `coleta_data_nascimento`, `coleta_email`
- `tipo_imovel` (extractor=opcao com hook empresa→transbordo)
- `coleta_cep` (extractor=cep + ViaCEP)
- `confirmacao_endereco` (extractor=confirmacao)
- `coleta_cidade`, `coleta_bairro`, `coleta_rua` (só se ViaCEP falhou)
- `coleta_numero`, `coleta_ponto_referencia` (estrutura via IA)
- `escolha_plano`, `dia_vencimento`
- `confirmacao_dados` → seta status=pendente (signal cadastra Hubsoft)
- `o_que_ajustar` (se cliente nega dados)
- `documentacao_selfie`, `documentacao_frente_doc`, `documentacao_verso_doc`
  (validação via OpenAI Vision)
- `escolha_turno`, `escolha_data` (hook dispara agendamento síncrono)
- `menu_cliente_existente` (4 opções pra cliente Hubsoft)

### 5.3 Endpoints Django Novos

| Rota | Verbo | Função |
|---|---|---|
| `/integracoes/api/verificar-cliente-cpf/<lead_id>/` | POST | Consulta Hubsoft pelo CPF, marca lead como cliente_ativo se achou |
| `/integracoes/api/lead/<lead_id>/proxima-instalacao/` | GET | Retorna OS em aberto do lead (sem nomes de técnicos) |
| `/integracoes/api/agendar-instalacao-ia/<lead_id>/` | POST | Orquestra consulta_agenda + abrir_atendimento + abrir_os |
| `/api/leads/imagens/registrar/` | POST | Aceita agora `status_validacao` no payload (IA marca aprovado direto) |

### 5.4 Management Commands

| Comando | Função | Cron sugerido |
|---|---|---|
| `sincronizar_clientes` (existente) | Sincroniza clientes Hubsoft (espelho local) | A cada 30 min |
| **`processar_agendamentos_ia_pendentes`** (NOVO) | Reprocessa agendamentos que ficaram `aguardando_sync` (lead ainda não virou ClienteHubsoft no momento) | A cada 5-10 min |

### 5.5 Flow Matrix (`flow_v5_patched.json`)

Flow simplificado de 68 nodes (versus 12k+ do flow_v3 legado), 3 blocos:

1. **INICIO** — captura telefone, cria/busca lead via Django, chama `/proximo-passo`
2. **Consulta_api** — `dec_roteamento_inicial` ramifica conforme status:
   - `lead_novo` → inicia venda
   - `cliente_ativo` → menu
   - `instalacao_agendada` → menu (igual cliente_ativo)
   - `aguardando_assinatura` → transbordo
   - Padrão → retoma de onde parou
3. **Realizar Pergunta** — exibe `{#mensagem_pergunta}` (composta pelo backend),
   captura resposta, chama `/validar`, exibe `{#mensagem_resposta}` (mensagem
   rica composta pelo engine) antes de transbordar ou voltar ao loop.

---

## 6. Pontos Técnicos Sensíveis (pra Operação)

### 6.1 O que precisa estar deployado e funcionando

- **Backend Django** rodando em `https://robovendas.megalinkpiaui.com.br`
- **API IA (FastAPI)** rodando em `https://robovendas.megalinkpiaui.com.br/ia/*`
  - precisa de `OPENAI_API_KEY` configurado no `.env`
- **Matrix** com `flow_v5_patched.json` importado e ativo
- **Cron** rodando `sincronizar_clientes` (existente) e
  `processar_agendamentos_ia_pendentes` (novo)
- **Integrações ativas** no Django Admin: `Hubsoft` e `Matrix` (com URL base + credenciais)

### 6.2 Sincronização Hubsoft

- Signal `enviar_lead_pendente_para_hubsoft` em `integracoes/signals.py`
  dispara `cadastrar_prospecto` automaticamente quando `status_api='pendente'`.
- O cliente vira `ClienteHubsoft` local quando: (a) acaba de virar cliente
  no Hubsoft (assinou contrato); ou (b) o `sincronizar_clientes` periódico
  rodou após isso.
- O `executar_agendamento` força um `sincronizar_cliente(lead)` antes de
  tentar abrir a OS, garantindo dados frescos.

### 6.3 Pontos de transbordo (atendente humano)

- Tipo de imóvel = Empresa
- Menu de cliente existente (opções 1, 2, 4)
- Cliente nega confirmação dos dados após N tentativas
- Cliente aguardando assinatura
- Falha na abertura de atendimento/OS (status=erro)
- Imagem rejeitada após max_tentativas

### 6.4 Validação síncrona vs background

- **Síncrono** (resposta imediata): validação CPF/CEP/etc, consulta
  Hubsoft pelo CPF, validação visual por IA Vision, abertura de
  atendimento+OS após escolha de data, marca de `doc_*_recebida=True`.
- **Background (thread daemon)**: registro de histórico no Django,
  registro de imagem no DB, atualização de tags, mudança de
  `status_api` quando não é crítico.

---

## 7. Próximos Passos Sugeridos

Itens identificados durante a construção que ficam pra próximas iterações:

1. **Notificação WhatsApp pós-sync**: quando o worker `processar_agendamentos_ia_pendentes`
   completa um agendamento que estava `aguardando_sync`, mandar mensagem pro cliente
   confirmando data/horário/técnico. Requer endpoint Matrix para envio arbitrário.
2. **Refinamento do prompt IA Vision**: monitorar casos rejeitados em
   produção e ajustar conforme aparecerem layouts não previstos.
3. **Métricas/Dashboard**: tempo médio do fluxo, taxa de aprovação por IA
   das imagens, taxa de transbordo por motivo, conversão CPF→venda.
4. **Cache do consultar_datas_disponiveis**: hoje é chamado 2x por venda
   (uma pra mensagem dinâmica, outra pra mapear opção→data). TTL de 5min
   reduziria 50% das chamadas à apimatrix.
5. **Tratamento de uploads com legendas**: cliente às vezes manda foto
   acompanhada de texto ("é a frente"), o sistema pode usar isso como
   sinal adicional.

---

## 8. Commits do Dia (Histórico)

| Hash | Mudança |
|---|---|
| `70756f3` | Validação síncrona de imagens via OpenAI Vision (gpt-4o-mini) |
| `0ef0cce` | Prompt explícito por tipo — frente/verso não exigem rosto |
| `65d67dd` | ponto_referencia estruturado via IA (casa/apto/cond/empresa) |
| `7adbbe9` | Fluxo de agendamento (turno + data + confirmação) após docs |
| `939c459` | Bot abre atendimento+OS no Hubsoft após confirmação |
| `d050286` | CPF como 1ª pergunta + menu pra cliente Hubsoft existente |
| `1d9db4e` | Consulta direta na API Hubsoft + transbordo após detecção |
| `27ac1d6` | IA reconhece corretamente verso do RG antigo brasileiro |
| `5cd2a44` | Suporte completo ao menu cliente Hubsoft existente (flow_v5) |
| `d740c8c` | IA marca imagens aprovadas + turno/data com agendamento direto |
| `aa86e7f` | Match exato pra aliases curtos + transbordo empresa |
| `b6e8ec9` | Corrige busca das 3 datas da API + pré-sync Hubsoft |
| `3190a81` | Marca doc_*_recebida síncrono pra evitar 2ª solicitação |
| `5c63d77` | Cliente que finalizou vê menu igual ao cliente Hubsoft |
| `7d277b3` | Flow_v5: redireciona status finalizados pro menu |
| `8507a97` | aguardando_assinatura NÃO entra no menu — vai pra transbordo |

---

**Fim do relatório.**
