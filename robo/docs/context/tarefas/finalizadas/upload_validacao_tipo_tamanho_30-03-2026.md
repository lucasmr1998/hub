---
name: "Validação de Upload — Tipo e Tamanho"
description: "Uploads de arquivos em carteirinha, parceiros e sistema não validam tipo de arquivo nem tamanho. Um usuário pode enviar "
prioridade: "🟡 Média"
responsavel: "Dev / Segurança (AppSec)"
---

# Validação de Upload — Tipo e Tamanho — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

Uploads de arquivos em carteirinha, parceiros e sistema não validam tipo de arquivo nem tamanho. Um usuário pode enviar executáveis, ZIPs ou arquivos de vários GB, causando DoS por esgotamento de disco ou upload de malware.

---

## Tarefas

- [ ] Criar validador reutilizável para uploads (tipo + tamanho)
- [ ] Definir tipos permitidos: jpg, jpeg, png, gif, webp (imagens)
- [ ] Definir tamanho máximo: 5MB para imagens, 10MB para documentos
- [ ] Aplicar em `apps/cs/carteirinha/views.py` (imagem_fundo, logo)
- [ ] Aplicar em `apps/cs/parceiros/views.py` (logo parceiro)
- [ ] Aplicar em `apps/sistema/views.py` (logo empresa)
- [ ] Retornar erro claro ao usuário quando validação falhar
- [ ] Adicionar `DATA_UPLOAD_MAX_MEMORY_SIZE` no settings

---

## Contexto e referências

- Views afetadas: carteirinha, parceiros, sistema
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Uploads rejeitam arquivos fora dos tipos e tamanhos permitidos. Mensagem de erro clara.
