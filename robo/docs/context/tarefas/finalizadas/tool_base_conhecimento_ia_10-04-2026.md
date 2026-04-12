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
**Status:** ✅ Concluido

---

## Descricao

Tool de sistema no Agente IA que consulta artigos da base de conhecimento para responder perguntas. Quando nao encontra, registra a pergunta para o gestor criar artigo depois.

---

## Tarefas

- [x] Criar tool de sistema `consultar_base_conhecimento` no engine
- [x] Buscar artigos por similaridade (titulo, conteudo, tags)
- [x] Retornar conteudo dos top 3 artigos como contexto para a IA
- [x] Se nenhum artigo encontrado, retornar mensagem e registrar pergunta
- [x] Model `PerguntaSemResposta` (pergunta, lead, conversa, ocorrencias, status, artigo_criado)
- [x] Evitar duplicatas (incrementa ocorrencias)
- [x] Checkbox no editor de fluxos (lista de tools do sistema)
- [x] Tela de gestao de perguntas sem resposta (filtro, busca, metricas)
- [x] Botoes: Criar Artigo, Resolver, Ignorar
- [x] Link "Perguntas IA" no sidebar do Suporte
- [x] Migration 0006

---

## Contexto e referencias

- Engine: `apps/comercial/atendimento/engine.py` (funcao _executar_consulta_base_conhecimento)
- Model: `apps/suporte/models.py` (PerguntaSemResposta)
- Views: `apps/suporte/views.py` (perguntas_sem_resposta, api_pergunta_resolver, api_pergunta_ignorar)
- Editor: `apps/comercial/atendimento/templates/.../editor_fluxo.html` (toolsSistema)
- Template: `suporte/perguntas_sem_resposta.html`
- Sessao 12/04/2026

---

## Fluxo

```
Lead pergunta algo → Agente IA chama tool consultar_base_conhecimento
  → Busca artigos na base (titulo, conteudo, tags)
    → Encontrou? → Retorna top 3 artigos → IA responde com base nos artigos
    → Nao encontrou? → Registra PerguntaSemResposta → IA responde com conhecimento geral
                        → Gestor ve na tela "Perguntas IA" → Cria artigo → Proxima vez encontra
```

---

## Resultado

Agente IA responde com base em artigos da empresa. Perguntas sem resposta sao registradas. Ciclo de melhoria continua.
