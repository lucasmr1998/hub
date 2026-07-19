# 🔔 Sistema de Notificações - Guia Rápido

> **📚 Documentação Completa**: [`DOCUMENTACAO_NOTIFICACOES.md`](./DOCUMENTACAO_NOTIFICACOES.md)

## 🚀 Acesso Rápido

- **Dashboard**: https://aurora.consulteplus.com/configuracoes/notificacoes/
- **Documentação Online**: https://aurora.consulteplus.com/documentacao/#notificacoes
- **Django Admin**: https://aurora.consulteplus.com/admin/vendas_web/notificacao/

---

## 📋 Índice Rápido

| Tópico | Link Direto |
|--------|-------------|
| 🗄️ **Estrutura de Banco** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#estrutura-de-banco-de-dados) |
| 🔌 **APIs REST** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#apis-rest) |
| 🚀 **Serviço Python** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#serviço-de-notificações) |
| 📱 **Tipos e Canais** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#tipos-de-notificação) |
| 🔗 **Integração N8N** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#integração-n8n) |
| 💻 **Exemplos de Uso** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#exemplos-de-uso) |
| 🐛 **Troubleshooting** | [Ver Detalhes](./DOCUMENTACAO_NOTIFICACOES.md#troubleshooting) |

---

## ⚡ Quick Start

### 1. Enviar Notificação (Python)

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
            'email': 'joao@empresa.com'
        }
    },
    prioridade='alta'
)
```

### 2. Enviar via API (JavaScript)

```javascript
fetch('/api/notificacoes/enviar/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
        tipo: 'lead_novo',
        destinatarios: [1, 2, 3],
        dados_contexto: { lead: {...} },
        prioridade: 'alta'
    })
})
```

### 3. Obter Estatísticas

```python
from vendas_web.services.notification_service import notification_service
from datetime import datetime, timedelta

# Últimos 30 dias
data_inicio = datetime.now() - timedelta(days=30)
data_fim = datetime.now()

stats = notification_service.obter_estatisticas(
    data_inicio=data_inicio,
    data_fim=data_fim
)

print(f"Total: {stats['total_notificacoes']}")
print(f"Taxa de entrega: {stats['taxa_entrega']}%")
```

---

## 🗄️ Tabelas do Banco

### Principais Tabelas

| Tabela | Descrição | Campos Principais |
|--------|-----------|-------------------|
| `vendas_web_tiponotificacao` | Tipos de notificações | codigo, nome, template_padrao, prioridade_padrao |
| `vendas_web_canalnotificacao` | Canais de comunicação | codigo, nome, configuracao, icone |
| `vendas_web_notificacao` | Registro de notificações | tipo_id, canal_id, destinatario_id, status, mensagem |
| `vendas_web_preferencianotificacao` | Preferências do usuário | usuario_id, tipo_id, canal_id, horarios, dias_semana |
| `vendas_web_templatenotificacao` | Templates personalizados | tipo_id, canal_id, corpo_html, corpo_texto |

### Relacionamentos

```
User (1) ──< (N) PreferenciaNotificacao
User (1) ──< (N) Notificacao

TipoNotificacao (1) ──< (N) Notificacao
TipoNotificacao (1) ──< (N) TemplateNotificacao

