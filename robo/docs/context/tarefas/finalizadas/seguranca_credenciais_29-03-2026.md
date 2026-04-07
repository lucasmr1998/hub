---
name: Remover credenciais hardcoded do código
description: Todas as credenciais movidas para variáveis de ambiente
type: tarefa
status: finalizada
criado_em: 29/03/2026
---

## Objetivo

Eliminar credenciais expostas no código fonte.

## Atividades

- [x] Remover SECRET_KEY hardcoded do settings.py
- [x] Remover senha do banco do settings.py (sem fallback)
- [x] Remover token Matrix API do atendimento_service.py
- [x] Remover credenciais HubSoft do setup_hubsoft.py
- [x] Remover IP do servidor do ALLOWED_HOSTS
- [x] Limpar settings_production.py (SECRET_KEY duplicada, IP do banco)
- [x] Configurar DEBUG=False por padrão
- [x] Criar .env.example com todas as variáveis
- [x] Verificar .gitignore (.env já ignorado)

## Resultado esperado

Zero credenciais no código. Deploy falha se variáveis não configuradas.
