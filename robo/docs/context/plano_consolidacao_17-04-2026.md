# Plano de Consolidacao — 17/04/2026

**Contexto:** Analise franca do estado do produto Hubtrix apos semanas de desenvolvimento intenso. Lista pontos fortes, pontos fracos e acoes concretas para resolver cada um. Executar por partes, sem pressa.

---

## Estado Atual

### O que esta forte

- **Engine de fluxo visual**: node-based, dual-mode (legado/visual), IA integrada em questoes, fallbacks inteligentes, delays, recontato, transferencia humana
- **Multi-tenancy serio**: TenantMixin, TenantManager, filtros em signals, auditoria cruzada
- **Assistente CRM via WhatsApp**: diferencial real, cross-tenant, reutiliza o engine de fluxo
- **Base de conhecimento automatica nos fallbacks**: transforma o bot em algo que melhora sozinho

### O que preocupa

1. **Engine complexo e dificil de debugar** — 2200 linhas, 11 tipos de nodos, multiplos caminhos de fallback. Cada bug consome horas abrindo banco.
2. **Muitas features, poucas concluidas** — bugs pendentes, prompts que precisam de ajuste manual no banco, Uazapi com problemas, deploy com surpresas. Cada nova feature adiciona superficie pra quebrar.
3. **Acoplamento ao bot** — produto gira em torno de "bot WhatsApp". CRM, inbox, dashboard — tudo ao redor disso. Bom mercado mas pode limitar posicionamento.
4. **Documentacao defasa** — sem regra automatica, a doc fica desatualizada cada vez que entra uma feature nova.
5. **Onboarding de cliente complicado** — FATEPI demorou dias pra configurar. Sem guia, novos clientes enfrentam o mesmo.

---

## Acoes Concretas (em ordem de prioridade)

### 1. Tela de debug da sessao (alto valor, baixo esforco)

**Problema:** Hoje precisa abrir o banco pra entender por que um fluxo deu erro.

**Solucao:** Criar `/sessoes/<id>/debug` com:
- Timeline de cada nodo executado + tempo
- Contexto (`dados_respostas`, variaveis) no momento de cada execucao
- Prompt enviado + resposta da LLM em cada chamada IA
- Base de conhecimento consultada (termos buscados, artigos encontrados/nao encontrados)
- Decisoes de branch (true/false) com justificativa

**Por que comecar por aqui:** a maioria dos bugs que enfrentamos seria obvia em 30 segundos. Baixo esforco, alto retorno. Reduz o custo de debug das proximas features.

---

### 2. Checklist de "feature completa" + regra anti-paralelismo

**Problema:** Features sao consideradas prontas antes de estarem. Features novas comecam enquanto bugs criticos continuam abertos.

**Solucao:** Adicionar ao `CLAUDE.md`:

```
Uma feature so e "completa" quando:
- Teste E2E passando (nao so unitario)
- Documentacao em robo/docs/PRODUTO/ atualizada
- Nenhum print/comentario de debug deixado no codigo
- Deploy validado em producao com teste real
- Zero bugs criticos abertos no escopo da feature

Nao comecar feature nova enquanto houver bug critico aberto.
```

**Por que:** ritmo cai no curto prazo mas acelera no medio. Menos retrabalho, menos surpresas no deploy.

---

### 3. Wizard de onboarding do cliente

**Problema:** FATEPI demorou dias pra configurar o fluxo. Sem guia, cada novo cliente enfrenta o mesmo.

**Solucao:** Wizard de setup dentro do sistema, passo a passo:

1. Conectar WhatsApp (Uazapi com teste de conexao)
2. Criar primeiro fluxo a partir de template (qualificacao/vendas/suporte)
3. Alimentar base de conhecimento (importacao CSV ou editor guiado)
4. Testar o fluxo (simulador embutido)
5. Ativar no canal real

**Por que:** maior barreira de adocao hoje e configuracao inicial. Um wizard bem feito transforma "dias de setup" em "30 minutos e funcionando".

---

### 4. Hook de documentacao

**Problema:** docs defasam cada vez que entra feature nova.

**Solucao (simples):** pre-commit hook que verifica se arquivos em `apps/comercial/atendimento/` ou `apps/inbox/` foram modificados sem mudanca correspondente em `robo/docs/PRODUTO/`. Alerta (nao bloqueia) no commit.

