# Inbox - Sugestoes IA de campos do Lead

**Status:** v1 em validacao (manual, opt-in)
**App:** `apps/inbox/`
**Workflow N8N:** `[Hubtrix] Extrair Campos do Texto`
**Disponivel desde:** 01/06/2026

Permite que o vendedor clique num botao **dentro do balao de uma mensagem do contato** e a IA extrai dados estruturados do texto (nome, CPF, data de nascimento, e-mail, etc.). O card de sugestoes aparece logo abaixo, com **trecho de origem destacado**, e o vendedor confirma quais aplica no Lead.

## Quando usar

Cliente manda algo como:
```
Olá
Diego liali do espírito santo
03.12.1996
diego@gmail.com
```

Vendedor clica em **🪄 Extrair dados** no proprio balao. Card aparece:
```
🪄 4 dado(s) identificado(s)                            ×
☑ Nome:        Diego Liali do Espírito Santo  "Diego liali do espírito santo"  95%
☑ Nascimento:  1996-12-03                     "03.12.1996"                    99%
☑ E-mail:      diego@gmail.com                "diego@gmail.com"               99%
☐ Cidade:      ...

[ Aplicar selecionados no Lead ]  [ Cancelar ]
```

Vendedor desmarca o que estiver errado, clica em **Aplicar**. Campos vao direto pro `LeadProspecto`.

## Catalogo v1 (8 campos)

| Campo | Validacao pos-LLM |
|---|---|
| `nome_razaosocial` | min 2 chars |
| `cpf_cnpj` | so digitos + checksum CPF (CNPJ tamanho) |
| `email` | regex |
| `data_nascimento` | formato ISO YYYY-MM-DD |
| `rg` | min 2 chars |
| `cep` | 8 digitos |
| `cidade` | min 2 chars |
| `estado` | UF 2 letras maiusculas |

Campos fora dessa lista sao rejeitados em 2 lugares: validador JS do workflow N8N E validador Python do `services_ia_extracao.py`.

## Arquitetura — LLM-first com validacao pos

```
Vendedor clica botao 🪄 no balao
  ↓
Frontend → POST /inbox/api/mensagens/<msg_id>/sugerir-campos/
  ↓
Django views.api_sugerir_campos:
  - Carrega Mensagem, valida tenant + remetente_tipo='contato'
  - Auditoria via registrar_acao('inbox', 'sugerir_campos', ...)
  - Chama services_ia_extracao.extrair_campos(mensagem)
  ↓
services_ia_extracao.extrair_campos:
  - Le settings.N8N_WEBHOOK_EXTRAIR_CAMPOS_URL
  - POST { texto, mensagem_id, tenant_slug, lead_id } pro webhook N8N
  - Sanitiza resposta (campo no catalogo, confianca >= 0.7, trecho in texto)
  ↓
N8N workflow [Hubtrix] Extrair Campos do Texto:
  1. Webhook trigger
  2. Code: monta system prompt + catalogo
  3. HTTP: OpenAI gpt-4o-mini com response_format=json_object, temperature=0
  4. Code: valida pos (trecho_origem in texto, regex, checksum CPF) + filtra
  5. Respond to Webhook devolve { sugestoes, total_brutas, total_validadas }
  ↓
Django devolve JSON pro frontend
  ↓
inbox.js renderCardSugestoes monta card com checkboxes + trecho amarelo
  ↓
Vendedor clica [Aplicar selecionados]
  ↓
POST /inbox/api/leads/<lead_id>/aplicar-sugestoes/ com lista selecionada
  ↓
services_ia_extracao.aplicar_sugestoes:
  - Por campo, normaliza (date.fromisoformat, so digitos, upper)
  - setattr no Lead, save com update_fields
  ↓
Frontend chama loadConversaDetalhe pra refletir os dados novos
```

## Endpoints

### `POST /inbox/api/mensagens/<msg_id>/sugerir-campos/`

Body: vazio (`{}`).

Resposta 200:
```json
{
  "mensagem_id": 12345,
  "lead_id": 678,
  "sugestoes": [
    {"campo": "nome_razaosocial", "valor": "Diego Liali do Espírito Santo",
     "trecho_origem": "Diego liali do espírito santo", "confianca": 0.95}
  ],
  "total_brutas": 4,
  "total_validadas": 3
}
```

Erros:
- `400` mensagem nao e do contato
- `403` mensagem de outro tenant
- `404` mensagem nao existe
- `502` webhook N8N nao configurado / timeout / OpenAI fora

