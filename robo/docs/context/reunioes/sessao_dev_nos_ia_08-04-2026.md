# Sessao Dev: Nos IA Modulares + Permissoes + Tools FATEPI — 08/04/2026

**Data:** 08/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / PM)

---

## Entregas

### Permissoes Granulares
- Removido is_superuser de 21 views (CRM, Sistema, Notificacoes)
- Substituido por user_tem_funcionalidade() em todas
- Tela de usuarios filtrada por tenant (fix vazamento multi-tenant)
- Campo Staff removido da interface
- Seed perfis Admin para todos os usuarios/tenants

### Timeline CRM Mesclada
- Timeline na oportunidade agora mostra estagios + contatos + conversas
- Todos ordenados cronologicamente (mais recente primeiro)
- Eventos de conversa: iniciada (icone WhatsApp) e finalizada (icone check)

### Tools Agente FATEPI (N8N)
- oportunidade_id adicionado ao payload enviado ao N8N
- API oportunidades aceita campos flat dados_custom.* 
- API aceita valores vazios sem erro
- N8N atualizado para versao mais recente
- No do agente recriado na versao 3.1
- Documentacao separada: system_prompt + tools + indice

### Nos IA Modulares no Editor Visual
- 4 novos tipos de no implementados:
  - ia_classificador: analisa mensagem, retorna categoria como variavel
  - ia_extrator: extrai dados estruturados, salva no lead/oportunidade
  - ia_respondedor: gera resposta IA, pausa e espera
  - ia_agente: conversa multi-turno com historico
- Engine completo com _chamar_llm_simples() (4 providers)
- Sistema de variaveis entre nos (dados_respostas['variaveis'])
- Editor visual com secao IA, paineis de config, CSS roxo
- Condicoes suportam variaveis IA (var.classificacao, etc.)

### Fluxo FATEPI via Nos IA
- Fluxo criado com 12 nos e 12 conexoes
- Testado E2E via widget: nome extraido, curso classificado, oportunidade criada
- dados_custom salvos na oportunidade (curso_interesse)
- Integracao OpenAI criada para FATEPI

### Canal + Fluxo de Atendimento
- CanalInbox agora tem FK para FluxoAtendimento
- Select de fluxo nas configuracoes de cada canal
- Widget token dinamico por tenant
- Lead criado automaticamente para conversas widget sem lead

### CRM dados_custom
- dados_custom exibidos no card do pipeline e detalhe da oportunidade
- Acao criar_oportunidade salva variaveis IA no dados_custom

### CLAUDE.md
- Regra de agente obrigatoria na resposta
- Documentacao obrigatoria apos implementacao

### Nome do Produto
- Definido: Hubtrix (dominio hubtrix.com.br disponivel)
- Implementacao da troca pendente

---

## Bugs Corrigidos
- is_superuser bloqueava acesso a configuracoes do CRM
- Usuarios de todos os tenants visiveis na tela de permissoes
- Signal N8N falhava silenciosamente (campo ativo vs ativa)
- EncryptedCharField encriptava API key da OpenAI
- Widget com token hardcoded (mesmo token para todos os tenants)
- Widget sendMessage falhava sem currentConversa
- Duplicacao de canal (IntegrityError)
- mover_estagio passava slug como ID
- Variaveis {{}} no template interpretadas pelo Django

---

## Pendente
- [ ] Integrar validacao/classificacao/extracao IA direto no no de questao
- [ ] Modal de configuracao (estilo N8N) para todos os tipos de no
- [ ] Tool calling nativo por provider no no ia_agente
- [ ] Completar fluxo FATEPI (forma ingresso, valores, fechamento com PIX)
- [ ] Testar fluxo via WhatsApp (testado apenas via widget)
- [ ] Troca de nome Aurora -> Hubtrix
- [ ] Deploy em producao
