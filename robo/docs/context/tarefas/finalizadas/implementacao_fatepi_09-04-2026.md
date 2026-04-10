# Implementacao FATEPI/FAESPI — Documentacao Completa

**Status:** Implementado
**Data:** 09/04/2026
**Cliente:** Fatepi/Faespi (Faculdade de Tecnologia de Teresina)
**Tenant ID:** 7

---

## 1. Visao Geral

A FATEPI e o primeiro cliente ativo da plataforma Hubtrix. A implementacao cobre o fluxo completo de captacao de alunos: desde o primeiro contato via WhatsApp ou Widget ate a matricula, com inteligencia artificial integrada em todas as etapas.

### Modulos ativos
- **Comercial** (CRM com pipeline de matriculas)
- **Atendimento** (fluxo visual com IA)
- **Inbox** (WhatsApp + Widget)

---

## 2. Pipeline CRM — Matriculas

O pipeline foi desenhado para refletir a jornada do candidato na faculdade:

| Ordem | Estagio | Slug | O que significa |
|-------|---------|------|-----------------|
| 1 | Novo Lead | `novo` | Candidato acabou de entrar em contato |
| 2 | Qualificacao | `qualificacao` | Curso identificado, oportunidade criada |
| 3 | Qualificado | `qualificado` | Forma de ingresso definida (ENEM/Vestibular/Transferencia) |
| 4 | Agendado | `agendado` | Candidato confirmou interesse na matricula |
| 5 | Matriculado | `matriculado` | Pagamento realizado, matricula confirmada |
| 6 | Perdido | `perdido` | Candidato desistiu ou nao respondeu |

### Dados customizados da oportunidade
- `curso_interesse` — curso escolhido pelo candidato
- `forma_ingresso` — ENEM, Prova Online, Transferencia ou Segunda Graduacao

---

## 3. Fluxo de Atendimento (ID: 9)

### Nome: FATEPI v2 - Qualificacao Completa

Fluxo visual com 18 nodos e 21 conexoes. Usa IA (OpenAI gpt-4o-mini) em todas as etapas criticas.

### Estrutura do fluxo

```
INICIO
  |
  v
PERGUNTA NOME (IA extratora)
  |-- Sucesso --> PERGUNTA CURSO (IA classifica + extrai)
  |-- Fallback --> AGENTE IA --> volta pra pergunta
  |
  v
CONDICAO: Curso valido?
  |-- Sim --> CRIAR OPORTUNIDADE --> MOVER "qualificacao"
  |-- Nao --> "Nao temos esse curso" --> volta pra condicao
  |
  v
PERGUNTA INGRESSO (IA extratora)
  |-- Sucesso --> MOVER "qualificado"
  |-- Fallback --> AGENTE IA --> volta pra pergunta
  |
  v
IA RESPONDEDOR (apresenta valores + bolsas + pergunta decisao)
  |
  v
CLASSIFICADOR SILENCIOSO (sim/nao/duvida)
  |
  v
CONDICAO: Quer matricular?
  |-- Sim --> MOVER "agendado" --> ENVIA PIX --> MOVER "matriculado" --> FIM (score 10)
  |-- Nao --> FIM (despedida)
```

### Detalhamento dos nodos

