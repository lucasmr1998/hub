# Sessao Intensiva — 13-14/04/2026

**Data:** 13 a 14 de abril de 2026
**Participantes:** Lucas (CEO) + Claude (Tech Lead / PM)
**Duracao:** Sessao muito longa (2 dias)

---

## Resumo

Sessao focada em: deploy de producao, assistente CRM via WhatsApp, redesign do aurora-admin, correcoes de bugs e infraestrutura de deploy.

---

## Entregas Principais

### Assistente CRM via WhatsApp
- App `apps/assistente/` completo com engine separado
- 15 tools do CRM: consultar_lead, listar_oportunidades, mover_oportunidade, criar_nota, criar_tarefa, atualizar_lead, resumo_pipeline, listar_tarefas, proxima_tarefa, agendar_followup, buscar_historico, marcar_perda, marcar_ganho, agenda_do_dia, ver_comandos
- Webhook com identificacao de usuario por telefone
- ConfiguracaoAssistenteGlobal (numero WhatsApp da Hubtrix) + ConfiguracaoAssistenteTenant (IA por tenant)
- Tela de configuracao no aurora-admin
- Fluxo de 2 agentes: Classificador (leve) + Executor (com tools) / Respondedor (conversa)
- Testado e funcionando via WhatsApp (numero 553181167572)

### Migrado para Opcao C (Inbox)
- Conversa.modo_atendimento ganha opcao 'assistente'
- Mensagens salvas no Inbox (visibilidade total)
- Tools CRM registradas como tools do sistema no engine.py
- Checkboxes [CRM] no editor de fluxos
- Fluxo "Assistente CRM" criado no tenant Aurora HQ com 2 agentes

### Redesign Aurora Admin
- Sidebar profissional com secoes (Geral, Tenants, Produto, Conteudo, Sistema)
- CSS variables alinhadas ao sistema principal
- Responsivo mobile com hamburger menu
- Dashboard com busca de tenants
- Tenant detalhe com 5 tabs (Dados, Modulos, Trial, Usuarios, Integracoes)
- Gestao de usuarios: criar, resetar senha, ativar/desativar
- Dashboard de auditoria com filtros
- Todas as paginas alinhadas ao design system

### Deploy e Infraestrutura
- entrypoint.sh com migrate automatico + seeds idempotentes
- Seeds: funcionalidades, perfis_padrao, tipos_notificacao
- Banco de producao espelhado do local (dump/restore)
- Dominio app.hubtrix.com.br configurado
- Porta 5433 do PostgreSQL para acesso remoto

### Distribuicao Automatica de Oportunidades
- Round robin entre membros da equipe configurada
- ConfiguracaoCRM: distribuicao_modo, distribuicao_equipe, distribuicao_ultimo_vendedor_id
- Integrado em 3 pontos: signal, engine, view manual
- Fix: signal usava ConfiguracaoCRM pk=1 hardcoded

### Permissoes em Dashboards
- Funcionalidade comercial.ver_relatorios
- Funcionalidades de suporte: ver_tickets, gerenciar_tickets, ver_conhecimento, gerenciar_conhecimento
- Views de relatorios agora checam permissao

### Integracoes
- Campo api_key dedicado na IntegracaoAPI (sem criptografia Fernet)
- Teste de conexao especifico para OpenAI, Anthropic, Groq
- base_url opcional para providers de IA
- Webhook URL visivel na tela de integracoes com botao Copiar

### Tela de Login
- Redesign completo com marca Hubtrix
- Card centralizado, minimalista

### Notificacoes
- Fix: som/toast repetindo a cada troca de pagina (localStorage)
- Fix: signal cargo__in inexistente
- playNotifSound exposto no escopo global

### Fluxo FATEPI
- Testado com respostas corretas e erradas
- Bug de extracao IA resolvido (API key via campo api_key)

---

## Problemas Pendentes

### Assistente CRM — resposta nao volta pelo WhatsApp
- O fluxo recebe e processa a mensagem (classificador + respondedor funcionam)
- Mas a resposta nao e enviada de volta pelo WhatsApp
- Causa: o engine do fluxo usa signals do Inbox para enviar, mas o canal nao esta configurado para enviar via Uazapi do assistente
- Proxima sessao: conectar a saida do fluxo ao envio via Uazapi

### Assistente CRM — classificador retornando 2 categorias
- Classificador IA retornou "ACAO\nCONVERSA" em vez de uma so
- Prompt precisa ser mais restritivo ou usar JSON output

### Simulador de teste nao funciona com fluxo do assistente
- Simulador espera um lead, assistente usa usuario
- Baixa prioridade

---

## Decisoes Tecnicas

1. **Assistente como numero unico da Hubtrix** (nao por tenant). Config global + config por tenant.
2. **Opcao C**: usar Inbox com modo_atendimento='assistente'. Visibilidade total no sistema.
3. **2 agentes**: Classificador (leve, sem tools) + Executor (com tools). Conversa vai pro Respondedor, acoes vao pro Executor.
4. **Fluxo no tenant Aurora HQ**: o assistente e da Hubtrix, mas tools operam no tenant do vendedor.
5. **Deploy automatico**: entrypoint.sh roda migrations + seeds. Nunca mais dump/restore.
6. **base_url opcional**: providers de IA usam URL padrao automaticamente.

---

## Estado do Backlog

- **16 pendentes** | **74 finalizadas**

---

## Proximos Passos (proxima sessao)

1. **Corrigir assistente**: resposta do fluxo precisa voltar pelo WhatsApp
2. **Corrigir classificador**: prompt mais restritivo
3. **Testar fluxo completo** do assistente via WhatsApp
4. **Fechar porta 5433** do PostgreSQL no Easypanel
5. **Continuar redesign admin**: polish (toasts, breadcrumbs)
6. **Implementar FATEPI**: configurar webhook Uazapi em producao
