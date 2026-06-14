---
modulo: Marketing — Emails (Editor Visual e Renderer)
status: 🟢 Implementado
data: 13/06/2026
---

# Marketing — Editor visual e renderer de email

Editor visual de blocos drag-drop pra montar emails responsivos. Cada bloco é um dict JSON; o renderer compila pra HTML inline-styled (Gmail/Outlook compatível).

Complementa [emails-dominios-remetentes.md](emails-dominios-remetentes.md), que cobre DNS/remetentes/Resend.

## Stack

| Camada | Onde | Função |
|---|---|---|
| **Models** | `apps/marketing/emails/models.py` | `TemplateEmail` (config + blocos), `EnvioEmail`, `CategoriaTemplate` |
| **Renderer** | `apps/marketing/emails/renderer.py` | JSON de blocos → HTML inline. Pure Python, sem dependência externa. |
| **Editor** | `templates/emails/editor.html` | Frontend JS — palette de blocos + canvas + props inspector |
| **API editor** | `views.salvar_email`, `views.preview_live`, `views.api_templates` | Salvar blocos, gerar preview ao vivo, listar templates pra duplicação |

## Model `TemplateEmail` (resumo)

| Campo | Função |
|---|---|
| `nome`, `descricao` | identificação interna |
| `assunto` | linha de assunto. Suporta `{{lead.nome}}` (render Resend service) |
| `config_json` | globais: largura, cor_fundo, fonte_padrao (default 600px / `#f5f5f5` / Arial) |
| `blocos_json` | **array ordenado de blocos** (estrutura abaixo) |
| `html_compilado` | output do renderer (cache; regenerado em cada save) |
| `categoria` FK | organização |
| `status` | rascunho / ativo / arquivado |
| `eh_modelo_base` | flag pra templates compartilhados entre tenants |
| `thumbnail` | ImageField, preview da lista |

## Estrutura de um bloco

```json
{
  "tipo": "<um_dos_12_tipos>",
  "props": { "...": "..." }
}
```

Renderer despacha pra `_render_<tipo>(props, fonte)`. Bloco inválido vira string vazia (silent skip).

## Catálogo de blocos (12)

