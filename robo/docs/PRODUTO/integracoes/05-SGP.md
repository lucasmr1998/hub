# Integração SGP (inSystem)

**Estado:** 🟡 Discovery parcial — endpoints mapeados, credenciais e URL base da Gigamax pendentes.
**Cliente piloto:** Gigamax ([docs/context/clientes/gigamax/](../../context/clientes/gigamax/README.md)).
**Primeira aparição do ERP no Hubtrix:** primeiro caso **não-HubSoft** do produto.

Este documento segue o mesmo formato de [01-HUBSOFT.md](01-HUBSOFT.md) e é regido pelo [guia de nova integração de ERP](04-GUIA-NOVA-INTEGRACAO-ERP.md). Mapeamento baseado na Postman collection pública do SGP (compartilhada pelo contato técnico da Gigamax em 23/04/2026).

---

## Visão Geral

O **SGP (inSystem)** é um ERP cloud amplamente usado por provedores ISP no Brasil. Oferece API REST com 3 métodos de autenticação e cobre integralmente os 7 endpoints mínimos exigidos pelos módulos Comercial e Cadastro.

| Padrão de integração | Status | Uso no Hubtrix |
|----------------------|--------|-----------------|
| **API REST (app + token)** | ✅ Disponível, **preferencial** | Comercial, Cadastro, CS |
| API REST (Basic Auth) | ✅ Disponível | Fallback se o tenant não gerar token de app |
| Banco direto | ❌ Não aplicável | SGP é SaaS, sem acesso ao PostgreSQL |
| N8N intermediado | Opcional | Só se Gigamax já operar com N8N |
| Webhook reverso | 🔍 A confirmar | Não visível na Postman collection |

### URL base

Cada provedor tem sua própria instância SGP. Formato observado:

- **Sandbox público:** `https://demo.sgp.net.br`
- **Produção:** `https://<slug-do-provedor>.sgp.net.br` (a confirmar com Gigamax)

Todos os endpoints usam prefixo `/api/...`.

### Autenticação

**Recomendado para Hubtrix:** `app + token` (método 2 da documentação oficial).

| Método | Como obter | Quando usar |
|--------|------------|-------------|
| **`app` + `token`** | No SGP: `Sistema → Ferramentas → Painel Admin → Tokens` | **Integrações de sistema** (Hubtrix). Token mapeado a um usuário SGP com permissões. |
| Basic Auth (`username` + `password`) | Usuário SGP em `Sistema → Usuários` | Fallback. Mesmas permissões do usuário. |
| `cpfcnpj` + `senha` | Central do assinante | Endpoints que o cliente-final usa (ex: 2ª via de boleto pela própria central). Não relevante pra Hubtrix. |

**Como passar:** `app` e `token` vão como campos de **formdata** ou **JSON body** em cada request. Não há header `Authorization: Bearer`. Não há TTL de token documentado (parece ser estático até ser revogado no painel).

Documentação detalhada: https://bookstack.sgp.net.br/books/api/page/autenticacoes-via-api

---

## Os 7 endpoints mínimos — mapeados

Tabela contra o contrato mínimo exigido pelo Hubtrix (seção 1.2 do [guia](04-GUIA-NOVA-INTEGRACAO-ERP.md)).

### Leitura

| # | Operação Hubtrix | Endpoint SGP | Método | Auth | Observação |
|---|------------------|--------------|--------|------|------------|
| 1 | Consultar cliente por CPF/CNPJ | `/api/ura/consultacliente/` | POST | app+token | Retorna dados completos: nome, endereço, telefones, emails, contratos, serviços. Alternativa: `/api/crm/cliente/?cpfcnpj=X` (GET, resposta mais enxuta). |
| 2 | Listar contratos do cliente | `/api/ura/listacontrato/` ou `/api/crm/cliente/{id}/contratos/` | POST / GET | app+token | Inclui status do contrato (Ativo/Suspenso/Cancelado/etc), plano, endereço, data de cadastro. |
| 3 | Consultar situação financeira | `/api/ura/titulos/` | POST | app+token | Filtra por `status: 'abertos' / 'pagos' / 'cancelados'`, datas de vencimento/pagamento. Retorna valor, data pagamento, código de barras, PIX. **Substitui o acesso direto ao banco que o HubSoft exige.** |
| 4 | Listar planos disponíveis | `/api/ura/consultaplano/` | GET / POST | app+token | Retorna id, descrição, preço, qtd de serviços. Filtro opcional por `pop`. |

