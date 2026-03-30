# Pipeline CI/CD — 30/03/2026

**Data:** 30/03/2026
**Responsável:** DevOps
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Não existe pipeline de CI/CD. Testes, linting e deploy são manuais. Para garantir qualidade e agilidade no deploy, é necessário configurar um pipeline automatizado (GitHub Actions ou similar).

---

## Tarefas

- [ ] Criar workflow de CI (rodar testes em cada push/PR)
- [ ] Adicionar linting ao pipeline (flake8 ou ruff)
- [ ] Adicionar verificação de segurança (bandit ou safety)
- [ ] Criar workflow de CD (deploy automatizado para produção)
- [ ] Configurar secrets no GitHub (DB, API keys)
- [ ] Configurar notificações de falha (e-mail ou Slack)
- [ ] Documentar processo de deploy automatizado

---

## Contexto e referências

- Depende de: Docker (`docker_containerizacao_30-03-2026.md`)
- Depende de: Testes (`cobertura_testes_30-03-2026.md`)

---

## Resultado esperado

Pipeline CI/CD funcional. Push na main roda testes automaticamente. Deploy em produção com um clique ou automático após merge.
