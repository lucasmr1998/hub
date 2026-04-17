# Inbox — Chat Widget (embeddable)

Widget JS vanilla, self-contained (~15KB), zero dependencias.

**Arquivo:** `apps/inbox/static/inbox/widget/aurora-chat.js`

---

## Embed

```html
<script src="https://app.auroraisp.com/static/inbox/widget/aurora-chat.js"
        data-token="<token-do-tenant>"></script>
```

---

## Interface (3 abas)

```
┌─────────────────────────────────┐
│ ✕                               │
│                                 │
│  Ola 👋                        │  ← Header com gradiente (cor_header)
│  Como podemos ajudar?           │
│                                 │
├─────────────────────────────────┤
│                                 │
│  [Envie uma mensagem      →]    │  ← CTA para abrir chat
│                                 │
│  Qual e a sua duvida?    🔍    │  ← Busca FAQ
│                                 │
│  Planos e Precos           →   │  ← Categorias FAQ
│  Suporte Tecnico           →   │
│  Financeiro                →   │
│                                 │
├─────────────────────────────────┤
│  🏠 Inicio  💬 Mensagens  ❓ Ajuda │  ← 3 abas
└─────────────────────────────────┘
```

---

## Funcionalidades

- **Botao flutuante** (bottom-right/left, cor configuravel)
- **Aba Inicio:** saudacao + CTA + busca FAQ + categorias com artigos
- **Aba Mensagens:** lista de conversas do visitante, chat com bolhas, formulario de dados (nome/email/telefone) antes do primeiro contato (configuravel)
- **Aba Ajuda:** browser de FAQ por categoria + busca
- **Visitor ID:** UUID em localStorage para continuidade entre sessoes
- **Polling 5s** para novas mensagens
- **Responsivo:** full-screen em telas < 480px
- **Isolamento CSS:** classes prefixadas `.aw-*`

---

## Configuracao via painel

Em `/inbox/configuracoes/` aba "Widget":

- Titulo, mensagem de boas-vindas
- Cores (primaria + header)
- Posicao (inferior direito/esquerdo)
- Mostrar FAQ, pedir dados antes do chat
- Campos obrigatorios (nome, email, telefone)
- Dominios permitidos (CORS)
- Codigo embed para copiar

---

## Endpoints publicos

O widget consome as 7 APIs publicas documentadas em [apis.md](apis.md#api-publica-widget--sem-login). Autenticacao via token UUID no query param.
