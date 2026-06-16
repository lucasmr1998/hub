# Sync de vendedor Matrix Brasil → Hubtrix (Nuvyon)

**Implementado em:** 16/06/2026
**Owner:** Tech Lead
**Status:** ✅ Em producao (cron `* * * * *`)

---

## Problema que resolve

Lead chega via anuncio Meta Ads → cai no bot Matrix Brasil da Nuvyon (`artelecomprovedor.matrixdobrasil.ai`) → flow coleta dados → cria lead+oportunidade no Hubtrix via `registrar_lead_api`. Mas o **vendedor que vai atender** so eh definido **depois**, dentro do proprio Matrix (distribuicao automatica deles).

Sem essa sync, oportunidade ficava com `responsavel = NULL` no Hubtrix indefinidamente — vendedor humano operava no Matrix, mas o Hubtrix nao sabia disso. Quebrava metrica de pipeline por vendedor, alertas de SLA, vinculo de venda → comissao.

## Solucao

Hubtrix **puxa** do Matrix periodicamente. Quando um lead Nuvyon nao tem responsavel e ja tem atendimento atribuido no Matrix, sync resolve qual usuario Hubtrix corresponde ao `login_agente` do Matrix e atribui `OportunidadeVenda.responsavel`.

## Arquitetura

```
Lead chega (anuncio Meta) → Matrix Brasil
    ↓
Matrix → POST /api/public/n8n/lead/                  (cria LeadProspecto + OportunidadeVenda)
Matrix → POST /api/public/n8n/historico/             (cada resposta do bot;
                                                       hub salva codigo_atendimento em
                                                       OportunidadeVenda.dados_custom.id_atendimento_matrix)
    ↓
Matrix distribui automaticamente atendimento pra agente humano (ex: Filial CB → Victoria)
    ↓
[CRON a cada 1min] sync_vendedores_matrix --tenant=nuvyon
    ↓
Pra cada oport Nuvyon com responsavel=NULL e id_atendimento_matrix:
    GET /rest/v1/atendimento?codigo_atendimento=<id>  →  login_agente='filialcb'
    PerfilUsuario.objects.filter(tenant=nuvyon, login_matrix='filialcb').user
    → OportunidadeVenda.responsavel = victoria.schiavelli
```

## Componentes

| Componente | Caminho |
|---|---|
| Cliente HTTP Matrix v1 | `apps/integracoes/services/matrix_brasil.py` |
| Persistencia do `id_atendimento_matrix` | `apps/comercial/leads/views.py:registrar_historico_api` (salva no `OportunidadeVenda.dados_custom`) |
| Campo `login_matrix` no usuario | `apps/sistema/models.py:PerfilUsuario` (migration `sistema/0012`) |
| Management command | `apps/comercial/crm/management/commands/sync_vendedores_matrix.py` |
| UI editar `login_matrix` | `/configuracoes/usuarios/` (modal Editar Usuario, campo "Login Matrix Brasil") |
| CronJob ativo | `sync_vendedores_matrix_nuvyon` em `cron_jobs` (schedule `* * * * *`, timeout 300s) |

## Filtro restrito — quem entra na sync

Sync **so atribui** oportunidades que satisfazem:
- `tenant = nuvyon`
- `responsavel IS NULL`
- `data_criacao` nos ultimos 7 dias (configurable via `--dias`)
- `dados_custom['id_atendimento_matrix']` presente (origem Matrix)

**Outros leads** (criados manual no CRM, importados, vindos de outras integracoes) **nao sao tocados** — seguem padrao normal do CRM (atribuicao manual ou FilaInbox).

## Mapeamento Hubtrix × Matrix

Cada `PerfilUsuario` da Nuvyon tem `login_matrix` (CharField) com o login do agente no Matrix. Match e por **string exata** (case insensitive na resolucao).

| Vendedor Hubtrix | login_matrix | Agente no Matrix |
|---|---|---|
| `ana.moraes` (Ana Paula Moraes) | `AnaP` | 1- Ana Paula |
| `caio.resende` (Caio Sávio) | `Caio` | Filial Arceburgo |
| `damaris.silva` (Damaris) | `damaris` | Filial Tapiratiba |
| `flavia.almeida` (Flávia) | `flavia` | 1 - Flavia |
| `gustavo.beraldo` (Gustavo) | `passos` | Filial Passos |
| `joyce.soares` (Joyce) | `joyce` | 1 - Joyce |
| `lavinia.martins` (Lavínia) | `filialrp` | Filial Rio Pardo |
| `sofia.salvato` (Sofia) | `sofia` | Filial Mogi Mirim Sofia |
| `thais.moreira` (Thaís) | `thais` | Filial Monte Santo |
| `victoria.schiavelli` (Victoria) | `filialcb` | Filial CB |
| `vilhena.magalhaes` (Vilhena) | `vilhena` | Filial Meganet Vilhena |
| `danielle.akemy` (admin) | — | Nao atende leads diretamente |

