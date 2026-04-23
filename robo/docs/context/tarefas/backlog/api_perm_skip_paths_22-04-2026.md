---
name: "RBAC em rotas /api/ — middleware pula PermissaoMiddleware"
description: "/api/ esta em _PERM_SKIP_PATHS e nunca passa pelo PermissaoMiddleware. Views chamam user_tem_funcionalidade que retorna True por default quando o cache do middleware nao foi setado. Resultado: qualquer usuario logado passa em todas APIs internas sem RBAC."
prioridade: "🟠 Alta"
responsavel: "Tech"
---

# RBAC em rotas /api/ — middleware pula verificacao — 22/04/2026

**Data:** 22/04/2026
**Responsavel:** Tech
**Prioridade:** 🟠 Alta (bug de seguranca com impacto RBAC)
**Status:** ⏳ Aguardando analise + decisao

---

## Contexto

Descoberto em 22/04/2026 ao corrigir 17 testes falhando no suite. Os 5 testes restantes (`*_sem_permissao_403`) revelaram um gap de seguranca:

### Comportamento atual

1. `PermissaoMiddleware` em `apps/sistema/middleware.py` tem `_PERM_SKIP_PATHS` que inclui `/api/`
2. Quando a rota comeca com `/api/`, o middleware NAO seta `request.user_funcionalidades`
3. Views chamam `user_tem_funcionalidade(request, 'codigo')` que faz:
   ```python
   funcs = getattr(request, 'user_funcionalidades', None)
   if funcs is None:  # None = sem perfil (legado), tudo liberado
       return True
   ```
4. Como `user_funcionalidades` nao foi setado pelo middleware, `getattr(...)` retorna o default None → liberado

### Impacto

APIs internas que deveriam ter RBAC (criar/editar/deletar usuario, salvar config, criar estagio, criar equipe, listar tipos/canais de notificacao) ficam abertas pra qualquer user autenticado do tenant:

- `/api/configuracoes/usuarios/` (CRUD usuarios) — qualquer login cria/edita/deleta usuario
- `/api/configuracoes/...` (todas rotas de config)
- `/api/crm/...` (varias rotas CRM sem token_required)
- `/api/notificacoes/...` (tipos/canais/templates)

**Impacto real limitado** porque:
- `api_token_required` (decorator) protege endpoints externos (N8N, Matrix) — esses estao OK
- Superuser/admin sempre passa mesmo com o bug (not actionable pra eles)
- Multi-tenant ainda isolado (usuarios do tenant B nao aparecem pra tenant A)

**Impacto real preocupante:**
- Qualquer user com login valido no tenant, sem perfil de permissao, consegue chamar APIs administrativas via DevTools/curl
- Logs nao mostram "Sem permissao" pra esses casos — parece sucesso

---

## Opcoes de correcao

### A. Remover `/api/` de `_PERM_SKIP_PATHS`
Middleware passa a rodar em rotas `/api/`, setando `user_funcionalidades`. Views com `user_tem_funcionalidade` passam a funcionar corretamente.

**Risco:** qualquer rota `/api/*` passa a ter o modulo-check do middleware (prefixo de URL → modulo). Pode bloquear rotas legitimas que hoje funcionam.

Mitigacao: rodar suite de testes completa e smoke test em prod antes de ligar.

### B. `user_tem_funcionalidade` faz fallback buscando no DB
Em vez de confiar no cache do middleware, a funcao busca direto:

```python
def user_tem_funcionalidade(request, codigo):
    if request.user.is_superuser:
        return True
    funcs = getattr(request, 'user_funcionalidades', None)
    if funcs is None:
        # Fallback: buscar direto
        from apps.sistema.models import PermissaoUsuario
        perm = PermissaoUsuario.get_for_user(request.user)
        if perm is None:
            return True  # retrocompat: sem PermissaoUsuario = liberado
        funcs = set(perm.perfil.funcionalidades.values_list('codigo', flat=True)) if perm.perfil else set()
    return codigo in funcs
```

**Risco:** uma query extra por chamada de API. Performance nao ideal mas aceitavel pra rotas admin.

**Recomendada.** Menor risco que A.

### C. Decorator `@perm_required('codigo')` substituindo user_tem_funcionalidade
Aplica a verificacao antes da view rodar, com lookup direto. Mais explicito mas refactor maior.

---

## Escopo recomendado

1. Implementar opcao B (fallback no `user_tem_funcionalidade`)
2. Rodar os 5 testes xfail-ed — todos devem passar
3. Remover o `xfail` dos testes
4. Smoke test em staging/prod
5. Auditar com grep quais rotas APIs tem `user_tem_funcionalidade` pra garantir cobertura

---

## Dependencias

- Nao bloqueia ninguem agora (bug existente ha tempo sem reclamacao)
- Blocks: real RBAC nas APIs internas do Hubtrix

---

## Testes afetados

Marcados como `@pytest.mark.xfail` em `tests/test_views_full_coverage.py`:
- `test_tipos_non_superuser_denied`
- `test_canais_non_superuser_denied`
- `test_criar_usuario_sem_permissao_403`
- `test_editar_usuario_sem_permissao_403`
- `test_deletar_usuario_sem_permissao_403`

Ao corrigir, remover os xfail.

---

## Referencias

- Middleware: `apps/sistema/middleware.py:137` (`_PERM_SKIP_PATHS`)
- Funcao: `apps/sistema/decorators.py:143` (`user_tem_funcionalidade`)
- Testes: `tests/test_views_full_coverage.py` (5 testes xfail)
