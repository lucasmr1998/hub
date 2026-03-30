# Implementar Rate Limiting — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / DevOps
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Nenhum endpoint possui rate limiting. APIs públicas (cadastro, consulta CEP) e webhooks podem ser abusados com enumeração massiva, scraping de dados ou ataques de força bruta. Sem limitação, um atacante pode extrair toda a base de leads.

---

## Tarefas

- [ ] Instalar django-ratelimit ou throttling do DRF
- [ ] Definir limites por categoria:
  - APIs públicas: 10 req/min por IP
  - Webhooks N8N: 100 req/min por IP
  - APIs do painel: 60 req/min por usuário
  - Login: 5 tentativas/min por IP
- [ ] Aplicar nos endpoints críticos (registrar_lead, cadastro, login, webhooks)
- [ ] Retornar 429 Too Many Requests quando exceder
- [ ] Logar tentativas que excedem o limite (alerta de possível ataque)
- [ ] Testar que uso normal não é bloqueado

---

## Contexto e referências

- Projeto inteiro não possui rate limiting
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Rate limiting ativo em todos os endpoints. Proteção contra brute force, scraping e DoS.
