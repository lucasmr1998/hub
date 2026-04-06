# 13. Comercial — Modulo de Fluxos

**Status:** ✅ Em producao
**Ultima atualizacao:** 06/04/2026
**App:** `apps/comercial/atendimento/`

---

## Contexto

O modulo de Fluxos e o motor de fluxos conversacionais (bot) da AuroraISP. Permite criar questionarios inteligentes que guiam o lead por etapas de qualificacao, venda, suporte ou onboarding. Cada fluxo e composto por questoes ordenadas com validacao, roteamento condicional e opcoes dinamicas.

A **execucao** dos fluxos (sessoes de atendimento, respostas, tentativas, integracao N8N) esta documentada em `14-MODULO_ATENDIMENTO.md`.

---

## Models

### FluxoAtendimento

Define um fluxo/bot reutilizavel.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| nome | CharField(255) | Nome do fluxo |
| descricao | TextField | Descricao detalhada |
| tipo_fluxo | CharField(20) | qualificacao, vendas, suporte, onboarding, pesquisa, customizado |
| status | CharField(20) | ativo, inativo, rascunho, teste |
| max_tentativas | PositiveInteger | Maximo de tentativas para completar (padrao: 3) |
| tempo_limite_minutos | PositiveInteger | Tempo limite em minutos |
| permite_pular_questoes | Boolean | Permite pular questoes opcionais |
| criado_por | CharField(100) | Usuario criador |
| ativo | Boolean | Ativo/inativo |

**Tabela:** `fluxos_atendimento`

**Metodos:**
- `get_questoes_ordenadas()` — questoes ativas ordenadas por indice
- `get_total_questoes()` — contagem de questoes ativas
- `pode_ser_usado()` — verifica se esta ativo e tem questoes
- `get_estatisticas()` — total de atendimentos, taxa de completacao, tempo medio

---

### QuestaoFluxo

Questao individual dentro de um fluxo. Suporta 20+ tipos e validacao multicamada.

**Tabela:** `questoes_fluxo`
**Constraint unico:** (fluxo, indice)

#### Campos basicos

| Campo | Tipo | Descricao |
|-------|------|-----------|
| fluxo | FK → FluxoAtendimento | Fluxo pai |
| indice | PositiveInteger | Ordem no fluxo |
| titulo | CharField(255) | Texto da questao |
| descricao | TextField | Instrucoes adicionais |
| tipo_questao | CharField(20) | Tipo (ver tabela abaixo) |
| tipo_validacao | CharField(25) | obrigatoria, opcional, condicional, ia_assistida, validacao_customizada |
| opcoes_resposta | JSONField | Opcoes para select/multiselect |
| resposta_padrao | TextField | Resposta padrao/placeholder |
| ativo | Boolean | Se a questao esta ativa |

#### Tipos de questao

| Tipo | Descricao |
|------|-----------|
| texto | Texto livre |
| numero | Numerico inteiro |
| email | E-mail com validacao |
| telefone | Telefone com validacao |
| cpf_cnpj | CPF ou CNPJ com validacao |
| cep | CEP com validacao |
| endereco | Endereco completo |
| select | Lista de opcoes (escolha unica) |
| multiselect | Lista de opcoes (multipla escolha) |
| data | Data |
| hora | Hora |
| data_hora | Data e hora |
| boolean | Sim/Nao |
| escala | Escala numerica (ex: 1 a 10) |
| arquivo | Upload de arquivo |
| planos_internet | Selecao dinamica de planos (PlanoInternet) |
| vencimentos | Selecao dinamica de vencimentos (OpcaoVencimento) |
| opcoes_dinamicas | Opcoes carregadas de fonte externa |
| ia_validacao | Validacao via IA |
| condicional_complexa | Logica condicional avancada |

#### Validacao

| Campo | Descricao |
|-------|-----------|
| regex_validacao | Regex para validacao customizada |
| tamanho_minimo / tamanho_maximo | Limites de caracteres |
| valor_minimo / valor_maximo | Limites numericos |
| prompt_ia_validacao | Prompt para validacao IA (template com `{{resposta}}`) |
| criterios_ia | Criterios com pesos: `{criterio: peso}` |
| webhook_n8n_validacao | URL do webhook N8N para validacao externa |
| webhook_n8n_pos_resposta | URL chamada apos resposta valida |

#### Roteamento inteligente

| Campo | Descricao |
|-------|-----------|
| questao_dependencia | Questao que precisa ser respondida antes |
| valor_dependencia | Valor exigido na questao dependente |
| roteamento_respostas | Mapa `{valor_resposta: questao_id}` para routing condicional |
| questao_padrao_proxima | Proxima questao padrao (fallback do roteamento) |

