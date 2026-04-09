# Sessao Dev: Fluxos IA, Editor Visual, Tools Customizadas — 08-09/04/2026

**Data:** 08-09/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / PM)

---

## Entregas

### Nos IA Modulares
- 4 tipos: ia_classificador, ia_extrator, ia_respondedor, ia_agente
- Engine completo com _chamar_llm_simples (4 providers)
- Sistema de variaveis entre nos (dados_respostas['variaveis'])
- Editor visual com secao IA, paineis de config, CSS roxo

### IA Integrada na Questao
- Classificar e extrair direto no no de questao (tab IA no modal)
- Acoes: validar, classificar, extrair, classificar_extrair
- Salva variaveis e dados no lead/oportunidade

### Modal de Config (estilo N8N)
- Substituiu painel lateral por modal centralizado
- Double-click no no para abrir
- Tabs (Mensagem / Resposta / IA / Avancado) para questoes
- Animacao, backdrop blur, ESC fecha

### Tools IA Customizadas no Agente
- Agentes especialistas como tools no no ia_agente
- Cada tool tem nome, descricao e prompt proprio
- Tool calling real via OpenAI/Groq API (function calling)
- Editor: lista dinamica de tools no modal

### Editor Visual Melhorias
- Controles de zoom (+/- e Reset) no canvas
- Undo/Redo com snapshots (Ctrl+Z / Ctrl+Y)
- Keyboard shortcuts (Ctrl+S, Ctrl+D, Delete, Escape)
- Duplicar no (Ctrl+D) com config copiada
- Questao com 2 outputs (sucesso/fallback)
- Extrator IA com 2 outputs (extraiu/fallback)

### Fluxo FATEPI v3
- 24 nos com fallback IA nas questoes
- Classificador IA no fallback do curso
- Respondedores especializados (valores, generico)
- Testado E2E via widget

### Formatacao WhatsApp
- *negrito*, _italico_, ~tachado~, quebra de linha
- Widget, Inbox e CRM templates
- Mensagens do bot divididas em paragrafos

### Edicao Inline Lead/CRM
- Campos clicaveis no detalhe do lead e oportunidade
- API PUT para editar via AJAX
- dados_custom editaveis

### Canal + Fluxo
- CanalInbox com FK para FluxoAtendimento
- Select de fluxo nas configuracoes do Inbox e Widget
- Widget token dinamico por tenant

### Permissoes e Navegacao
- is_superuser removido de 21 views
- Fluxos movidos para sidebar do Suporte
- Questoes legado removidas
- Comercial aponta para dashboard

### Nome do Produto
- Definido: Hubtrix (dominio hubtrix.com.br)

---

## Bugs Corrigidos
- Signal N8N falhava (ativa vs ativo)
- Widget com token hardcoded
- Canal duplicado (IntegrityError)
- mover_estagio passava slug como ID
- Questao vazia pausava sem enviar mensagem
- EncryptedCharField encriptava API key
- Lead nao criado para conversas widget

---

## Revertido (precisa reimplementar)
- Indicadores de status nos nos (badges verde/amarelo/vermelho)
- Preview do conteudo no no
- Minimap
- Command palette (Ctrl+K)
- Historico de execucao por no
- Auto-save
- Melhoria visual dos nos (CSS)

Essas features quebraram o layout do Drawflow e precisam ser reimplementadas testando cada mudanca individualmente.

---

## Pendente
- [ ] Reimplementar melhorias visuais do editor (Fase 2 e 3) sem quebrar Drawflow
- [ ] Testar fluxo FATEPI v3 completo via WhatsApp
- [ ] Implementar Fase 4: multi-select, notas, versionamento, templates
- [ ] Teste/Debug no editor (chat de teste embutido)
- [ ] Troca de nome Aurora -> Hubtrix
- [ ] Deploy em producao
