# Tarefa: Sistema de Permissões por Módulo/Papel/Escopo

**Data:** 05/04/2026
**Status:** Em andamento
**Prioridade:** Alta

---

## Objetivo

Implementar controle granular de permissões com 3 camadas: módulo (acesso sim/não), papel (role dentro do módulo) e escopo (visibilidade de dados).

## Escopo

1. Model `PermissaoUsuario` com flags por módulo e papel
2. Decorator `@permissao_required` para views
3. Filtro de escopo nos querysets (meus/equipe/todos)
4. Sidebar filtrada por permissões
5. Tela de gestão de permissões (na página de usuários existente)

## Papéis por módulo

- Comercial: vendedor, supervisor, gerente
- Marketing: analista, gerente
- CS: operador, gerente
- Inbox: agente, supervisor, gerente
- Configurações: acesso sim/não (só admin)
