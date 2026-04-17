# CS — Indicacoes

**App:** `apps/cs/indicacoes/`

Programa de indicacao member-get-member. Cada membro do clube recebe um codigo unico de indicacao e uma pagina publica personalizada. Quando a indicacao e convertida (contato feito, virou cliente), o indicador ganha pontos automaticamente via GamificationService.

---

## Models (2)

### IndicacaoConfig (Singleton)

Configuracao visual da pagina publica de indicacao.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `titulo` / `subtitulo` | CharField | Textos |
| `texto_indicador` | CharField | "Voce foi indicado por" |
| `texto_botao` | CharField | "Enviar Indicacao" |
| `texto_sucesso_titulo` / `texto_sucesso_msg` | Char / Text | Mensagem de sucesso |
| `logo` / `imagem_fundo` | ImageField | Visuais |
| `cor_fundo` / `cor_botao` | CharField(7) | Cores hex |
| `mostrar_campo_cpf` / `mostrar_campo_cidade` | Boolean | Campos opcionais |

### Indicacao

**Unique:** `(membro_indicador, telefone_indicado)`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `membro_indicador` | FK MembroClube | Quem indicou |
| `nome_indicado` | CharField(255) | Nome do indicado |
| `telefone_indicado` | CharField(20) | Telefone |
| `cpf_indicado` | CharField(14) | CPF (opcional) |
| `cidade_indicado` | CharField(100) | Cidade (opcional) |
| `status` | CharField | pendente / contato_feito / convertido / cancelado |
| `membro_indicado` | FK MembroClube (nullable) | Membro criado (quando converteu) |
| `pontos_creditados` | Boolean | Se os pontos ja foram dados |
| `data_indicacao` | DateTime (auto) | Quando indicou |
| `data_conversao` | DateTime | Quando converteu |
| `observacoes` | TextField | Observacoes |

---

## IndicacaoService

Arquivo: `apps/cs/indicacoes/services/services.py`

| Metodo | O que faz |
|--------|-----------|
| `criar_indicacao(membro_indicador, nome, telefone, cpf, cidade)` | Valida: sem auto-indicacao, sem duplicata (indicador + telefone). Cria Indicacao. Retorna `(sucesso, msg, indicacao)` |
| `confirmar_conversao(indicacao_id)` | Marca `status=convertido`, `data_conversao=now()`. Chama `GamificationService.atribuir_pontos(gatilho='indicacao_convertida')`. Marca `pontos_creditados=True`. `@transaction.atomic` |

---

## Views (5)

| View | Rota | Auth | Descricao |
|------|------|------|-----------|
| `dashboard_indicacoes_home` | `/roleta/dashboard/indicacoes/` | `@login_required` | KPIs (total, pendentes, convertidos, taxa), variacao 7 dias, top 5 embaixadores |
| `dashboard_indicacoes` | `/roleta/dashboard/indicacoes/lista/` | `@login_required` | Lista com filtros (busca, status), acoes |
| `dashboard_indicacoes_membros` | `/roleta/dashboard/indicacoes/membros/` | `@login_required` | Membros com contagem de indicacoes, auto-gera codigo |
| `dashboard_indicacoes_visual` | `/roleta/dashboard/indicacoes/visual/` | `@login_required` | Config visual da pagina publica |
| `pagina_indicacao` | `/roleta/indicar/<codigo>/` | Publico | Pagina publica de indicacao. Busca membro pelo codigo, form de indicacao |

---

## Templates (5+)

- `dashboard/home.html` — KPIs, grafico 7 dias, top embaixadores
- `dashboard/indicacoes.html` — Lista com filtros
- `dashboard/membros.html` — Membros embaixadores
- `dashboard/visual.html` — Config visual
- `pagina_indicacao.html` — Pagina publica personalizada

---

## Admin

**IndicacaoAdmin:** list com indicador/nome_indicado/telefone/status/pontos_creditados/data. Filtros por status/pontos_creditados.

---

## Integracao com automacoes

O signal de conversao dispara o evento `indicacao_convertida` consumido por [marketing/automacoes/](../marketing/automacoes/). Permite mandar mensagem de agradecimento, notificar o indicador, etc.
