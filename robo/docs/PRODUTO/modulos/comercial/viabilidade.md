# Comercial — Viabilidade

**App:** `apps/comercial/viabilidade/`

Verifica se o provedor tem cobertura tecnica (fibra optica) na regiao do cliente. Consultado durante o cadastro e pelo bot de atendimento.

---

## Model

### CidadeViabilidade

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cidade` | CharField(120) | Nome da cidade |
| `estado` | CharField(2) | UF (27 estados brasileiros) |
| `cep` | CharField(9) | CEP especifico (opcional, regex `^\d{5}-?\d{3}$`) |
| `bairro` | CharField(120) | Bairro (opcional) |
| `observacao` | TextField | Informacoes sobre a regiao |
| `ativo` | BooleanField | Status |

Se `cep` nao informado, a cidade inteira e considerada viavel. `save()` normaliza CEP (insere hifen) e capitaliza nome da cidade.

---

## API

```
GET /api/viabilidade/?cep=64000000
GET /api/viabilidade/?cidade=Teresina&uf=PI
```

### Logica de busca por CEP

1. Busca direta no banco por CEP exato
2. Consulta ViaCEP para descobrir cidade/estado do CEP
3. Busca cidade na lista de viabilidade
4. Retorna `viavel_pelo_cep` e/ou `viavel_pela_cidade`

---

## Gestao no sistema

Pagina server-side dentro do DS: **`/viabilidade/cidades/`** (Comercial > Configuracoes CRM > Viabilidade tecnica).

Funcionalidades:
- Listagem com filtros (busca livre em cidade/CEP/bairro, UF, status ativo/inativo)
- Paginacao (30 por pagina)
- Modal de criar / editar (cidade + UF obrigatorios; CEP, bairro, observacao opcionais)
- Botao toggle ativo/inativo
- Botao excluir (hard delete)

Multi-tenant: views usam `CidadeViabilidade.objects.all()` e o `TenantManager` filtra pelo `request.tenant` automaticamente. Criacao usa `tenant=request.tenant` no create.

Permissao: `@login_required`. Apenas configuracoes CRM (is_superuser ou `perm.acesso_configuracoes`) veem o link no subnav.

### Rotas

| Rota | Metodo | Nome URL | Funcao |
|------|--------|----------|--------|
| `/viabilidade/cidades/` | GET | `comercial_viabilidade:cidades_lista` | Pagina de listagem |
| `/viabilidade/cidades/salvar/` | POST | `comercial_viabilidade:cidade_salvar` | Criar ou atualizar (JSON body) |
| `/viabilidade/cidades/<pk>/toggle/` | POST | `comercial_viabilidade:cidade_toggle` | Alterna flag ativo |
| `/viabilidade/cidades/<pk>/excluir/` | DELETE | `comercial_viabilidade:cidade_excluir` | Remove registro |

### Template

`apps/comercial/viabilidade/templates/viabilidade/cidades.html` — extende `sistema/base.html` (shim do DS). Usa `components/badge.html`, `components/pagination.html` e JS global `toast()`.