CanalNotificacao (1) ──< (N) Notificacao
CanalNotificacao (1) ──< (N) TemplateNotificacao
```

---

## 🔌 APIs Principais

### Enviar Notificação
```
POST /api/notificacoes/enviar/
```

### Listar Notificações
```
GET /api/notificacoes/listar/?status=enviada&limit=50
```

### Estatísticas
```
GET /api/notificacoes/estatisticas/?data_inicio=2025-10-01&data_fim=2025-10-31
```

### Preferências
```
GET  /api/notificacoes/preferencias/
POST /api/notificacoes/preferencias/
```

### Testar
```
POST /api/notificacoes/teste/
```

### CRUD de Tipos
```
GET    /api/tipos-notificacao/
POST   /api/tipos-notificacao/
PUT    /api/tipos-notificacao/{id}/
DELETE /api/tipos-notificacao/{id}/
```

---

## 📱 Tipos Disponíveis

| Código | Nome | Descrição | Prioridade |
|--------|------|-----------|------------|
| `lead_novo` | Novo Lead | Novo lead cadastrado | Normal |
| `lead_convertido` | Lead Convertido | Lead virou prospecto | Alta |
| `venda_aprovada` | Venda Aprovada | Venda aprovada | Alta |
| `venda_rejeitada` | Venda Rejeitada | Venda rejeitada | Alta |
| `prospecto_aguardando` | Prospecto Aguardando | Aguardando validação | Normal |

---

## 📢 Canais Disponíveis

| Código | Nome | Status | Limitações |
|--------|------|--------|-----------|
| `whatsapp` | WhatsApp | ✅ ATIVO | 4096 caracteres |
| `webhook` | Webhook | ✅ ATIVO | Sem limite |
| `email` | Email | 🚧 Config. | Sem limite |
| `sms` | SMS | 🚧 Config. | 160 caracteres |

---

## 📊 Status das Notificações

### Estados Possíveis

| Código | Tradução | Descrição | Ícone |
|--------|----------|-----------|-------|
| `pendente` | **Pendente** | Aguardando processamento | ⏳ |
| `enviando` | **Enviando** | Em processo de envio | 📤 |
| `enviada` | **Enviada** | Enviada com sucesso | ✅ |
| `falhou` | **Falhou** | Erro após todas tentativas | ❌ |
| `cancelada` | **Cancelada** | Cancelada manualmente | 🚫 |

### Fluxo de Status

```
[pendente] → [enviando] → [enviada] ✅
                    ↓
                [falhou] ❌
                    
[pendente] → [cancelada] 🚫
```

### Prioridades

| Código | Tradução | Tempo Processamento |
|--------|----------|---------------------|
| `baixa` | **Baixa** | Pode ter delay |
| `normal` | **Normal** | Até 5 minutos |
| `alta` | **Alta** | Até 1 minuto |
| `urgente` | **Urgente** | Até 30 segundos |

---

## 🔗 Integração N8N

### Webhook URL
```
https://n8n.aurora.consulteplus.com/webhook/notifications
```

### Payload Exemplo
```json
{
  "notificacao_id": 123,
  "tipo": "lead_novo",
  "canal": "whatsapp",
  "titulo": "Novo Lead Recebido",
  "mensagem": "Um novo lead foi cadastrado...",
  "destinatario": {
    "id": 5,
    "nome": "Usuário",
    "email": "usuario@email.com",
    "telefone": "5511999999999"
  },
  "dados_contexto": {
    "lead": {
      "nome": "João Silva",
      "empresa": "Empresa ABC"
    }
  },
  "prioridade": "alta",
  "timestamp": "2025-10-23T10:00:00Z"
}
```

### Resposta Esperada
```json
{
  "success": true,
  "execution_id": "exec-456",
  "status": "sent",
  "message": "Notificação enviada com sucesso",
  "timestamp": "2025-10-23T10:01:30Z"
}
```

---

## 🛠️ Comandos Úteis

```bash
# Processar notificações pendentes
python manage.py process_notifications

# Processar com limite
python manage.py process_notifications --limit 100

# Forçar processamento
python manage.py process_notifications --force

# Testar sistema
python manage.py test_notifications

# Limpar notificações antigas (30+ dias)
python manage.py cleanup_notifications --days 30

# Configurar dados iniciais
python manage.py setup_notifications

# Adicionar telefone aos usuários
python manage.py add_phone_to_users

# Configurar preferências padrão
python manage.py setup_user_preferences
```

---

## 🐛 Troubleshooting Rápido

### ⏳ Por que notificações ficam PENDENTES?

**É NORMAL!** Notificações ficam pendentes por motivos estratégicos:

| Motivo | % Casos | Solução |
|--------|---------|---------|
| **Fora do horário permitido** | 80% | Aguardar horário (8h-18h configurável) |
| **Dia da semana não permitido** | 15% | Aguardar dia útil |
| **Agendamento futuro** | 3% | Aguardar data agendada |
| **Retry após falha** | 1% | Aguardar retry automático |
| **Sem preferências** | 1% | Configurar preferências do usuário |
| **Sem processamento automático** | <1% | Configurar cron/celery |

**Verificar Status:**
```python
from vendas_web.models import Notificacao
from django.utils import timezone

