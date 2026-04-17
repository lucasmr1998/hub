# Customer Success

**Status:** Em desenvolvimento
**App:** `apps/cs/`

Cobre todo o ciclo de fidelizacao do cliente: do primeiro contato pos-venda ate a prevencao de churn. Composto por 6 sub-apps que se integram via services e o engine de gamificacao. Migrado do projeto megaroleta para o hub em 29/03/2026.

```
Cliente ativado no HubSoft
    │
    ▼
┌──────────┐     ┌────────────┐     ┌──────────────┐
│  CLUBE   │────▶│ INDICACOES │────▶│  PARCEIROS   │
│ Roleta   │     │ Programa   │     │  Cupons      │
│ Missoes  │     │ Conversao  │     │  Resgates    │
│ XP/Niveis│     │ Pagina pub.│     │  Validacao   │
└────┬─────┘     └────────────┘     └──────────────┘
     │
     ├──▶ CARTEIRINHA (ID digital com QR code)
     ├──▶ NPS (Pesquisa de satisfacao) [stub]
     └──▶ RETENCAO (Score de saude, alertas churn) [stub]
```

---

## Indice

| Arquivo | Sub-app | Descricao |
|---------|---------|-----------|
| [parceiros.md](parceiros.md) | `parceiros/` | Cupons de desconto + resgates + categorias |
| [indicacoes.md](indicacoes.md) | `indicacoes/` | Programa de indicacao + pagina publica + service |
| [carteirinha.md](carteirinha.md) | `carteirinha/` | Carteirinha digital com QR code |
| [nps.md](nps.md) | `nps/` | Pesquisa de satisfacao (stub) |
| [retencao.md](retencao.md) | `retencao/` | Score de saude + alertas churn (stub) |
| [clube/](clube/) | `clube/` | Motor de gamificacao (roleta, missoes, niveis, XP, 10 models) |

---

## Sidebar do painel

```
CUSTOMER SUCCESS
├── Dashboard          → clube:dashboard_home
└── Clientes           → clube:dashboard_participantes

FIDELIZACAO
├── Indicacoes         → indicacoes:dashboard_indicacoes_home
├── Parceiros          → parceiros:dashboard_parceiros_home
├── Cupons             → parceiros:dashboard_cupons
└── Roleta             → clube:dashboard_premios

CONFIGURACOES
├── Banners            → clube:dashboard_banners
├── Carteirinhas       → carteirinha:dashboard_carteirinha
└── Niveis e XP        → clube:dashboard_gamificacao
```

---

## Integracoes entre submodulos

```
Clube ──GamificationService──▶ Indicacoes (pontos ao converter)
Clube ──GamificationService──▶ Automacoes (acao dar_pontos)
Clube ──MembroClube──▶ Parceiros (cupons exigem membro)
Clube ──NivelClube──▶ Parceiros (cupons por nivel)
Clube ──Cidade──▶ Parceiros + Premios (restricao geografica)
Indicacoes ──IndicacaoService──▶ Clube (confirmar_conversao → atribuir_pontos)
Parceiros ──CupomService──▶ Clube (debita saldo, valida nivel)
Carteirinha ──CarteirinhaService──▶ Clube (NivelClube, XP para regras)
```

---

## Integracoes externas

| Servico | Uso | Integracao |
|---------|-----|------------|
| **N8N** | OTP via WhatsApp, consulta HubSoft | Webhook POST |
| **HubSoft** | Consulta de clientes por CPF, verificacao de recorrencia/adiantamento/app | Webhook N8N ou conexao PostgreSQL direta |

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Sub-apps | 6 (clube, parceiros, indicacoes, carteirinha, nps, retencao) |
| Models | 24 (10 clube + 4 parceiros + 2 indicacoes + 3 carteirinha + 2 NPS + 3 retencao) |
| Views | 55+ funcoes |
| Templates | 30+ |
| APIs | 40+ endpoints |
| Services | 6 (Gamification, OTP, Sorteio, Hubsoft, Cupom, Indicacao, Carteirinha) |
| Management commands | 2 (gerar_faq, testar_pontuacoes) |

---

## Stack

TenantMixin (multi-tenancy), Django 5.2, PostgreSQL, N8N (OTP/WhatsApp), HubSoft API.