| # | Tipo | Config |
|---|------|--------|
| 1 | Entrada | Canal: qualquer |
| 2 | Questao Nome | IA extratora, salva em `lead.nome_razaosocial`, pula se preenchido |
| 3 | Questao Curso | IA classifica (valido/invalido) + extrai `curso_interesse` |
| 4 | Condicao | `var.validacao_curso == curso_valido` |
| 5 | Questao Re-ask | "Nao temos esse curso", mesma IA do nodo 3 |
| 6 | Acao | Criar Oportunidade: `{{lead_nome}} - {{curso_interesse}}` |
| 7 | Acao | Mover estagio → `qualificacao` |
| 8 | Questao Ingresso | IA extrai `forma_ingresso` (ENEM/Prova Online/Transferencia) |
| 9 | Acao | Mover estagio → `qualificado` |
| 10 | IA Respondedor | Apresenta valores com tabela de precos, bolsas progressivas, pergunta decisao |
| 11 | Questao Decisao | `espera_resposta=False`, IA classifica como sim/nao/duvida |
| 12 | Condicao | `var.decisao_matricula == sim` |
| 13 | Acao | Mover estagio → `agendado` |
| 14 | Questao PIX | Envia chave PIX e pede comprovante |
| 15 | Acao | Mover estagio → `matriculado` |
| 16 | Finalizacao | Score 10, mensagem de boas-vindas |
| 17 | Finalizacao | Despedida (candidato nao quis) |
| 18 | Agente IA | Fallback central com 3 tools |

### Agente IA (Fallback)

Todas as perguntas tem saida de fallback conectada ao Agente IA. Quando o candidato responde algo fora do esperado (duvida, pergunta, off-topic), o Agente:

1. Recebe a mensagem
2. Usa tool calling (OpenAI) para selecionar o especialista correto
3. Responde a duvida
4. Retoma a pergunta original de forma natural (instrucao no prompt)

**Tools do Agente:**

| Tool | Especialidade | Exemplos |
|------|--------------|----------|
| `consultor_comercial` | Valores, mensalidades, bolsas, pagamento | "Quanto custa Direito?", "Tem desconto?" |
| `info_academica` | Cursos, horarios, localizacao, estrutura | "Onde fica?", "Qual horario?" |
| `suporte_geral` | Documentos, processo seletivo, prazos | "Que documentos preciso?", "Como funciona o ENEM?" |

### Tabela de precos (embarcada nas tools)

| Curso | Mensalidade | Vestibular | ENEM | Transferencia |
|-------|-------------|------------|------|---------------|
| Direito | R$525 | R$199 | R$49,99 | R$99,99 |
| Sistemas de Informacao | R$350 | R$149 | R$49,99 | R$99,99 |
| Psicologia | R$570,50 | R$199 | R$49,99 | R$99,99 |
| Enfermagem | R$483 | R$169 | R$49,99 | R$99,99 |
| Fisioterapia | R$483 | R$169 | R$49,99 | R$99,99 |
| Administracao | R$311,50 | R$139 | R$49,99 | R$99,99 |
| Ciencias Contabeis | R$311,50 | R$139 | R$49,99 | R$99,99 |
| Pedagogia | R$294 | R$139 | R$49,99 | R$99,99 |
| Fonoaudiologia | R$483 | R$169 | R$49,99 | R$99,99 |
| Educacao Fisica | R$294 | R$139 | R$49,99 | R$99,99 |
| Servico Social | R$294 | R$139 | R$49,99 | R$99,99 |

Bolsas progressivas: 65% (2026.1), 60% (2026.2), 55% (2027.1), 50% (2027.2+)

---

## 4. Canais de Atendimento

| Canal | Tipo | Fluxo vinculado | Status |
|-------|------|-----------------|--------|
| WhatsApp FATEPI | whatsapp | FATEPI v2 (ID:9) | Ativo (Uazapi) |
| Chat Widget | widget | FATEPI v2 (ID:9) | Ativo |

### WhatsApp
- Provider: Uazapi (consulteplus.uazapi.com)
- Webhook: via ngrok (desenvolvimento) ou dominio (producao)
- Token: configurado no campo `api_token` da integracao

### Widget
- Embutido no site via JS
- Token publico por tenant
- FAQ integrado

---

## 5. Equipe e Distribuicao

### Equipe: Comercial FATEPI

| Nome | Email | Perfil | Cargo |
|------|-------|--------|-------|
| NTI FATEPI | nti@faespi.com.br | Admin | - |
| Direcao Geral | direcaogeral@faespi.com.br | Admin | - |
| Anne Caroline | annecaroline@faespi.com.br | Vendedor | Agente |
| Italo Viana | italoviana@faespi.com.br | Vendedor | Agente |
| Marisa Sousa | marisasousa@faespi.com.br | Vendedor | Agente |

