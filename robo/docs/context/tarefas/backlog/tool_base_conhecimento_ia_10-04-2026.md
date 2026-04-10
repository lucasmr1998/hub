---
name: "Tool IA: Consultar Base de Conhecimento"
description: "Tool do Agente IA que consulta a base de conhecimento e registra perguntas sem resposta"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Tool IA: Consultar Base de Conhecimento — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Criar uma tool do sistema no Agente IA que consulta a base de conhecimento (`ArtigoConhecimento`) para responder perguntas do lead. O agente decide quando chamar a tool (igual as tools customizadas). Se nao encontrar artigos relevantes, registra a pergunta para o gestor criar resposta depois.

---

## Tarefas

### Tool no Engine
- [ ] Criar tool de sistema `consultar_base_conhecimento` no engine
- [ ] Buscar artigos por similaridade (titulo, conteudo, tags) usando a pergunta do lead
- [ ] Retornar conteudo dos top 3 artigos mais relevantes como contexto para a IA
- [ ] Se nenhum artigo encontrado, retornar "Nenhuma informacao encontrada na base"

### Perguntas sem resposta
- [ ] Criar model `PerguntaSemResposta` (pergunta, lead, data, fluxo, nodo, status: pendente/respondida, artigo_criado FK)
- [ ] Registrar pergunta quando a busca nao encontra resultados
- [ ] Evitar duplicatas (mesma pergunta similar)

### UI — Config do Agente
- [ ] Adicionar `consultar_base_conhecimento` na lista de tools do sistema no editor
- [ ] Checkbox para ativar/desativar (igual atualizar_lead, criar_oportunidade, etc)

### UI — Gestao de perguntas
- [ ] Tela com lista de perguntas sem resposta (filtro por status, busca)
- [ ] Botao "Criar Artigo" que abre o form pre-preenchido com a pergunta
- [ ] Ao criar artigo, marca pergunta como respondida
- [ ] Metricas: total pendentes, mais frequentes

---

## Contexto e referencias

- Base de conhecimento: `apps/suporte/models.py` → `ArtigoConhecimento`, `CategoriaConhecimento`
- Agente IA tools: `apps/comercial/atendimento/engine.py` → `_chamar_llm_com_tools`
- Tools do sistema no editor: `apps/comercial/atendimento/templates/.../editor_fluxo.html`
- Busca existente: `apps/suporte/views.py` → `api_buscar_conhecimento` (busca por titulo/conteudo/tags)

---

## Fluxo de funcionamento

```
Lead pergunta algo → Agente IA decide chamar tool "consultar_base_conhecimento"
  → Busca artigos relevantes na base
    → Encontrou? → Retorna conteudo como contexto → IA responde com base no artigo
    → Nao encontrou? → Registra como PerguntaSemResposta → IA responde com conhecimento geral
                        → Gestor ve na tela → Cria artigo → Proxima vez a tool encontra
```

---

## Resultado esperado

1. Agente IA responde com base em artigos da base de conhecimento da empresa
2. Perguntas sem resposta sao registradas automaticamente
3. Gestor cria artigos para as perguntas mais frequentes
4. Ciclo de melhoria continua: mais perguntas → mais artigos → respostas melhores