# Quantas estão prontas para enviar?
prontas = Notificacao.objects.filter(
    status='pendente',
    data_agendamento__lte=timezone.now()
).count()

print(f"Prontas para enviar: {prontas}")
```

**Processar Manualmente:**
```bash
# Enviar todas pendentes que já podem ser enviadas
python manage.py process_notifications

# Ver o que seria processado
python manage.py process_notifications --dry-run
```

**Configurar Processamento Automático (Cron):**
```bash
# Adicionar ao crontab (processar a cada 5 min)
*/5 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py process_notifications
```

**⚠️ QUANDO SE PREOCUPAR:**
- ✅ Pendentes há < 1h = Normal
- ✅ Com data_agendamento futura = Normal  
- ⚠️ Prontas há > 30min = Verificar processamento
- ❌ Muitas (>50) prontas não enviadas = PROBLEMA!

📖 [Ver diagnóstico completo](./DOCUMENTACAO_NOTIFICACOES.md#problema-1-por-que-notificações-ficam-pendentes-)

---

### Notificações não são enviadas
```python
# Verificar preferências
from vendas_web.models import PreferenciaNotificacao
prefs = PreferenciaNotificacao.objects.filter(
    usuario=usuario,
    tipo_notificacao__codigo='lead_novo'
)
print(prefs)
```

### Erro de conexão N8N
```bash
# Testar conectividade
curl -X POST https://n8n.aurora.com/webhook/notifications \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

### Templates não renderizam
```python
from django.template import Template, Context

template = Template("Olá {{nome}}")
contexto = Context({'nome': 'João'})
resultado = template.render(contexto)
print(resultado)  # Deve mostrar: Olá João
```

### Ver logs
```bash
# Logs do Django
tail -f /var/log/aurora/notifications.log

# Logs do Gunicorn
tail -f /var/log/gunicorn/error.log
```

---

## 📊 Status do Sistema

### Verificar Status Geral

```python
from vendas_web.services.notification_service import notification_service

stats = notification_service.obter_estatisticas()

print(f"""
Sistema de Notificações - Status
=================================
Total de Notificações: {stats['total_notificacoes']}
Enviadas: {stats['notificacoes_enviadas']} ({stats.get('taxa_entrega', 0)}%)
Falharam: {stats['notificacoes_falharam']}
Pendentes: {stats['notificacoes_pendentes']}
Canais Ativos: {stats['canais_ativos']}
Tipos Ativos: {stats['tipos_ativos']}
""")
```

---

## 📞 Suporte

- **Email**: suporte@aurora.consulteplus.com
- **Documentação Completa**: [`DOCUMENTACAO_NOTIFICACOES.md`](./DOCUMENTACAO_NOTIFICACOES.md)
- **Documentação Online**: https://aurora.consulteplus.com/documentacao/#notificacoes
- **Django Admin**: https://aurora.consulteplus.com/admin/

---

## 🔐 Segurança

- ✅ Autenticação obrigatória em todas as APIs
- ✅ Token CSRF requerido
- ✅ Permissões granulares (superuser, adm_all, usuário comum)
- ✅ Rate limiting: 100 req/min, 1000 notif/hora
- ✅ Validação de dados e sanitização de templates
- ✅ Logs detalhados de todas as operações

---

## 📈 Performance

- **Índices**: status, data_criacao, tipo_id, canal_id
- **Batch Size**: 100 notificações por vez
- **Cache**: Templates renderizados são cacheados
- **Timeout**: 30 segundos (configurável)
- **Retry**: 3 tentativas com backoff (2, 4, 8 min)

---

**Versão**: 2.0.0  
**Última Atualização**: 23 de outubro de 2025  
**Autor**: Equipe Megalink

© 2025 Megalink. Todos os direitos reservados.