### Escrita

| # | Operação Hubtrix | Endpoint SGP | Método | Auth | Observação |
|---|------------------|--------------|--------|------|------------|
| 5 | Criar prospecto | **Opção A:** `/api/precadastro/F` (PF) ou `/api/precadastro/J` (PJ) | POST | app+token | Pré-cadastro. Se passar `precadastro_ativar=1`, já vira cliente efetivo + contrato. Melhor pra lead vindo do WhatsApp. |
| 5b | Criar cliente + contrato (alternativa) | `/api/crm/cliente/F` (ou J/E/EJ) + `/api/crm/cliente/{id}/contratos` | POST | app+token | Fluxo em 2 passos. Mais controle, usado se quisermos separar cadastro de cliente e geração de contrato. |
| 6 | Anexar documento | `/api/suporte/cliente/{cliente_id}/documento/add/` | PUT | app+token ou Basic | **Observação:** SGP anexa no **cliente**, não no contrato diretamente (diferente do HubSoft). Suporta upload de arquivo (`file` como multipart). |
| 7 | Aceitar contrato | `/api/contrato/termoaceite/{idcontrato}` | POST | app+token | Body: `aceite=sim`. Existe também GET `/api/contrato/termoaceite/{idcontrato}/` pra exibir o termo antes. |

**Status CRM (bônus útil):** `POST /api/crm/cliente/{id}/status/` atualiza status do lead (Em análise, Aprovado, Reprovado, Aguardando Contato, Inviabilidade técnica, etc). Útil pra sincronizar kanban do CRM Hubtrix com o CRM do SGP.

---

## Endpoints adicionais relevantes (fora dos 7 mínimos)

Pontos de integração extras que vão facilitar módulos além de Comercial:

| Operação | Endpoint | Módulo Hubtrix que usa |
|----------|----------|------------------------|
| Viabilidade técnica por endereço | `POST /api/ura/viabilidade/` | Comercial — Viabilidade |
| Validar credenciais do token | `GET /api/auth/info/` | Setup (testar integração) |
| Listar POPs do provedor | `POST /api/ura/pops/` | Cadastro (choice-list) |
| Listar vencimentos disponíveis | `POST /api/precadastro/vencimento/list` | Cadastro (choice-list) |
| Listar vendedores | `POST /api/precadastro/vendedor/list` | Cadastro (escolher vendedor padrão) |
| Verificar status de conexão | `POST /api/ura/verificaacesso/` | Suporte |
| Gerar 2ª via de fatura | `POST /api/ura/fatura2via/` | CS / Clube |
| Abrir chamado/OS | `POST /api/ura/chamado/` | Suporte (reverso) |
| Listar ordens de serviço | `POST /api/os/list/` | Suporte |

