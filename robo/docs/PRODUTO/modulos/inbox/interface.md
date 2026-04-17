# Inbox — Interface (Dashboard + Configuracoes)

---

## Dashboard de metricas

**URL:** `/inbox/dashboard/`

| Secao | Dados |
|-------|-------|
| **KPIs** (5 cards) | Abertas, Pendentes, Resolvidas hoje, Tempo medio 1a resposta, Total conversas |
| **Grafico** | Linha: volume nos ultimos 30 dias (Chart.js) |
| **Por Canal** | Tabela com volume por canal |
| **Por Equipe** | Volume por equipe com badges coloridos |
| **Ranking Agentes** | Top 15 agentes: resolvidas (30d) + tempo medio |

---

## Pagina de configuracoes

**URL:** `/inbox/configuracoes/`

9 abas:

| Aba | O que configura |
|-----|-----------------|
| **Equipes** | CRUD equipes + adicionar/remover membros (cargo: agente/supervisor/gerente) |
| **Filas** | CRUD filas (round-robin/menor carga/manual) + regras de roteamento (por canal/etiqueta/horario) |
| **Respostas Rapidas** | CRUD templates com atalhos (ex: `/ola`) |
| **Etiquetas** | CRUD labels com cores |
| **Canais** | Configurar webhook de envio por canal |
| **Horario** | Dias/horas de atendimento (segunda a domingo) |
| **FAQ** | CRUD categorias + artigos (titulo + conteudo) |
| **Widget** | Config visual + campos + dominios + codigo embed (ver [widget-chat.md](widget-chat.md)) |
| **Geral** | Distribuicao padrao, auto-atribuir ao responder, mensagem fora do horario |

---

## Navegacao (sidebar)

```
ATENDIMENTO
  💬 Inbox              ← /inbox/ (three-panel, full-bleed)
  📊 Dashboard Inbox    ← /inbox/dashboard/

SUPORTE
  📊 Dashboard          ← /suporte/
  📋 Tickets            ← /suporte/tickets/
  ➕ Novo Ticket        ← /suporte/tickets/criar/

CONFIGURACOES
  ⚙️ Configuracoes      ← /inbox/configuracoes/
```

---

## Management commands

### Seed de dados de teste

```bash
python manage.py seed_inbox --tenant=aurora-hq --settings=gerenciador_vendas.settings_local
```

Cria: 2 canais, 5 etiquetas, 5 respostas rapidas, 7 conversas com 29 mensagens.
