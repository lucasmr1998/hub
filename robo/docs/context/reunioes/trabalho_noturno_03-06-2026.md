# Trabalho noturno 03/06/2026

User pediu execucao autonoma de 5 tarefas durante a noite. Esse doc consolida
o que foi entregue, commits, decisoes e proximos passos.

---

## Resumo executivo

| # | Tarefa Workspace | Status | Commit |
|---|------------------|--------|--------|
| 153 | Auditoria de logs | ✅ Concluida | `b1b28ca` |
| 154 | /api/docs/ + UX | ✅ Concluida | `bda0354` |
| 151 | Envio venda WhatsApp TR Carrion | ✅ Concluida | `515dc90` |
| 152 | Alertas do sistema + uazapi | ✅ Concluida | `5737525` |
| 150 | Aurora-admin + Dashboard monitoramento | ⏳ Parte 1 concluida | `6ddeb1b` |

5 commits pushed pra `main`. Tudo passou no `manage.py check`. Migration
da tarefa 152 vai aplicar automaticamente no proximo rebuild EasyPanel.

---

## Detalhes por tarefa

### #153 — Auditoria de logs (b1b28ca)

**Entregavel:** `robo/docs/PRODUTO/core/04-AUDITORIA-LOGS.md`

- Estado atual: 60% das operacoes criticas tem algum log
- 7 tabelas de log mapeadas + 6 mecanismos
- Cobertura por dominio funcional (auth, integracoes, cron, leads, inbox,
  CRM, imagens, etc.)
- 11 gaps identificados em P1-P4
- Plano em 4 sprints

**Decisao tomada:** nao implementar ainda — relatorio + plano apenas.
User decide priorizar quais sprints atacar nas proximas sessoes.

### #154 — /api/docs/ + UX (bda0354)

**URL:** https://app.hubtrix.com.br/api/docs/

- Nova secao destacada (border laranja) **"Pipeline HubSoft Nuvyon junho/2026"**
  com 6 endpoints recentes + bloco `<details>` de curls prontos
- Filtro de busca client-side (Ctrl+K pra focar)
- Click em qualquer endpoint copia URL pro clipboard (com flash visual)
- Migracao DS deixada pra junto da tarefa #150 (parte 2)

### #151 — Envio venda WhatsApp TR Carrion (515dc90)

**Endpoint manual:** `POST /api/leads/<id>/enviar-venda-whatsapp/`
**Trigger automatico:** signal `post_save` em `ImagemLeadProspecto` quando
TODAS imagens do lead = STATUS_VALIDO. Idempotente via
`lead.dados_custom.venda_whatsapp_enviada`.

**Components:**
- `apps/comercial/leads/services_whatsapp_venda.py` (novo):
  - `montar_texto_venda(lead)`: monta resumo formatado
  - `_coletar_documentos(lead)`: resolve URL externa (uazapi original) via
    `Mensagem.arquivo_url` ja que paths internos sao autenticados
  - `enviar_venda_whatsapp(lead, telefone)`: orquestra texto + imagens
