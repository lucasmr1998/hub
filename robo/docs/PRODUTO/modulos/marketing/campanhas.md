# Marketing — Campanhas

**App:** `apps/marketing/campanhas/`

Gerencia campanhas de trafego pago com deteccao automatica de palavras-chave em mensagens de clientes. Identifica de qual campanha veio cada lead, calcula ROI, taxa de conversao e metricas por plataforma. Integracao direta com N8N para deteccao em tempo real.

---

## Models (2)

### CampanhaTrafego

**Tabela:** `campanha_trafego` | **Unique:** `(tenant, codigo)`

| Grupo | Campos principais |
|-------|-------------------|
| **Identificacao** | nome (200), codigo (50, unique/tenant), descricao |
| **Palavra-chave** | palavra_chave (200), tipo_match (exato/parcial/regex), case_sensitive (default False) |
| **Classificacao** | plataforma (google_ads, facebook_ads, instagram_ads, tiktok_ads, linkedin_ads, email, sms, whatsapp, outro), tipo_trafego (pago/organico/hibrido) |
| **Configuracao** | prioridade (1-10, default 5), ativa (default True) |
| **Periodo** | data_inicio, data_fim (DateField, opcionais) |
| **Comercial** | url_destino (500), orcamento (Decimal 12,2), meta_leads |
| **Estatisticas** | contador_deteccoes (auto), ultima_deteccao (auto) |
| **Visual** | cor_identificacao (hex, default #667eea), ordem_exibicao |
| **Auditoria** | criado_por FK User, criado_em, atualizado_em |

**4 indices:** codigo, ativa, palavra_chave, plataforma

**Propriedades:**

| Propriedade | Retorno | Descricao |
|-------------|---------|-----------|
| `esta_no_periodo` | bool | Se esta dentro das datas inicio/fim |
| `esta_ativa` | bool | Ativa AND dentro do periodo |
| `total_leads` | int | Count de LeadProspecto com `campanha_origem=self` |
| `total_conversoes` | int | Deteccoes com `converteu_venda=True` |
| `taxa_conversao` | float | (conversoes / deteccoes) × 100 |
| `receita_total` | Decimal | Sum de `valor_venda` das deteccoes convertidas |
| `roi` | float | (receita - orcamento) / orcamento × 100 |

### DeteccaoCampanha

**Tabela:** `deteccao_campanha`

Registra cada vez que uma palavra-chave de campanha e detectada em uma mensagem de cliente.

| Grupo | Campos principais |
|-------|-------------------|
| **Relacionamentos** | lead FK LeadProspecto, campanha FK CampanhaTrafego |
| **Mensagem** | telefone (20), mensagem_original, mensagem_normalizada (auto), tamanho_mensagem (auto) |
| **Deteccao** | trecho_detectado (500), posicao_inicio, posicao_fim, metodo_deteccao (exato/parcial/regex), score_confianca (Decimal 0-100) |
| **Contexto** | eh_primeira_mensagem, origem (whatsapp/sms/email/chat/telefone), timestamp_mensagem |
| **Tecnico** | ip_origem, user_agent (500), metadata (JSON) |
| **Validacao** | aceita (default True), motivo_rejeicao, rejeitada_por FK User, data_rejeicao |
| **N8N** | processado_n8n, data_processamento_n8n, resposta_n8n (JSON) |
| **Conversao** | converteu_venda, data_conversao, valor_venda (Decimal 12,2) |
| **Auditoria** | detectado_em (auto) |

**6 indices:** telefone, lead, campanha, -detectado_em, aceita, converteu_venda

**`save()` override:**

1. Normaliza mensagem (NFKD, lowercase, remove acentos)
2. Calcula tamanho da mensagem
3. Atualiza `contador_deteccoes` da campanha

---

## APIs (4 endpoints)

| Endpoint | Metodo | Auth | Descricao |
|----------|--------|------|-----------|
| `/marketing/configuracoes/campanhas/` | GET | `@login_required` | Pagina de campanhas |
| `/marketing/configuracoes/campanhas/deteccoes/` | GET | `@login_required` | Pagina de deteccoes com filtros |
| `/marketing/api/campanhas/` | GET/POST/PUT/DELETE | `@login_required` | CRUD completo via JSON |
| `/marketing/api/campanhas/detectar/` | POST | `@api_token_required` | Deteccao (N8N) |

### API de Deteccao (N8N)

Endpoint principal de integracao. O N8N envia cada mensagem recebida no WhatsApp e a API detecta automaticamente a campanha de origem.

**Request:**

```json
{
    "telefone": "5589999999999",
    "mensagem": "vi o cupom50 no Instagram",
    "origem": "whatsapp",
    "timestamp": "2024-11-20 10:30:00"
}
```

**Algoritmo:**

1. Normaliza a mensagem (remove acentos, lowercase)
2. Itera campanhas ativas ordenadas por prioridade
3. Aplica metodo de deteccao (exato → parcial → regex)
4. Calcula score de confianca (100% exato, 95% parcial, 90% regex)
5. Cria/vincula lead se nao existe
6. Registra DeteccaoCampanha
7. Retorna campanha detectada com score

**Response:**

```json
{
    "success": true,
    "campanha_detectada": {
        "id": 5, "codigo": "CUPOM50", "nome": "Promo 50% OFF",
        "plataforma": "instagram_ads"
    },
    "deteccao": {
        "id": 12345, "trecho_detectado": "cupom50",
        "score_confianca": 95.5, "metodo": "parcial"
    },
    "lead_id": 123,
    "lead_criado": false
}
```

---

## Template

`campanhas.html` — Grid 4 colunas de cards. KPIs no topo (total, ativas, deteccoes, leads). Modal de criacao/edicao.

---

## Admin

**CampanhaTrafegoAdmin:** list com nome/codigo/plataforma/ativa/deteccoes. Filtros por ativa/plataforma/tipo_trafego. Fieldsets organizados por grupo. Custom method `estatisticas_display()` com tabela HTML de metricas.

**DeteccaoCampanhaAdmin:** list com campanha/telefone/score/origem/aceita. Filtros por aceita/converteu_venda/origem/metodo. Campos de mensagem e timestamps como readonly.