**Pendentes** (aguardando email institucional pra criar User Hubtrix):
| Pessoa | login_matrix Matrix |
|---|---|
| Letícia Donizetti | `caconde` |
| Nicole Barbosa | `nicole` |
| Nicoly Araújo | `nicolyaraujo` |

## Credenciais Matrix Brasil

| Campo | Valor |
|---|---|
| `IntegracaoAPI.id` | `20` (tenant 12) |
| `tipo` | `n8n` |
| `nome` | `Matrix Nuvyon` |
| `base_url` | `https://artelecomprovedor.matrixdobrasil.ai` |
| `access_token` | armazenado encriptado (Fernet); v1 raw bearer; renovar com pessoal do Matrix se voltar a dar 401 |

## Cron

```
nome: sync_vendedores_matrix_nuvyon
command: sync_vendedores_matrix
args: --tenant=nuvyon
schedule: * * * * *   (a cada 1min — menor granularidade do dispatcher Hubtrix)
timeout: 300s
ativo: True
```

Gerenciar em `/aurora-admin/cron/` ou `/admin/cron/cronjob/`.

## Endpoints Matrix Brasil usados

| Endpoint | Pra que |
|---|---|
| `GET /rest/v1/atendimento?codigo_atendimento=<id>` | Pega `login_agente`, `id_agente`, `agente` |
| `GET /rest/v1/getDadosUltimoAtendimento?telefone=<...>` | Fallback pra descobrir `codigo_atendimento` quando nao temos em `dados_custom` |
| `GET /rest/v1/agentes` | Listar todos agentes (debug + mapeamento manual) |
| `GET /rest/v1/agente/{login}` | Verificar agente especifico (cod_agente, status, contas) |

Doc completa: [`docs/PRODUTO/integracoes/apis/matrix/`](../../../PRODUTO/integracoes/apis/matrix/).

## Validacao em prod (16/06)

- Op 761 (lead Kamily, telefone 5541920056365): `responsavel=NULL` → sync atribuiu `victoria.schiavelli` ✓
- Op 759 (lead Jose Carlos, 5519981785279): ja tinha `responsavel=flavia.almeida` manualmente. Matrix tambem mostrava `flavia` → sync respeitou (filtro `responsavel IS NULL` pulou) ✓

## O que fica em aberto

- **Backfill historico**: leads existentes (anteriores ao deploy) com `dados_custom={}` precisam ter `id_atendimento_matrix` populado retroativamente. Pra cada um, basta chamar `GET getDadosUltimoAtendimento` por telefone e gravar. Posso fazer script de backfill quando necessario.
- **3 logins sem User Hubtrix** (Letícia, Nicole, Nicoly) — quando emails institucionais sairem, criar User + popular `login_matrix`.
- **Agentes filiais "passos"/"filialrp"/"caconde"/"filialcb"**: hoje cada um eh uma pessoa individual (Gustavo, Lavínia, Letícia, Victoria). Se mais de uma pessoa passar a operar a mesma filial, o `login_matrix` fica ambiguo — vai precisar mapeamento por `id_agente` (numerico) em vez de `login_agente`.

## Tooling pra retoma futura

Listar agentes Matrix com seus codigos:
```bash
# Via service no Hubtrix
python manage.py shell
>>> from apps.integracoes.services.matrix_brasil import MatrixBrasilService
>>> from apps.sistema.models import Tenant
>>> svc = MatrixBrasilService.from_tenant(Tenant.objects.get(slug='nuvyon'))
>>> for a in svc.listar_agentes(): print(a['nom_agente'], a['nom_email_agente'])
```

Rodar sync manualmente (dry-run pra debug):
```bash
python manage.py sync_vendedores_matrix --tenant=nuvyon --dry-run --limit=20
```

Forcar atribuicao de uma oport especifica (debug):
```python
from apps.comercial.crm.models import OportunidadeVenda
op = OportunidadeVenda.objects.get(pk=761)
op.dados_custom = {**op.dados_custom, 'id_atendimento_matrix': '1013040'}
op.responsavel = None
op.save()
# Roda o command e ve o resultado
```
