# Remover Dados Sensíveis dos Responses de API — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

A API de integrações retorna campos sensíveis nos JSON responses: login PPPoE, senha PPPoE, MAC address, IPv4 de clientes. Esses dados não deveriam ser expostos via API.

---

## Tarefas

- [ ] Auditar todos os serializers/dicts que retornam dados de `ClienteHubsoft` e `ServicoClienteHubsoft`
- [ ] Remover campos: `login`, `senha`, `mac_addr`, `ipv4`, `ipv6` dos responses
- [ ] Criar listas explícitas de campos permitidos (allowlist) em vez de retornar tudo
- [ ] Verificar outros endpoints que possam expor dados desnecessários

---

## Contexto e referências

- Views: `apps/integracoes/views.py`, função `_servico_para_dict()`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

APIs retornam apenas campos necessários. Dados de rede (login, senha, MAC, IP) nunca expostos via API.
