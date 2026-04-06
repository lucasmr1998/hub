# 14. Comercial — Modulo de Atendimento

**Status:** ✅ Em producao
**Ultima atualizacao:** 06/04/2026
**App:** `apps/comercial/atendimento/`

---

## Contexto

O modulo de Atendimento gerencia a **execucao** dos fluxos conversacionais: sessoes ativas com leads, respostas, tentativas, validacao e integracao com N8N/WhatsApp. A **configuracao** de fluxos e questoes esta documentada em `13-MODULO_FLUXOS.md`.

---

## Arquitetura

```
N8N (WhatsApp) ou Painel Web
          ↓
   POST /api/n8n/atendimento/iniciar/
          ↓
   Cria AtendimentoFluxo (sessao)
          ↓
   Retorna primeira questao
          ↓
   Lead responde → POST /api/n8n/atendimento/<id>/responder/
          ↓
   Validacao multicamada:
     1. Tipo (email, CPF, telefone, numero...)
     2. Regras (tamanho, regex, faixa numerica)
     3. Opcoes dinamicas (planos, vencimentos)
     4. Webhook N8N (validacao externa)
     5. IA (placeholder para Claude/OpenAI)
          ↓
   Invalido? → Cria TentativaResposta → Aplica estrategia de erro
   Valido?   → Salva RespostaQuestao → Webhook pos-resposta → Roteamento
          ↓
   Proxima questao (loop) ou fim do fluxo
          ↓
   POST /api/n8n/atendimento/<id>/finalizar/
          ↓
   Calcula score → Atualiza lead → Resultado final
```

---

## Models

### AtendimentoFluxo

Sessao ativa de um lead em um fluxo. Controla o progresso, respostas e resultado.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| lead | FK → LeadProspecto | Lead sendo atendido |
| fluxo | FK → FluxoAtendimento | Fluxo utilizado |
| historico_contato | FK → HistoricoContato | Historico vinculado (opcional) |
| status | CharField(30) | Status da sessao (ver tabela) |
| questao_atual | PositiveInteger | Indice da questao atual |
| total_questoes | PositiveInteger | Total de questoes no fluxo |
| questoes_respondidas | PositiveInteger | Quantas foram respondidas |
| dados_respostas | JSONField | Todas as respostas: `{indice: {resposta, data, valida, tentativas}}` |
| score_qualificacao | Integer(1-10) | Score calculado ao finalizar |
| resultado_final | JSONField | Resultado processado da sessao |
| tempo_total | PositiveInteger | Duracao total em segundos |
| tentativas_atual | PositiveInteger | Tentativa atual da sessao |
| max_tentativas | PositiveInteger | Maximo de tentativas (padrao: 3) |
| observacoes | TextField | Notas da sessao |
| ip_origem | GenericIPAddress | IP do usuario |
| user_agent | TextField | Navegador/dispositivo |
| dispositivo | CharField(100) | Tipo de dispositivo |
| id_externo | CharField(100) | ID no sistema externo (ex: HubSoft) |

**Tabela:** `atendimentos_fluxo`

**Status possiveis:**

| Status | Descricao |
|--------|-----------|
| iniciado | Sessao criada, primeira questao pendente |
| em_andamento | Lead esta respondendo |
| pausado | Sessao pausada (pode retomar) |
| completado | Todas as questoes respondidas |
| abandonado | Lead desistiu |
| erro | Erro no processamento |
| cancelado | Cancelado manualmente |
| aguardando_validacao | Esperando validacao externa |
| validado | Validacao aprovada |
| rejeitado | Validacao rejeitada |

**Metodos principais:**
- `responder_questao_inteligente(indice, resposta, contexto)` — valida, cria tentativa, roteia. Retorna `(sucesso, mensagem, proxima_acao, dados_extras)`. Acoes possiveis: `proxima_questao`, `finalizar_fluxo`, `repetir_questao`, `pular_questao`, `redirecionar`, `escalar_humano`
- `finalizar_atendimento(sucesso)` — calcula score, tempo total, atualiza lead
- `calcular_score_qualificacao()` — score 1 a 10 baseado nas respostas
- `atualizar_lead_com_resultados()` — atualiza score e observacoes do lead
- `get_progresso_percentual()` — percentual de progresso
- `get_contexto_dinamico()` — contexto para templates: nome_cliente, telefone, email, progresso, respostas anteriores (resposta_qX), valor_lead, cidade, estado
- `get_estatisticas_tentativas()` — total, validas, invalidas, media por questao, taxa IA, estrategias aplicadas
- `get_questoes_problematicas()` — questoes com 2+ erros
- `pode_ser_reiniciado()` — se pode reiniciar (completado, abandonado ou cancelado)
- `reiniciar_atendimento()` — reseta sessao mantendo contador de tentativas

