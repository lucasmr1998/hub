# Matrix API — Contato, Blacklist/Blocklist

## Contato

### Criar contato

`POST /rest/v1/contato` ou `POST /rest/v2/contato`

| Campo | Descricao |
|---|---|
| `codigo_conta` | Conta da Matrix |
| `codigo` | ID externo (opcional) |
| `nome`, `telefone`, `cpf`, `data_nascimento`, `rg`, `email` | Dados basicos |
| `ativo` | true/false |
| `codigo_canal` | Canal de origem |
| `matricula` | ID interno do cliente |
| `id_externo` | ID em sistema terceiro (ERP/CRM) |
| `codigo_agente` | Agente responsavel |
| `enderecos[]` | Array com `tipo_endereco`, `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf` |

Resposta: `{ "msg": "Contato inserido com sucesso", "codigo_contato": 2 }`

### Alterar contato

`PUT /rest/v1/contato` ou `PUT /rest/v2/contato`

Mesmo body do POST, com `codigo` preenchido (ID do contato a alterar). Use `id_externo` ou `matricula` pra correlacionar com o lead/cliente do nosso lado.

### Consultar contato (v2)

`GET /rest/v2/contato?cod_contato=N`
ou `GET /rest/v2/contato?telefone=N&cod_conta=N`

Retorna dados completos: identificacao, classificacao, tags, enderecos, redes sociais, observacoes, agente associado, campos extras, imagem.

```bash
curl 'https://nuvyon.matrixdobrasil.ai/rest/v2/contato?telefone=5511999999999&cod_conta=177' \
  -H 'Authorization: Bearer <jwt>'
```

---

## Blacklist (v1) / Blocklist (v2)

Mesma funcionalidade — v2 renomeou `blacklist` -> `blocklist`. **v2 e o caminho** pra implementacoes novas.

### Listar

`GET /rest/v1/blacklist` ou `GET /rest/v2/blocklist`

Query params (use combinacao):
- `num_telefone`, `nom_email`, `cod_contato`, `num_cpf` — identificacao
- `tip_blacklist` (v1) / `tip_blocklist` (v2): **1**=HSM, **2**=Receptivo, **3**=ambos
- `cod_blacklist` / `cod_blocklist` — ID especifico
- `restringir_contato` (v2) — `1` filtra so contatos restritos

### Criar

`POST /rest/v1/blacklist` ou `POST /rest/v2/blocklist`

```json
{
  "num_telefone": "5511999888777",
  "nom_email": "contato@contato.com",
  "cod_contato": 1,
  "num_cpf": "12345678900",
  "tip_blacklist": 1
}
```

### Alterar

`PUT /rest/v1/blacklist` ou `PUT /rest/v2/blocklist`

Use `filter[]` (v1) pra identificar o registro a alterar:

```json
{
  "num_telefone": "5511999888777",
  "tip_blacklist": 1,
  "filter": { "cod_blacklist": 1 }
}
```

### Remover

`DELETE /rest/v1/blacklist` ou `DELETE /rest/v2/blocklist`

Body com `cod_blacklist` / `cod_blocklist` ou identificacao (telefone, cpf etc).

---

## Como o Hubtrix poderia usar

### Bloqueio LGPD / opt-out

Quando cliente pede pra parar de receber:
1. Marcar `LeadProspecto.bloqueado=True` no nosso DB.
2. **Tambem** chamar `POST /rest/v2/blocklist` na Matrix dele com `tip_blocklist=3` (HSM + receptivo).
3. Isso garante que mesmo um disparo em batch nao "vaze" pro contato bloqueado.

### Reconciliacao Lead <-> Contato Matrix

Quando criamos um LeadProspecto e a Matrix tambem tem registro:
- Salvar `LeadProspecto.matrix_id_contato` (campo novo) com o retorno de `GET /rest/v2/contato`.
- Usar `id_externo` da Matrix = nosso `lead.id` na criacao via `POST /contato`.
