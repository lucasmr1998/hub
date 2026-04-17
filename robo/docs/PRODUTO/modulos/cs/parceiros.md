# CS — Parceiros

**App:** `apps/cs/parceiros/`

Gerencia rede de parceiros comerciais com descontos exclusivos para membros do clube. Parceiros cadastram cupons que podem ser gratuitos, custar pontos ou exigir nivel minimo. Inclui fluxo completo de aprovacao, resgate e validacao no ponto de venda.

---

## Models (4)

### CategoriaParceiro

**Unique:** `(tenant, slug)`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(100) | Nome da categoria |
| `slug` | SlugField | Slug unico/tenant |
| `icone` | CharField(50) | Classe FontAwesome (default `fas fa-tag`) |
| `ordem` | Integer | Ordem de exibicao |
| `ativo` | Boolean | Status |

### Parceiro

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(255) | Nome do parceiro |
| `logo` | ImageField | Logo (tenant_upload_path) |
| `descricao` | TextField | Descricao |
| `contato_nome` / `contato_telefone` / `contato_email` | Char / Email | Dados de contato |
| `usuario` | OneToOne User | Acesso ao painel de parceiro |
| `categoria` | FK CategoriaParceiro | Categoria |
| `cidades` | M2M Cidade | Cobertura geografica |
| `ativo` | Boolean | Status |

### CupomDesconto

**Unique:** `(tenant, codigo)`

| Grupo | Campos principais |
|-------|-------------------|
| **Identificacao** | titulo (255), descricao, imagem, codigo (50, unique/tenant) |
| **Desconto** | tipo_desconto (percentual/fixo), valor_desconto (Decimal 10,2) |
| **Modalidade** | modalidade: gratuito (livre), pontos (custo em saldo), nivel (exige NivelClube minimo) |
| **Custo** | custo_pontos (Integer, quando modalidade=pontos), nivel_minimo (FK NivelClube, quando modalidade=nivel) |
| **Estoque** | quantidade_total (0 = ilimitado), quantidade_resgatada (auto), limite_por_membro (default 1) |
| **Periodo** | data_inicio, data_fim (DateTime) |
| **Restricao** | cidades_permitidas (M2M Cidade), parceiro (FK Parceiro) |
| **Aprovacao** | status_aprovacao (aprovado/pendente/rejeitado), motivo_rejeicao |
| **Status** | ativo |

**Propriedades:** `estoque_disponivel` (bool), `estoque_restante` (int ou "Ilimitado")

### ResgateCupom

**Unique:** `(tenant, codigo_unico)`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `membro` | FK MembroClube | Quem resgatou |
| `cupom` | FK CupomDesconto | Cupom resgatado |
| `codigo_unico` | CharField(20) | UUID gerado (para validacao) |
| `pontos_gastos` | Integer | Pontos debitados |
| `status` | CharField | resgatado / utilizado / expirado / cancelado |
| `valor_compra` | Decimal(10,2) | Valor da compra (preenchido na validacao) |
| `data_resgate` | DateTime (auto) | Quando resgatou |
| `data_utilizacao` | DateTime | Quando utilizou no parceiro |

---

## CupomService

Arquivo: `apps/cs/parceiros/services/services.py`

| Metodo | O que faz |
|--------|-----------|
| `resgatar_cupom(membro, cupom_id)` | Validacoes: ativo, periodo, estoque, limite/membro, cidade, pontos/nivel. Debita saldo (se pontos). Cria ResgateCupom com codigo_unico UUID. Retorna `(sucesso, mensagem, resgate)` |
| `cupons_disponiveis(membro)` | Filtra cupons ativos, aprovados, em periodo, com estoque, por cidade. Retorna queryset |

---

## Views (6)

### Dashboard admin

| View | Rota | Descricao |
|------|------|-----------|
| `dashboard_parceiros_home` | `/roleta/dashboard/parceiros/` | KPIs (total, cupons, resgates, utilizados), variacao 7 dias, grafico evolucao, top cupons |
| `dashboard_parceiros` | `/roleta/dashboard/parceiros/lista/` | CRUD de parceiros com busca |
| `dashboard_cupons` | `/roleta/dashboard/cupons/` | CRUD de cupons com filtros (parceiro, modalidade, aprovacao). Acoes: aprovar/rejeitar |
| `dashboard_cupom_detalhe` | `/roleta/dashboard/cupons/<id>/` | Detalhe do cupom com KPIs e lista de resgates |
| `dashboard_cupons_resgates` | `/roleta/dashboard/cupons/resgates/` | Historico de resgates com filtros (busca, status) |

### Pagina publica

| View | Rota | Descricao |
|------|------|-----------|
| `validar_cupom` | `/roleta/cupom/validar/` | Validacao no ponto de venda. Busca por codigo_unico, confirma uso, registra valor_compra |

---

## Templates (5+)

- `dashboard/home.html` — KPIs e graficos
- `dashboard/parceiros.html` — CRUD de parceiros
- `dashboard/cupons.html` — Gestao de cupons
- `dashboard/cupom_detalhe.html` — Detalhe + resgates
- `dashboard/cupons_resgates.html` — Historico de resgates
- `validar_cupom.html` — Pagina publica de validacao

---

## Admin

- **ParceiroAdmin:** list com nome/ativo/data_cadastro. Filtro por ativo.
- **CupomDescontoAdmin:** list com titulo/parceiro/modalidade/tipo/valor/ativo. Filtros por ativo/modalidade/parceiro.
- **ResgateCupomAdmin:** list com membro/cupom/codigo_unico/status. Filtro por status.