---

### RespostaQuestao

Registro de resposta a uma questao (versao final, apos validacao).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| questao | FK → QuestaoFluxo | Questao respondida |
| resposta | TextField | Texto da resposta |
| resposta_processada | JSONField | Resposta estruturada/validada |
| valida | Boolean | Se a resposta foi valida |
| mensagem_erro | TextField | Mensagem de erro (se invalida) |
| tentativas | PositiveInteger | Numero de tentativas ate acertar |
| data_resposta | DateTime | Quando respondeu |
| tempo_resposta | PositiveInteger | Tempo para responder (segundos) |
| ip_origem | GenericIPAddress | IP do usuario |
| dados_extras | JSONField | Dados adicionais |

**Tabela:** `respostas_questao`

---

### TentativaResposta

Rastreio detalhado de **cada tentativa** de resposta. Essencial para IA, analytics e estrategias de erro.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| questao | FK → QuestaoFluxo | Questao |
| tentativa_numero | PositiveInteger | Numero da tentativa (1, 2, 3...) |
| resposta_original | TextField | Resposta bruta do usuario |
| resposta_processada | JSONField | Resposta processada |
| valida | Boolean | Se foi valida |
| mensagem_erro | TextField | Mensagem de erro |
| resultado_ia | JSONField | Resultado completo da validacao IA |
| confianca_ia | Decimal(5,4) | Score de confianca 0.0 a 1.0 |
| resultado_webhook | JSONField | Resposta do webhook N8N |
| estrategia_aplicada | CharField(50) | Estrategia de erro aplicada |
| contexto_tentativa | JSONField | Contexto no momento da tentativa |
| data_tentativa | DateTime | Quando tentou |
| tempo_resposta_segundos | PositiveInteger | Tempo da resposta |
| ip_origem | GenericIPAddress | IP |
| user_agent | TextField | Navegador/dispositivo |

**Tabela:** `tentativas_resposta`
**Constraint unico:** (atendimento, questao, tentativa_numero)

---

## Fluxo de execucao (passo a passo)

### 1. Inicio

O N8N (WhatsApp) ou painel chama `POST /api/n8n/atendimento/iniciar/` com `lead_id` e `fluxo_id`. O sistema:
- Verifica se nao existe sessao ativa para o lead nesse fluxo
- Cria `AtendimentoFluxo` com status `iniciado`
- Retorna primeira questao renderizada

### 2. Questao

A questao e renderizada com opcoes (estaticas ou dinamicas). Se usar `template_questao`, as variaveis do contexto sao substituidas (ex: "Ola {{nome_cliente}}, qual plano?").

### 3. Resposta

O lead responde via `POST /api/n8n/atendimento/<id>/responder/`. O sistema valida em cascata:

1. **Tipo** (email, CPF, telefone, etc.)
2. **Regras** (tamanho, regex, faixa numerica)
3. **Opcoes dinamicas** (planos, vencimentos)
4. **Webhook N8N** (se configurado)
5. **IA** (se configurado, placeholder)

### 4. Resposta invalida

Cria `TentativaResposta` com `valida=False` e aplica estrategia de erro:

| Estrategia | Comportamento |
|------------|--------------|
| repetir | Repete a questao com mensagem de erro |
| pular | Avanca para a proxima questao |
| redirecionar | Envia para uma questao especifica |
| finalizar | Encerra o atendimento |
| escalar_humano | Transfere para atendente humano |

### 5. Resposta valida

1. Cria `RespostaQuestao` e `TentativaResposta` com `valida=True`
2. Salva em `dados_respostas[indice]`
3. Executa webhook pos-resposta (se configurado)
4. Determina proxima questao via roteamento inteligente

### 6. Finalizacao

Via `POST /api/n8n/atendimento/<id>/finalizar/`:
1. Status → `completado`
2. Tempo total calculado
3. Score de qualificacao calculado (1 a 10)
4. Lead atualizado com score e observacoes
5. Resultado final armazenado em `resultado_final`

---

## Integracao N8N / WhatsApp

```
WhatsApp (lead envia mensagem)
      ↓
N8N recebe webhook
      ↓
N8N chama POST /api/n8n/atendimento/iniciar/
      ↓
Aurora retorna primeira questao
      ↓
N8N envia questao via WhatsApp
      ↓
Lead responde
      ↓
N8N chama POST /api/n8n/atendimento/<id>/responder/
      ↓
Aurora valida, roteia e retorna proxima questao/acao
      ↓
[loop ate finalizar]
      ↓
N8N chama POST /api/n8n/atendimento/<id>/finalizar/
      ↓
Lead qualificado com score e dados no sistema
```