Catálogo completo de endpoints: ver Postman collection original (compartilhada via [documenter.getpostman.com](https://documenter.getpostman.com/view/6682240/2sB34hHg2V)).

---

## Paginação e rate limits

- **Paginação:** parâmetros `offset` (default 0) e `limit` em endpoints de listagem. Limites variam: 100–250 padrão, até 1000 com filtros obrigatórios.
- **Rate limit:** não documentado na Postman collection. Assumir conservador e implementar backoff exponencial no adapter.

---

## Armadilhas antecipadas

Com base na leitura da doc + experiência HubSoft:

| Armadilha | Prevenção |
|-----------|-----------|
| Response vem com `status: 0/1` dentro do body mesmo em HTTP 200 | Validar **shape** da resposta (campo `status` ou `success`), não só status_code |
| Alguns endpoints aceitam `formdata` e outros `raw JSON` — misto | Respeitar o content-type indicado em cada endpoint no Postman |
| `app` + `token` é efetivamente um secret duplo (ambos precisam ser mantidos) | Armazenar em `IntegracaoAPI.client_id` (app) + `IntegracaoAPI.access_token` (token) — nunca em arquivo versionado |
| Anexo fica no cliente, não no contrato | Adaptador Hubtrix precisa fazer translation: quando o fluxo "anexar ao contrato" dispara, enviar pro `documento/add/` do cliente correspondente e guardar a associação internamente |
| Endpoints mistos retornam encoding com mojibake (acentos) | Forçar `Accept-Charset: utf-8` no client |
| Central do assinante usa auth diferente (`cpfcnpj + senha`) — não confundir com o token da aplicação | Isolar nos services: `SGPService` usa `app+token`; se precisar da central, classe separada |

---

## Próximos passos — o que falta destravar

**Depende da Gigamax:**
- [ ] URL base da instância SGP (ex: `https://gigamax.sgp.net.br`?)
- [ ] Confirmar se `app + token` já foi gerado e é o que está sendo usado (token atual no `.env.prod_readonly` local)
- [ ] Nome do `app` (é separado do `token`)
- [ ] Confirmar se SGP emite webhooks reversos (não visível na Postman collection)
- [ ] IDs padrão a serem usados pelo Hubtrix: `pop_id` padrão, `portador_id` padrão (para criação de contrato), `vendedor_id` padrão (leads via WhatsApp)
- [ ] Rate limits reais (pedir ao time técnico)
- [ ] Ambiente de homologação separado de produção?

**Do nosso lado (implementação — fase 2):**
1. Adicionar `('sgp', 'SGP (inSystem)')` em `IntegracaoAPI.TIPO_CHOICES` ([apps/integracoes/models.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models.py))
2. Criar migration
3. Criar `SGPService` em `apps/integracoes/services/sgp.py` espelhando interface do [`HubsoftService`](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft.py). Métodos mínimos:
   - `obter_token()` → apenas valida `app + token` via `GET /api/auth/info/` (não há renovação, token é estático)
   - `cadastrar_prospecto(lead)` → `POST /api/precadastro/F` ou `/J` com `precadastro_ativar=1`
   - `consultar_cliente(cpf_cnpj)` → `POST /api/ura/consultacliente/`
   - `sincronizar_cliente(lead)` → consulta + upsert em `ClienteERPExterno` (ou modelo novo `ClienteSGP`)
   - `listar_titulos(cliente_id, **filtros)` → `POST /api/ura/titulos/` — substitui consulta ao banco que o HubSoft exige
   - `consultar_viabilidade(endereco)` → `POST /api/ura/viabilidade/`
4. Criar `setup_sgp` management command (pedindo `base_url`, `app`, `token`)
5. Branch `elif integracao.tipo == 'sgp'` em [signals.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/signals.py)
6. Testes unitários com `requests_mock` + integração end-to-end
7. Homologação com token real da Gigamax

---

## Relacionados

- [04-GUIA-NOVA-INTEGRACAO-ERP.md](04-GUIA-NOVA-INTEGRACAO-ERP.md) — processo mestre de integração de novo ERP
- [01-HUBSOFT.md](01-HUBSOFT.md) — único ERP integrado em produção hoje; serve de benchmark
- [02-INTEGRACOES.md](02-INTEGRACOES.md) — mapa geral dos 35 pontos de integração do Hubtrix
- [docs/context/clientes/gigamax/](../../context/clientes/gigamax/README.md) — dados do cliente piloto
- [docs/context/clientes/gigamax/integracoes.md](../../context/clientes/gigamax/integracoes.md) — IDs e credenciais específicos do tenant
- Postman pública SGP: https://documenter.getpostman.com/view/6682240/2sB34hHg2V
- Doc oficial de auth SGP: https://bookstack.sgp.net.br/books/api/page/autenticacoes-via-api
