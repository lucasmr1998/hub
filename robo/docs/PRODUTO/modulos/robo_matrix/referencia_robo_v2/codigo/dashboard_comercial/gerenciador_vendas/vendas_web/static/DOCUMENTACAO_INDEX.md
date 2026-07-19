# 📚 Índice de Documentação - Megalink

Bem-vindo ao índice central de documentação do sistema Megalink. Aqui você encontra todos os documentos organizados por categoria.

---

## 🔔 Sistema de Notificações

### Documentos Disponíveis

| Documento | Descrição | Ideal Para |
|-----------|-----------|------------|
| [**NOTIFICACOES_README.md**](./NOTIFICACOES_README.md) | Guia rápido com comandos e exemplos | Quick start, referência rápida |
| [**DOCUMENTACAO_NOTIFICACOES.md**](./DOCUMENTACAO_NOTIFICACOES.md) | Documentação técnica completa | Desenvolvimento, arquitetura, troubleshooting |
| [**SISTEMA_NOTIFICACOES.md**](./SISTEMA_NOTIFICACOES.md) | Visão geral do sistema (resumida) | Introdução, conceitos gerais |

### Acesso Rápido

- **Dashboard**: https://aurora.consulteplus.com/configuracoes/notificacoes/
- **Documentação Online**: https://aurora.consulteplus.com/documentacao/#notificacoes
- **Admin Panel**: https://aurora.consulteplus.com/admin/vendas_web/notificacao/

### Por Tópico

