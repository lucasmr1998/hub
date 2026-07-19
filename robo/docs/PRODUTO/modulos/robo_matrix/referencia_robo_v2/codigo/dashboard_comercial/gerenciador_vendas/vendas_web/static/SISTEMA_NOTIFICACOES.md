# 🔔 Sistema de Notificações - Megalink

> **📚 Nota**: Esta é a versão resumida. Para documentação completa, consulte [`DOCUMENTACAO_NOTIFICACOES.md`](./DOCUMENTACAO_NOTIFICACOES.md)

## Visão Geral

O Sistema de Notificações do Megalink é uma solução completa para envio de notificações através de múltiplos canais (Email, WhatsApp, SMS, Webhook) integrada com N8N para máxima flexibilidade e automação.

## 🏗️ Arquitetura

### Componentes Principais

1. **Modelos de Dados** (`models.py`)
   - `TipoNotificacao`: Tipos de eventos que geram notificações
   - `CanalNotificacao`: Canais disponíveis (email, WhatsApp, SMS, etc.)
   - `PreferenciaNotificacao`: Preferências por usuário
   - `Notificacao`: Registro de notificações enviadas
   - `TemplateNotificacao`: Templates por canal

2. **Serviço de Notificações** (`services/notification_service.py`)
   - `NotificationService`: Classe principal para gerenciar notificações
   - Integração com N8N via webhook
   - Sistema de retry automático
   - Agendamento de envios

3. **APIs REST** (`views.py`)
   - Envio de notificações
   - Gerenciamento de preferências
   - Estatísticas e histórico
   - Teste de notificações

4. **Interface Web** (`templates/configuracoes/notificacoes.html`)
   - Dashboard completo de gerenciamento
   - Configuração de tipos e canais
   - Teste de notificações
   - Monitoramento em tempo real

## 🚀 Configuração Inicial

### 1. Configurar Variáveis de Ambiente

```bash
# N8N Integration
export N8N_WEBHOOK_URL="https://n8n.aurora.consulteplus.com/webhook/notifications"
export N8N_API_KEY="sua_chave_api_n8n"

# Site URL
export SITE_URL="https://aurora.consulteplus.com"
```

### 2. Executar Migrações

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Configurar Dados Iniciais

```bash
python manage.py setup_notifications
```

Este comando criará:
- 13 tipos de notificação básicos
- 5 canais de notificação
- Templates básicos para email

## 📱 Canais Disponíveis

### Email
- **Configuração**: SMTP padrão
- **Template**: HTML + Texto
- **Limitações**: Sem limite de caracteres

### WhatsApp
- **Configuração**: API WhatsApp Business
- **Template**: Texto simples
- **Limitações**: 4096 caracteres

### SMS
- **Configuração**: Twilio ou similar
- **Template**: Texto simples
- **Limitações**: 160 caracteres

### Push Notification
- **Configuração**: Service Worker
- **Template**: JSON
- **Limitações**: 4KB payload

### Webhook
- **Configuração**: URL customizada
- **Template**: JSON
- **Limitações**: Configurável

## 🎯 Tipos de Notificação

### Eventos de Negócio
- **lead_novo**: Novo lead cadastrado
- **lead_convertido**: Lead convertido em prospecto
- **venda_aprovada**: Venda aprovada
- **venda_rejeitada**: Venda rejeitada
- **prospecto_aguardando**: Prospecto aguardando validação

### Eventos de Sistema
- **sistema_erro**: Erro crítico no sistema
- **backup_concluido**: Backup concluído
- **sistema_manutencao**: Manutenção programada

### Eventos de Usuário
- **usuario_criado**: Novo usuário criado
- **atendimento_iniciado**: Atendimento iniciado
- **atendimento_finalizado**: Atendimento finalizado
- **meta_atingida**: Meta atingida

### Relatórios
- **relatorio_diario**: Relatório diário de atividades

## 🔧 Como Usar

### 1. Enviar Notificação Simples

```python
from vendas_web.services.notification_service import notification_service

# Enviar para usuários específicos
notificacoes = notification_service.enviar_notificacao(
    tipo_codigo='lead_novo',
    destinatarios=[user1, user2],
    dados_contexto={
        'lead': {
            'nome': 'João Silva',
            'empresa': 'Empresa ABC',
            'email': 'joao@empresa.com',
            'telefone': '(11) 99999-9999',
            'origem': 'Site'
        }
    },
    prioridade='alta'
)
```

### 2. Enviar para Grupo

```python
# Enviar para todos os vendedores
notificacoes = notification_service.enviar_notificacao_para_grupo(
    tipo_codigo='venda_aprovada',
    grupo_nome='vendedores',
    dados_contexto={
        'venda': {
            'valor': 'R$ 1.500,00',
            'cliente': 'Maria Santos'
        }
    }
)
```

### 3. Enviar para Destinatário Externo

```python
# Enviar para cliente externo
notificacao = notification_service.enviar_notificacao_externa(
    tipo_codigo='venda_aprovada',
    email='cliente@email.com',
    dados_contexto={
        'venda': {
            'valor': 'R$ 1.500,00',
            'produto': 'Plano 100MB'
        }
    },
    canal_preferido='email'
)
```

### 4. Via API REST

