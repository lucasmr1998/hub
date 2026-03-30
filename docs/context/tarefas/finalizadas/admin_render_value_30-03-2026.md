# Corrigir Exibição de Senhas no Admin — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O formulário de edição de integrações no Django Admin usa `render_value=True` nos campos de senha e client_secret. Isso faz com que os valores apareçam em texto plano no HTML da página, expostos no histórico do navegador e no código-fonte.

---

## Tarefas

- [ ] Remover `render_value=True` dos PasswordInput em `apps/integracoes/admin.py`
- [ ] Verificar se outros formulários de admin expõem senhas da mesma forma

---

## Contexto e referências

- Arquivo: `robo/dashboard_comercial/gerenciador_vendas/apps/integracoes/admin.py`, linhas 15-24
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Campos de senha no admin nunca exibem o valor armazenado. Comportamento padrão do Django (campo vazio ao editar).