---

## Endpoints da API

### APIs de Sessao

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/atendimentos/` | Listar sessoes (paginado, filtravel) |
| POST | `/api/atendimentos/criar/` | Criar sessao |
| PUT | `/api/atendimentos/<id>/atualizar/` | Atualizar sessao |
| POST | `/api/atendimentos/<id>/responder/` | Responder questao (com validacao inteligente) |
| POST | `/api/atendimentos/<id>/finalizar/` | Finalizar sessao |

### APIs de Respostas

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/respostas/` | Listar respostas (paginado, filtravel) |

### APIs de Estatisticas

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/atendimento/estatisticas/` | Estatisticas gerais por fluxo |

### APIs N8N (Bot WhatsApp)

| Metodo | URL | Descricao |
|--------|-----|-----------|
| POST | `/api/n8n/atendimento/iniciar/` | Iniciar atendimento |
| GET | `/api/n8n/atendimento/<id>/consultar/` | Consultar sessao |
| POST | `/api/n8n/atendimento/<id>/responder/` | Responder questao |
| POST | `/api/n8n/atendimento/<id>/avancar/` | Avancar para proxima questao |
| POST | `/api/n8n/atendimento/<id>/finalizar/` | Finalizar |
| POST | `/api/n8n/atendimento/<id>/pausar/` | Pausar sessao |
| POST | `/api/n8n/atendimento/<id>/retomar/` | Retomar sessao pausada |
| GET | `/api/n8n/lead/buscar/` | Buscar lead por telefone |
| POST | `/api/n8n/lead/criar/` | Criar lead via N8N |
| GET | `/api/n8n/fluxos/` | Listar fluxos ativos |
| GET | `/api/n8n/fluxo/<id>/questao/<indice>/` | Obter questao especifica |
| GET | `/api/n8n/fluxo/<id>/questao/<indice>/inteligente/` | Questao com roteamento |
| GET | `/api/n8n/atendimento/<id>/tentativas/` | Historico de tentativas |
| GET | `/api/n8n/atendimento/<id>/estatisticas/inteligente/` | Estatisticas da sessao |

---

## Servico externo (atendimento_service.py)

Integra com a API Matrix/HubSoft para buscar dados de atendimentos externos e gerar HTML das conversas.

| Funcao | Descricao |
|--------|-----------|
| `buscar_dados_atendimento(codigo)` | Busca dados do atendimento na API Matrix |
| `_gerar_html(dados, lead)` | Gera HTML estilo chat (bolhas WhatsApp) com header, contato e timeline de mensagens |
| `_substituir_emojis(texto)` | Converte codigos `##1f680##` para emojis reais |
| `_mascarar_cpf(cpf)` | Mascara CPF para privacidade (mostra 3 primeiros e 2 ultimos) |

**Variaveis de ambiente:** `MATRIX_API_URL`, `MATRIX_API_TOKEN`
**Saida:** Arquivo HTML em `media/conversas_atendimento/{lead_id}_{codigo}.html`

**Gatilho:** Signal em `apps/comercial/cadastro/signals.py`. Quando todas as imagens de documento de um lead sao validadas (`documentos_validos`), gera automaticamente o PDF e o HTML da conversa.

---

## Relacionamentos

```
AtendimentoFluxo
├── lead → LeadProspecto (N:1, cascade)
├── fluxo → FluxoAtendimento (N:1, cascade)
├── historico_contato → HistoricoContato (N:1, opcional)
├── respostas_detalhadas → RespostaQuestao (1:N, cascade)
└── tentativas_respostas → TentativaResposta (1:N, cascade)

RespostaQuestao
├── atendimento → AtendimentoFluxo (N:1)
└── questao → QuestaoFluxo (N:1)

TentativaResposta
├── atendimento → AtendimentoFluxo (N:1)
└── questao → QuestaoFluxo (N:1)
```

---

## Tabelas no banco

| Model | Tabela |
|-------|--------|
| AtendimentoFluxo | `atendimentos_fluxo` |
| RespostaQuestao | `respostas_questao` |
| TentativaResposta | `tentativas_resposta` |

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `apps/comercial/atendimento/models.py` | Models AtendimentoFluxo, RespostaQuestao, TentativaResposta |
| `apps/comercial/atendimento/views_api.py` | APIs de sessao, respostas, N8N |
| `apps/comercial/atendimento/admin.py` | Admin com inlines e acoes |
| `apps/comercial/atendimento/services/atendimento_service.py` | Integracao Matrix/HubSoft, geracao HTML |
