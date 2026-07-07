# Prospecto rascunho HubSoft (criar cedo + atualizar depois)

> Status: implementado em 17/06/2026, refatorado em 18/06/2026 pra motor de automação do CRM. **Inativo por padrão** — ativação pela Gabi (Nuvyon) pela UI de Automações do Pipeline.
>
> **Atualização 18/06 (limpa):** removida flag `OportunidadeVenda.is_rascunho` (inventada por engano). Webhook Matrix já cria oportunidade direto — não precisa de flag intermediária. Regras agora usam só `lead.id_hubsoft` (existe/não existe) como gatilho.
>
> **Atualização 29/06/2026:** o motor genérico de marketing (`apps/marketing/automacoes/`) foi **completamente aposentado** (código deletado, 8 tabelas `automacoes_*` dropadas em prod). Os vestígios citados na seção "Motor genérico (marketing/automacoes)" abaixo não existem mais. Esta implementação roda no **motor CRM** (`RegraPipelineEstagio`), que segue ativo e não foi afetado.

## Problema

Hoje o prospecto HubSoft só é criado quando o lead atinge `status_api='pendente'` (todos os dados reais coletados: CPF, score, docs, endereço). Resultado: leads que entram mas não completam o atendimento dentro do mês **não aparecem nos relatórios da Nuvyon no HubSoft**. A Gabi precisa fechar o mês (30/06) com o funil completo de prospectos abertos, não só os que viraram cliente.

## Solução

**Criar prospecto cedo** (assim que o lead entra no Hubtrix com nome + telefone) com **placeholders** nos campos vazios. Depois, quando o lead atinge `status_api='pendente'`, **atualizar** o prospecto existente via `PUT /prospecto/{id}` com os dados reais.

Implementação **dentro do motor de automação do Pipeline (CRM)** — Gabi vê e ajusta as regras no mesmo lugar onde já tem outras regras comerciais (`🎯 13. Automações do Pipeline`).

## Pré-requisito chave: webhook Matrix cria oportunidade direto

