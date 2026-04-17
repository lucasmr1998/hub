# Status do Produto — AuroraISP

**Última atualização:** 11/04/2026

Este documento é a fonte da verdade sobre o que está pronto, em desenvolvimento e planejado em cada módulo da AuroraISP. Atualizar sempre que uma funcionalidade mudar de status.

---

## Legenda

| Status | Significado |
|--------|-------------|
| ✅ Pronto | Funciona, tem UI, testável pelo cliente |
| 🔧 Parcial | Backend existe mas UI incompleta, ou funciona com limitações |
| 🚧 Em desenvolvimento | Trabalho iniciado, não utilizável ainda |
| 📋 Planejado | Definido, não iniciado |
| ❌ Desativado | Código existe mas está desligado |

---

## Visão Geral por Módulo

| Módulo | Plano | Status Geral | Pronto | Parcial | Planejado |
|--------|-------|-------------|--------|---------|-----------|
| **Comercial** | Start / Pro | 🟢 Produção | 18 | 1 | 1 |
| **Marketing** | Start / Pro | 🟡 Inicial | 3 | 2 | 4 |
| **CS** | Start / Pro | 🟡 Em desenvolvimento | 12 | 3 | 4 |
| **Suporte** | Interno | 🟡 Inicial | 4 | 0 | 2 |
| **Sistema** | Base | 🟢 Produção | 11 | 2 | 1 |

---

## MÓDULO COMERCIAL

### Leads (apps/comercial/leads/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Captura de leads via WhatsApp/N8N | ✅ Pronto | Integração ativa com N8N |
| Score de qualificação automático | ✅ Pronto | 0 a 10 |
| Listagem com filtros, busca, paginação | ✅ Pronto | |
| Upload e validação de documentos | ✅ Pronto | Fotos de RG, comprovante |
| Histórico de interações por lead | ✅ Pronto | |
| Visualização de conversa HTML/PDF | ✅ Pronto | |

### Atendimento (apps/comercial/atendimento/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Fluxos conversacionais configuráveis | ✅ Pronto | 20 tipos de questão |
| Sessão de atendimento com estado | ✅ Pronto | |
| APIs para N8N (15+ endpoints) | ✅ Pronto | |
| Roteamento condicional inteligente | ✅ Pronto | |

### Cadastro (apps/comercial/cadastro/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Formulário de cadastro de cliente | ✅ Pronto | |
| Catálogo de planos de internet | ✅ Pronto | |
| Opções de vencimento | ✅ Pronto | |
| Geração de PDF do contrato | ✅ Pronto | WeasyPrint |
| Envio de docs e aceite no HubSoft | ✅ Pronto | Automático via signal |

### CRM (apps/comercial/crm/) — Plano Pro

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Pipeline Kanban com drag and drop | ✅ Pronto | Multi-pipeline por tenant |
| Estágios configuráveis por pipeline | ✅ Pronto | |
| Oportunidades com valor, probabilidade, tags | ✅ Pronto | |
| Tarefas com vencimento e prioridade | ✅ Pronto | |
| Notas internas | ✅ Pronto | |
| Equipes de vendas | ✅ Pronto | Página dedicada |
| Metas individuais e por equipe | ✅ Pronto | |
| Dashboard de desempenho | ✅ Pronto | |
| Auto-criação de oportunidade por score | ✅ Pronto | Signal automático |
| Catálogo de produtos/serviços (CRUD) | ✅ Pronto | Genérico, com mapeamento HubSoft opcional |
| Itens vinculados a oportunidades | ✅ Pronto | N produtos por oportunidade, recalcula valor |
| Webhooks N8N por evento CRM | 🔧 Parcial | Configurado mas não testado em produção |

### Viabilidade (apps/comercial/viabilidade/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Consulta de cobertura por CEP | ✅ Pronto | ViaCEP |

---

## MÓDULO MARKETING

### Campanhas (apps/marketing/campanhas/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Cadastro de campanhas de tráfego | ✅ Pronto | |
| Detecção automática de origem por keyword | ✅ Pronto | |
| Métricas por campanha | ✅ Pronto | |

### Segmentação (apps/comercial/crm/ — usado pelo Marketing)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Segmentação de leads | 🔧 Parcial | Model existe, UI básica |

### Automações (apps/marketing/automacoes/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Lista de automações com toggle | 🚧 Em desenvolvimento | Frontend pronto, backend pendente |
| Builder visual (Quando/Se/Então) | 🚧 Em desenvolvimento | Frontend pronto, backend pendente |
| Engine de execução de regras | 📋 Planejado | |
| Histórico de execuções | 📋 Planejado | |

### Funcionalidades planejadas

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Landing pages configuráveis | 📋 Planejado | Placeholder no menu |
| Réguas de automação (email, WhatsApp) | 📋 Planejado | Depende do módulo Automações |

---

## MÓDULO CUSTOMER SUCCESS

### Clube de Benefícios (apps/cs/clube/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Dashboard com KPIs e gráficos | ✅ Pronto | Cadastros, validações, giros |
| Gestão de membros (clientes) | ✅ Pronto | |
| Roleta de prêmios | ✅ Pronto | |
| Níveis e XP (gamificação) | ✅ Pronto | Bronze, Prata, Ouro, Diamante |
| Regras de pontuação configuráveis | ✅ Pronto | |
| Banners configuráveis | ✅ Pronto | |
| Extrato de pontuação | ✅ Pronto | |
| Relatórios do clube | ✅ Pronto | |