### `POST /inbox/api/leads/<lead_id>/aplicar-sugestoes/`

Body:
```json
{"sugestoes": [{"campo": "...", "valor": "..."}]}
```

Resposta 200:
```json
{
  "lead_id": 678,
  "aplicados": [{"campo": "nome_razaosocial", "valor": "Diego Liali do Espírito Santo"}],
  "ignorados": []
}
```

Auditoria automatica via `@auditar('inbox', 'aplicar_sugestoes_ia', 'lead')`.

## Configuracao

Em `settings.py`:
```python
N8N_WEBHOOK_EXTRAIR_CAMPOS_URL = os.environ.get(
    'N8N_WEBHOOK_EXTRAIR_CAMPOS_URL',
    'https://automation-n8n.v4riem.easypanel.host/webhook/extrair-campos-hubtrix',
)
```

**Credencial OpenAI:** unica no N8N (Aurora-HQ paga). Em v2 cabe switch por tenant se virar feature consolidada.

## Custo

- gpt-4o-mini com schema enxuto: ~$0.00021 por extracao (~R$ 0,0011)
- Modo manual MVP: vendedor clica → custo apenas quando alguem usa
- Estimativa TR Carrion: R$ 0,22/mes
- Sem risco de explosao: cada chamada e um clique humano deliberado

## Anti-alucinacao

Tres camadas de defesa:

1. **Prompt** instrui: "So extraia campos com EVIDENCIA DIRETA no texto. Em caso de duvida, OMITA."
2. **Validador N8N (Code node):** rejeita se `trecho_origem` nao aparece no texto literal; checksum CPF; regex por campo; confianca < 0.7 cai.
3. **Validador Django (services_ia_extracao):** mesmas regras re-aplicadas no backend antes de retornar pro frontend.

UX reforca: vendedor sempre ve o trecho de origem destacado em amarelo, **decide caso a caso**, nunca aplica em lote sem ver.

## Limitacoes conhecidas

- **Sem fluxo de campos custom.** Catalogo fixo v1 nao cobre `nome_mae`, `endereco`, `plano de interesse`. Plano: v2 abre catalogo configuravel por tenant.
- **Latencia ~1-3s** por chamada (Django → N8N → OpenAI → volta). Suficiente pra clique manual; insuficiente pra auto em tempo real.
- **Sem persistencia.** Sugestoes nao sao gravadas em DB, so retornadas no fly. Plano v2: criar tabela `SugestaoCampoLead` pra medir taxa de aceitacao.

## Roadmap

| Versao | Mudancas |
|---|---|
| **v1 (atual)** | Manual, catalogo fixo 8 campos, OpenAI unica Aurora-HQ |
| v2 | Auto em toda msg recebida (trigger paralelo no MESMO workflow N8N), persistencia em `SugestaoCampoLead`, dashboard de aceitacao |
| v3 | Catalogo configuravel por tenant, switch de credencial OpenAI por tenant, fallback Anthropic/Groq |

## Arquivos

| Arquivo | Conteudo |
|---|---|
| `apps/inbox/services_ia_extracao.py` | Thin wrapper HTTP pro N8N + aplicador |
| `apps/inbox/views.py` *(append)* | 2 endpoints REST |
| `apps/inbox/urls.py` *(append)* | 2 rotas |
| `apps/inbox/static/inbox/js/inbox.js` | Botao no balao + card + delegation |
| `apps/inbox/static/inbox/css/inbox.css` | Estilos do card e botao |
| `gerenciador_vendas/settings.py` | `N8N_WEBHOOK_EXTRAIR_CAMPOS_URL` |
| `robo/docs/context/n8n-workflows/hubtrix_extrair_campos_v1.json` | Workflow N8N versionado pra importar |

## Como ativar

1. **Importar** `hubtrix_extrair_campos_v1.json` no N8N de prod.
2. **Configurar credencial OpenAI** no node "OpenAI" (usar a credencial existente do tenant Aurora-HQ).
3. **Ativar** o workflow no painel N8N.
4. **Validar webhook URL:** o path do webhook deve bater com o configurado em `N8N_WEBHOOK_EXTRAIR_CAMPOS_URL` (`/webhook/extrair-campos-hubtrix`).
5. **Testar** no inbox com uma mensagem real do contato com dados.

## Auditoria

- `sugerir_campos` (inbox/mensagem): log a cada clique no botao.
- `aplicar_sugestoes_ia` (inbox/lead): log a cada PATCH aplicado.

Consultavel em `/sistema/auditoria/` filtrando por `categoria=inbox`.
