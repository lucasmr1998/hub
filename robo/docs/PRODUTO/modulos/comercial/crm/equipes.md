# CRM — Equipes e Perfis de Vendedor

## EquipeVendas

**Tabela:** `crm_equipes`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField | Nome da equipe |
| `lider` | FK User | Lider da equipe |
| `descricao` | TextField | Descricao |
| `cor_hex` | Char | Visual |
| `ativo` | BooleanField | Status |

---

## PerfilVendedor

**Tabela:** `crm_perfis_vendedor`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `user` | OneToOne User | Usuario |
| `equipe` | FK EquipeVendas | Equipe (1:1) |
| `cargo` | CharField | vendedor / supervisor / gerente / diretor / outro |
| `telefone_direto` / `whatsapp` | CharField | Contato |
| `id_vendedor_hubsoft` | Integer | ID no HubSoft |

---

## Visibilidade

O sistema usa `PerfilVendedor` + flag `is_superuser` para decidir o que cada usuario ve no CRM.

- **Superuser / admin:** ve todas as oportunidades do tenant
- **Vendedor comum:** ve apenas oportunidades onde e `responsavel` + oportunidades sem responsavel atribuido

Atribuicao e feita via `api_atribuir_responsavel`.
