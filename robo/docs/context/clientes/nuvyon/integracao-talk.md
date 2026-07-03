# Integração Talk (matrixdobrasil.ai) — Nuvyon

**Implementado em:** 03/07/2026
**Owner:** Tech Lead
**Status:** ✅ Em produção (cron `* * * * *`)

---

## Problema que resolve

A Nuvyon usa a plataforma **Talk** (softphone/PABX da matrixdobrasil.ai) pra receber ligações de leads. Quando o cliente liga, o Talk automaticamente cria um prospect no HubSoft com nome placeholder `CLIENTE TALK - ADICIONAR ETIQUETA E USUARIO E NOME DO CLIENTE*` + telefone real. Sem essa integração:

- **1.186 prospects** acumulados no HubSoft desde 10/07/2025 (média ~3/dia útil)
- Vendedora precisava ir manualmente no HubSoft, pescar o telefone, abrir op no Hubtrix
- Ninguém rastreava quem atendeu → op sem responsável no CRM → churn de leads

## Solução

Duas camadas rodando no mesmo cron `sync_vendedores_matrix_nuvyon` (`* * * * *`):

1. **Importador Talk** (`importar_prospects_talk`): consulta HubSoft por prospects com nome `CLIENTE TALK`, cria Lead + Oportunidade no CRM com anti-duplicação por `id_hubsoft` e por telefone.
2. **Sync Talk** (fase 2 do `sync_vendedores_matrix`): consulta a rastreabilidade do Talk (chamadas por telefone), identifica o agente que atendeu via `cod_agente`, mapeia pra `PerfilUsuario.cod_talk` e atribui `OportunidadeVenda.responsavel`.

## Arquitetura

```
Cliente liga → Talk (softphone) → HubSoft cria prospect nome placeholder + telefone
                                              ↓
                              [CRON * * * * *]
                                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. importar_prospects_talk_nuvyon                          │
│     ├─ GET HubSoft /prospecto?busca=nome_razaosocial        │
│     │     &termo_busca=CLIENTE TALK                         │
│     ├─ Filtra por data (desde=hoje BRT default)             │
│     └─ Pra cada prospect:                                   │
│         ├─ Existe LeadProspecto com id_hubsoft=id_prospecto?│
│         │   → skip                                          │
│         ├─ Existe LeadProspecto com mesmo telefone?         │
│         │   → vincula id_hubsoft ao lead existente          │
│         └─ Senao → cria Lead novo + Oportunidade            │
│                   (SEM chamar distribuir_oportunidade)      │
├─────────────────────────────────────────────────────────────┤
│  2. sync_vendedores_matrix_nuvyon (fase 2 — Talk)           │
│     ├─ Filtra ops sem responsavel + importado_do_talk=True  │
│     ├─ Pra cada op:                                         │
│     │   ├─ Consulta Talk restRastreabilidade.php            │
│     │   │   pra telefone do lead + data do lead             │
│     │   ├─ Pega chamada mais recente com nom_agente         │
│     │   ├─ Mapa nom_agente -> cod_agente (via lista Talk)   │
│     │   └─ Busca PerfilUsuario.cod_talk == cod_agente       │
│     └─ Atribui OportunidadeVenda.responsavel = user         │
└─────────────────────────────────────────────────────────────┘
```

## Componentes

| Componente | Caminho |
|---|---|
| Service Talk | `apps/integracoes/services/talk.py` |
| Importador de prospects | `apps/integracoes/services/importador_prospects_talk.py` |
| Command importador | `apps/integracoes/management/commands/importar_prospects_talk.py` |
| Command sync (fase 2) | `apps/comercial/crm/management/commands/sync_vendedores_matrix.py` |
| Campo `cod_talk` | `apps/sistema/models.py:PerfilUsuario` (migration `sistema/0014`) |
| Tipo `talk` | `apps/integracoes/models.py:IntegracaoAPI` (migration `integracoes/0018`) |
| CronJob importador | `importar_prospects_talk_nuvyon` (`* * * * *`, timeout 60s) |
| CronJob sync (Matrix + Talk) | `sync_vendedores_matrix_nuvyon` (`* * * * *`, timeout 300s) |

## Endpoints Talk usados

| Endpoint | Uso |
|---|---|
| `GET /ws/rest/restGerenciaAgente.php?modulo=listaagentes&token=X` | Lista agentes cadastrados (cod_agente + nom_agente). Chamado toda execução do sync pra montar mapa nom_agente → cod_agente. |
| `GET /ws/rest/restRastreabilidade.php?query={num_token,dat_inicial,dat_final,num_origem}` | Lista chamadas pra um telefone numa data. Retorna dat_ligacao, cod_cdr, nom_agente, nom_resposta, num_seg_bilhetado. |

⚠️ **API só aceita HTTP** — HTTPS dá timeout (firewall Talk bloqueia 443 externo). Cliente Python usa `http://17603.talk.matrixdobrasil.ai/`.

## Configuração

### IntegracaoAPI Talk (tenant Nuvyon)

- `id`: 25
- `tenant`: nuvyon (12)
- `tipo`: `talk`
- `nome`: `Talk Nuvyon`
- `base_url`: `http://17603.talk.matrixdobrasil.ai`
- `configuracoes_extras.token`: armazenado (raw string, ver `.env.prod_readonly` ou painel `/admin/integracoes/`)
- `ativa`: True

### Mapeamento vendedora → cod_agente Talk

Cada `PerfilUsuario.cod_talk` (Integer, indexado) mapeia direto pro `cod_agente` do Talk. Estado atual (13 vendedoras mapeadas):

