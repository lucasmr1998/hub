# Linting e Qualidade de Código — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O projeto não possui ferramentas de linting, formatação automática nem verificação de qualidade de código. Para manter consistência à medida que o projeto cresce, é necessário configurar essas ferramentas.

---

## Tarefas

- [ ] Instalar e configurar ruff (linter + formatter)
- [ ] Criar pyproject.toml com configurações do ruff
- [ ] Rodar linting no código existente e corrigir erros críticos
- [ ] Configurar pre-commit hooks (ruff, trailing whitespace, end-of-file)
- [ ] Adicionar ao requirements-dev.txt
- [ ] Integrar ao pipeline CI/CD

---

## Contexto e referências

- Depende de: Pipeline CI/CD (`cicd_pipeline_30-03-2026.md`)
- Codebase: 30.000+ linhas de código Python

---

## Resultado esperado

Linting automático com ruff. Pre-commit hooks impedem código fora do padrão. Integrado ao CI.