### Fila: Atendimento Comercial
- Distribuicao: Round Robin
- Horario: Seg-Sex 08:00-18:00
- Regra de roteamento: Canal WhatsApp → esta fila

### Fluxo de transferencia
1. Lead entra pelo WhatsApp ou Widget
2. Bot atende (modo_atendimento = 'bot')
3. Bot completa o fluxo OU transfere para humano
4. Se transferido: conversa aparece na fila humana, distribuida por round robin
5. Vendedor ve apenas suas conversas + nao atribuidas da fila

---

## 6. Integracoes

| Integracao | Tipo | Status | Uso |
|------------|------|--------|-----|
| OpenAI | openai | Ativa | IA em todas as etapas (gpt-4o-mini) |
| Uazapi | uazapi | Ativa | Envio/recebimento WhatsApp |
| N8N | n8n | Desativada | Substituido pelo fluxo interno |

### API Key OpenAI
Armazenada em `IntegracaoAPI.configuracoes_extras['api_key']` (nao no access_token, que e EncryptedCharField).

---

## 7. Como tudo se conecta

```
CANDIDATO
    |
    v
[WhatsApp / Widget]
    |
    v
[Webhook Uazapi] --> [Signal: on_mensagem_recebida]
    |
    v
[Engine: iniciar_fluxo_visual]
    |
    v
[Fluxo FATEPI v2]
    |-- Perguntas com IA extratora/classificadora
    |-- Fallback --> Agente IA com tools
    |-- Acoes: criar oportunidade, mover estagio
    |
    v
[CRM Pipeline]
    |-- Novo Lead --> Qualificacao --> Qualificado --> Agendado --> Matriculado
    |
    v
[Transferir para Humano] (se necessario)
    |
    v
[Fila: Atendimento Comercial]
    |-- Round Robin --> Anne / Italo / Marisa
    |
    v
[Inbox] --> Vendedor atende no painel
```

---

## 8. Funcionalidades especificas implementadas

### Para o fluxo
- **Pular se preenchido**: pergunta do nome pula se lead ja tem nome
- **Fallback inteligente**: Agente IA responde duvidas e retoma pergunta naturalmente
- **IA multi-turno**: Respondedor de valores conversa com historico
- **Recontato automatico**: configuravel por fluxo (tentativas + intervalo + mensagem)
- **Simulador de teste**: chat embutido no editor para testar sem WhatsApp

### Para o CRM
- Oportunidade criada automaticamente com nome + curso
- Dados custom (curso_interesse, forma_ingresso) salvos na oportunidade
- Pipeline com 6 estagios refletindo jornada do candidato
- Movimentacao automatica entre estagios pelo fluxo

### Para o inbox
- Modo atendimento (bot/humano) para separar conversas
- Filas com horario de atendimento e distribuicao por equipe
- Transferencia para humano via nodo no fluxo
- Badge "Bot" visual para admin acompanhar

---

## 9. Acessos

| Email | Usuario | Senha | Perfil |
|-------|---------|-------|--------|
| admin@fatepi.com.br | admin | (definida anteriormente) | Admin |
| nti@faespi.com.br | nti_fatepi | Fatepi@2026 | Admin |
| direcaogeral@faespi.com.br | direcao_fatepi | Fatepi@2026 | Admin |
| annecaroline@faespi.com.br | anne_fatepi | Fatepi@2026 | Vendedor |
| italoviana@faespi.com.br | italo_fatepi | Fatepi@2026 | Vendedor |
| marisasousa@faespi.com.br | marisa_fatepi | Fatepi@2026 | Vendedor |

### Permissoes do perfil Vendedor
- Ver dashboard e pipeline do CRM
- Mover oportunidades entre estagios
- Criar e editar tarefas
- Ver suas conversas no inbox
- Responder, transferir e resolver conversas
