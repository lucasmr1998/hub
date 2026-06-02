# Robo de Conversao de Prospect → Cliente (HubSoft)

Automatiza, via Selenium, a etapa de **converter prospect em cliente** no painel UI do HubSoft — passo que **a API HubSoft nao expoe**.

Multi-tenant: a config (URL, login, senha) e carregada em runtime do DB Hubtrix
a partir de `IntegracaoAPI` do tenant passado via `--tenant`. Senha decryptada
localmente via Fernet+SECRET_KEY.

## Fluxo

```
Lead criado no Hubtrix (via Matrix / cadastro)
            ↓
Hubtrix → HubSoft API: cadastrar_prospecto       ← ja existe
            ↓
Prospect no HubSoft (id_prospecto retornado, salvo em leads_prospectos.id_hubsoft)
            ↓
ESTE ROBO → HubSoft UI: converter prospect em cliente   ← gap que este script preenche
            ↓
prospectos.status='finalizado' no Hubtrix
```

## Setup (uma vez)

```bash
cd web_driver_conversao_lead
python3 -m venv myenv && source myenv/bin/activate
pip install -r requirements.txt

# Copie e preencha com valores reais (gitignored):
cp .env.example .env.hubtrix
vim .env.hubtrix
```

## Como rodar

```bash
python main_refatorado.py \
  --tenant nuvyon \
  --nome "LUCAS DE MELLO RODRIGUES" \
  --id-prospecto 22651 \
  --boleto "Boleto Digital" \
  --grupo "Varejo" \
  --banco "BANCO ITAU" \
  --no-headless           # opcional, abre o navegador visivelmente pra debug
```

Bot resolve em runtime:
- URL UI HubSoft (derivada de `IntegracaoAPI.base_url`)
- Email + senha do "usuario robo" do tenant (decryptados)
- Defaults de vendedor/origem (`vendedor_id_padrao`, `id_origem_padrao`)
- `tenant_id` + `lead_id` no INSERT da tabela `prospectos`

## Onde o estado e gravado

Tabela `prospectos` no DB Hubtrix:

| Coluna | Uso |
|---|---|
| `tenant_id` | tenant que disparou a conversao |
| `lead_id` | FK pra `leads_prospectos` (resolvido por `id_hubsoft`) |
| `id_prospecto_hubsoft` | id do prospect no HubSoft |
| `status` | `processando` / `finalizado` / `erro` |
| `tentativas_processamento` | max 3 antes de marcar erro final |
| `erro_processamento` | mensagem da ultima falha |
| `data_inicio_processamento` / `data_fim_processamento` | janela da execucao |

## Monitoramento

```sql
-- Conversoes por tenant nas ultimas 24h
SELECT t.slug, p.status, COUNT(*)
FROM prospectos p JOIN sistema_tenant t ON t.id=p.tenant_id
WHERE p.data_atualizacao > NOW() - INTERVAL '24 hours'
GROUP BY t.slug, p.status ORDER BY t.slug;

-- Falhas recentes
SELECT id, nome_prospecto, id_prospecto_hubsoft, status, erro_processamento, data_atualizacao
FROM prospectos WHERE status='erro' ORDER BY data_atualizacao DESC LIMIT 10;
```

## Adicionar suporte a outro tenant

Pre-requisito (no Hubtrix admin):

1. Tenant cadastrado e ativo.
2. `IntegracaoAPI` tipo=`hubsoft`, ativa, com `base_url` da API HubSoft do cliente.
3. `username` + `password` da `IntegracaoAPI` preenchidos com email + senha do
   "usuario robo" criado no painel HubSoft do cliente (com permissao de
   converter prospect em cliente).
4. `configuracoes_extras.vendedor_id_padrao` e `id_origem_padrao` setados.

Depois e so rodar `python main_refatorado.py --tenant <slug> ...`. Nao precisa
mudar codigo.

## Resolucao de problemas

### `Falha ao decryptar credencial: SECRET_KEY do .env.hubtrix difere da que salvou no DB`

A `SECRET_KEY` no `.env.hubtrix` precisa ser EXATAMENTE a mesma do Django prod
que encriptou o password. Confirme com:

```bash
docker exec <container_hubtrix> python -c "from django.conf import settings; print(settings.SECRET_KEY)"
```

### `IntegracaoAPI hubsoft ativa nao encontrada para tenant=<slug>`

```sql
SELECT t.slug, i.id, i.ativa, i.tipo
FROM integracoes_api i JOIN sistema_tenant t ON t.id=i.tenant_id
WHERE t.slug='<slug>';
```

Garanta `tipo='hubsoft'` e `ativa=TRUE`.

### Chrome em uso

```bash
pkill -f chrome
```