| Username Hubtrix | cod_talk | nom_agente Talk |
|---|---|---|
| ana.moraes | 1106 | 1- ANA PAULA |
| joyce.soares | 153 | 1- Joyce |
| flavia.almeida | 1120 | 1- Flavia |
| gabriela_ferreira | 113 | 1- Gabriela |
| maria.furtunato | 128 | Maria eduarda |
| leticia.carvalho | 11 | Filial Caconde |
| lavinia.martins | 222 | Filial Rio Pardo |
| victoria.schiavelli | 224 | Filial Casa branca |
| thais.moreira | 300 | Filial Monte Santo |
| gustavo.beraldo | 400 | Filial Passos |
| sofia.salvato | 501 | Filial Mogi Mirim |
| damaris.silva | 510 | Filial Tapiratiba |
| caio.resende | 1104 | Filial Arceburgo |

**Danielle Akemy** (`2- Danielle`, cod 117) NÃO tem `cod_talk` populado — ela é admin, não atende leads Talk.

### Pendências de mapeamento (Gabi validar)

- `andressa.silva` — não achamos correspondência no Talk
- `nicoly.araujo` — não achamos correspondência
- `ryan_ribeiro`, `vilhena.magalhaes`, `bianca_ribeiro` — aparecem em `7-XXX MEGA` (grupo Meganet, outra empresa). Precisa confirmar se usam algum código Talk pra Nuvyon.

## Antidup / regras de segurança

### No importador (`importar_prospects_talk`)

1. Filtro `--desde` (default: hoje BRT) — só puxa prospects criados a partir dessa data. Evita puxar os 1.186 antigos.
2. Anti-duplicação em cascata:
   - Se já existe `LeadProspecto` com `id_hubsoft == prospect['id_prospecto']` → skip
   - Se já existe `LeadProspecto` com mesmo telefone (endswith últimos 11 dígitos) → vincula `id_hubsoft` (sem criar novo)
   - Senão → cria novo Lead + Op no primeiro estágio ativo do pipeline padrão
3. **NÃO chama** `distribuir_oportunidade()` (round-robin) — deixa `responsavel=NULL`. O sync Talk cuida disso no próximo minuto.

### No sync (fase 2)

1. Filtro pelas ops elegíveis usa 2 passos (Django JSONField+FK+all_tenants não propaga bem em 1 filtro só):
   ```python
   lead_ids = list(LeadProspecto.all_tenants.filter(
       tenant=tenant, dados_custom__importado_do_talk=True
   ).values_list('id', flat=True))
   qs = OportunidadeVenda.all_tenants.filter(
       tenant=tenant, responsavel__isnull=True, lead_id__in=lead_ids, ...
   )
   ```
2. Só considera chamada Talk com `nom_agente` preenchido E `nom_resposta` in ('atendida', ''). Chamadas em fila sem resposta ficam sem responsável.
3. `registrar_acao` grava tenant explícito (senão o fallback busca via `entidade_id`).

## Erros conhecidos

### API Talk HTTP-only

Se testar via HTTPS, timeout. Sempre `http://`.

### `nom_agente` vazio

Cerca de 40% das chamadas têm `nom_agente=""` (fila sem atendente). Ops correspondentes ficam sem responsável. **Comportamento correto** — se ninguém atendeu, sistema não inventa.

### Nome placeholder do prospect

O Talk sempre grava `CLIENTE TALK - ADICIONAR ETIQUETA E USUARIO E NOME DO CLIENTE*` como nome. A vendedora precisa completar via modal "Completar dados" no CRM. TODO futuro: enriquecer com o `nom_agente` da chamada.

## Verificação em prod

Rodar dry-run (não escreve nada):
```bash
python manage.py importar_prospects_talk --tenant=nuvyon --dry-run --desde=2026-07-01
python manage.py sync_vendedores_matrix --tenant=nuvyon --dry-run
```

Consultar chamadas de um telefone específico:
```python
from apps.sistema.models import Tenant
from apps.integracoes.services.talk import TalkService
svc = TalkService.from_tenant(Tenant.objects.get(slug='nuvyon'))
chamadas = svc.listar_chamadas_por_telefone('35991897675', '2026-07-02')
for c in chamadas:
    print(c['dat_ligacao'], c['nom_agente'], c['nom_resposta'])
```

Listar agentes Talk (útil pra popular `cod_talk` de novos vendedores):
```python
for a in svc.listar_agentes():
    if not a.get('dat_termino'):
        print(a['cod_agente'], a['nom_agente'])
```

## Validação em prod (03/07/2026)

- 8 prospects Talk dos dias 01-02/07 importados → 6 leads criados + 2 vinculados por telefone
- Sync atribuiu responsável real em 8 ops (ana.moraes: 4, maria.furtunato: 3, flavia.almeida: 1)
- Cron `sync_vendedores_matrix_nuvyon` rodando `* * * * *`, latência ~5s

## O que fica em aberto

- **3 vendedoras sem `cod_talk`**: Andressa, Nicoly, e as três Mega (Ryan/Vilhena/Bianca) — aguarda Gabi confirmar o cod real.
- **Prospects Talk antigos (1.186 registros)**: continuam no HubSoft. Se a Gabi quiser limpar, precisa pedir DELETE em massa ao suporte HubSoft (API não expõe DELETE de prospect).
- **Nome do lead melhorar**: hoje entra como o placeholder literal. Podemos substituir por `Ligacao Talk 03/07 15:29` ou similar pra ficar mais legível na kanban.

## Como adicionar novo vendedor no futuro

1. Descobrir `cod_agente` na plataforma Talk (ou via `svc.listar_agentes()`)
2. `PerfilUsuario.objects.filter(user__username='novo.user', tenant=nuvyon).update(cod_talk=X)`
3. Próximo cron (1 min) já pega
