# Remover PII de Logs e Print Statements — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Existem `print()` em `vendas_web/views.py` que expõem email e telefone de leads em stdout. Logs de produção podem conter dados pessoais (CPF, telefone, email) sem mascaramento, violando boas práticas de LGPD.

---

## Tarefas

- [ ] Remover todos os `print()` com PII em `vendas_web/views.py` (linhas 2557, 2648, 2700)
- [ ] Substituir por `logging.debug()` com ID do lead (sem dados pessoais)
- [ ] Buscar outros `print()` no projeto inteiro e substituir por logging
- [ ] Implementar filtro de PII no logging (mascarar CPF, email, telefone)
- [ ] Verificar que `LogIntegracao` não armazena PII no campo `payload_enviado`

---

## Contexto e referências

- Arquivo: `vendas_web/views.py`, linhas 2557-2701
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Zero PII em logs e stdout. Logging estruturado com `logging` module. Filtro de mascaramento ativo.