| # | tipo | Props principais | Uso |
|---|---|---|---|
| 1 | `cabecalho` | `logo_url`, `cor_fundo` (#1a1a2e), `altura` (80), `alinhamento` | Topo com logo da marca |
| 2 | `texto` | `conteudo` (HTML), `alinhamento`, `padding`, `cor_texto`, `tamanho_fonte` | Parágrafo/título livre |
| 3 | `imagem` | `url`, `alt_text`, `largura` (100%), `link`, `border_radius`, `alinhamento`, `padding` | Imagem com link opcional |
| 4 | `botao` | `texto`, `url`, `cor_botao` (#3b82f6), `cor_texto`, `border_radius`, `tamanho` (pequeno/medio/grande), `alinhamento` | CTA |
| 5 | `divisor` | `estilo` (solid/dashed/espaco), `cor`, `espessura`, `largura`, `margem` | Linha separadora ou espaço vazio |
| 6 | `espacamento` | `altura` (px) | Espaçador vertical isolado |
| 7 | `colunas` | `layout` (1/2/3/1-2/2-1), `gap`, `colunas[]` (cada uma com `blocos[]` recursivos), `padding` | Layout em colunas; cada coluna aceita blocos aninhados |
| 8 | `card_plano` | `nome`, `preco`, `beneficios[]`, `texto_botao`, `url_botao`, `cor_destaque`, `cor_fundo`, `padding` | Card de oferta (plano + lista + CTA) |
| 9 | `lista` | `itens[]`, `estilo` (check/bullet/star/arrow/numero), `cor_icone`, `padding` | Lista com ícones |
| 10 | `depoimento` | `texto`, `nome`, `cargo`, `foto_url`, `padding` | Testemunho com avatar |
| 11 | `rodape` | `texto`, `endereco`, `unsubscribe_url`, `cor_fundo`, `cor_texto`, `padding` | Rodapé com infos + descadastro |
| 12 | `html_custom` | `html` (string) | Escape hatch — HTML cru pra casos avançados |

### Aninhamento

`colunas` aceita blocos recursivamente em `colunas[].blocos[]`. Permite layouts ricos (ex: imagem à esquerda + texto à direita) sem hardcodar template.

## Variáveis dinâmicas

Render simples via regex no `resend_service.py:_render_simple`:

- Sintaxe: `{{lead.<campo>}}`
- Campos disponíveis: qualquer atributo do `LeadProspecto` (`nome`, `email`, `telefone`, etc) + tudo que vier em `contexto_extra` passado pro `disparar_para_lead`.
- Fallback silencioso pra string vazia quando campo não existe.
- **Limitação atual:** sem filters Django (`|upper`, `|date`), sem `{% if %}` ou `{% for %}`. Pra evolução, ver "Próximas evoluções" abaixo.

## Fluxo de criação de template

```
1. Tenant entra em /marketing/emails/
2. "Criar template" → escolhe categoria + nome → salva
3. Vai pro editor: arrasta blocos da palette pro canvas, edita props
4. Preview ao vivo: views.preview_live recompila HTML a cada save
5. Marca como "ativo" → fica disponível pra envio/automação
```

## Fluxo de envio

```
disparar_para_lead(template, lead) [resend_service.py]
  ↓
resolve remetente padrão do tenant
  ↓
valida dominio.esta_verificado
  ↓
_render_simple no assunto e em template.html_compilado
  ↓
cria EnvioEmail (status=pendente, tracking_id UUID)
  ↓
resend.Emails.send(tags=[tracking_id, tenant])
  ↓
status='enviado' + resend_message_id salvo
  ↓
webhook do Resend atualiza status pra entregue/aberto/clicado/bounce/complained
```

## Tracking

| Mecanismo | Onde |
|---|---|
| `tracking_id` (UUID) | Pixel histórico — `EnvioEmail.tracking_id` único, embedável como pixel `?tid=<uuid>` |
| `resend_message_id` | Correlaciona webhooks Resend → EnvioEmail (vai no header `tags` do envio) |
| Eventos | `entregue_em`, `aberto_em`, `clicado_em` setados pelo webhook handler |

## Reuso do renderer fora de email

O renderer é **puro Python sem dependência de model Email** — recebe lista de blocos + config e devolve HTML. **Pode ser reusado para Landing Pages** (ver [landing-pages.md](landing-pages.md)). A única diferença: HTML de LP não precisa ser inline-styled como email — pode usar `<style>` em `<head>`.

## URLs

| URL | View |
|---|---|
| `/marketing/emails/` | `lista_emails` — grid de templates |
| `/marketing/emails/criar/` | `criar_email` |
| `/marketing/emails/<pk>/editor/` | `editor_email` |
| `/marketing/emails/<pk>/preview/` | `preview_email` |
| `/marketing/emails/<pk>/salvar/` (POST AJAX) | `salvar_email` |
| `/marketing/emails/<pk>/duplicar/` | `duplicar_email` |
| `/marketing/emails/<pk>/excluir/` | `excluir_email` |
| `/marketing/emails/api/preview/` (POST) | `preview_live` — recompila HTML on-demand pro editor |
| `/marketing/emails/api/templates/` | `api_templates` — JSON pra listas externas (CRM/Automação) |

## Próximas evoluções

- **Renderer Django Template completo:** `Template(html).render(Context({...}))` — habilita `|filter` e `{% for %}`. Hoje só `{{lead.X}}` via regex
- **Multi-template por automação:** template diferente por estágio (ex: boas-vindas vs lembrete)
- **A/B test de templates:** automação dispara 50/50 entre 2 templates da mesma categoria, mede taxa de abertura/clique
- **Componente de "produto/plano dinâmico":** bloco que lê catálogo do tenant (`Plano`) em vez de hardcoded
- **Renderer Markdown:** opção de bloco texto receber MD em vez de HTML
