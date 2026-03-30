# Remover Credencial HubSoft Hardcoded — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O arquivo `apps/cs/clube/management/commands/testar_pontuacoes.py` contém a senha do banco HubSoft em texto plano. Qualquer pessoa com acesso ao código consegue conectar ao banco de produção do HubSoft.

---

## Tarefas

- [ ] Substituir credenciais hardcoded por `os.getenv()` no `testar_pontuacoes.py`
- [ ] Verificar se há outros arquivos com credenciais hardcoded no módulo CS
- [ ] Solicitar rotação da senha exposta ao administrador do HubSoft
- [ ] Adicionar as variáveis `HUBSOFT_DB_*` ao `.env.example`

---

## Contexto e referências

- Arquivo: `robo/dashboard_comercial/gerenciador_vendas/apps/cs/clube/management/commands/testar_pontuacoes.py`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Zero credenciais hardcoded no código. Senha exposta rotacionada no HubSoft.
