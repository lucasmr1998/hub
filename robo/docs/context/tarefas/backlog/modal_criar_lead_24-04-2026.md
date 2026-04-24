---
name: "Modal de criacao de lead na pagina de leads"
description: "Botao 'Novo lead' atualmente chama toast('Em desenvolvimento'). Implementar modal + view + form pra criar lead direto, sem depender de import CSV ou cadastro publico"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Modal criar lead — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ⏳ Pendente

---

## Descrição

Na pagina de leads ([comercial/leads/leads.html:15](../../../../dashboard_comercial/gerenciador_vendas/apps/comercial/leads/templates/comercial/leads/leads.html)) o botao "Novo lead" eh placeholder: `onclick="toast('Info', 'Em desenvolvimento', 'info')"`. Nao ha modal nem view de criacao manual de lead hoje — leads entram via import CSV, cadastro publico, ou API N8N.

## Decisoes pendentes (alinhar antes de implementar)

1. **Campos minimos** — nome + telefone? + CPF/CNPJ? + origem?
2. **Origem default** — 'outros', 'site', 'telefone'?
3. **Validacao** — obrigatoria de duplicidade por telefone? Por CPF?
4. **Signal/automacao** — criacao via modal dispara `on_lead_criado` (automacoes de boas-vindas)? Assumo que sim, mas precisa confirmar
5. **Envio pro HubSoft** — marca `status_api='pendente'` pra signal disparar `cadastrar_prospecto`? Ou marca como `manual` pra nao enviar?

## Escopo sugerido

### View
- `POST /comercial/leads/criar/` em `apps/comercial/leads/views.py`
- Usa `LeadProspecto.objects.create(tenant=request.tenant, ...)`
- Retorna JSON pra o frontend
- Permissao: `comercial.criar_lead`

### Template
- Modal com componente `{% include "components/modal.html" %}` (ou inline, seguindo padrao tarefas_lista.html)
- Campos: nome_razaosocial (obrigatorio), telefone (obrigatorio), email, cpf_cnpj, origem (select), canal

### JS
- Funcao `abrirModalLead()` / `fecharModalLead()` (evitar colisao com globais — ver bug corrigido em 23/04)
- `salvarLead()` faz POST, em caso de sucesso: `location.reload()` ou inserir card na grid

## Tarefas

- [ ] Alinhar campos + origem default + dedupe com Lucas
- [ ] Criar view + URL + permissao
- [ ] Adicionar modal ao template de leads
- [ ] Trocar `onclick="toast(...)"` no botao por `onclick="abrirModalLead()"`
- [ ] Teste unit + integracao
- [ ] Atualizar doc em `docs/PRODUTO/modulos/comercial/`

## Referencias

- Bug relacionado: botao placeholder [leads.html:15](../../../../dashboard_comercial/gerenciador_vendas/apps/comercial/leads/templates/comercial/leads/leads.html)
- Padrao de modal: `apps/comercial/crm/templates/crm/tarefas_lista.html`
- Model: `LeadProspecto` em `apps/comercial/leads/models.py`