```javascript
// Enviar notificação via API
fetch('/api/notificacoes/enviar/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
        tipo: 'lead_novo',
        destinatarios: [1, 2, 3], // IDs dos usuários
        dados_contexto: {
            lead: {
                nome: 'João Silva',
                empresa: 'Empresa ABC'
            }
        },
        prioridade: 'alta'
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

## ⚙️ Configuração de Preferências

### Por Usuário
Cada usuário pode configurar:
- Quais tipos de notificação receber
- Canal preferido para cada tipo
- Horários permitidos para recebimento
- Dias da semana para recebimento

### Por Tipo
Cada tipo de notificação pode ter:
- Prioridade padrão
- Template padrão
- Canais disponíveis

## 🔄 Integração com N8N

### Webhook Payload

```json
{
    "notificacao_id": 123,
    "tipo": "lead_novo",
    "canal": "email",
    "titulo": "Novo Lead Recebido - João Silva",
    "mensagem": "Um novo lead foi cadastrado...",
    "destinatario": {
        "email": "usuario@email.com",
        "telefone": "(11) 99999-9999",
        "nome": "Usuário Nome"
    },
    "dados_contexto": {
        "lead": {
            "nome": "João Silva",
            "empresa": "Empresa ABC"
        }
    },
    "prioridade": "alta"
}
```

### Exemplo de Workflow N8N

1. **Webhook Receiver**: Recebe dados do Django
2. **Router**: Direciona baseado no canal
3. **Email Node**: Para notificações por email
4. **WhatsApp Node**: Para notificações por WhatsApp
5. **SMS Node**: Para notificações por SMS
6. **Response**: Retorna status para o Django

## 📊 Monitoramento

### Estatísticas Disponíveis
- Total de notificações enviadas
- Notificações do dia
- Taxa de entrega
- Canais ativos
- Status das notificações

### Comandos de Gerenciamento

```bash
# Processar notificações pendentes
python manage.py process_notifications

# Processar com limite específico
python manage.py process_notifications --limit 100

# Forçar processamento
python manage.py process_notifications --force
```

## 🛠️ Manutenção

### Limpeza de Dados Antigos

```python
from django.utils import timezone
from datetime import timedelta
from vendas_web.models import Notificacao

# Remover notificações antigas (30 dias)
data_limite = timezone.now() - timedelta(days=30)
Notificacao.objects.filter(
    data_criacao__lt=data_limite,
    status__in=['enviada', 'falhou']
).delete()
```

### Backup de Configurações

```python
# Exportar configurações
from vendas_web.models import TipoNotificacao, CanalNotificacao

tipos = list(TipoNotificacao.objects.values())
canais = list(CanalNotificacao.objects.values())

# Salvar em arquivo JSON
import json
with open('notifications_config.json', 'w') as f:
    json.dump({'tipos': tipos, 'canais': canais}, f, indent=2)
```

## 🔒 Segurança

### Permissões
- Apenas superusuários e grupo 'adm_all' podem acessar configurações
- Usuários podem gerenciar apenas suas próprias preferências
- APIs protegidas por autenticação

### Rate Limiting
- Máximo de 100 notificações por lote
- Retry automático com backoff exponencial
- Timeout de 30 segundos para webhooks

### Validação
- Validação de dados de entrada
- Sanitização de templates
- Verificação de permissões

## 🐛 Troubleshooting

### Problemas Comuns

1. **N8N não recebe notificações**
   - Verificar URL do webhook
   - Verificar conectividade de rede
   - Verificar logs do N8N

2. **Templates não renderizam**
   - Verificar sintaxe das variáveis
   - Verificar dados de contexto
   - Verificar logs de erro

3. **Notificações não são enviadas**
   - Verificar preferências do usuário
   - Verificar horários permitidos
   - Verificar status dos canais

### Logs

```python
import logging
logger = logging.getLogger('vendas_web.notifications')

# Logs são salvos em:
# - Django logs
# - N8N execution logs
# - Database (campo erro_detalhes)
```

## 📈 Performance

### Otimizações
- Índices no banco de dados
- Processamento em lotes
- Cache de templates
- Conexões persistentes com N8N

### Métricas
- Tempo médio de processamento
- Taxa de sucesso por canal
- Volume de notificações por hora
- Uso de recursos do servidor

## 🔮 Roadmap

### Próximas Funcionalidades
- [ ] Notificações push para mobile
- [ ] Integração com Slack/Teams
- [ ] Templates visuais drag-and-drop
- [ ] Analytics avançados
- [ ] A/B testing de templates
- [ ] Integração com calendário
- [ ] Notificações por geolocalização

### Melhorias Planejadas
- [ ] Interface mobile responsiva
- [ ] API GraphQL
- [ ] Webhooks bidirecionais
- [ ] Machine learning para otimização
- [ ] Integração com CRM externo

---

## 📞 Suporte

Para dúvidas ou problemas:
- **Email**: suporte@aurora.consulteplus.com
- **Documentação**: `/static/SISTEMA_NOTIFICACOES.md`
- **Logs**: Django admin → Notificações
- **Status**: Dashboard de notificações

---

**Versão**: 1.0.0  
**Última atualização**: {{ data_atual }}  
**Autor**: Sistema Megalink