### Parceiros (apps/cs/parceiros/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Dashboard de parceiros | ✅ Pronto | |
| Gestão de parceiros e categorias | ✅ Pronto | |
| Cupons de desconto | ✅ Pronto | |
| Resgates de cupom | 🔧 Parcial | Model existe, sem dados populados |
| Painel do parceiro (portal externo) | 🔧 Parcial | Templates existem, fluxo não testado |

### Indicações (apps/cs/indicacoes/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Dashboard de indicações | ✅ Pronto | |
| Registro e acompanhamento | ✅ Pronto | |

### Carteirinhas (apps/cs/carteirinha/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Modelos de carteirinha | 🔧 Parcial | Model existe, UI básica |

### Funcionalidades planejadas

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Retenção / Alertas de churn | 📋 Planejado | Models ScoreCliente, AlertaChurn criados |
| NPS (pesquisa de satisfação) | 📋 Planejado | Models ConfiguracaoNPS, PesquisaNPS criados |
| Upsell automático | 📋 Planejado | |
| Onboarding guiado de novos clientes | 📋 Planejado | |

---

## MÓDULO SUPORTE (interno Aurora)

### Tickets (apps/suporte/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Dashboard de tickets | ✅ Pronto | |
| Criar ticket | ✅ Pronto | |
| Detalhe do ticket com comentários | ✅ Pronto | |
| SLA automático por plano | ✅ Pronto | |
| Categorias configuráveis | ✅ Pronto | |
| Relatórios de suporte | 📋 Planejado | |
| Portal do cliente (abertura externa) | 📋 Planejado | |

---

## SISTEMA (base)

### Infraestrutura (apps/sistema/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Multi-tenancy (isolamento por provedor) | ✅ Pronto | TenantMixin em todos os models. Pendente deploy |
| Gestão de usuários e permissões | ✅ Pronto | |
| Configurações da empresa | ✅ Pronto | |
| Logs do sistema | ✅ Pronto | |
| Recuperação de senha (email + WhatsApp) | ✅ Pronto | Config pelo aurora-admin |
| Status customizáveis | ✅ Pronto | |

### Notificações (apps/notificacoes/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Models completos (tipos, canais, templates, preferências) | ✅ Pronto | 5 models, 16 tipos, 4 canais |
| Admin completo | ✅ Pronto | |
| APIs de CRUD + leitura | ✅ Pronto | 30+ endpoints |
| Config WhatsApp/N8N | ✅ Pronto | |
| Service centralizado (criar, marcar lida, contar) | ✅ Pronto | services/notificacao_service.py |
| Signals automáticos (lead, conversa, ticket) | ✅ Pronto | 4 signals |
| Frontend (sino, badge, toasts, som, marcar lida) | ✅ Pronto | Polling 15s, Web Audio API |
| Página de configurações | ✅ Pronto | |

### Integrações (apps/integracoes/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| OAuth2 com HubSoft | ✅ Pronto | |
| Envio automático de leads | ✅ Pronto | Signal post_save |
| Sincronização de clientes | ✅ Pronto | Command + automático |
| Anexação de docs ao contrato | ✅ Pronto | |
| Logs de auditoria | ✅ Pronto | |
| Conexão direta banco HubSoft (CS) | ✅ Pronto | Para dados não disponíveis na API |

### API REST (apps/api/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Endpoints DRF com TokenAuth + SessionAuth | ✅ Pronto | |
| Swagger/OpenAPI em /api/docs/ | ✅ Pronto | drf-spectacular |
| Endpoints N8N | ✅ Pronto | |

### Admin Aurora (apps/admin_aurora/)

| Funcionalidade | Status | Observação |
|----------------|--------|------------|
| Gestão de tenants | ✅ Pronto | |
| Gestão de planos (9 planos, 115 features) | ✅ Pronto | |
| Config recuperação de senha | ✅ Pronto | SMTP + WhatsApp/Uazapi |
| Monitoramento | 🔧 Parcial | Logs e status básicos |

---

## Infraestrutura e DevOps

| Item | Status | Observação |
|------|--------|------------|
| CI/CD GitHub Actions | ✅ Pronto | Roda testes + linting |
| Docker (Dockerfile + compose + nginx) | ✅ Pronto | Não usado em produção ainda |
| 225 testes automatizados | ✅ Pronto | 10 arquivos, 28+ factories |
| Deploy produção multi-tenant | 📋 Planejado | Produção atual é single-tenant Megalink |
| Monitoramento (Sentry, uptime) | 📋 Planejado | |

---

## Prioridades Imediatas

1. **Finalizar módulo Marketing**: backend de Automações (regras configuráveis pelo cliente)
2. **Reativar Notificações**: conectar ao módulo de Automações
3. **Finalizar CS**: Retenção (churn alerts), NPS, resgates de cupom
4. **Deploy multi-tenant**: primeira vez com 2+ provedores em produção
5. **Onboarding Grupo Magister**: primeiro cliente com contrato assinado