#### 🗄️ Banco de Dados
- [Estrutura Completa](./DOCUMENTACAO_NOTIFICACOES.md#estrutura-de-banco-de-dados)
- [Diagrama ER](./DOCUMENTACAO_NOTIFICACOES.md#diagrama-er)
- [Tabelas e Relacionamentos](./DOCUMENTACAO_NOTIFICACOES.md#detalhamento-das-tabelas)
- [Status das Notificações - Tradução](./DOCUMENTACAO_NOTIFICACOES.md#3-notificacao-vendas_web_notificacao) ⭐
- [Prioridades](./DOCUMENTACAO_NOTIFICACOES.md#3-notificacao-vendas_web_notificacao)
- [Índices e Performance](./DOCUMENTACAO_NOTIFICACOES.md#performance-e-otimizações)

#### 🔌 APIs REST
- [Endpoints Completos](./DOCUMENTACAO_NOTIFICACOES.md#apis-rest)
- [Enviar Notificação](./DOCUMENTACAO_NOTIFICACOES.md#1-enviar-notificação)
- [Listar Notificações](./DOCUMENTACAO_NOTIFICACOES.md#2-listar-notificações)
- [Estatísticas](./DOCUMENTACAO_NOTIFICACOES.md#3-obter-estatísticas)
- [Autenticação e Segurança](./DOCUMENTACAO_NOTIFICACOES.md#autenticação-e-segurança)

#### 🚀 Serviço Python
- [NotificationService](./DOCUMENTACAO_NOTIFICACOES.md#notificationservice)
- [Métodos Principais](./DOCUMENTACAO_NOTIFICACOES.md#métodos-principais)
- [Fluxo Interno](./DOCUMENTACAO_NOTIFICACOES.md#fluxo-interno-do-serviço)
- [Configuração](./DOCUMENTACAO_NOTIFICACOES.md#configuração)

#### 📱 Tipos e Canais
- [Tipos Disponíveis](./DOCUMENTACAO_NOTIFICACOES.md#tipos-de-notificação)
- [Canais de Comunicação](./DOCUMENTACAO_NOTIFICACOES.md#canais-de-comunicação)
- [Como Criar Novo Tipo](./DOCUMENTACAO_NOTIFICACOES.md#como-criar-novo-tipo-de-notificação)
- [Como Adicionar Canal](./DOCUMENTACAO_NOTIFICACOES.md#como-adicionar-novo-canal)

#### 🔗 Integração N8N
- [Workflow Recomendado](./DOCUMENTACAO_NOTIFICACOES.md#workflow-recomendado)
- [Configuração do Webhook](./DOCUMENTACAO_NOTIFICACOES.md#configuração-do-webhook)
- [Payload e Resposta](./DOCUMENTACAO_NOTIFICACOES.md#integração-n8n)

#### 💻 Exemplos Práticos
- [Notificar Novo Lead](./DOCUMENTACAO_NOTIFICACOES.md#exemplo-1-notificar-novo-lead)
- [Notificar Venda Aprovada](./DOCUMENTACAO_NOTIFICACOES.md#exemplo-2-notificar-venda-aprovada)
- [Notificação Agendada](./DOCUMENTACAO_NOTIFICACOES.md#exemplo-3-notificação-agendada)
- [Webhook Customizado](./DOCUMENTACAO_NOTIFICACOES.md#exemplo-4-webhook-customizado)

#### ⚙️ Configuração e Deploy
- [Requisitos](./DOCUMENTACAO_NOTIFICACOES.md#requisitos)
- [Variáveis de Ambiente](./DOCUMENTACAO_NOTIFICACOES.md#variáveis-de-ambiente)
- [Instalação](./DOCUMENTACAO_NOTIFICACOES.md#instalação)
- [Deploy Produção](./DOCUMENTACAO_NOTIFICACOES.md#deploy-em-produção)
- [Comandos de Gerenciamento](./DOCUMENTACAO_NOTIFICACOES.md#comandos-de-gerenciamento)

#### 📊 Monitoramento
- [Métricas Disponíveis](./DOCUMENTACAO_NOTIFICACOES.md#métricas-disponíveis)
- [Dashboard](./DOCUMENTACAO_NOTIFICACOES.md#dashboard-principal)
- [Exportar Dados](./DOCUMENTACAO_NOTIFICACOES.md#exportar-dados)

#### 🐛 Troubleshooting
- [Problemas Comuns](./DOCUMENTACAO_NOTIFICACOES.md#troubleshooting)
- [Notificações não enviadas](./DOCUMENTACAO_NOTIFICACOES.md#problema-1-notificações-não-são-enviadas)
- [Erro de conexão N8N](./DOCUMENTACAO_NOTIFICACOES.md#problema-2-erro-de-conexão-com-n8n)
- [Templates não renderizam](./DOCUMENTACAO_NOTIFICACOES.md#problema-3-templates-não-renderizam)
- [Taxa de falha alta](./DOCUMENTACAO_NOTIFICACOES.md#problema-4-taxa-de-falha-alta)
- [Performance lenta](./DOCUMENTACAO_NOTIFICACOES.md#problema-5-performance-lenta)

---

## 🤖 Sistema de Robôs

### Documentos Disponíveis

| Documento | Localização | Descrição |
|-----------|-------------|-----------|
| **Documentação Online** | [Link](https://aurora.consulteplus.com/documentacao/#robos) | Visão geral do sistema de robôs |
| **Código Fonte** | `/robo/main_refatorado.py` | Robô principal de processamento |
| **Código Leads** | `/robo/main_leads.py` | Robô de captura de leads |

---

## 📱 Sistema de Campanhas de Tráfego

### Documentos Disponíveis

| Documento | Localização | Descrição |
|-----------|-------------|-----------|
| **Documentação Online** | [Link](https://aurora.consulteplus.com/documentacao/#campanhas-trafego) | Sistema completo de campanhas |
| **Models** | `vendas_web/models.py` | CampanhaTrafego model |
| **API** | `/api/campanhas/detectar/` | Endpoint de detecção |

---

## 🗄️ Banco de Dados

### Documentos Disponíveis

| Documento | Localização | Descrição |
|-----------|-------------|-----------|
| **BANCO_DE_DADOS_DETALHADO.md** | Raiz do projeto | Arquitetura completa do banco |
| **Documentação Online** | [Link](https://aurora.consulteplus.com/documentacao/#banco-dados) | Visão geral do banco |

---

## 🌐 APIs e Integrações

### Documentos Disponíveis

| Documento | Localização | Descrição |
|-----------|-------------|-----------|
| **APIS_N8N_REFERENCE.md** | `staticfiles/` | Referência de integração N8N |
| **Documentação Online** | [Link](https://aurora.consulteplus.com/documentacao/#apis) | Todos os endpoints disponíveis |

### APIs por Módulo

#### 📊 Dashboard
- `GET /api/dashboard/data/` - Dados do dashboard
- `GET /api/dashboard/charts/` - Dados dos gráficos
- `GET /api/dashboard/leads/` - Dados de leads

#### 👥 Leads
- `GET /api/leads/` - Listar leads
- `POST /api/leads/` - Criar lead
- `PUT /api/leads/{id}/` - Atualizar lead
- `DELETE /api/leads/{id}/` - Deletar lead

#### 🔔 Notificações
- `POST /api/notificacoes/enviar/` - Enviar notificação
- `GET /api/notificacoes/listar/` - Listar notificações
- `GET /api/notificacoes/estatisticas/` - Estatísticas
- `GET/POST /api/notificacoes/preferencias/` - Preferências
- `POST /api/notificacoes/teste/` - Testar notificação

#### 📱 Campanhas
- `POST /api/campanhas/detectar/` - Detectar campanha
- `GET /api/campanhas/` - Listar campanhas
- `POST /api/campanhas/` - Criar campanha
- `PUT /api/campanhas/{id}/` - Atualizar campanha

#### 🎯 Atendimento
- `GET /api/fluxos/` - Listar fluxos
- `POST /api/fluxos/executar/` - Executar fluxo
- `GET /api/atendimento/estatisticas/` - Estatísticas

---

## 📖 Guias de Uso

### Para Desenvolvedores

1. **Começando**: [Documentação Online - Visão Geral](https://aurora.consulteplus.com/documentacao/#visao-geral)
2. **Arquitetura**: [Documentação Online - Arquitetura](https://aurora.consulteplus.com/documentacao/#arquitetura)
3. **Banco de Dados**: [BANCO_DE_DADOS_DETALHADO.md](../../BANCO_DE_DADOS_DETALHADO.md)
4. **APIs**: [Documentação Online - APIs](https://aurora.consulteplus.com/documentacao/#apis)
5. **Notificações**: [DOCUMENTACAO_NOTIFICACOES.md](./DOCUMENTACAO_NOTIFICACOES.md)

### Para Usuários

1. **Como Usar**: [Documentação Online](https://aurora.consulteplus.com/documentacao/)
2. **Sistema de Notificações**: [NOTIFICACOES_README.md](./NOTIFICACOES_README.md)
3. **Campanhas de Tráfego**: [Documentação Online - Campanhas](https://aurora.consulteplus.com/documentacao/#campanhas-trafego)

### Para Administradores

1. **Configuração Inicial**: [Documentação Online - Configuração](https://aurora.consulteplus.com/documentacao/)
2. **Deploy**: [DOCUMENTACAO_NOTIFICACOES.md - Configuração e Deploy](./DOCUMENTACAO_NOTIFICACOES.md#configuração-e-deploy)
3. **Monitoramento**: [DOCUMENTACAO_NOTIFICACOES.md - Monitoramento](./DOCUMENTACAO_NOTIFICACOES.md#monitoramento-e-estatísticas)
4. **Troubleshooting**: [DOCUMENTACAO_NOTIFICACOES.md - Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#troubleshooting)

---

## 🔍 Busca Rápida

### Por Funcionalidade

- **Enviar Notificação**: [Guia Rápido](./NOTIFICACOES_README.md#1-enviar-notificação-python) | [Documentação Completa](./DOCUMENTACAO_NOTIFICACOES.md#exemplo-1-notificar-novo-lead)
- **Configurar Webhook N8N**: [Integração N8N](./DOCUMENTACAO_NOTIFICACOES.md#integração-n8n)
- **Criar Novo Tipo**: [Como Criar Tipo](./DOCUMENTACAO_NOTIFICACOES.md#como-criar-novo-tipo-de-notificação)
- **Ver Estatísticas**: [Dashboard](https://aurora.consulteplus.com/configuracoes/notificacoes/) | [API](./DOCUMENTACAO_NOTIFICACOES.md#3-obter-estatísticas)
- **Detectar Campanha**: [API Campanhas](https://aurora.consulteplus.com/documentacao/#campanhas-trafego)

### Por Problema

- **🔥 Por que notificações ficam PENDENTES?**: [Diagnóstico Completo](./DOCUMENTACAO_NOTIFICACOES.md#problema-1-por-que-notificações-ficam-pendentes-) ⭐ **NOVO**
- **Notificação não envia**: [Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#problema-2-erro-de-conexão-com-n8n)
- **Erro N8N**: [Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#problema-2-erro-de-conexão-com-n8n)
- **Template não funciona**: [Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#problema-3-templates-não-renderizam)
- **Performance ruim**: [Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#problema-5-performance-lenta)
- **Alta taxa de falha**: [Troubleshooting](./DOCUMENTACAO_NOTIFICACOES.md#problema-4-taxa-de-falha-alta)

---

## 📞 Suporte e Contato

### Canais de Suporte

- **Email**: suporte@aurora.consulteplus.com
- **Documentação Online**: https://aurora.consulteplus.com/documentacao/
- **Admin Panel**: https://aurora.consulteplus.com/admin/
- **Status do Sistema**: https://status.aurora.consulteplus.com (se disponível)

### Recursos Adicionais

- **Changelog**: [README.md](../../README.md) - Histórico de versões
- **Guia de Contribuição**: [CONTRIBUTING.md](../../CONTRIBUTING.md) (se disponível)
- **Padrões de Código**: [CODING_STANDARDS.md](../../CODING_STANDARDS.md) (se disponível)
- **Testes**: [TESTING.md](../../TESTING.md) (se disponível)

---

## 🔄 Última Atualização

- **Data**: 23 de outubro de 2025
- **Versão**: 2.0.0
- **Autor**: Equipe Megalink

---

## 📋 Checklist de Documentação

### Notificações ✅
- [x] Estrutura de banco completa
- [x] APIs REST documentadas
- [x] Serviço Python documentado
- [x] Tipos e canais documentados
- [x] Integração N8N documentada
- [x] Exemplos práticos
- [x] Configuração e deploy
- [x] Monitoramento
- [x] Troubleshooting

### Robôs 🚧
- [x] Visão geral
- [ ] Documentação técnica detalhada
- [ ] Exemplos de uso
- [ ] Troubleshooting

### Campanhas ✅
- [x] Visão geral
- [x] API documentada
- [x] Exemplos de uso
- [x] Testes

### Banco de Dados ✅
- [x] Arquitetura geral
- [x] Tabelas principais
- [x] Relacionamentos
- [x] Otimizações

---

© 2025 Megalink. Todos os direitos reservados.

