# Prospecto rascunho HubSoft (criar cedo + atualizar depois)

> Status: implementado em 17/06/2026. **Inativo por padrao** — ativacao pela Gabi (Nuvyon) via management command.

## Problema

Hoje o prospecto HubSoft so eh criado quando o lead atinge `status_api='pendente'` (todos os dados reais coletados: CPF, score, docs, endereco). Resultado: leads que entram mas nao completam o atendimento dentro do mes **nao aparecem nos relatorios da Nuvyon no HubSoft**. A Gabi precisa fechar o mes (30/06) com o funil completo de prospectos abertos, nao so os que viraram cliente.

## Solucao

**Criar prospecto cedo** (assim que o lead entra no Hubtrix com nome + telefone) com **placeholders** nos campos vazios. Depois, quando o lead atinge `status_api='pendente'`, **atualizar** o prospecto existente via `PUT /prospecto/{id}` com os dados reais.

Implementacao 100% via motor de **automacoes** do Hubtrix — **configuravel por tenant**, sem hardcode. Outro cliente HubSoft que entrar (TR Carrion etc.) ativa as 2 regras dele em 2 minutos.

## Fluxo

```
Lead entra (Matrix webhook / Inbox WhatsApp / CRM manual / Widget)
        |
        v
[Signal post_save] dispara evento 'lead_criado'
        |
        v
[Regra 1 da Nuvyon]
   tipo: linear
   gatilho: lead_criado
   acao: sincronizar_prospecto_hubsoft
        |
        v
   - Se lead.id_hubsoft VAZIO:
       POST /api/v1/integracao/prospecto
       payload com nome+telefone reais + placeholders (cep=00000000,
       endereco="A confirmar", bairro="A confirmar", numero="S/N",
       observacao="RASCUNHO - dados pendentes via Hubtrix")
       -> grava id_hubsoft no Lead
       -> status_api = 'rascunho_hubsoft'

... atendimento prossegue normalmente ...

Lead atinge status_api='pendente' (todos dados reais)
        |
        v
[Signal post_save] dispara evento 'lead_status_pendente'  <-- NOVO
        |
        v
[Regra 2 da Nuvyon]
   tipo: linear
   gatilho: lead_status_pendente
   acao: sincronizar_prospecto_hubsoft
        |
        v
   - Se lead.id_hubsoft PREENCHIDO:
       PUT /api/v1/integracao/prospecto/{id_hubsoft}
       payload com dados reais (cpf, email, endereco real, etc.)
       -> status_api = 'processado'
```

## Idempotencia & coexistencia com fluxo antigo

- **Cron `processar_pendentes`** (legado, Matrix bot) continua ativo. Ele pula leads que ja tem `id_hubsoft` preenchido. Logo nao duplica.
- **Cron `criar_prospectos_crm`** (legado, leads humanos travados) continua ativo. Idem.
- **Cooldown 1h + max_execucoes 1/lead** na Regra 1 evita reprocessar lead que tenha multiplos `post_save` (ex: edicoes seguidas).
- **`id_externo = lead.pk`** em ambos payloads garante rastreabilidade cross-system.

## Reversibilidade

Pra **rollback total** sem deploy:

```bash
python manage.py seed_regra_prospecto_hubsoft --tenant nuvyon --desativar
```

Resultado: as 2 regras ficam com `ativa=False`. Fluxo antigo continua. Zero impacto. Pra reativar:

```bash
python manage.py seed_regra_prospecto_hubsoft --tenant nuvyon
```

## Endpoints HubSoft usados

| Endpoint | Metodo | Quando | Formato endereco |
|---|---|---|---|
| `/api/v1/integracao/prospecto` | POST | Cria rascunho | flat (`cep`, `endereco`, `bairro`, `numero`) |
| `/api/v1/integracao/prospecto/{id}` | PUT | Atualiza | aninhado (`prospecto_endereco.cep`, etc.) |

Atencao: a API HubSoft usa formatos **diferentes** pro create e pro edit. O Hubtrix tem 2 mappers separados em `HubsoftService`.

## Validacao pos-deploy (checklist Gabi)

1. [ ] Logar no Hubtrix Nuvyon como admin
2. [ ] `python manage.py seed_regra_prospecto_hubsoft --tenant nuvyon` (cria + ativa as 2 regras)
3. [ ] Conferir as 2 regras em **Automacoes**:
   - HubSoft - Criar rascunho ao receber lead (gatilho `lead_criado`)
   - HubSoft - Atualizar prospecto quando pendente (gatilho `lead_status_pendente`)
4. [ ] Criar 1 lead de teste via CRM (nome real, telefone real, demais campos vazios)
5. [ ] Em <1min: conferir no painel HubSoft que prospecto foi criado com observacao "RASCUNHO"
6. [ ] No Hubtrix: completar dados do lead (CPF, endereco real, etc.) ate `status_api='pendente'`
7. [ ] Em <1min: conferir no painel HubSoft que prospecto foi **atualizado** (mesmo id, dados reais)
8. [ ] No relatorio Hubtrix: lead deve aparecer em **Comercial - Funil completo**

## Logs & auditoria

Toda execucao das acoes vai pra `LogExecucao` do motor de automacao (tabela `automacoes_logexecucao`). UI em `/automacoes/` -> Logs.

Erros (timeout HubSoft, validacao rejeitada, etc.) sao logados em **status=erro** sem travar o lead — proxima tentativa via cooldown.

## Pontos abertos pra v2

- UI form da acao com toggle "executar imediatamente (sincrono)" vs "executar via cron (default)" — hoje async via cron, suficiente pra Gabi.
- Configurar fakes via UI (ex: trocar email default `noreply@nuvyon.com.br`) — hoje hardcoded.
- Dashboard especifico de "leads sincronizados com HubSoft" — pode virar widget no dashboard **Comercial** quando os dados estabilizarem.

## Arquivos tocados

| Arquivo | Tipo |
|---|---|
| `apps/integracoes/services/hubsoft.py` | adicao (`editar_prospecto`, `_mapear_lead_para_hubsoft_editar`, `ENDPOINT_PROSPECTO_EDITAR_TPL`) |
| `apps/integracoes/services/hubsoft_prospecto_rascunho.py` | arquivo novo (helper `sincronizar_prospecto_hubsoft`) |
| `apps/marketing/automacoes/engine.py` | adicao (`_acao_sincronizar_prospecto_hubsoft` + entrada no `_get_executor`) |
| `apps/marketing/automacoes/models.py` | adicao (1 choice em `TIPO_CHOICES`, 1 choice em `EVENTO_CHOICES`) |
| `apps/marketing/automacoes/signals.py` | adicao (`on_lead_status_pendente`) |
| `apps/marketing/automacoes/management/commands/seed_regra_prospecto_hubsoft.py` | arquivo novo |
| Migrations | `automacoes/0005`, `automacoes/0006` |

Nenhum arquivo do fluxo antigo (`hubsoft_prospecto.py::criar_prospecto_para_lead`, crons `processar_pendentes` / `criar_prospectos_crm`, `validar_lead_pronto_para_prospect`) foi tocado.
