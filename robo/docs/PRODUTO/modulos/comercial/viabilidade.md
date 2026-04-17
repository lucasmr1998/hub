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

## Template

Nenhum. Modulo e API-only.
