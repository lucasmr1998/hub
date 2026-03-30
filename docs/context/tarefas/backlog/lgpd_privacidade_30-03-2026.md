# LGPD e Privacidade de Dados — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Segurança (AppSec) / Jurídico
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O sistema armazena dados pessoais de leads e clientes (nome, CPF, telefone, endereço, documentos). Com a operação SaaS multi-tenant, é necessário garantir conformidade com a LGPD, incluindo consentimento, portabilidade e exclusão de dados.

---

## Tarefas

- [ ] Mapear dados pessoais armazenados por model (Lead, Cliente, Membro, etc.)
- [ ] Implementar registro de consentimento no cadastro de leads
- [ ] Criar endpoint de exportação de dados pessoais (portabilidade)
- [ ] Criar endpoint de exclusão/anonimização de dados (direito ao esquecimento)
- [ ] Definir política de retenção de dados por tipo
- [ ] Revisar logs e auditoria para não expor dados pessoais
- [ ] Criptografar campos sensíveis (CPF, documentos) em repouso
- [ ] Documentar fluxo de tratamento de dados no sistema

---

## Contexto e referências

- Termos de uso e política de privacidade: `backlog/contrato_termos_30-03-2026.md`
- Models com dados pessoais: Lead, ClienteHubSoft, MembroClube, Parceiro

---

## Resultado esperado

Sistema em conformidade com LGPD. Consentimento registrado, dados exportáveis/excluíveis, campos sensíveis criptografados.