**Alternativa mais leve:** script rodado antes de cada deploy que lista models/views modificados desde ultimo commit em producao e verifica se tem entrada nos docs.

**Por que:** disciplina sem depender de lembrar manualmente.

---

### 5. Posicionamento do produto (narrativa, nao codigo)

**Problema:** comunicacao hoje e "CRM + bot + inbox + automacao + ...". Dilui o valor real.

**Solucao:** posicionar a Hubtrix como **"CRM com assistente IA via WhatsApp"**. O assistente CRM e o diferencial mais unico — nenhum CRM brasileiro pequeno tem isso. Todas as outras features sao suporte para esse ponto central.

**Por que:** nao mexe em codigo, so na narrativa (site, propostas, pitches). Com o tempo, features que nao servem esse posicionamento viram candidatas a simplificar ou remover.

---

### 6. Debitos dos nodos do engine de fluxo

**Problema:** diagnostico em `diagnostico_nodos_fluxo_17-04-2026.md` identificou problemas em cada um dos 11 tipos de nodos. Alguns criticos, outros de manutencao de longo prazo.

#### P0 — Tapa buraco obvio (2-3 dias)

- **Logar raw das LLMs** (classificador, extrator, respondedor, agente) nos logs de atendimento
  - Resolve ~80% dos bugs de IA que aparecem
  - Hoje nao da pra saber o que a LLM realmente respondeu
- **`motivo_finalizacao` configuravel** no nodo finalizacao (hoje fica tudo "completado")
- **Interpolacao de variaveis** na `mensagem_final` da finalizacao (`{{lead_nome}}`, etc.)

#### P1 — Melhorias importantes (3-5 dias)

- **Branches multiplos no `ia_classificador`** — uma saida por categoria, evita forcar `condicao` depois
- **Branch `erro` opcional no nodo `acao`** — se `criar_oportunidade` falhar, ir pra tratamento em vez de continuar como se nada tivesse acontecido
- **Validacao de schema JSON** nas configuracoes de nodos (evita typo em chaves virar bug silencioso)

#### P2 — Saude de medio prazo (5-7 dias)

- **Condicao composta (AND/OR)** — evita encadear varios nodos de condicao em serie
- **`max_turnos` funcionando** no `ia_respondedor` — hoje nunca sai, historico cresce indefinidamente
- **Tools extensiveis por tenant** no `ia_agente` — hoje estao hardcoded no codigo

#### P3 — Refatoracao de longo prazo

- **Quebrar `engine.py`** em modulos por tipo de nodo (`engine/nodes/questao.py`, etc.) — hoje sao 2200 linhas num arquivo so
- **Testes unitarios por tipo de nodo** — hoje so tem integracao via simulador
- **Contexto imutavel ou com eventos** — hoje e dict mutavel passado por referencia, dificil debugar

**Referencia completa:** `diagnostico_nodos_fluxo_17-04-2026.md`

---

## Ordem de Execucao Sugerida

| Ordem | Acao | Esforco | Quando |
|-------|------|---------|--------|
| 1 | Tela de debug de sessao | 1-2 dias | Proxima semana |
| 2 | Checklist de feature completa | 30 min | Imediato (CLAUDE.md) |
| 3 | Debitos P0 dos nodos (raw LLMs + finalizacao) | 2-3 dias | Proxima semana |
| 4 | Wizard de onboarding | 3-5 dias | Apos a 1 e 3 |
| 5 | Hook de documentacao | 2 horas | Qualquer momento |
| 6 | Debitos P1 dos nodos (branches, erro, schema) | 3-5 dias | Apos a 4 |
| 7 | Posicionamento | Conversas | Paralelo |
| 8 | Debitos P2 e P3 dos nodos | 1-2 semanas | Medio/longo prazo |

Nao precisa fazer tudo de uma vez. Cada item independe do outro.

A recomendacao especifica dos nodos: rodar **P0 + P1 antes de adicionar features novas**. Sao 5-8 dias de trabalho focado que estabilizam muito o sistema.

---

## Referencias

- `13-MODULO_FLUXOS.md` — documentacao da configuracao dos fluxos
- `14-MODULO_ATENDIMENTO.md` — documentacao da execucao
- `17-ASSISTENTE_CRM.md` — assistente CRM via WhatsApp
- `diagnostico_nodos_fluxo_17-04-2026.md` — analise critica detalhada de cada nodo