Na Nuvyon, leads chegam via webhook N8N do Matrix ([`views_n8n_webhook.py:299`](robo/dashboard_comercial/gerenciador_vendas/apps/integracoes/views_n8n_webhook.py#L299)). Esse webhook **já cria a OportunidadeVenda** no momento da chegada, com estágio definido pelo Matrix (pipeline "Atendimento Bot (Nuvyon)").

Significa: lead recém-chegado **já tem oportunidade** → motor CRM (`RegraPipelineEstagio`) consegue avaliar regras desde o primeiro `post_save`.

Não precisa de flag/scaffolding intermediário. Idempotência é via `lead.id_hubsoft`.

## Fluxo

```
Lead entra (Matrix webhook / Inbox WhatsApp / CRM manual / Widget)
        |
        v
[Signal post_save Lead] cria OportunidadeVenda com:
   - is_rascunho = True (se nao qualificou)
   - is_rascunho = False (se qualificou no momento da criacao)
        |
        v
[Signal post_save OportunidadeVenda] dispara processar_oportunidade
        |
        v
[Motor CRM avalia REGRAS DE AÇÃO PURA (estagio=NULL)]
        |
        +-- Regra 1: "HubSoft - Criar rascunho ao receber lead (CRM)"
        |   Condições:
        |     - lead_campo: id_hubsoft nao_existe
        |   Ação: sincronizar_prospecto_hubsoft
        |     -> POST /api/v1/integracao/prospecto
        |     -> payload com nome+telefone reais + placeholders
        |        (cep=00000000, endereco/bairro="A confirmar", numero="S/N")
        |     -> grava Lead.id_hubsoft, Lead.status_api='rascunho_hubsoft'
        |
        +-- Regra 2: "HubSoft - Atualizar prospecto quando pendente (CRM)"
            Condições:
              - lead_status_api == "pendente"
              - lead_campo: id_hubsoft existe
            Ação: sincronizar_prospecto_hubsoft
              -> PUT /api/v1/integracao/prospecto/{id}
              -> payload com dados reais (formato aninhado prospecto_endereco.*)
              -> Lead.status_api='processado'

   ... atendimento prossegue normalmente ...
   ... bot/humano coleta CPF, endereco, email, dia de vencimento, etc ...
   ... quando lead bate score minimo ou status='sucesso' ...
        |
        v
[Signal qualificar_oportunidade_rascunho]
   Oportunidade.is_rascunho: True -> False
   Distribui pra vendedor via round robin
```

## Coexistência com fluxo antigo (intocado)

- **Cron `processar_pendentes`** (legado, Matrix bot → pendente → create): continua ativo. Pula leads que já têm `id_hubsoft`.
- **Cron `criar_prospectos_crm`** (legado, leads humanos travados): idem.
- **`hubsoft_prospecto.criar_prospecto_para_lead`** (helper antigo do create): não modificado.
- **`validar_lead_pronto_para_prospect`** (pre-flight do create): não modificado.

O novo helper `hubsoft_prospecto_rascunho.sincronizar_prospecto_hubsoft` opera em paralelo. Por causa da idempotência via `lead.id_hubsoft`, não há duplicação.

## Reversibilidade

**Rollback total sem deploy** — desativar as 2 regras via UI:

1. Acessar `🎯 13. Automações do Pipeline` no admin Django
2. Procurar as 2 regras "HubSoft - ... (CRM)"
3. Desmarcar `ativo` em cada uma
4. Salvar

Comportamento volta a ser 100% o de antes.

## Endpoints HubSoft usados

| Endpoint | Método | Quando | Formato endereço |
|---|---|---|---|
| `/api/v1/integracao/prospecto` | POST | Cria rascunho | flat (`cep`, `endereco`, `bairro`, `numero`) |
| `/api/v1/integracao/prospecto/{id}` | PUT | Atualiza | aninhado (`prospecto_endereco.cep`, etc.) |

Atenção: a API HubSoft usa formatos **diferentes** pro create e pro edit. O Hubtrix tem 2 mappers separados em `HubsoftService`: `_mapear_lead_para_hubsoft` (create) e `_mapear_lead_para_hubsoft_editar` (update).

## Estado pós-deploy

Em prod Nuvyon (tenant id=12):

| ID | Tabela | Nome | Ativo | Estágio | Condições | Ações |
|---|---|---|---|---|---|---|
| 23 | `crm_regras_pipeline_estagio` | HubSoft - Criar rascunho ao receber lead (CRM) | **False** | NULL | 2 | 1 |
| 24 | `crm_regras_pipeline_estagio` | HubSoft - Atualizar prospecto quando pendente (CRM) | **False** | NULL | 2 | 1 |

Ambas com `estagio=NULL` (regras de ação pura — não movem oportunidade entre estágios).

## Validação pós-deploy (checklist Gabi)

1. [ ] Logar no Hubtrix Nuvyon como admin
2. [ ] Acessar `🎯 13. Automações do Pipeline`
3. [ ] Encontrar as 2 regras "HubSoft - ... (CRM)" com `ativo=False`
4. [ ] **Ativar primeiro só a Regra 23** (criar rascunho)
5. [ ] Criar 1 lead de teste via CRM com só **nome + telefone**
6. [ ] Em <1min: conferir no painel HubSoft que prospecto foi criado com observação "RASCUNHO"
7. [ ] Verificar no Hubtrix: `Lead.id_hubsoft` preenchido, `Lead.status_api='rascunho_hubsoft'`
8. [ ] **Ativar a Regra 24** (atualizar pendente)
9. [ ] No Hubtrix: completar dados do lead (CPF, endereço real, etc.) até `status_api='pendente'`
10. [ ] Em <1min: conferir no painel HubSoft que prospecto foi **atualizado** (mesmo ID)

## Logs & auditoria

Toda execução das ações vai pra `LogExecucao` do motor de automação (motor CRM tem contadores em `RegraPipelineEstagio.total_disparos` e `total_acoes_efetivas`).

Erros (timeout HubSoft, validação rejeitada, etc.) são logados em `motivo_rejeicao` do Lead sem travar o atendimento — próxima tentativa via cooldown.

## Arquivos tocados

### Motor CRM (foco atual)
| Arquivo | Tipo |
|---|---|
| `apps/comercial/crm/services/automacao_pipeline.py` | adição (`_acao_sincronizar_prospecto_hubsoft` + entrada em `_EXECUTORES_ACAO`) |

Arquivos tocados em 18/06 e revertidos no mesmo dia (campo `is_rascunho` era desnecessário):
- `models.py` (campo `is_rascunho` adicionado e removido via migrations 0024 → 0025)
- `signals.py` (`criar_oportunidade_automatica` refatorada e revertida; `qualificar_oportunidade_rascunho` criada e removida)
- `views.py` (filtros `is_rascunho=False` adicionados e revertidos no kanban + lista)
- `automacao_condicoes.py` (`CondicaoOportunidadeIsRascunho` adicionada e removida)

### Integrações HubSoft (já em prod desde 17/06)
| Arquivo | Tipo |
|---|---|
| `apps/integracoes/services/hubsoft.py` | adição (`editar_prospecto`, `_mapear_lead_para_hubsoft_editar`, `ENDPOINT_PROSPECTO_EDITAR_TPL`) |
| `apps/integracoes/services/hubsoft_prospecto_rascunho.py` | arquivo novo (helper `sincronizar_prospecto_hubsoft`) |

### Motor genérico (marketing/automacoes)
Adicionado em 17/06 e **REMOVIDO** em 18/06 com o refactor pro CRM:
- Choice `sincronizar_prospecto_hubsoft` no `AcaoRegra.TIPO_CHOICES` permanece (não atrapalha, pode usar futuramente)
- Choice `lead_status_pendente` no `EVENTO_CHOICES` permanece (signal `on_lead_status_pendente` ainda dispara, sem regra ativa)
- As 2 regras `RegraAutomacao` foram deletadas em prod

## Pontos abertos pra v2

- UI form da ação com toggle "executar imediatamente (síncrono)" vs "executar via cron (default)" — hoje sempre síncrono no motor CRM.
- Permitir configurar fakes via UI (ex: trocar email default `noreply@nuvyon.com.br`) — hoje hardcoded em `hubsoft_prospecto_rascunho.py`.
- Dashboard específico de "leads sincronizados com HubSoft" — pode virar widget no dashboard **Comercial** quando os dados estabilizarem.

## Retry em 2 fases pra rejeicao plano x cidade (07/07/2026)

O HubSoft valida o plano do payload contra a cidade ATUAL do prospecto. Como o rascunho nasce com CEP default (Mococa), qualquer PUT que traga endereco real + plano juntos entra em ciclo vicioso: o plano novo e rejeitado contra a cidade velha, e o endereco novo nunca entra. Impacto medido antes do fix: 82 rejeicoes, 13 leads em 12 dias, toda ocorrencia virava correcao manual do time.

Comportamento apos o fix (`hubsoft.py`):

- `_eh_erro_plano_cidade(msg)`: detecta a substring "permitido ser vendido na cidade" na resposta de erro.
- **PUT** (`editar_prospecto` -> `_editar_em_duas_fases`): fase 1 reenvia o payload sem `prospecto_servico` (endereco e cidade entram); fase 2 reenvia so `prospecto_servico` + `id_externo` (agora validado contra a cidade nova). Retorno ganha marcador `retry_plano_cidade: true`.
- **POST** (`cadastrar_prospecto` -> `_cadastrar_sem_servico`): recria o prospecto sem a chave `servico` (rascunho nasce); o plano entra no proximo update via Regra 24, que ja passa pelo retry do PUT.
- Retry e 1x, sem recursao. Se a fase 2 falhar com o mesmo erro, o plano e genuinamente invalido pra cidade real do lead: `HubsoftServiceError` sobe com contexto e um humano decide.
- Se o HubSoft mudar o texto do erro, o retry deixa de ativar e o comportamento degrada pro anterior (erro direto), nunca piora.