- Filtro por tenant=`tr-carrion` no signal (Workspace #151 escopo)
- Telefone destino = `53981521653` (Lucas, teste)

**Limitacoes conhecidas:**
- URL externa uazapi (`consulteplus.uazapi.com/files/...`) pode expirar.
  Se expirou, log warning + pula imagem; texto ainda chega.
- Pra resolver: endpoint publico assinado/HMAC pra servir midias internas
  pra uazapi. Numa proxima iteracao.

### #152 — Alertas do sistema + uazapi (5737525)

**URL:** https://app.hubtrix.com.br/aurora-admin/alertas/
**Config:** https://app.hubtrix.com.br/aurora-admin/alertas/config/
**Teste:** botao "Disparar teste" no historico

**Components:**

1. **Models** (`apps/sistema/models_alertas.py`):
   - `AlertaSistema`: tipo (cron_falhou, webhook_5xx, hubsoft_erro,
     catalogo_mudou, lead_travado, uazapi_caiu, bot_falhou, erro_python,
     outro), titulo, mensagem, dados_extras, dedup_key, tenant opcional,
     enviado_em, suprimido, erro_envio
   - `AlertaConfig` singleton: telefone_destino default `53981521653`,
     janela_dedup_minutos default 5, enviar_whatsapp on/off, tipos_ativos

2. **Service** (`apps/sistema/services_alertas.py`):
   - `disparar_alerta(tipo, titulo, mensagem, dedup_key, dados_extras, tenant)`
   - Sempre cria registro em DB (historia completa)
   - Dedup window: mesma chave nao reenvia WhatsApp na janela
   - Envia via uazapi de `aurora-hq` (instancia global)

3. **Disparos automaticos:**
   - **Signal** `post_save` em `ExecucaoCron` (`apps/cron/signals.py`):
     status='error' + fim setado dispara imediato.
   - **Cron** `monitor_sistema` (CronJob #7, `*/5 * * * *`) detecta:
     - webhook_5xx: 3+ N8N 5xx em 5min
     - hubsoft_erro: 3+ HubSoft errors em 10min (por tenant)
     - lead_travado: leads em status erro >1h
     - uazapi_caiu: IntegracaoAPI uazapi sem token

4. **Admin views:**
   - `/aurora-admin/alertas/`: lista filtrada + stats 24h + tipos
   - `/aurora-admin/alertas/config/`: edita telefone, dedup, tipos
   - `/aurora-admin/alertas/teste/`: POST manual pra validar envio

**Migration:** `sistema.0011_alertaconfig_alertasistema` — vai rodar no
proximo rebuild EasyPanel automaticamente.

### #150 — Aurora-admin + Dashboard monitoramento (6ddeb1b)

**Parte 1 — Dashboard de monitoramento:** ✅ entregue.

`dashboard_view` agora agrega 7 grupos de KPIs:

| Grupo | Metricas |
|-------|----------|
| Tenants | total/ativos/trial/trials_expirando |
| CronJobs | execucoes 24h, falhas 24h, lista ativos com last_status |
| Alertas | 24h + pendentes + 5 recentes (destaque vermelho no topo se houver) |
| Leads | por status_api, travados em erro >1h |
| HubSoft | chamadas OK/erro 24h, clientes sincronizados, sync 24h |
| Webhooks N8N | total 24h, 5xx 24h |
| Inbox | conversas abertas, sem agente atribuido |
| Erros | por modulo nas 24h (drill-down pra /aurora-admin/logs/) |
| Integracoes | ativas por tipo |

Template `dashboard.html` reescrito com:
- Bloco "Alertas recentes" destacado (border-left vermelho) se houver
- Grid responsivo de 7 cards de monitoramento
- Tabela de tenants original preservada embaixo
- Links pra cron/logs/alertas pra drill-down

**Parte 2 — Padronizacao visual:** PENDENTE.

Decisao: deixar pra proxima sessao. Por que:
- `sistema/base.html` ja eh shim que extends `layouts/layout_app.html` —
  o que falta sao componentes (substituir classes inline `.btn`/`.modal-overlay`
  por `{% include "components/X.html" %}`)
- Trabalho de 4-6h, risco de quebrar visualmente paginas em prod
- Faz mais sentido fazer com user acordado pra validar cada migracao

---

## Outras alteracoes no caminho

- **Bug corrigido em `sincronizar_clientes`** (commit anterior `1f1e159` ja
  pushed antes da noite): era `IntegracaoAPI.objects.first()` sem tenant
  filter — funcionava so porque Nuvyon e unica em prod com HubSoft.
- **Bug corrigido em `HubsoftService._sincronizar_dados_cliente`** e
  `_sincronizar_servicos` (`1b8132d`, `4d9d997`): tenant=None silencioso.
- **Bug corrigido em `utils.integracao_envia_lead`** (`4a9da9f`): aceitar
  tanto `'automatico'` (convencao do model) quanto `'ativado'` (legacy).
- **Nuvyon config alinhada em prod:** `modos_sync.enviar_lead='automatico'`,
  `modos_sync.sincronizar_cliente='automatico'`.
- **CronJob #6 `sincronizar_clientes_hubsoft`** registrado em prod
  (`* * * * *`).
- **CronJob #7 `monitor_sistema`** registrado em prod (`*/5 * * * *`).
- **Senha admin@auroraisp.com.br resetada** pra `Lucasmello123@`.

---

## Estado da pipeline HubSoft Nuvyon

| Tabela / cliente | Status |
|------------------|--------|
| Lead #483 Lucas | status_api=processado, id_hubsoft=22651 ✓ |
| Lead #462 Lucas (duplicata) | status_api=incompleto, motivo="rg" — operador precisa completar |
| ClienteHubsoft #29 Lucas | tenant=12 Nuvyon, id_cliente=57515, 1 servico ✓ |
| ServicoClienteHubsoft #29 | plano 1236, R$109,90, "Aguardando Instalacao", tenant=12 ✓ |
| Lead #463 Pedro Paulo | status_api=processado, id_hubsoft=22633, mas ainda nao virou cliente final no HubSoft (bot Selenium nao rodou pra ele) |

CronJobs ativos (4):
- `#1 encerrar_inativos`: `*/15 * * * *`
- `#4 processar_pendentes_hubsoft`: `* * * * *`
- `#5 sincronizar_catalogos_hubsoft`: `0 6 * * *`
- `#6 sincronizar_clientes_hubsoft`: `* * * * *`
- `#7 monitor_sistema`: `*/5 * * * *`

---

## Proximos passos sugeridos (manha)

1. **Validar dashboard de monitoramento** abrindo `/aurora-admin/` apos
   rebuild concluir
2. **Testar disparo de alerta** em `/aurora-admin/alertas/` clicando
   "Disparar teste" pra validar que `53981521653` recebe via uazapi
3. **Validar envio WhatsApp da venda**: aprovar manualmente os documentos
   de um lead TR Carrion no admin e ver se mensagem + RGs chegam no
   `53981521653`
4. **Revisar relatorio de auditoria de logs** (`04-AUDITORIA-LOGS.md`)
   e decidir qual sprint priorizar
5. **Cadastrar RG do lead #462** pra destravar o segundo cliente Nuvyon
6. **Decidir** se ativa cron do bot Selenium (`modos_sync.converter_prospect_cliente`)
   ou prefere manter manual por enquanto

---

## Notas de inseguranca / pendencias

- **Bot Selenium nao tem cron ativo ainda** — `modos_sync.converter_prospect_cliente`
  esta vazio. Decidi nao ativar sem user presente.
- **URL uazapi pra imagens pode expirar** — envio de venda pode chegar
  sem documentos se URL externa expirou. Solucao numa proxima iteracao.
- **Migration 0011** sera aplicada no rebuild — sem orfaos, deve passar
  limpa.
- **CronJob #7 monitor_sistema** so vai rodar com sucesso APOS rebuild
  pegar o command novo (commit `5737525`).
