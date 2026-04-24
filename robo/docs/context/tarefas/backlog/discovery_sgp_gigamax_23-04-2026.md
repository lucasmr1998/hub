---
name: "Discovery técnico SGP (inSystem) — Gigamax"
description: "Mapear API SGP, auth, endpoints e IDs antes de implementar adapter do primeiro cliente não-HubSoft"
prioridade: "🟡 Média"
responsavel: "Tech Lead + João Ferreira (técnico Gigamax)"
---

# Discovery técnico SGP (inSystem) — Gigamax — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead (Hubtrix) + João Ferreira (técnico Gigamax)
**Prioridade:** 🟡 Média (a maior parte já foi destravada via Postman pública)
**Status:** 🔧 Em andamento — Postman analisado, faltam apenas credenciais específicas do tenant

---

## Descrição

Gigamax entra como **primeiro cliente Hubtrix com ERP SGP (inSystem)**. Hoje o Hubtrix só integra com HubSoft. Antes de escrever uma linha do `SGPService`, precisamos levantar toda a superfície de integração do SGP e decidir os padrões (API direta / banco / N8N / webhook reverso) para cada um dos 7 endpoints mínimos exigidos pelos módulos Comercial e Cadastro.

O resultado deste discovery alimenta:
- [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md) — doc técnica da integração.
- [clientes/gigamax/integracoes.md](../../clientes/gigamax/integracoes.md) — IDs e credenciais do tenant.
- Próxima tarefa: `implementacao_adapter_sgp_*.md` (só criar depois deste fechar).

---

## Tarefas

### Pré-call
- [x] Obter contato técnico da Gigamax (João Ferreira — 23/04/2026)
- [x] Pedir antecipadamente: Postman collection / Swagger / PDF da API SGP ✅ recebido 23/04
- [ ] Confirmar se Gigamax já tem acesso ao sandbox/homologação do SGP

### Análise da doc (concluída via Postman pública)
- [x] Confirmar método de auth da API SGP — **3 opções: `app+token` (recomendado), Basic Auth, CPF/CNPJ + senha (central)**
- [x] Levantar TTL de token — **não há rotação; token é estático até ser revogado manualmente no painel**
- [x] Mapear os **7 endpoints mínimos** contra a API real (tabela fechada em [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md))
  - [x] Consultar cliente por CPF/CNPJ → `POST /api/ura/consultacliente/`
  - [x] Listar contratos do cliente → `POST /api/ura/listacontrato/`
  - [x] Consultar situação financeira (recorrência / inadimplência / adiantado) → `POST /api/ura/titulos/` ✅ **via API, sem precisar de banco direto (diferente do HubSoft)**
  - [x] Listar planos disponíveis → `POST /api/ura/consultaplano/`
  - [x] Criar prospecto → `POST /api/precadastro/F` ou `/J` (com `precadastro_ativar=1`)
  - [x] Anexar documento → `PUT /api/suporte/cliente/{id}/documento/add/` (anexa no cliente, não no contrato)
  - [x] Aceitar contrato → `POST /api/contrato/termoaceite/{idcontrato}` com `aceite=sim`
- [x] Decidir padrões por operação — **100% via 3.1 API REST direta; sem necessidade de banco direto (3.2) ou N8N (3.3)**

### Confirmar com João (pendente)
- [ ] URL base da instância SGP da Gigamax (ex: `https://gigamax.sgp.net.br`)
- [ ] Nome do `app` que acompanha o token já compartilhado
- [ ] Rate limits reais da API (a Postman não documenta)
- [ ] SGP emite webhooks reversos (venda aprovada, pagamento confirmado)? Se sim, formato
- [ ] Ambiente de homologação separado de produção, ou só produção?
- [ ] Liberação de firewall / IP whitelist necessária?
- [ ] IDs padrão a serem usados pelo Hubtrix ao criar leads via WhatsApp:
  - `pop_id_padrao`, `plano_id_padrao`, `portador_id_padrao`, `vendedor_id_padrao`, `forma_cobranca_id_padrao`
  - Podem ser descobertos via endpoints de listagem, mas vale validar com o comercial da Gigamax antes de fixar

### Pós-call (quando todas as confirmações acima chegarem)
- [x] Fechar tabela dos 7 endpoints em [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md)
- [ ] Preencher [clientes/gigamax/integracoes.md](../../clientes/gigamax/integracoes.md) com credenciais (campos — não valores) e IDs
- [x] Documentar armadilhas antecipadas em [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md)
- [ ] Criar próxima tarefa no backlog: `implementacao_adapter_sgp_*.md` (Passo 2 a 5 da seção 5 do guia)
- [ ] Mover esta tarefa para `tarefas/finalizadas/`

---

## Contexto e referências

- Guia mestre: [04-GUIA-NOVA-INTEGRACAO-ERP.md](../../../PRODUTO/integracoes/04-GUIA-NOVA-INTEGRACAO-ERP.md)
- Benchmark HubSoft: [01-HUBSOFT.md](../../../PRODUTO/integracoes/01-HUBSOFT.md)
- Doc técnica (🟡 discovery parcial): [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md)
- Cliente: [clientes/gigamax/README.md](../../clientes/gigamax/README.md)
- Adapter de referência: `apps/integracoes/services/hubsoft.py`
- Postman pública SGP: https://documenter.getpostman.com/view/6682240/2sB34hHg2V
- Doc oficial de auth SGP: https://bookstack.sgp.net.br/books/api/page/autenticacoes-via-api

---

## Resultado esperado

- [x] [05-SGP.md](../../../PRODUTO/integracoes/05-SGP.md) com os 7 endpoints mapeados (método + path + auth) e padrão de integração escolhido por operação
- [ ] [clientes/gigamax/integracoes.md](../../clientes/gigamax/integracoes.md) com estrutura de credenciais e IDs confirmada (sem valores reais no arquivo)
- [ ] Tarefa seguinte criada (`implementacao_adapter_sgp_*.md`) com checklist puxado dos Passos 2–5 do guia
- [x] Equipe tem clareza de que a integração é só via API REST (sem banco direto nem N8N obrigatório)

---

## Principais descobertas (23/04/2026)

- **Auth:** SGP oferece `app + token` (ideal pra sistemas), com alternativas de Basic Auth e cpfcnpj+senha (central). Usamos `app + token`.
- **Base URL:** variável por provedor (`https://<slug>.sgp.net.br`). Pendente confirmar com Gigamax.
- **Recorrência/pagamento via API:** ✅ resolvido via `POST /api/ura/titulos/` — não precisamos de acesso ao banco (diferente do HubSoft, onde tivemos que cair pro `mega_leitura`).
- **Anexo de documento:** fica no cliente, não no contrato. Adapter vai precisar traduzir.
- **IDs customizados:** não há "IDs mandatórios" do tipo `id_origem` do HubSoft. Só precisamos guardar valores **padrão** (pop, plano, portador, vendedor) pra criação automática via WhatsApp.
- **Webhook reverso do SGP:** não visível na Postman collection. Se não existir, Hubtrix sincroniza sob demanda (igual HubSoft hoje).