Logica de roteamento (em ordem de prioridade):
1. Rota especifica por valor da resposta (`roteamento_respostas`)
2. Acoes especiais (ver_mais_planos, ver_mais_vencimentos)
3. Questao padrao proxima (`questao_padrao_proxima`)
4. Proxima sequencial por indice
5. Fim do fluxo

#### Estrategia de erro

| Campo | Descricao |
|-------|-----------|
| max_tentativas | Maximo de tentativas antes de aplicar estrategia (padrao: 3) |
| estrategia_erro | repetir, pular, redirecionar, finalizar, escalar_humano |
| questao_erro_redirecionamento | Questao destino em caso de redirecionamento |
| mensagem_erro_padrao | Mensagem de erro customizada |
| mensagem_tentativa_esgotada | Mensagem quando esgota tentativas |

| Estrategia | Comportamento |
|------------|--------------|
| repetir | Repete a questao com mensagem de erro |
| pular | Avanca para a proxima questao |
| redirecionar | Envia para uma questao especifica |
| finalizar | Encerra o atendimento |
| escalar_humano | Transfere para atendente humano |

#### Opcoes dinamicas

| Campo | Descricao |
|-------|-----------|
| opcoes_dinamicas_fonte | planos_internet, opcoes_vencimento, api_externa, query_customizada |
| query_opcoes_dinamicas | SQL ou config para buscar opcoes |
| variaveis_contexto | Variaveis para template: `{nome: valor}` |
| template_questao | Template com variaveis: "Ola {{nome}}, qual plano?" |

#### Comportamento

| Campo | Descricao |
|-------|-----------|
| permite_voltar | Permite voltar para esta questao |
| permite_editar | Permite editar resposta apos enviar |
| ordem_exibicao | Ordem de exibicao (visual) |

---

## Exemplo de roteamento

```
Questao 1: "Qual plano voce prefere?"
  tipo: select
  opcoes_dinamicas_fonte: planos_internet
  roteamento_respostas: {"1": 3, "2": 3, "3": 4}

  Se resposta = plano 1 ou 2 → vai para questao 3
  Se resposta = plano 3 → vai para questao 4
  Se resposta = "ver_mais_planos" → mostra todos os planos
  Default → proxima sequencial (questao 2)
```

---

## Endpoints — Configuracao

### Paginas (HTML)

| URL | Descricao |
|-----|-----------|
| `/configuracoes/fluxos/` | Gerenciamento de fluxos |
| `/configuracoes/questoes/` | Gerenciamento de questoes |
| `/configuracoes/questoes/<fluxo_id>/` | Questoes de um fluxo especifico |

### APIs de Fluxos

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/fluxos/` | Listar fluxos (paginado, filtravel) |
| POST | `/api/fluxos/criar/` | Criar fluxo |
| PUT | `/api/fluxos/<id>/atualizar/` | Atualizar fluxo |
| DELETE | `/api/fluxos/<id>/deletar/` | Deletar fluxo (bloqueia se tem atendimentos) |

### APIs de Questoes

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/questoes/` | Listar questoes (filtra por fluxo_id) |
| POST | `/api/questoes/criar/` | Criar questao |
| PUT | `/api/questoes/<id>/atualizar/` | Atualizar questao |
| DELETE | `/api/questoes/<id>/deletar/` | Deletar questao (bloqueia se tem respostas) |
| GET/POST/PUT/DELETE | `/api/configuracoes/questoes/` | CRUD unificado para gerencia |
| POST | `/api/configuracoes/questoes/duplicar/` | Duplicar questao |

---

## Relacionamentos

```
FluxoAtendimento
├── questoes → QuestaoFluxo (1:N, cascade)
└── atendimentos → AtendimentoFluxo (1:N, cascade)

QuestaoFluxo
├── questao_dependencia → QuestaoFluxo (self-ref, opcional)
├── questao_padrao_proxima → QuestaoFluxo (self-ref, opcional)
├── questao_erro_redirecionamento → QuestaoFluxo (self-ref, opcional)
├── respostas → RespostaQuestao (1:N)
└── tentativas → TentativaResposta (1:N)
```

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `apps/comercial/atendimento/models.py` | Models FluxoAtendimento e QuestaoFluxo |
| `apps/comercial/atendimento/views.py` | Views HTML de configuracao |
| `apps/comercial/atendimento/views_api.py` | APIs de CRUD de fluxos e questoes |
| `apps/comercial/atendimento/admin.py` | Admin com inlines e acoes |
| Templates: `fluxos.html`, `questoes.html` | Interface de configuracao |
