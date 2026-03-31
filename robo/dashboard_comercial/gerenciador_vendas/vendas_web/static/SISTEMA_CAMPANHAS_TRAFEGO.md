# 📢 Sistema de Campanhas de Tráfego Pago - Megalink

## 📋 Índice

1. [Visão Geral](#-visão-geral)
2. [Arquitetura do Sistema](#-arquitetura-do-sistema)
3. [Modelos de Dados](#-modelos-de-dados)
4. [API de Detecção](#-api-de-detecção)
5. [Interface de Usuário](#-interface-de-usuário)
6. [Integração com N8N](#-integração-com-n8n)
7. [Analytics e Métricas](#-analytics-e-métricas)
8. [Exemplos de Uso](#-exemplos-de-uso)
9. [Troubleshooting](#-troubleshooting)

---

## 🎯 Visão Geral

O Sistema de Campanhas de Tráfego Pago é uma funcionalidade completa para identificar, rastrear e analisar a origem dos leads através de campanhas de marketing digital. O sistema detecta automaticamente palavras-chave em mensagens de WhatsApp e outros canais, associando os leads às suas respectivas campanhas.

### 🌟 Principais Características

- **Detecção Automática**: Identifica campanhas em mensagens recebidas
- **Multi-plataforma**: Suporte para Google Ads, Facebook, Instagram, TikTok, LinkedIn e mais
- **Métodos Flexíveis**: Detecção exata, parcial ou por regex
- **Attribution Models**: First-touch e Last-touch tracking
- **Analytics Avançado**: ROI, conversão, receita por campanha
- **Integração N8N**: API dedicada para automação
- **Dashboard Visual**: Interface moderna e intuitiva

---

## 🏗️ Arquitetura do Sistema

### Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRADA DE DADOS                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  WhatsApp    │  │  N8N Webhook │  │  Manual/Interface    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API DE DETECÇÃO                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  POST /api/campanhas/detectar/                           │   │
│  │  - Normalização de mensagem                              │   │
│  │  - Busca de campanhas ativas                             │   │
│  │  - Matching com algoritmo configurável                   │   │
│  │  - Cálculo de score de confiança                         │   │
│  │  - Atualização de contadores                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BANCO DE DADOS                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ CampanhaTrafego │  │DeteccaoCampanha │  │ LeadProspecto  │  │
│  │  - Configuração │  │  - Histórico    │  │  - Attribution │  │
│  │  - Palavras-chave│ │  - Metadata     │  │  - Counters    │  │
│  │  - Plataforma   │  │  - Score        │  │  - Metadata    │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYTICS & REPORTING                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - Taxa de Conversão                                     │   │
│  │  - ROI por Campanha                                      │   │
│  │  - Receita Gerada                                        │   │
│  │  - Leads por Plataforma                                  │   │
│  │  - Performance Timeline                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Componentes Principais

1. **API de Detecção**: Endpoint para receber e processar mensagens
2. **Engine de Matching**: Algoritmo que identifica palavras-chave
3. **Sistema de Attribution**: Rastreamento first-touch e last-touch
4. **Analytics Engine**: Cálculo de métricas e KPIs
5. **Interface de Gerenciamento**: CRUD completo de campanhas

---

## 📊 Modelos de Dados

### 1. CampanhaTrafego

Modelo principal que representa uma campanha de marketing.

```python
class CampanhaTrafego(models.Model):
    # Identificação
    nome = CharField(max_length=200)
    codigo = CharField(max_length=50, unique=True)
    descricao = TextField(blank=True)
    
    # Detecção
    palavra_chave = CharField(max_length=200)
    tipo_match = CharField(choices=TIPO_MATCH_CHOICES)  # exato, parcial, regex
    case_sensitive = BooleanField(default=False)
    
    # Plataforma
    plataforma = CharField(choices=PLATAFORMA_CHOICES)
    tipo_trafego = CharField(choices=TIPO_TRAFEGO_CHOICES)
    
    # Configuração
    prioridade = IntegerField(default=5)  # 1-10
    ativa = BooleanField(default=True)
    data_inicio = DateField(null=True, blank=True)
    data_fim = DateField(null=True, blank=True)
    
    # Metas e Orçamento
    url_destino = URLField(max_length=500, blank=True)
    orcamento = DecimalField(max_digits=12, decimal_places=2)
    meta_leads = IntegerField(null=True, blank=True)
    
    # Estatísticas
    contador_deteccoes = IntegerField(default=0)
    ultima_deteccao = DateTimeField(null=True, blank=True)
    
    # Visual
    cor_identificacao = CharField(max_length=7, default='#667eea')
    ordem_exibicao = IntegerField(default=0)
    
    # Metadata
    observacoes = TextField(blank=True)
    criado_em = DateTimeField(auto_now_add=True)
    atualizado_em = DateTimeField(auto_now=True)
    criado_por = ForeignKey(User)
```

#### Plataformas Suportadas

- `google_ads` - Google Ads
- `facebook_ads` - Facebook Ads
- `instagram_ads` - Instagram Ads
- `tiktok_ads` - TikTok Ads
- `linkedin_ads` - LinkedIn Ads
- `twitter_ads` - Twitter Ads
- `youtube_ads` - YouTube Ads
- `whatsapp_business` - WhatsApp Business
- `email_marketing` - Email Marketing
- `seo_organico` - SEO Orgânico
- `indicacao` - Indicação
- `outros` - Outros

#### Tipos de Match

- `exato`: Palavra-chave deve aparecer exatamente como configurada
- `parcial`: Palavra-chave pode aparecer em qualquer parte da mensagem
- `regex`: Expressão regular customizada

#### Tipos de Tráfego

- `pago` - Tráfego Pago
- `organico` - Tráfego Orgânico
- `direto` - Tráfego Direto
- `referral` - Referência
- `social` - Redes Sociais
- `email` - Email Marketing
- `outros` - Outros

---

### 2. DeteccaoCampanha

Registra cada detecção de campanha em uma mensagem.

```python
class DeteccaoCampanha(models.Model):
    # Relacionamentos
    lead = ForeignKey(LeadProspecto)
    campanha = ForeignKey(CampanhaTrafego)
    
    # Origem
    telefone = CharField(max_length=20)
    origem = CharField(choices=ORIGEM_CHOICES)  # whatsapp, sms, email, etc.
    
    # Mensagem
    mensagem_original = TextField()
    mensagem_normalizada = TextField(blank=True)
    tamanho_mensagem = IntegerField(null=True, blank=True)
    
    # Detecção
    trecho_detectado = CharField(max_length=500)
    posicao_inicio = IntegerField(null=True, blank=True)
    posicao_fim = IntegerField(null=True, blank=True)
    metodo_deteccao = CharField(choices=METODO_DETECCAO_CHOICES)
    score_confianca = DecimalField(max_digits=5, decimal_places=2)
    eh_primeira_mensagem = BooleanField(default=False)
    
    # Contexto
    timestamp_mensagem = DateTimeField(null=True, blank=True)
    ip_origem = GenericIPAddressField(null=True, blank=True)
    user_agent = CharField(max_length=500, blank=True)
    metadata = JSONField(default=dict, blank=True)
    
    # Validação
    aceita = BooleanField(default=True)
    motivo_rejeicao = TextField(blank=True)
    rejeitada_por = ForeignKey(User, null=True, blank=True)
    data_rejeicao = DateTimeField(null=True, blank=True)
    
    # Processamento N8N
    processado_n8n = BooleanField(default=False)
    data_processamento_n8n = DateTimeField(null=True, blank=True)
    resposta_n8n = JSONField(default=dict, blank=True)
    
    # Conversão
    converteu_venda = BooleanField(default=False)
    data_conversao = DateTimeField(null=True, blank=True)
    valor_venda = DecimalField(max_digits=12, decimal_places=2)
    
    # Timestamp
    detectado_em = DateTimeField(auto_now_add=True)
```

---

### 3. LeadProspecto (Campos Adicionados)

Campos adicionados ao modelo existente para suportar campanhas.

```python
# Campos de Campanhas de Tráfego Pago
campanha_origem = ForeignKey(
    CampanhaTrafego,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='leads_origem',
    help_text="Campanha pela qual o lead entrou pela primeira vez"
)

campanha_conversao = ForeignKey(
    CampanhaTrafego,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='leads_convertidos',
    help_text="Campanha ativa quando o lead converteu em cliente"
)

total_campanhas_detectadas = IntegerField(
    default=0,
    help_text="Contador de quantas campanhas foram detectadas para este lead"
)

metadata_campanhas = JSONField(
    default=dict,
    blank=True,
    help_text="Dados adicionais sobre campanhas detectadas"
)
```

---

## 🔌 API de Detecção

### Endpoint Principal

```http
POST /api/campanhas/detectar/
Content-Type: application/json
```

### Request Body

```json
{
  "telefone": "5589999999999",
  "mensagem": "Oi, vi o CUPOM50 no Instagram e quero assinar!",
  "origem": "whatsapp",
  "timestamp": "2025-10-21 14:30:00",
  "metadata": {
    "dispositivo": "mobile",
    "versao_app": "2.23.1"
  }
}
```

### Parâmetros

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `telefone` | string | Sim | Número de telefone do lead (formato: 5589999999999) |
| `mensagem` | string | Sim | Texto da mensagem a ser analisada |
| `origem` | string | Não | Canal de origem (whatsapp, sms, email, etc.) |
| `timestamp` | string | Não | Data/hora da mensagem (YYYY-MM-DD HH:MM:SS) |
| `metadata` | object | Não | Dados adicionais contextuais |

### Response - Campanha Detectada

```json
{
  "success": true,
  "campanha_detectada": {
    "id": 5,
    "codigo": "CUPOM50",
    "nome": "Promoção Cupom 50% OFF",
    "plataforma": "instagram_ads",
    "tipo_trafego": "pago",
    "cor": "#667eea",
    "ativa": true
  },
  "deteccao": {
    "id": 123,
    "trecho_detectado": "CUPOM50",
    "posicao_inicio": 11,
    "posicao_fim": 18,
    "score_confianca": 95.5,
    "metodo": "parcial",
    "eh_primeira_mensagem": true
  },
  "lead": {
    "id": 456,
    "telefone": "5589999999999",
    "criado": false,
    "campanha_origem_atualizada": true,
    "total_campanhas": 1
  },
  "message": "Campanha detectada com sucesso!"
}
```

### Response - Nenhuma Campanha Detectada

```json
{
  "success": false,
  "campanha_detectada": null,
  "deteccao": null,
  "lead": null,
  "message": "Nenhuma campanha ativa correspondente encontrada"
}
```

### Response - Erro

```json
{
  "success": false,
  "error": "Telefone e mensagem são obrigatórios",
  "details": {
    "telefone": "Campo obrigatório",
    "mensagem": "Campo obrigatório"
  }
}
```

### Códigos de Status HTTP

- `200 OK`: Processamento bem-sucedido (com ou sem detecção)
- `400 Bad Request`: Dados de entrada inválidos
- `500 Internal Server Error`: Erro no processamento

---

## 🎨 Interface de Usuário

### Página de Gerenciamento

**URL**: `https://aurora.consulteplus.com/configuracoes/campanhas/`

#### Seções

1. **Breadcrumbs**
   - Navegação contextual: Início > Configurações > Campanhas de Tráfego

2. **Cabeçalho**
   - Título: "Campanhas de Tráfego Pago"
   - Botão: "Nova Campanha"

3. **Estatísticas (Cards)**
   - Total de Campanhas
   - Campanhas Ativas
   - Total de Detecções
   - Taxa de Conversão

4. **Lista de Campanhas**
   - Cards visuais com informações principais
   - Ações: Editar, Excluir
   - Badges de status (Ativa/Inativa)
   - Cores personalizadas

5. **Modal de Criação/Edição**
   - Formulário completo com validação
   - Campos organizados em seções
   - Preview de cor
   - Validação em tempo real

#### Campos do Formulário

**Informações Básicas:**
- Nome da Campanha *
- Código Único *
- Descrição
- Plataforma *
- Tipo de Tráfego

**Configuração de Detecção:**
- Palavra-chave *
- Tipo de Detecção * (Exato, Parcial, Regex)
- Case Sensitive

**Metas e Orçamento:**
- Orçamento
- Meta de Leads
- URL de Destino

**Período:**
- Data de Início
- Data de Término

**Configurações Avançadas:**
- Prioridade (1-10)
- Cor de Identificação
- Ativa/Inativa
- Observações

---

## 🤖 Integração com N8N

### Fluxo Recomendado

```
┌──────────────────┐
│  WhatsApp Trigger│
│  (Webhook/API)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Extrair Dados   │
│  - Telefone      │
│  - Mensagem      │
│  - Timestamp     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  HTTP Request    │
│  POST /api/      │
│  campanhas/      │
│  detectar/       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  IF Node         │
│  success == true?│
└────┬────────┬────┘
     │        │
   SIM       NÃO
     │        │
     ▼        ▼
┌────────┐ ┌────────┐
│ Ações  │ │ Log    │
│ Persona│ │ Padrão │
│lizadas │ │        │
└────────┘ └────────┘
```

### Exemplo de Nó HTTP Request (N8N)

```json
{
  "method": "POST",
  "url": "https://aurora.consulteplus.com/api/campanhas/detectar/",
  "authentication": "none",
  "options": {
    "timeout": 10000
  },
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "telefone": "{{ $json.from }}",
    "mensagem": "{{ $json.body }}",
    "origem": "whatsapp",
    "timestamp": "{{ $json.timestamp }}",
    "metadata": {
      "message_id": "{{ $json.id }}",
      "chat_id": "{{ $json.chat_id }}"
    }
  }
}
```

### Ações Personalizadas Baseadas em Campanha

```javascript
// Exemplo de lógica no N8N após detecção

const campanha = $json.campanha_detectada;

if (campanha) {
  switch(campanha.codigo) {
    case 'CUPOM50':
      // Enviar mensagem específica de cupom 50% OFF
      return {
        mensagem: "Ótimo! Seu cupom de 50% OFF está ativo! 🎉",
        tag: "promocao_50",
        prioridade: "alta"
      };
      
    case 'BLACK_FRIDAY':
      // Redirecionar para atendimento VIP
      return {
        mensagem: "Black Friday! Conectando você com nosso time VIP...",
        fila: "atendimento_vip",
        prioridade: "urgente"
      };
      
    default:
      // Mensagem padrão
      return {
        mensagem: `Olá! Vi que você veio através da campanha ${campanha.nome}!`,
        tag: campanha.codigo.toLowerCase()
      };
  }
} else {
  // Sem campanha detectada
  return {
    mensagem: "Olá! Como posso ajudar?",
    tag: "atendimento_padrao"
  };
}
```

---

## 📈 Analytics e Métricas

### Métricas Calculadas

#### 1. Taxa de Conversão

```python
taxa_conversao = (leads_convertidos / total_deteccoes) * 100
```

#### 2. ROI (Return on Investment)

```python
roi = ((receita_gerada - orcamento_gasto) / orcamento_gasto) * 100
```

#### 3. Custo por Lead

```python
custo_por_lead = orcamento_gasto / total_deteccoes
```

#### 4. Custo por Aquisição (CPA)

```python
cpa = orcamento_gasto / leads_convertidos
```

#### 5. Valor Médio por Lead

```python
valor_medio = receita_total / leads_convertidos
```

### Properties Calculadas Automaticamente

Todas as campanhas têm estas properties calculadas dinamicamente:

```python
@property
def taxa_conversao(self):
    """Calcula taxa de conversão da campanha"""
    if self.contador_deteccoes == 0:
        return 0
    convertidos = self.deteccoes.filter(converteu_venda=True).count()
    return round((convertidos / self.contador_deteccoes) * 100, 2)

@property
def receita_gerada(self):
    """Calcula receita total gerada pela campanha"""
    return self.deteccoes.filter(
        converteu_venda=True
    ).aggregate(
        total=Sum('valor_venda')
    )['total'] or Decimal('0.00')

@property
def roi(self):
    """Calcula ROI da campanha"""
    if not self.orcamento or self.orcamento == 0:
        return None
    lucro = self.receita_gerada - self.orcamento
    return round((lucro / self.orcamento) * 100, 2)

@property
def esta_ativa_periodo(self):
    """Verifica se a campanha está ativa no período configurado"""
    if not self.ativa:
        return False
    
    hoje = date.today()
    
    if self.data_inicio and hoje < self.data_inicio:
        return False
    
    if self.data_fim and hoje > self.data_fim:
        return False
    
    return True
```

---

## 💡 Exemplos de Uso

### Exemplo 1: Campanha de Cupom Simples

```python
# Criar campanha
campanha = CampanhaTrafego.objects.create(
    nome="Promoção 50% OFF",
    codigo="CUPOM50",
    palavra_chave="cupom50",
    tipo_match="parcial",
    case_sensitive=False,
    plataforma="instagram_ads",
    tipo_trafego="pago",
    prioridade=8,
    ativa=True,
    orcamento=Decimal("5000.00"),
    meta_leads=100,
    cor_identificacao="#FF6B6B"
)
```

**Mensagens que detectariam:**
- "Oi, vi o CUPOM50 no Instagram"
- "Quero usar o cupom50 para assinar"
- "Me falaram do cupom50"

---

### Exemplo 2: Campanha Black Friday com Regex

```python
# Campanha com regex para múltiplas variações
campanha = CampanhaTrafego.objects.create(
    nome="Black Friday 2025",
    codigo="BF2025",
    palavra_chave=r"black\s*friday|bf\s*2025|blackfriday",
    tipo_match="regex",
    case_sensitive=False,
    plataforma="google_ads",
    tipo_trafego="pago",
    prioridade=10,  # Máxima prioridade
    ativa=True,
    data_inicio=date(2025, 11, 20),
    data_fim=date(2025, 11, 30),
    orcamento=Decimal("50000.00"),
    meta_leads=1000,
    cor_identificacao="#000000"
)
```

**Mensagens que detectariam:**
- "Vi a promoção da Black Friday"
- "Quero o plano da BF 2025"
- "BlackFriday ainda está valendo?"

---

### Exemplo 3: Campanha de Indicação (Orgânica)

```python
# Campanha sem orçamento (orgânica)
campanha = CampanhaTrafego.objects.create(
    nome="Programa de Indicações",
    codigo="INDICACAO",
    palavra_chave="indicação|indicacao|indiquei|me indicaram",
    tipo_match="regex",
    case_sensitive=False,
    plataforma="indicacao",
    tipo_trafego="organico",
    prioridade=5,
    ativa=True,
    meta_leads=50,
    cor_identificacao="#4ECDC4"
)
```

---

### Exemplo 4: Consultar Analytics via API

```python
# Buscar campanhas e suas métricas
from vendas_web.models import CampanhaTrafego

campanhas = CampanhaTrafego.objects.filter(ativa=True)

for campanha in campanhas:
    print(f"Campanha: {campanha.nome}")
    print(f"  - Detecções: {campanha.contador_deteccoes}")
    print(f"  - Taxa de Conversão: {campanha.taxa_conversao}%")
    print(f"  - Receita Gerada: R$ {campanha.receita_gerada}")
    print(f"  - ROI: {campanha.roi}%")
    print(f"  - Status Período: {campanha.esta_ativa_periodo}")
    print("---")
```

---

### Exemplo 5: Detecção Manual via Python

```python
from vendas_web.views import api_detectar_campanha
from django.http import JsonResponse
import json

# Simular request
data = {
    "telefone": "5589999999999",
    "mensagem": "Oi! Vi o CUPOM50 no Instagram",
    "origem": "whatsapp"
}

# Processar
response = api_detectar_campanha(request)
result = json.loads(response.content)

if result['success']:
    campanha = result['campanha_detectada']
    print(f"Campanha detectada: {campanha['nome']}")
    print(f"Score: {result['deteccao']['score_confianca']}%")
```

---

## 🔧 Troubleshooting

### Problema: Campanhas não estão sendo detectadas

**Possíveis causas:**

1. **Campanha inativa**
   - Verificar se `ativa=True`
   - Verificar se está dentro do período (data_inicio e data_fim)

2. **Palavra-chave incorreta**
   - Verificar se a palavra-chave está escrita corretamente
   - Testar com `case_sensitive=False`
   - Usar tipo_match="parcial" para maior flexibilidade

3. **Prioridade conflitante**
   - Se múltiplas campanhas detectam, apenas a de maior prioridade é retornada
   - Ajustar campo `prioridade` (1-10)

4. **Normalização de mensagem**
   - Mensagens são normalizadas (removido acentos, caracteres especiais)
   - Testar palavra-chave sem acentos

**Solução:**

```python
# Debugar detecção
from vendas_web.models import CampanhaTrafego

mensagem = "sua mensagem aqui"
mensagem_normalizada = mensagem.lower().strip()

campanhas = CampanhaTrafego.objects.filter(
    ativa=True
).order_by('-prioridade')

for campanha in campanhas:
    palavra = campanha.palavra_chave.lower()
    if campanha.tipo_match == 'parcial':
        if palavra in mensagem_normalizada:
            print(f"✓ Detectaria: {campanha.nome}")
    elif campanha.tipo_match == 'exato':
        if palavra == mensagem_normalizada:
            print(f"✓ Detectaria: {campanha.nome}")
```

---

### Problema: Score de confiança muito baixo

**Causas:**

- Palavra-chave aparece no final da mensagem
- Mensagem muito longa
- Match parcial em palavra composta

**Solução:**

O score é calculado baseado em:
- Posição da palavra-chave (início = maior score)
- Tamanho relativo da palavra vs mensagem
- Tipo de match usado

Para aumentar score:
- Use match "exato" quando possível
- Incentive uso da palavra-chave no início
- Configure palavras-chave mais específicas

---

### Problema: Múltiplas campanhas detectam a mesma mensagem

**Comportamento esperado:**

O sistema retorna apenas a campanha de **maior prioridade** quando múltiplas detectam.

**Solução:**

```python
# Ajustar prioridades
CampanhaTrafego.objects.filter(codigo='CUPOM50').update(prioridade=10)
CampanhaTrafego.objects.filter(codigo='CUPOM30').update(prioridade=8)
```

---

### Problema: Lead não está sendo criado automaticamente

**Verificação:**

1. Telefone está no formato correto? (5589999999999)
2. Lead já existe no banco?
3. Erro na API?

**Debug:**

```python
from vendas_web.models import LeadProspecto

# Verificar se lead existe
telefone = "5589999999999"
lead_exists = LeadProspecto.objects.filter(telefone=telefone).exists()

if lead_exists:
    print("Lead já existe, será atualizado")
else:
    print("Lead será criado")
```

---

## 📊 Relatórios Personalizados

### Leads por Campanha (Last 30 days)

```python
from django.utils import timezone
from datetime import timedelta
from vendas_web.models import DeteccaoCampanha

trinta_dias_atras = timezone.now() - timedelta(days=30)

relatorio = DeteccaoCampanha.objects.filter(
    detectado_em__gte=trinta_dias_atras
).values(
    'campanha__nome',
    'campanha__codigo'
).annotate(
    total_deteccoes=Count('id'),
    convertidos=Count('id', filter=Q(converteu_venda=True)),
    receita=Sum('valor_venda')
).order_by('-total_deteccoes')

for item in relatorio:
    print(f"{item['campanha__nome']}: {item['total_deteccoes']} leads")
```

---

### Performance por Plataforma

```python
from django.db.models import Avg, Sum, Count

relatorio_plataforma = CampanhaTrafego.objects.values(
    'plataforma'
).annotate(
    total_campanhas=Count('id'),
    total_deteccoes=Sum('contador_deteccoes'),
    media_conversao=Avg('taxa_conversao'),
    receita_total=Sum('receita_gerada')
).order_by('-total_deteccoes')
```

---

## 🔐 Segurança e Boas Práticas

### 1. Validação de Dados

Sempre validar entrada da API:

```python
# Exemplo de validação robusta
def validar_request_deteccao(data):
    erros = {}
    
    if not data.get('telefone'):
        erros['telefone'] = 'Campo obrigatório'
    elif len(data['telefone']) < 10:
        erros['telefone'] = 'Telefone inválido'
    
    if not data.get('mensagem'):
        erros['mensagem'] = 'Campo obrigatório'
    elif len(data['mensagem']) > 5000:
        erros['mensagem'] = 'Mensagem muito longa'
    
    return erros
```

### 2. Rate Limiting

Implementar rate limiting na API para prevenir abuse:

```python
# Em settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
    }
}
```

### 3. Logging

Sempre logar detecções para auditoria:

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Campanha detectada: {campanha.codigo} para lead {telefone}")
```

### 4. Proteção de Dados Sensíveis

Nunca expor informações sensíveis na API:

```python
# ❌ NÃO FAZER
response = {
    'lead': model_to_dict(lead)  # Expõe TODOS os dados
}

# ✓ FAZER
response = {
    'lead': {
        'id': lead.id,
        'telefone': lead.telefone,
        'criado': lead_criado
    }
}
```

---

## 📚 Recursos Adicionais

### Documentação Relacionada

- [README Principal](../README.md)
- [CHANGELOG](../CHANGELOG.md)
- [Sistema de Notificações](SISTEMA_NOTIFICACOES.md)
- [API N8N Reference](../../staticfiles/APIS_N8N_REFERENCE.md)

### APIs REST Completas

- `GET /api/campanhas/` - Listar campanhas
- `POST /api/campanhas/` - Criar campanha
- `PUT /api/campanhas/` - Atualizar campanha
- `DELETE /api/campanhas/` - Deletar campanha
- `POST /api/campanhas/detectar/` - Detectar campanha

### Admin Django

Acesse o admin em: `/admin/vendas_web/campanhatrafego/`

Funcionalidades:
- CRUD completo
- Filtros avançados
- Estatísticas em tempo real
- Busca por código, nome, plataforma
- Ordenação customizada

---

## 🆘 Suporte

### Contato

- **Email**: suporte@aurora.consulteplus.com
- **Telefone**: +55 (11) 99999-9999
- **Horário**: Segunda a Sexta, 8h às 18h

### Reportar Problemas

1. Descreva o problema detalhadamente
2. Inclua logs relevantes
3. Forneça exemplo de request/response
4. Especifique ambiente (produção/desenvolvimento)

---

**Última atualização**: 21 de Outubro de 2025  
**Versão**: 2.2.0  
**Autor**: Equipe Megalink




