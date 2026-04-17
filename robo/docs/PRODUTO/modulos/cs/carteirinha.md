# CS — Carteirinha

**App:** `apps/cs/carteirinha/`

Sistema de carteirinha digital para membros do clube. Modelos visuais configuraveis (cores, logo, background), regras de atribuicao automatica (por nivel, XP, cidade ou todos), QR code de validacao e foto do membro.

---

## Models (3)

### ModeloCarteirinha

Template visual da carteirinha.

| Grupo | Campos principais |
|-------|-------------------|
| **Identificacao** | nome (100), descricao |
| **Fundo** | tipo_fundo (cor/imagem), cor_fundo_primaria, cor_fundo_secundaria, imagem_fundo |
| **Textos** | cor_texto, cor_texto_secundario, cor_destaque, texto_marca, texto_rodape |
| **Logo** | logo (ImageField) |
| **Visibilidade** | mostrar_nome, mostrar_cpf, mostrar_nivel, mostrar_data_emissao, mostrar_data_validade, mostrar_qr_code, mostrar_foto, mostrar_pontos, mostrar_cidade |
| **Status** | ativo, data_criacao |

### RegraAtribuicao

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `modelo` | FK ModeloCarteirinha | Modelo a atribuir |
| `tipo` | CharField | nivel / pontuacao_minima / cidade / todos / manual |
| `nivel` | FK NivelClube | Quando tipo=nivel |
| `pontuacao_minima` | Integer | Quando tipo=pontuacao_minima (XP minimo) |
| `cidade` | CharField(100) | Quando tipo=cidade |
| `prioridade` | Integer | Maior vence em conflito |
| `ativo` | Boolean | Status |

### CarteirinhaMembro

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `membro` | FK MembroClube | Dono |
| `modelo` | FK ModeloCarteirinha | Template visual |
| `foto` | ImageField | Foto do membro |
| `data_emissao` | DateTime (auto) | Quando emitiu |
| `data_validade` | DateField | Validade |
| `ativo` | Boolean | Status |

---

## CarteirinhaService

Arquivo: `apps/cs/carteirinha/services/services.py`

| Metodo | O que faz |
|--------|-----------|
| `obter_modelo_para_membro(membro)` | Avalia regras (por prioridade desc): `todos` → `nivel` → `pontuacao_minima` → `cidade`. Fallback: primeiro modelo ativo |
| `obter_carteirinha_membro(membro)` | Retorna CarteirinhaMembro existente ou cria automaticamente via regras. Usa `update_or_create()` |

---

## Views (7)

| View | Rota | Auth | Descricao |
|------|------|------|-----------|
| `dashboard_carteirinha` | `/roleta/dashboard/carteirinha/` | `@login_required` | Home: modelos, regras, total emitidas |
| `dashboard_modelos` | `/roleta/dashboard/carteirinha/modelos/` | `@login_required` | CRUD de modelos |
| `dashboard_modelo_criar` | `/roleta/dashboard/carteirinha/modelos/criar/` | `@login_required` | Criacao com preview |
| `dashboard_modelo_editar` | `/roleta/dashboard/carteirinha/modelos/<id>/editar/` | `@login_required` | Edicao com preview |
| `dashboard_regras` | `/roleta/dashboard/carteirinha/regras/` | `@login_required` | CRUD de regras de atribuicao |
| `dashboard_preview` | `/roleta/dashboard/carteirinha/preview/<id>/` | `@login_required` | Preview com dados fake |
| `membro_carteirinha` | `/roleta/membro/carteirinha/` | Sessao membro | Carteirinha do membro (auto-criada) |

---

## Admin

- **ModeloCarteirinhaAdmin:** list com nome/ativo/data_criacao
- **RegraAtribuicaoAdmin:** list com modelo/tipo/prioridade/ativo
- **CarteirinhaMembroAdmin:** list com membro/modelo/data_emissao/ativo
