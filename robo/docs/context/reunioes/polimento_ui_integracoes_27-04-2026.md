# Polimento UI da página de integrações — 27/04/2026

**Data:** 27/04/2026
**Participantes:** Lucas + Tech Lead (sessão IA)
**Duração:** ~1h30 (intercalado com a sessão de paridade HubSoft)

---

## Contexto

Durante a sessão de implementação da paridade HubSoft × SGP, várias melhorias visuais e de UX foram identificadas e aplicadas na página de gerenciamento de integrações (`/configuracoes/integracoes/` e `/configuracoes/integracoes/<pk>/`). Cada uma virou commit pequeno separado pra não atrapalhar a tarefa principal.

---

## Principais pontos discutidos

### 1. Sandbox financeiro no painel da integração

- Necessidade de testar endpoints REST sem precisar do Inbox (que ainda não tem UI).
- Decisão: adicionar card "Sandbox" no detalhe da integração HubSoft com input de CPF/CNPJ + botões de consulta-only.
- Evolução: sandbox cobriu progressivamente H3 (financeiro), H4 (operacional incluindo destrutivas com `confirm()`), H5 (viabilidade endereço/coords/CEP) e H6 reduzido (atendimento/OS).
- Ações destrutivas (suspender, reset MAC, desbloqueio) ficam separadas com label vermelho e `confirm()` obrigatório.

### 2. Tabs no design system

- Página de detalhe estava com 6+ cards empilhados verticalmente exigindo scroll longo.
- Decisão: usar componente `components/tabs.html` (já existia no DS, com JS global no `layout_app.html`).
- Estrutura final: header + stats + 6 abas (Credenciais default → Configuração → Catálogos → Sandbox → Modos sync → Logs).
- Insight do usuário: credenciais não deveriam ficar fixas, deveriam estar dentro das tabs também. Aplicado.

### 3. Logs expansíveis

- Tabela "Últimas chamadas" só mostrava status, tempo e mensagem de erro.
- Decisão: cada linha vira clicável com chevron animado; expande mostrando payload enviado + resposta recebida (JSON pretty-printed) + mensagem de erro completa.
- Sem roundtrip de API — tudo já vem renderizado no SSR (via filtro `|pprint`).

### 4. Padronização de cards na listagem

- Cards de HubSoft e SGP mostravam conteúdo diferente: HubSoft tinha "Modos de sincronização" inline + campo "Usuario", SGP não.
- Decisão: remover ambos do card de listagem (modos vivem na aba dedicada do detalhe).
- Cards agora idênticos visualmente: header + URL Base + Configurações extras (opcional) + stats 24h + webhook (uazapi/evolution) + ações.

### 5. Bug do badge component

- Componente `badge.html` usava `{% if label %}` que trata `0` como falsy.
- Catálogos com 0 itens cacheados mostravam badge vazio.
- Fix: trocar pra `{% if label is not None %}`. Validado em Django 5.2.

### 6. Modos de sincronização ampliados + cron

- Aba "Modos de sincronização" tinha só 6 features pra HubSoft, mas algumas (`sincronizar_planos/vencimentos/vendedores`) não tinham nada honrando o modo automático em runtime.
- Pergunta do usuário: "deveria ter mais nd tbm?"
- Decisão: manter as 6 + adicionar 2 novas (`anexar_documentos_contrato`, `aceitar_contrato`) com lógica real no signal/service. Adicionar cron `sincronizar_catalogo_hubsoft --apenas-automatico` pra honrar os modos automáticos das categorias.
- Mapeamento categoria → feature em `CATEGORIA_FEATURE` no command, com `sincronizar_vendedores` servindo como modo grupo dos 9 catálogos cacheados secundários.

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Sandbox no painel da integração (consulta-only por default) | Testar endpoints sem precisar do Inbox/CRM de cliente; debugar credenciais |
| Ações destrutivas no sandbox precisam de `confirm()` + label vermelho | Reduzir risco de operação acidental em ambiente real |
| Credenciais como primeira aba (default) | Caso mais frequente: vir aqui pra editar credenciais |
| Cards da listagem 100% padronizados (sem condicionais por tipo) | UX consistente; informação detalhada é responsabilidade do detalhe |
| Logs expansíveis no SSR (não API) | Latência zero; payload já é renderizado no Django |
| `{% if label is not None %}` no badge | Suportar valor 0 como display válido |
| Cron de catálogos respeita `sync_habilitado(feature)` por categoria | Multi-tenant: cada provedor decide o que roda automaticamente |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Configurar `Aurora HubSoft Catalogos` no EasyPanel | Ops (1x/dia, 03:00) |
| Validar visual em produção com tenants reais | Lucas (acessar painel HubSoft Megalink + SGP Gigamax) |

---

## Próximos passos

- [ ] Após validação visual, considerar replicar tabs/sandbox para o painel SGP (hoje só HubSoft tem sandbox)
- [ ] Avaliar se outros tipos de integração (uazapi, n8n, providers IA) ganhariam com sandbox próprio — provavelmente não pois fluxos são bem diferentes
