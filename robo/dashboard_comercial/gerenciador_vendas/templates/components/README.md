# Componentes reutilizáveis

Pasta para componentes de UI que serão incluídos em várias páginas via `{% include %}`.

**Vazia por enquanto** — adicionar conforme a demanda das telas. Candidatos iniciais:

- `button.html` — variantes primary / secondary / ghost / danger
- `card.html` — wrapper padrão de cartão com header / body / footer
- `input.html` — input com label, helper, estado de erro
- `badge.html` — pill de status (success, warning, danger, info, neutral)
- `modal.html` — modal padrão com header, body, footer
- `table.html` — estrutura de tabela com sort e filtros
- `empty_state.html` — "nenhum item encontrado" com ícone e CTA

## Convenção de uso

Cada componente é um snippet que recebe contexto via parâmetro. Exemplo:

```django
{# Em qualquer template: #}
{% include "components/button.html" with text="Salvar" variant="primary" icon="bi-check" %}
```

## Princípios

- **Sem lógica complexa** — componente é visual, não comportamento
- **Tokens do `base.html`** — usar as variáveis CSS (`--color-primary`, `--sp-4`, etc.), não hardcodar
- **Documentar no topo do arquivo** — parâmetros esperados, exemplo de uso
