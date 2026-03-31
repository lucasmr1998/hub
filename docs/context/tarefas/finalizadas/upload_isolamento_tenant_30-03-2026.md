---
name: "Isolar Uploads por Tenant"
description: "Uploads de arquivos (logos, imagens de carteirinha, logos de parceiros) são armazenados em diretórios compartilhados (`l"
prioridade: "🟠 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Isolar Uploads por Tenant — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Uploads de arquivos (logos, imagens de carteirinha, logos de parceiros) são armazenados em diretórios compartilhados (`logos/`, `carteirinhas/modelos/`). Todos os tenants usam o mesmo diretório. Se o servidor de mídia for mal configurado, um tenant pode acessar arquivos de outro.

---

## Tarefas

- [ ] Criar função `tenant_upload_path(instance, filename)` que gera path com tenant_id
- [ ] Atualizar `ConfiguracaoEmpresa.logo_empresa` → `upload_to=tenant_upload_path`
- [ ] Atualizar `ModeloCarteirinha.imagem_fundo` e `logo` → `upload_to=tenant_upload_path`
- [ ] Atualizar `Parceiro.logo` → `upload_to=tenant_upload_path`
- [ ] Gerar migrations
- [ ] Migrar arquivos existentes para os novos paths (script de migração)
- [ ] Testar que URLs de mídia ainda funcionam após migração

---

## Contexto e referências

- Models afetados: `apps/sistema/models.py`, `apps/cs/carteirinha/models.py`, `apps/cs/parceiros/models.py`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Cada tenant tem seu diretório de uploads isolado: `media/tenants/{tenant_id}/logos/`, etc.
