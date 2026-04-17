# CRM — Produtos e Servicos

## ProdutoServico

**Tabela:** `crm_produtos`

Catalogo generico de produtos/servicos. Funciona para qualquer tipo de empresa (nao apenas ISPs).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(150) | Nome do produto |
| `descricao` | TextField | Descricao |
| `codigo` | CharField(50) | Codigo/SKU |
| `categoria` | CharField | plano / servico / equipamento / addon / outro |
| `preco` | Decimal(10,2) | Preco (R$) |
| `recorrencia` | CharField | mensal / trimestral / semestral / anual / avulso |
| `ativo` | BooleanField | Se esta ativo |
| `plano_internet` | FK PlanoInternet | Mapeamento opcional para HubSoft |
| `id_externo` | CharField(100) | ID no sistema integrado |

**unique_together:** `(tenant, codigo)`

---

## Vinculo com oportunidades

ItemOportunidade vincula um produto a uma oportunidade. Ver [oportunidades.md](oportunidades.md#itemoportunidade).

---

## Mapeamento com PlanoInternet

O campo `plano_internet` permite mapear um produto do catalogo CRM para um plano especifico do HubSoft. Ao criar contrato, o sistema usa esse mapeamento para enviar o `id_plano_rp` correto ao ERP.
