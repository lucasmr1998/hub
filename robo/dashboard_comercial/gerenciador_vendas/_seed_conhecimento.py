"""Seed da base de conhecimento da Aurora — versão completa e detalhada."""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'
django.setup()

from apps.sistema.middleware import set_current_tenant
from apps.sistema.models import Tenant
from django.utils.text import slugify
from django.contrib.auth.models import User
from apps.suporte.models import CategoriaConhecimento, ArtigoConhecimento

tenant = Tenant.objects.get(slug='aurora-hq')
set_current_tenant(tenant)
user = User.objects.get(pk=1)

# ──────────────────────────────────────────────
# Categorias
# ──────────────────────────────────────────────
categorias_data = [
    ('Produto', 'fa-cube', '#3b82f6', 1),
    ('Integrações', 'fa-plug', '#8b5cf6', 2),
    ('Vendas', 'fa-handshake', '#16a34a', 3),
    ('Onboarding', 'fa-rocket', '#f59e0b', 4),
    ('Técnico', 'fa-cog', '#64748b', 5),
    ('Perguntas Frequentes', 'fa-circle-question', '#ec4899', 6),
]

cats = {}
for nome, icone, cor, ordem in categorias_data:
    cat, cr = CategoriaConhecimento.all_tenants.update_or_create(
        tenant=tenant, slug=slugify(nome),
        defaults={'nome': nome, 'icone': icone, 'cor_hex': cor, 'ordem': ordem, 'ativo': True}
    )
    cats[nome] = cat
    print(f"Categoria: {nome} ({'criada' if cr else 'atualizada'})")

# ──────────────────────────────────────────────
# Artigos
# ──────────────────────────────────────────────
artigos = [
    # ═══════════════════════════════════════════
    # PRODUTO
    # ═══════════════════════════════════════════
    {
        'cat': 'Produto', 'destaque': True,
        'titulo': 'Visao Geral da AuroraISP',
        'resumo': 'O que e a Aurora, quais modulos oferece, diferencial competitivo e para quem e indicada',
        'tags': 'aurora, produto, modulos, visao-geral, hub',
        'conteudo': """## O que e a AuroraISP?

A AuroraISP e um hub de tecnologia com inteligencia artificial desenvolvido exclusivamente para provedores de internet. A plataforma conecta todas as etapas da jornada do cliente: da captacao do lead ate a fidelizacao pos-venda.

**Tagline:** Vende mais. Perde menos. Fideliza sempre.
**Subtitulo:** Do lead ao cliente fidelizado com inteligencia.

## Modulos do Hub

A Aurora e dividida em 3 grandes modulos, cada um com planos Start e Pro:

### 1. Modulo Comercial
Cobre todo o funil de vendas do provedor, do primeiro contato no WhatsApp ate o contrato ativado no ERP.

**Sub-apps incluidos:**
- **Leads:** captura multicanal, qualificacao automatica, score inteligente, 60+ campos
- **Atendimento:** bot conversacional com fluxos configuráveis, 20+ tipos de questao, validacao por IA
- **Cadastro Digital:** landing page publica personalizada, selecao de planos, vencimentos, validacao de CEP, upload de documentos, contrato digital com aceite
- **Viabilidade Tecnica:** consulta de cobertura por CEP com integracao ao ERP
- **CRM (plano Pro):** pipeline Kanban visual com drag-and-drop, oportunidades, tarefas com prazos, metas por vendedor, equipes de vendas, segmentos dinamicos, alertas de churn

**Numeros:** 28 models, 80+ views, 70+ endpoints, 22 templates.

### 2. Modulo Marketing
Motor de automacao inteligente do hub. Permite criar campanhas, segmentar a base e automatizar comunicacoes.

**Sub-apps incluidos:**
- **Campanhas:** deteccao automatica por palavra-chave (UTM), ROI por campanha, rastreamento de origem
- **Segmentos:** dinamicos (score >= 7, origem = whatsapp) e manuais, preview em tempo real, contagem automatica
- **Automacoes:** editor visual drag-and-drop (Drawflow), 14 gatilhos, 8 acoes, condicoes if/else, delays reais, rate limiting

**Gatilhos disponiveis:** lead criado, lead qualificado, oportunidade criada, oportunidade movida de estagio, documentos validados, contrato aceito, venda finalizada, tarefa vencida, lead sem contato, membro clube criado, indicacao convertida, disparo por segmento, webhook recebido, agendamento (cron).

**Acoes disponiveis:** enviar WhatsApp, enviar e-mail, criar notificacao, criar tarefa no CRM, mover estagio do pipeline, dar pontos no clube, disparar webhook, atribuir responsavel.

**Numeros:** 11 models, 22 views, 22 APIs, 60+ testes.

### 3. Modulo Customer Success (CS)
Sistema completo de fidelizacao e retencao de clientes.

**Sub-apps incluidos:**
- **Clube de Beneficios:** gamificacao com roleta premiada, sistema de pontos (saldo + XP), missoes, niveis (Iniciante, Bronze, Prata, Ouro, Diamante), landing page publica
- **Parceiros:** rede de parceiros com cupons de desconto (gratuitos, por pontos, por nivel), fluxo de aprovacao
- **Indicacoes:** programa "indique e ganhe" com rastreamento automatico e pontuacao na conversao
- **Carteirinha Digital:** cartao de membro com QR code, templates visuais configuraveis, atribuicao automatica por regras
- **NPS:** pesquisas de satisfacao (em desenvolvimento)
- **Retencao:** prevencao de churn com health score e alertas (em desenvolvimento)

**Numeros:** 24 models, 55+ views, 40+ APIs, 30+ templates.

## Diferencial Central

**Integracao nativa e profunda com HubSoft.** Nenhum concorrente oferece essa integracao. O lead entra pelo WhatsApp e sai como contrato ativado no ERP, sem intervencao manual.

A Aurora tambem suporta integracao com MK Solutions, IXCSoft e outros ERPs via API REST.

## Para quem e indicada (ICP)

- Provedores regionais de internet
- Que utilizam HubSoft (ou outro ERP com API)
- 500 a 50.000 clientes ativos
- 2 a 20 vendedores na equipe
- Que buscam digitalizar e escalar a operacao comercial

## Case de producao

Provedor com 30.000 clientes:
- 1.000 leads/mes capturados automaticamente
- 400 vendas digitais/mes sem intervencao humana
- 2 pessoas fazem o que 8 faziam antes
- Economia de R$ 284.400/ano em pessoal
- Ticket medio: R$ 99,90""",
    },
    {
        'cat': 'Produto', 'destaque': True,
        'titulo': 'Modulo Comercial — Guia Completo',
        'resumo': 'Fluxo completo do lead ao contrato: Leads, Atendimento, Cadastro, Viabilidade e CRM',
        'tags': 'comercial, leads, crm, cadastro, vendas, atendimento, viabilidade, pipeline',
        'conteudo': """## Visao Geral

O Modulo Comercial cobre todo o funil de vendas do provedor de internet, desde a captura do lead ate a ativacao do contrato no ERP. E composto por 5 sub-apps integrados.

## Fluxo Principal

```
Lead chega (WhatsApp/Site/Campanha)
  → Bot qualifica automaticamente
    → Cadastro digital (plano, documentos, contrato)
      → Validacao e aprovacao
        → Ativacao no ERP (HubSoft/MK/IXC)
```

## 1. Leads

O app de Leads e o ponto de entrada de todos os contatos comerciais.

**Funcionalidades:**
- Captura multicanal: WhatsApp, site, landing page, importacao manual
- Score automatico de qualificacao (0 a 10)
- 60+ campos por lead (dados pessoais, endereco, plano, documentos)
- Status: novo, em_atendimento, qualificado, cadastro, documentos, contrato, finalizado, cancelado
- Gestao de imagens/documentos (RG, CPF, comprovante)
- Historico completo de interacoes

**Campos principais:** nome, telefone, email, cpf, data_nascimento, cep, endereco completo, plano_interesse, vencimento, score, origem, campanha, responsavel, observacoes.

**Score de qualificacao:** calculado automaticamente com base em: preenchimento de dados, validacao de CPF, confirmacao de interesse, viabilidade tecnica, tempo de resposta.

## 2. Atendimento (Bot)

O bot conversacional automatiza o primeiro contato e qualificacao do lead.

**Funcionalidades:**
- Fluxos configuráveis com 20+ tipos de questao
- Tipos de questao: texto, numero, CPF, CNPJ, email, telefone, CEP, data, sim/nao, escolha unica, escolha multipla, foto, documento, localizacao
- Validacao inteligente por IA (verifica se a resposta faz sentido)
- Roteamento para humano quando necessario
- Integração com N8N para webhooks

**Fluxo do bot:**
1. Recepciona o lead (mensagem de boas-vindas)
2. Faz perguntas de qualificacao na ordem configurada
3. Valida cada resposta (formato + IA)
4. Preenche automaticamente os campos do lead
5. Move o lead para o proximo estagio
6. Notifica o vendedor responsavel

## 3. Cadastro Digital

Landing page publica para o cliente completar seu cadastro.

**Funcionalidades:**
- Pagina personalizada com logo e cores do provedor
- Selecao de plano de internet (sincronizado com ERP)
- Escolha de dia de vencimento
- Validacao de CEP e preenchimento automatico de endereco
- Upload de documentos (RG, CPF, comprovante de residencia)
- Contrato digital com aceite via checkbox
- Gera link unico por lead

**Configuracoes visuais:** cor primaria, cor secundaria, logo, banner, texto de boas-vindas, campos obrigatorios, tipos de documento aceitos, template do contrato.

## 4. Viabilidade Tecnica

Verifica se o provedor atende determinado endereco.

**Funcionalidades:**
- Consulta por CEP
- Integracao com base do ERP para verificar cobertura
- Retorno de planos disponiveis na regiao
- Bloqueio automatico de cadastro se nao houver viabilidade

## 5. CRM (Plano Pro)

Pipeline visual completo para gestao de oportunidades comerciais.

**Funcionalidades:**
- Pipeline Kanban com drag-and-drop entre estagios
- Estagios padrao: Novo Lead, Primeiro Contato, Qualificacao, Proposta Enviada, Negociacao, Fechado/Ganho, Fechado/Perdido
- Oportunidades com valor estimado, probabilidade, data prevista
- Tarefas vinculadas a oportunidades (com prazo, responsavel, status)
- Notas internas por oportunidade
- Equipes de vendas com supervisor
- Metas por vendedor (mensal, por quantidade ou valor)
- Dashboard de desempenho com graficos
- Segmentos dinamicos (filtros salvos para segmentar oportunidades)
- Alertas de churn (oportunidades paradas por X dias)

**Metricas disponíveis:** taxa de conversao por estagio, ticket medio, tempo medio de fechamento, meta atingida (%), ranking de vendedores, oportunidades por origem.

## Integracao com ERP

O modulo comercial sincroniza com o ERP do provedor:
- **Consome:** planos disponiveis, status de clientes, viabilidade por CEP
- **Envia:** novo prospecto/lead, documentos, contrato aceito, status de processamento

A sincronizacao pode ser via API REST (HubSoft, MK, IXC) ou via N8N (webhooks).""",
    },
    {
        'cat': 'Produto', 'destaque': True,
        'titulo': 'Modulo Marketing e Automacoes — Guia Completo',
        'resumo': 'Campanhas, segmentos dinamicos e editor visual de automacoes com gatilhos e acoes',
        'tags': 'marketing, automacoes, campanhas, segmentos, gatilhos, acoes, drawflow',
        'conteudo': """## Visao Geral

O Modulo Marketing e o motor de automacao inteligente da Aurora. Permite criar campanhas com rastreamento de ROI, segmentar leads dinamicamente e construir fluxos automatizados com editor visual.

## 1. Campanhas

Gerenciamento de campanhas de trafego com rastreamento automatico de leads.

**Funcionalidades:**
- Criacao de campanhas com nome, plataforma, investimento e periodo
- Deteccao automatica: quando um lead menciona uma palavra-chave, e vinculado a campanha
- Calculo automatico de ROI (receita gerada vs investimento)
- Dashboard com metricas: leads captados, custo por lead, conversoes, ROI

**Plataformas suportadas:** Meta Ads (Facebook/Instagram), Google Ads, TikTok Ads, Indicacao, Organico.

**Como funciona a deteccao:**
1. Configure palavras-chave na campanha (ex: "promo200", "black-friday")
2. Quando um lead chega pelo WhatsApp e menciona a palavra-chave
3. O sistema automaticamente vincula o lead a campanha
4. As metricas da campanha sao atualizadas em tempo real

## 2. Segmentos

Agrupamento dinamico de leads com base em criterios configuráveis.

**Funcionalidades:**
- Segmentos dinamicos: atualizam automaticamente conforme leads mudam
- Segmentos manuais: selecao fixa de leads
- Preview em tempo real (contagem de leads que atendem aos criterios)
- Uso em automacoes (gatilho "disparo por segmento")

**Campos disponiveis para filtro:**
- score (>=, <=, =)
- origem (whatsapp, site, indicacao, campanha)
- status (novo, qualificado, finalizado, etc)
- data_criacao (ultimos X dias)
- cidade, estado
- plano_interesse
- responsavel
- estagio do CRM
- dias sem contato

**Exemplo:** "Leads com score >= 7, origem WhatsApp, criados nos ultimos 30 dias, sem contato ha 3 dias" → segmento "Leads Quentes Sem Retorno".

## 3. Automacoes (Editor Visual)

O coracao do modulo. Permite criar fluxos de automacao com interface drag-and-drop.

### Como funciona o editor

O editor utiliza a biblioteca Drawflow para criar fluxos visuais:
1. **Arraste** nodos da barra lateral para o canvas
2. **Conecte** os nodos arrastando de uma saida para uma entrada
3. **Configure** cada nodo clicando nele (gatilho, condicao ou acao)
4. **Salve** e ative o fluxo

### Tipos de nodos

**Gatilhos (triggers)** — o que inicia a automacao:
| Gatilho | Descricao | Tipo |
|---------|-----------|------|
| lead_criado | Novo lead no sistema | Signal (tempo real) |
| lead_qualificado | Lead atinge score minimo | Signal |
| oportunidade_criada | Nova oportunidade no CRM | Signal |
| oportunidade_movida | Oportunidade muda de estagio | Signal |
| documentos_validados | Docs do lead aprovados | Signal |
| contrato_aceito | Cliente aceita contrato digital | Signal |
| venda_finalizada | Venda confirmada no ERP | Signal |
| membro_clube_criado | Novo membro no clube | Signal |
| indicacao_convertida | Indicacao virou cliente | Signal |
| lead_sem_contato | Lead sem interacao ha X dias | Cron (cada 5 min) |
| tarefa_vencida | Tarefa do CRM passou do prazo | Cron |
| disparo_por_segmento | Leads que entram num segmento | Cron |
| webhook_recebido | Webhook externo recebido | Signal |
| agendamento | Execucao em horario fixo | Cron |

**Condicoes (conditions)** — filtros if/else:
- Campo: qualquer campo do lead, oportunidade ou contexto
- Operadores: igual, diferente, maior, menor, contem, nao contem
- Saidas: "Sim" (condicao atendida) e "Nao" (nao atendida)

**Acoes (actions)** — o que a automacao faz:
| Acao | Descricao | Configuracao |
|------|-----------|-------------|
| enviar_whatsapp | Envia mensagem no WhatsApp | telefone, mensagem (suporta variaveis) |
| enviar_email | Envia e-mail | destinatario, assunto, corpo |
| criar_notificacao | Notifica usuario do sistema | titulo, mensagem, destinatario |
| criar_tarefa_crm | Cria tarefa no CRM | titulo, descricao, responsavel, prazo |
| mover_estagio | Move oportunidade no pipeline | estagio_destino |
| dar_pontos_clube | Adiciona pontos ao membro | quantidade, tipo (saldo/xp), motivo |
| disparar_webhook | Envia dados para URL externa | url, metodo, payload |
| atribuir_responsavel | Atribui vendedor ao lead | equipe (round-robin automatico) |

### Variaveis disponiveis nas mensagens

Dentro de mensagens de WhatsApp e e-mail, voce pode usar variaveis:
- `{lead_nome}` — nome do lead
- `{lead_telefone}` — telefone
- `{lead_email}` — e-mail
- `{lead_plano}` — plano de interesse
- `{oportunidade_valor}` — valor da oportunidade
- `{estagio_nome}` — estagio atual no pipeline
- `{responsavel}` — nome do vendedor responsavel

### Execucao

A engine de automacoes funciona em duas camadas:
- **Signals (tempo real):** quando um evento ocorre (lead criado, oportunidade movida), o Django signal dispara imediatamente
- **Cron (a cada 5 minutos):** verifica condicoes temporais (lead sem contato, tarefa vencida, segmentos)

Cada execucao gera um log com: automacao, nodo executado, resultado, dados de entrada, timestamp. Execucoes com erro ficam marcadas para analise.

### Rate Limiting

O sistema controla para nao executar a mesma automacao para o mesmo lead mais de uma vez (ControleExecucao). Isso evita spam e loops infinitos.""",
    },
    {
        'cat': 'Produto', 'destaque': True,
        'titulo': 'Modulo Customer Success — Guia Completo',
        'resumo': 'Clube de Beneficios, Parceiros, Indicacoes, Carteirinha Digital e retencao',
        'tags': 'cs, clube, parceiros, indicacoes, carteirinha, fidelizacao, gamificacao, pontos',
        'conteudo': """## Visao Geral

O Modulo Customer Success (CS) e o sistema de fidelizacao e retencao de clientes da Aurora. Transforma clientes em promotores da marca atraves de gamificacao, beneficios exclusivos e programas de indicacao.

## 1. Clube de Beneficios

Sistema de gamificacao completo para engajar clientes do provedor.

### Como funciona

1. Cliente acessa a landing page do clube (link no boleto, WhatsApp, etc)
2. Se cadastra informando nome e CPF
3. Recebe SMS/WhatsApp com codigo OTP para validacao
4. Ao entrar, pode girar a roleta, resgatar cupons, indicar amigos

### Sistema de Pontos

O clube usa dois tipos de pontos:
- **Saldo:** moeda virtual que o cliente gasta (resgatar premios, cupons)
- **XP (Experiencia):** acumula e nunca diminui, serve para subir de nivel

**Regras de pontuacao configuráveis:**
- Cadastro no clube: X pontos
- Confirmar telefone (OTP): X pontos
- Indicacao que converte: X pontos
- Compra de plano upgrade: X pontos
- Aniversario: X pontos
- Missoes especiais: X pontos

### Niveis

5 niveis padrao (configuráveis por provedor):
| Nivel | XP Minimo | Beneficios |
|-------|-----------|-----------|
| Iniciante | 0 | Acesso basico ao clube |
| Bronze | 100 | Cupons exclusivos nivel Bronze |
| Prata | 500 | Cupons Prata + 1 giro extra na roleta |
| Ouro | 1.500 | Cupons Ouro + 2 giros extras |
| Diamante | 5.000 | Todos os cupons + 3 giros extras + prioridade suporte |

### Roleta Premiada

Mecanica de gamificacao visual com roleta que gira e sorteia premios.

**Configuracoes:**
- Premios com nome, descricao, probabilidade e imagem
- Giros diarios (padrao: 1 por dia, mais por nivel)
- Cooldown entre giros
- Assets visuais customizaveis (fundo, seta, centro)

**Tipos de premio:** desconto em mensalidade, cupom de parceiro, pontos bonus, brinde fisico, upgrade temporario.

### Landing Page Publica

Cada provedor tem sua landing page do clube personalizada:
- URL: `seudominio.com/clube/`
- Logo, cores e banners do provedor
- Secoes: banner principal, beneficios, parceiros em destaque, como funciona
- Formulario de cadastro integrado

### Dashboard do Membro

Apos login, o membro acessa:
- Saldo de pontos e XP
- Nivel atual e progresso para o proximo
- Roleta (se tiver giros disponiveis)
- Cupons disponiveis para resgate
- Historico de pontos (extrato)
- Indicacoes realizadas e status
- Carteirinha digital

## 2. Parceiros

Rede de parceiros locais que oferecem descontos aos membros do clube.

### Como funciona

1. Provedor cadastra parceiros (restaurantes, academias, lojas)
2. Cada parceiro pode ter multiplos cupons de desconto
3. Membros do clube resgatam cupons pelo app/site
4. Parceiro valida o cupom pelo codigo unico

### Tipos de cupom

- **Gratuito:** qualquer membro pode resgatar
- **Por pontos:** custa X pontos de saldo
- **Por nivel:** disponivel apenas para membros de determinado nivel ou superior

### Gestao de parceiros

- Categorias: alimentacao, saude, educacao, lazer, servicos, varejo
- Dados: nome, CNPJ, contato, endereco, logo, descricao
- Status: pendente, ativo, inativo
- Cupons vinculados com validade, quantidade maxima e regras

## 3. Indicacoes

Programa "indique e ganhe" para aquisicao organica de clientes.

### Fluxo

1. Membro compartilha seu link/codigo de indicacao
2. Indicado se cadastra usando o link
3. Sistema rastreia a indicacao automaticamente
4. Quando o indicado se torna cliente ativo, ambos ganham pontos

### Configuracoes

- Pontos para quem indica (ex: 200 pontos)
- Pontos para quem foi indicado (ex: 100 pontos)
- Limite de indicacoes por membro (ou ilimitado)
- Condicao de conversao: cadastro, primeiro pagamento, X dias ativo

### Rastreamento

- Status da indicacao: pendente, convertida, expirada, cancelada
- Dashboard com: total de indicacoes, convertidas, taxa de conversao, top indicadores

## 4. Carteirinha Digital

Cartao de membro digital com QR code para identificacao.

### Funcionalidades

- Template visual configuravel (cores, layout, campos exibidos)
- QR code unico por membro (valida identidade)
- Dados exibidos: nome, nivel, foto, validade, numero do membro
- Regras de atribuicao automatica (ex: todos os membros Bronze+)
- Visualizacao em tela cheia no celular (funciona como cartao fisico)

## 5. NPS e Retencao (Em Desenvolvimento)

### NPS
- Envio automatico de pesquisa de satisfacao
- Calculo do Net Promoter Score
- Alertas para detratores

### Retencao
- Health Score por cliente (baseado em: pagamentos, suporte, engajamento)
- Alertas automaticos para clientes em risco
- Acoes preventivas via automacao (desconto, contato proativo)""",
    },
    {
        'cat': 'Produto', 'destaque': False,
        'titulo': 'Inbox e Atendimento Omnichannel',
        'resumo': 'Central de atendimento multicanal com WhatsApp, tickets, base de conhecimento e widget',
        'tags': 'inbox, atendimento, suporte, whatsapp, tickets, omnichannel, widget',
        'conteudo': """## Visao Geral

O Inbox e a central de atendimento unificada da Aurora. Reune todas as conversas de todos os canais em uma unica interface, permitindo que agentes atendam clientes de forma eficiente.

## Interface (3 paineis)

### Painel Esquerdo: Lista de Conversas
- Filtros por status: Todas, Abertas, Pendentes, Resolvidas
- Filtros por atribuicao: Minhas, Nao atribuidas, Todas
- Busca por nome, telefone ou conteudo
- Ordenacao por data (mais recente primeiro)
- Badge com contagem de nao lidas
- Preview da ultima mensagem

### Painel Central: Chat
- Historico completo de mensagens
- Identificacao visual: mensagens do cliente (esquerda), do agente (direita), do bot (centro)
- Envio de texto, emojis, arquivos (imagem, video, audio, PDF, documentos)
- Respostas rapidas (digite "/" para selecionar)
- Notas privadas (visiveis apenas para agentes)
- Indicador de "digitando..."

### Painel Direito: Contexto
- Dados do contato (nome, telefone, e-mail)
- Acoes da conversa: atribuir agente, equipe, prioridade, etiquetas
- Informacoes do lead/CRM (se vinculado)
- Notas internas do contato
- Ticket de suporte vinculado
- Busca na base de conhecimento
- Conversas anteriores do mesmo contato

## Funcionalidades Principais

### Atribuicao de Conversas
- Manual: selecionar agente no dropdown
- "Atribuir a mim": um clique para assumir a conversa
- Por equipe: atribuir a uma equipe (distribuicao automatica)
- Automatica: regras de roteamento por fila

### Status da Conversa
- **Aberta:** conversa ativa, aguardando resolucao
- **Pendente:** aguardando resposta do cliente ou acao externa
- **Resolvida:** atendimento concluido (sai da lista principal)

### Transferencia
- Para outro agente (com motivo opcional)
- Para outra equipe
- Para outra fila
- Historico de transferencias mantido

### Prioridade
4 niveis: Baixa, Normal, Alta, Urgente

### Etiquetas
Tags coloridas para categorizar conversas (ex: "financeiro", "tecnico", "cancelamento")

### Respostas Rapidas
Templates pre-configurados que o agente acessa digitando "/":
- Saudacao padrao
- Informacoes de planos
- Procedimentos tecnicos
- Encerramento

## Canais Suportados

| Canal | Provider | Status |
|-------|----------|--------|
| WhatsApp | Uazapi | Ativo |
| WhatsApp | Evolution API | Planejado |
| WhatsApp | Meta Cloud API | Planejado |
| WhatsApp | Twilio | Planejado |
| E-mail | SMTP/IMAP | Planejado |
| Chat (Widget) | Proprio | Ativo |

## Widget de Chat

Widget embedavel no site do provedor para atendimento em tempo real.

**Funcionalidades:**
- 3 abas: Inicio, Mensagens, Ajuda
- Rastreamento de visitantes
- Customizacao visual (cores, textos, logo)
- Validacao de CORS (seguranca)
- Polling a cada 5 segundos para novas mensagens
- Zero dependencias externas (JS puro)

**Instalacao:** copiar um snippet de script no site do provedor.

## Tickets de Suporte

Sistema formal de tickets com SLA para demandas que exigem acompanhamento.

### Ciclo de vida
```
Aberto → Em Andamento → Aguardando Cliente → Resolvido → Fechado
```

### SLA
- Configuravel por plano do provedor (Starter, Start, Pro)
- Tempo de primeira resposta (em horas)
- Tempo de resolucao (em horas)
- Alerta automatico quando SLA esta proximo de ser violado

### Criacao de ticket
- A partir de uma conversa do Inbox (1 clique)
- Manualmente pelo painel de suporte
- Via API (integracoes externas)

## Base de Conhecimento

Central de artigos e documentacao para autoatendimento.

**Funcionalidades:**
- Categorias com icones e cores
- Artigos com conteudo rico, tags e resumo
- Busca por titulo, conteudo e tags
- Artigos em destaque na pagina principal
- Feedback por artigo (util sim/nao)
- Contador de visualizacoes
- Integrado ao Inbox (agente pesquisa artigos durante atendimento)
- Pagina de gerenciamento (criar, editar, remover categorias e artigos)""",
    },
    {
        'cat': 'Produto', 'destaque': False,
        'titulo': 'Sistema de Permissoes',
        'resumo': 'Perfis, funcionalidades granulares e controle de acesso por modulo',
        'tags': 'permissoes, perfis, seguranca, funcionalidades, acesso',
        'conteudo': """## Visao Geral

A Aurora possui um sistema de permissoes em 3 camadas que permite controlar exatamente o que cada usuario pode acessar.

## As 3 Camadas

### Camada 1: Modulo
Controle de acesso por modulo do sistema (Comercial, Marketing, CS, etc). Se o usuario nao tem acesso ao modulo, nao ve nada daquela area.

### Camada 2: Funcionalidade
Dentro de cada modulo, 35 funcionalidades granulares que podem ser ligadas ou desligadas individualmente.

### Camada 3: Escopo
Dentro de cada funcionalidade, o escopo de dados visiveis:
- **Meus dados:** apenas registros proprios
- **Equipe:** registros da sua equipe
- **Todos:** todos os registros do tenant

## Funcionalidades por Modulo

### Comercial (9 funcionalidades)
- Ver dashboard comercial
- Ver pipeline/Kanban
- Gerenciar oportunidades
- Ver desempenho de vendedores
- Gerenciar metas
- Gerenciar equipes de vendas
- Gerenciar leads
- Gerenciar atendimentos (bot)
- Configurar modulo comercial

### Marketing (7 funcionalidades)
- Ver leads/contatos
- Gerenciar campanhas
- Gerenciar segmentos
- Gerenciar automacoes
- Ver relatorios de marketing
- Configurar modulo marketing
- Gerenciar fluxos de atendimento

### Customer Success (6 funcionalidades)
- Ver dashboard CS
- Gerenciar membros do clube
- Gerenciar cupons/parceiros
- Aprovar parceiros
- Gerenciar indicacoes
- Configurar modulo CS

### Inbox / Suporte (8 funcionalidades)
- Ver conversas (minhas)
- Ver conversas (equipe)
- Ver conversas (todas)
- Responder conversas
- Transferir conversas
- Resolver conversas
- Gerenciar tickets
- Configurar inbox/suporte

### Configuracoes (5 funcionalidades)
- Gerenciar usuarios
- Gerenciar perfis de permissao
- Gerenciar planos e funcionalidades
- Gerenciar fluxos de atendimento
- Configurar notificacoes

## Perfis Padrao

A Aurora vem com 11 perfis pre-configurados:

| Perfil | Modulo | Descricao |
|--------|--------|-----------|
| Vendedor | Comercial | Ve apenas seus leads e oportunidades |
| Supervisor Comercial | Comercial | Ve dados da equipe, gerencia metas |
| Gerente Comercial | Comercial | Acesso total ao modulo comercial |
| Analista Marketing | Marketing | Cria campanhas e automacoes |
| Gerente Marketing | Marketing | Acesso total ao marketing |
| Operador CS | CS | Gerencia membros e cupons |
| Gerente CS | CS | Acesso total ao CS |
| Agente Suporte | Suporte | Atende conversas e tickets |
| Supervisor Suporte | Suporte | Ve todas as conversas, transfere |
| Gerente Suporte | Suporte | Acesso total ao suporte |
| Admin | Todos | Acesso completo a tudo |

## Como Gerenciar

### Criar/Editar Perfis
1. Acesse **Configuracoes > Usuarios > Perfis**
2. Clique em "Novo Perfil" ou edite um existente
3. Marque as funcionalidades desejadas (checkboxes)
4. Salve

### Atribuir Perfil a Usuario
1. Acesse **Configuracoes > Usuarios**
2. Selecione o usuario
3. Escolha o perfil de permissao no dropdown
4. Salve

### Superusuarios
Usuarios marcados como superusuario (admin Django) tem acesso total automatico, independente de perfil atribuido.""",
    },

    # ═══════════════════════════════════════════
    # VENDAS
    # ═══════════════════════════════════════════
    {
        'cat': 'Vendas', 'destaque': True,
        'titulo': 'Pitch de Vendas — Script Completo',
        'resumo': 'Script detalhado para apresentar a Aurora a provedores de internet',
        'tags': 'vendas, pitch, script, apresentacao, prospecção',
        'conteudo': """## Antes de ligar/visitar

**Pesquise o provedor:**
- Quantos clientes tem? (site, redes sociais, Teleco)
- Qual ERP usa? (perguntar ou verificar no site)
- Tem equipe de vendas ou e centralizado?
- Tem presenca digital? (site, Instagram, Google)

## Abertura (30 segundos)

"Ola [nome]! Sou [seu nome] da AuroraISP. A gente ajuda provedores de internet a vender mais, perder menos clientes e fidelizar atraves de tecnologia e inteligencia artificial."

"Posso te fazer 3 perguntas rapidas pra entender se faz sentido conversarmos?"

## Perguntas de Qualificacao (2 minutos)

1. **"Quantos clientes ativos voce tem hoje?"**
   → Mapeia o porte. ICP: 500 a 50.000.

2. **"Quantas pessoas cuidam da parte comercial (vendas + atendimento)?"**
   → Mapeia a dor de custo e eficiencia.

3. **"Qual ERP voce usa?"**
   → HubSoft = fit perfeito. MK/IXC = integracao via API. Outro = avaliar.

4. **"Como funciona o processo de venda hoje? Lead chega como?"**
   → Identifica gargalos. Geralmente: WhatsApp manual, planilha, sem controle.

5. **"Quantos leads por mes voce recebe, mais ou menos?"**
   → Mapeia volume. Mesmo que nao saiba, ja revela que nao tem controle.

6. **"Voce tem algum programa de fidelizacao ou indicacao?"**
   → Abre a porta para o modulo CS.

## Diagnostico (1 minuto)

Com base nas respostas, identifique as 2 maiores dores:

| Dor identificada | Modulo Aurora |
|------------------|---------------|
| "Perco leads no WhatsApp" | Comercial (bot + captura) |
| "Nao sei quantos leads recebo" | Comercial (dashboard) |
| "Vendedor esquece de retornar" | CRM (tarefas + alertas) |
| "Processo de venda e manual" | Cadastro digital + ERP |
| "Nao consigo medir ROI de marketing" | Marketing (campanhas) |
| "Clientes cancelam muito" | CS (clube + retencao) |
| "Nao tenho indicacoes" | CS (programa de indicacoes) |

## Apresentacao da Solucao (3 minutos)

**Adapte conforme as dores. Nao apresente tudo, foque no que resolve o problema.**

### Se a dor e vendas/leads:
"Com a Aurora, o lead chega pelo WhatsApp, o bot qualifica automaticamente, coleta documentos, gera o contrato digital e ativa direto no [ERP]. O vendedor so precisa acompanhar pelo CRM. Temos um provedor que faz 400 vendas digitais por mes com 2 pessoas."

### Se a dor e controle/gestao:
"O CRM da Aurora e um Kanban visual. Voce ve todas as oportunidades, o estagio de cada uma, quem e o responsavel, quanto tempo esta parada. Tem metas, desempenho por vendedor e alertas automaticos."

### Se a dor e fidelizacao/churn:
"O modulo de CS cria um clube de beneficios pros seus clientes. Tem roleta premiada, cupons de parceiros locais, programa de indicacoes. O cliente ganha pontos por ficar, por indicar amigos, por interagir. Isso reduz churn e gera vendas organicas."

## Case de Prova

"Um provedor com 30.000 clientes, que usava planilha e WhatsApp manual, hoje recebe 1.000 leads por mes pela Aurora. 400 viram vendas digitais. Antes precisava de 8 pessoas na equipe comercial, hoje sao 2. A economia anual e de R$ 284.400."

## Precos (so se perguntarem)

"Temos 3 niveis por modulo. O Comercial Starter comeca em R$ 297/mes. O Pro, com CRM completo, e R$ 897/mes mais R$ 7 por venda finalizada. Nao tem limite de volume."

"O ROI medio e de 5x em 90 dias. Se voce faz 50 vendas por mes, o sistema ja se paga no primeiro mes."

## Proximo Passo

"Posso agendar uma demo de 30 minutos pra te mostrar ao vivo? Vou criar um ambiente de teste com o logo da [provedor] e simular o fluxo completo."

**Se hesitar:**
"Sem compromisso. Em 30 minutos voce vai ver exatamente como funciona e ai decide se faz sentido. Qual o melhor horario essa semana?"

## Apos a Demo

1. Enviar resumo por WhatsApp com os pontos principais
2. Enviar proposta comercial personalizada
3. Agendar follow-up em 3 dias
4. Se nao responder, follow-up em 7 dias
5. Maximo 5 tentativas de follow-up""",
    },
    {
        'cat': 'Vendas', 'destaque': True,
        'titulo': 'Objecoes Comuns e Como Contornar',
        'resumo': 'Respostas detalhadas para as principais objecoes de provedores',
        'tags': 'vendas, objecoes, contorno, argumentos, negociacao',
        'conteudo': """## Guia de Contorno de Objecoes

### "Ja tenho um sistema / Ja uso o [concorrente]"

**O que o provedor quer dizer:** "Nao quero trocar tudo de novo."

**Resposta:**
"A Aurora nao substitui seu ERP. Na verdade, integramos com ele. Se voce usa HubSoft, a integracao e nativa: o lead entra pelo WhatsApp e sai como contrato ativado la dentro. Se usa MK ou IXC, integramos via API. A Aurora e uma camada de inteligencia em cima do que voce ja usa."

**Se mencionar concorrente especifico (ex: ISPRO AI):**
"Conhego o [concorrente]. A diferenca e que a Aurora ja esta em producao real, com case comprovado. Temos um provedor fazendo 400 vendas digitais/mes. Alem disso, a integracao com HubSoft e nativa e profunda, nao e apenas webhook."

---

### "E muito caro" / "Nao tenho orcamento"

**O que o provedor quer dizer:** "Nao vejo o retorno." ou "Preciso justificar internamente."

**Resposta:**
"Entendo. Vamos fazer as contas juntos. Quanto voce gasta por mes com a equipe comercial? [esperar]"

"Um vendedor CLT custa em media R$ 2.500/mes com encargos. Se a Aurora automatiza o trabalho de 3 vendedores, sao R$ 7.500/mes de economia. O plano Comercial Pro custa R$ 897/mes + R$ 7 por venda. Se voce faz 100 vendas/mes, o custo total e R$ 1.597. O ROI e de quase 5x."

"E o Starter comeca em R$ 297/mes. Sem taxa por venda. Para comecar a testar, e menos que um terco de um salario."

**Tabela rapida de ROI:**

| Vendas/mes | Custo Aurora (Pro) | Economia estimada | ROI |
|------------|-------------------|-------------------|-----|
| 50 | R$ 1.247 | R$ 5.000 | 4x |
| 100 | R$ 1.597 | R$ 7.500 | 4.7x |
| 200 | R$ 2.297 | R$ 12.500 | 5.4x |
| 400 | R$ 3.697 | R$ 17.500 | 4.7x |

---

### "Nao tenho tempo para implementar"

**O que o provedor quer dizer:** "Parece complicado."

**Resposta:**
"A implementacao leva de 2 a 4 horas, e a gente faz junto. Configuramos o tenant, integramos com o ERP, ativamos o bot e o CRM. Em uma tarde voce ja esta operando."

"O que voce precisa nos passar: credenciais do ERP, numero do WhatsApp, logo e cores. A gente cuida do resto."

---

### "Ja tentei algo parecido e nao funcionou"

**O que o provedor quer dizer:** "Fui frustrado antes, tenho medo de investir de novo."

**Resposta:**
"Faz sentido. A maioria das ferramentas do mercado nao integra de verdade com o ERP. O lead fica preso num CRM separado e alguem precisa digitar tudo no HubSoft manualmente. Na Aurora, o fluxo e end-to-end: lead chega, bot qualifica, documentos sao coletados, contrato e gerado e ativado no ERP. Sem retrabalho."

"Posso te mostrar numa demo de 30 minutos exatamente como funciona. Se nao fizer sentido, voce nao perde nada."

---

### "Preciso pensar" / "Vou avaliar"

**O que o provedor quer dizer:** "Ainda nao estou convencido o suficiente."

**Resposta:**
"Claro, faz todo sentido avaliar com calma. Posso te enviar um resumo por WhatsApp com os pontos que conversamos e os numeros do ROI?"

"E se quiser, posso preparar uma demo personalizada com o logo da [provedor] para voce ver como ficaria na pratica. Sem compromisso. Qual o melhor dia essa semana?"

---

### "Meu provedor e pequeno"

**O que o provedor quer dizer:** "Acho que e so para provedores grandes."

**Resposta:**
"O plano Starter foi feito exatamente para provedores menores. R$ 297/mes, sem limite de leads, sem taxa por venda. Se voce faz 10 vendas por mes e cada uma economiza 30 minutos de trabalho manual, ja faz sentido."

"E a medida que voce cresce, o sistema escala junto. Comeca com Starter, depois migra para Start ou Pro quando precisar de CRM e automacoes mais avancadas."

---

### "Nao uso HubSoft"

**O que o provedor quer dizer:** "Sera que funciona pro meu ERP?"

**Resposta:**
"A integracao mais profunda e com o HubSoft, mas a Aurora tambem funciona com MK Solutions, IXCSoft e outros ERPs que tenham API REST. Precisamos avaliar caso a caso qual o nivel de integracao possivel."

"Mesmo sem integracao com ERP, os modulos de CRM, marketing e clube de beneficios funcionam de forma independente. A integracao com ERP automatiza a ativacao do contrato, mas nao e obrigatoria para comecar."

---

### "Minha equipe nao vai usar"

**O que o provedor quer dizer:** "Tenho medo de resistencia interna."

**Resposta:**
"A Aurora e mais simples que um WhatsApp Web. O vendedor abre o Inbox, ve as conversas, responde. O CRM e um Kanban visual, arrasta o card e pronto. Nao precisa de treinamento longo."

"Alem disso, o bot faz a parte mais chata (qualificacao, coleta de documentos). O vendedor so entra quando o lead ja esta quente e com tudo preenchido."

"E as metricas de desempenho motivam a equipe: ranking, metas, dashboard. Vira uma competicao saudavel." """,
    },
    {
        'cat': 'Vendas', 'destaque': True,
        'titulo': 'Tabela de Precos e Planos',
        'resumo': 'Precos detalhados por modulo e plano, modelo de cobranca e simulacoes',
        'tags': 'precos, planos, precificacao, valores, starter, start, pro',
        'conteudo': """## Modelo de Precificacao

A Aurora cobra uma **mensalidade fixa por modulo** + uma **taxa transacional variavel** mensal. Nao ha limite de volume.

## Precos por Modulo

### Modulo Comercial

| | Starter | Start | Pro |
|---|---------|-------|-----|
| Mensalidade | R$ 297/mes | R$ 497/mes | R$ 897/mes |
| Transacional | — | R$ 7/venda | R$ 7/venda |
| Leads | Ilimitados | Ilimitados | Ilimitados |
| Bot/Atendimento | Basico | Avancado | Avancado |
| Cadastro Digital | Sim | Sim | Sim |
| Viabilidade | Sim | Sim | Sim |
| CRM Kanban | — | — | Completo |
| Equipes/Metas | — | — | Sim |
| Segmentos CRM | — | — | Sim |

**O que conta como "venda":** contrato finalizado e validado no ERP.

### Modulo Marketing

| | Starter | Start | Pro |
|---|---------|-------|-----|
| Mensalidade | R$ 197/mes | R$ 397/mes | R$ 697/mes |
| Transacional | — | R$ 0,05/contato/mes | R$ 0,05/contato/mes |
| Campanhas | Basico | Avancado | Avancado |
| Segmentos | Manuais | Dinamicos | Dinamicos |
| Automacoes | — | Basicas (5) | Ilimitadas |
| Editor Visual | — | — | Sim |

**O que conta como "contato":** lead ativo na base (nao removido/cancelado).

### Modulo Customer Success

| | Starter | Start | Pro |
|---|---------|-------|-----|
| Mensalidade | R$ 197/mes | R$ 397/mes | R$ 697/mes |
| Transacional | — | R$ 0,15/cliente ativo | R$ 0,15/cliente ativo |
| Clube de Beneficios | Basico | Completo | Completo |
| Roleta | Sim | Sim | Personalizada |
| Parceiros/Cupons | Ate 10 | Ilimitados | Ilimitados |
| Indicacoes | Basico | Completo | Completo |
| Carteirinha | — | Sim | Personalizada |
| NPS | — | — | Sim |
| Retencao | — | — | Sim |

**O que conta como "cliente ativo":** membro ativo no clube de beneficios.

## Simulacoes de Custo

### Provedor Pequeno (1.000 clientes, 30 vendas/mes)

| Stack | Custo mensal |
|-------|-------------|
| Comercial Starter | R$ 297 |
| **Total** | **R$ 297/mes** |

### Provedor Medio (5.000 clientes, 100 vendas/mes, 2.000 leads)

| Stack | Custo mensal |
|-------|-------------|
| Comercial Start | R$ 497 + R$ 700 (100 vendas) = R$ 1.197 |
| Marketing Start | R$ 397 + R$ 100 (2.000 contatos) = R$ 497 |
| CS Start | R$ 397 + R$ 300 (2.000 membros) = R$ 697 |
| **Total** | **R$ 2.391/mes** |

### Provedor Grande (20.000 clientes, 400 vendas/mes, 8.000 leads)

| Stack | Custo mensal |
|-------|-------------|
| Comercial Pro | R$ 897 + R$ 2.800 (400 vendas) = R$ 3.697 |
| Marketing Pro | R$ 697 + R$ 400 (8.000 contatos) = R$ 1.097 |
| CS Pro | R$ 697 + R$ 1.800 (12.000 membros) = R$ 2.497 |
| **Total** | **R$ 7.291/mes** |

## ROI Estimado

- Economia media por venda digitalizada: R$ 45 (tempo do vendedor + retrabalho)
- Economia por lead qualificado pelo bot: R$ 15
- Reducao de churn com clube: 2 a 5 pontos percentuais

**ROI medio:** 2,4x a 5x em 90 dias, dependendo do volume.

## Condicoes Especiais

- **Trial 14 dias:** disponivel para provedores com HubSoft
- **Parceiros comerciais:** 30% do lucro liquido por cliente indicado
- **Desconto anual:** a definir""",
    },

    # ═══════════════════════════════════════════
    # INTEGRACOES
    # ═══════════════════════════════════════════
    {
        'cat': 'Integrações', 'destaque': True,
        'titulo': 'Integracao com HubSoft (ERP)',
        'resumo': 'Configuracao, endpoints consumidos e enviados, autenticacao OAuth2',
        'tags': 'hubsoft, erp, integracao, api, oauth2',
        'conteudo': """## Visao Geral

A integracao com o HubSoft e o diferencial central da Aurora. Permite que o fluxo comercial seja completamente automatizado: lead entra pelo WhatsApp e sai como contrato ativado no ERP.

## Autenticacao

A API do HubSoft usa **OAuth2** com as seguintes credenciais:
- URL da API (ex: https://api.hubsoft.com.br/v1/)
- Client ID
- Client Secret
- Username (usuario da API)
- Password (senha da API)

O token OAuth2 e renovado automaticamente pela Aurora quando expira.

## O que a Aurora consome do HubSoft

### 1. Consulta de cliente por CPF
- Verifica se o lead ja e cliente do provedor
- Retorna dados cadastrais e status

### 2. Planos disponiveis
- Lista planos de internet ativos
- Usado no cadastro digital para o cliente escolher o plano
- Sincroniza automaticamente: nome, velocidade, valor

### 3. Status do contrato
- Verifica se o contrato foi ativado
- Atualiza o status do lead automaticamente

### 4. Situacao financeira
- Consulta inadimplencia do cliente
- Usado pelo modulo CS para health score

### 5. Viabilidade tecnica
- Verifica cobertura por CEP/endereco
- Retorna se o provedor atende aquela regiao

### 6. Vencimentos disponiveis
- Lista os dias de vencimento aceitos pelo provedor

## O que a Aurora envia para o HubSoft

### 1. Novo prospecto/lead
- Cria registro de prospecto no HubSoft com dados do lead
- Campos: nome, CPF, telefone, e-mail, endereco, plano escolhido

### 2. Documentos
- Envia imagens de RG, CPF, comprovante de residencia
- Vincula ao prospecto criado

### 3. Contrato aceito
- Sinaliza que o cliente aceitou o contrato digital
- Dispara o fluxo de ativacao no HubSoft

### 4. Status de processamento
- Atualiza o status do prospecto conforme o fluxo avanca
- Permite acompanhamento no ERP

## Configuracao

### Pelo Painel de Integracoes

1. Acesse **Configuracoes > Integracoes**
2. Clique em **"Nova Integracao"**
3. Selecione tipo **HubSoft**
4. Preencha: URL da API, Client ID, Client Secret, Username, Password
5. Clique **"Testar Conexao"** para validar
6. Salve

### IDs Necessarios

Para a integracao funcionar corretamente, o provedor precisa fornecer:
- **id_origem:** identificador da origem "Aurora" no HubSoft
- **id_vendedor:** identificador do vendedor padrao para leads da Aurora
- **id_servico:** identificador do servico/plano principal

Esses IDs sao configurados no painel de integracoes apos a conexao ser estabelecida.

## Outros ERPs Suportados

| ERP | Tipo de Integracao | Status |
|-----|-------------------|--------|
| HubSoft | API REST OAuth2 (nativa) | Ativo |
| MK Solutions | API REST | Planejado |
| IXCSoft | API REST | Planejado |
| SGP | A avaliar | Futuro |
| Controllr | A avaliar | Futuro |
| Topapp | A avaliar | Futuro |

Para ERPs sem API, a integracao pode ser feita via N8N (webhooks) com adaptacoes.""",
    },
    {
        'cat': 'Integrações', 'destaque': False,
        'titulo': 'Integracao com WhatsApp (Uazapi)',
        'resumo': 'Configurar WhatsApp via Uazapi: webhook, envio de mensagens, tipos suportados',
        'tags': 'uazapi, whatsapp, webhook, mensageria, integracao',
        'conteudo': """## Visao Geral

O Uazapi e o provedor de WhatsApp atualmente integrado a Aurora. Permite enviar e receber mensagens de WhatsApp diretamente pelo Inbox.

## Configuracao

### 1. Criar a Integracao

1. Acesse **Configuracoes > Integracoes**
2. Clique em **"Nova Integracao"**
3. Selecione tipo **Uazapi**
4. Preencha:
   - **Nome:** ex: "WhatsApp Principal"
   - **URL:** URL da sua instancia Uazapi (ex: https://suainstancia.uazapi.com)
   - **Token:** token de autenticacao da instancia
5. Clique **"Testar Conexao"**
6. Salve

### 2. Configurar o Canal no Inbox

Apos criar a integracao, um canal WhatsApp e criado automaticamente no Inbox vinculado a essa integracao.

### 3. Configurar o Webhook no Uazapi

No painel do Uazapi, configure o webhook:
- **URL:** `https://seudominio.com/inbox/api/webhook/uazapi/{canal_id}/`
- **Eventos:** messages (mensagens recebidas)

O `canal_id` e o ID do canal criado no passo anterior (visivel na pagina de integracoes).

## Tipos de Mensagem Suportados

### Envio (Aurora → WhatsApp)

| Tipo | Descricao | Endpoint Uazapi |
|------|-----------|-----------------|
| Texto | Mensagem de texto simples | /send/text |
| Imagem | Imagem com legenda opcional | /send/media |
| Video | Video com legenda opcional | /send/media |
| Audio | Mensagem de audio | /send/media |
| Documento | PDF, DOC, XLS, etc | /send/media |
| VCard | Cartao de contato | /send/vcard |
| Localizacao | Pin no mapa | /send/location |
| Menu Interativo | Botoes ou lista de opcoes | /send/menu |
| Carrossel | Cards com imagem e botoes | /send/carousel |
| Botao PIX | Botao de pagamento PIX | /send/pix |

### Recebimento (WhatsApp → Aurora)

Todos os tipos de mensagem recebidos sao processados:
- Texto
- Imagem (com ou sem legenda)
- Video
- Audio
- Documento
- Localizacao
- Contato (VCard)
- Sticker

As midias recebidas sao armazenadas e exibidas no Inbox.

## Formato do Webhook

O Uazapi envia webhooks no seguinte formato:

```
{
    "EventType": "messages",
    "message": {
        "text": "Ola, quero contratar",
        "type": "text"
    },
    "chat": {
        "phone": "+5553912345678",
        "name": "Joao Silva"
    },
    "key": {
        "id": "MSG123456"
    }
}
```

A Aurora processa automaticamente:
1. Identifica o contato pelo telefone
2. Cria ou localiza a conversa no Inbox
3. Registra a mensagem
4. Se nao existe lead, cria automaticamente
5. Notifica os agentes online

## Troubleshooting

**Mensagens nao chegam no Inbox:**
- Verifique se o webhook esta configurado no Uazapi
- Verifique se a URL do webhook esta acessivel externamente
- Verifique se o token esta correto
- Verifique os logs em Configuracoes > Integracoes > Logs

**Mensagens nao sao enviadas:**
- Verifique se a instancia Uazapi esta conectada (status: connected)
- Verifique se o token esta correto
- Verifique se o numero de destino esta no formato correto (+5500000000000)

**Teste de conexao falha:**
- Verifique se a URL da instancia esta correta
- Verifique se a instancia esta online
- Verifique se o token nao expirou""",
    },
    {
        'cat': 'Integrações', 'destaque': False,
        'titulo': 'Integracao com N8N (Orquestracao)',
        'resumo': 'Workflows essenciais, APIs disponiveis e configuracao de webhooks',
        'tags': 'n8n, automacao, webhook, api, orquestracao',
        'conteudo': """## Visao Geral

O N8N e a ferramenta de orquestracao que conecta a Aurora com servicos externos. Funciona como uma "cola" entre sistemas, processando webhooks e executando acoes automatizadas.

## Workflows Essenciais

### 1. Bot de Atendimento
**Gatilho:** webhook da Aurora quando nova mensagem chega
**Fluxo:** recebe mensagem → consulta estado do atendimento → gera resposta → envia via Aurora API
**Usado para:** qualificacao automatica de leads via WhatsApp

### 2. Deteccao de Campanha
**Gatilho:** webhook da Aurora quando lead criado
**Fluxo:** analisa texto da primeira mensagem → busca palavra-chave → vincula lead a campanha
**Usado para:** rastreamento de ROI de campanhas de trafego

### 3. OTP (Codigo de Verificacao)
**Gatilho:** webhook da Aurora quando membro do clube solicita OTP
**Fluxo:** gera codigo → envia via WhatsApp → retorna para Aurora validar
**Usado para:** verificacao de telefone no Clube de Beneficios

### 4. Notificacoes
**Gatilho:** webhook da Aurora para eventos diversos
**Fluxo:** formata mensagem → envia via WhatsApp/e-mail para destinatario
**Usado para:** alertas de tarefas vencidas, novas conversas, metas atingidas

### 5. Sincronizacao com ERP
**Gatilho:** webhook da Aurora quando venda finalizada
**Fluxo:** coleta dados do lead → cria prospecto no ERP → envia documentos → ativa contrato
**Usado para:** integracao com ERPs que nao tem API REST direta

### 6. Consultas ao ERP
**Gatilho:** API call da Aurora
**Fluxo:** recebe CPF/dados → consulta no ERP → retorna resultado
**Usado para:** verificacao de viabilidade, consulta de planos, status de cliente

## APIs da Aurora para N8N

O N8N se comunica com a Aurora atraves de APIs autenticadas por token.

### Endpoints Disponiveis

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | /api/n8n/receber-mensagem/ | Envia mensagem para o Inbox |
| POST | /api/n8n/atualizar-status/ | Atualiza status de entrega |
| GET | /api/v1/leads/ | Lista leads |
| POST | /api/v1/leads/ | Cria lead |
| PATCH | /api/v1/leads/{id}/ | Atualiza lead |
| GET | /api/v1/oportunidades/ | Lista oportunidades CRM |
| POST | /api/v1/oportunidades/ | Cria oportunidade |

### Autenticacao

Todas as APIs requerem token no header:
```
Authorization: Token seu-token-aqui
```

O token e gerado em **Configuracoes > Integracoes > Token API**.

## Configuracao do Webhook

Para a Aurora enviar eventos para o N8N:

1. No N8N, crie um workflow com trigger "Webhook"
2. Copie a URL do webhook gerada
3. Na Aurora, configure a URL do webhook no canal/integracao correspondente
4. Teste enviando um evento (ex: nova mensagem no Inbox)

## Boas Praticas

- Use um N8N dedicado por provedor (nao compartilhe entre tenants)
- Monitore execucoes com falha no painel do N8N
- Configure retry automatico para webhooks criticos
- Mantenha tokens API rotacionados periodicamente""",
    },

    # ═══════════════════════════════════════════
    # ONBOARDING
    # ═══════════════════════════════════════════
    {
        'cat': 'Onboarding', 'destaque': True,
        'titulo': 'Checklist de Implementacao — Novo Cliente',
        'resumo': 'Guia passo a passo completo para implementar um novo provedor na Aurora',
        'tags': 'onboarding, implementacao, checklist, novo-cliente, setup',
        'conteudo': """## Pre-requisitos

Antes de comecar a implementacao, colete do provedor:

**Dados da empresa:**
- Nome fantasia e razao social
- CNPJ
- Slug desejado (ex: megalink, speednet)

**Contrato:**
- Modulos contratados (Comercial, Marketing, CS)
- Plano por modulo (Starter, Start, Pro)
- Periodo de trial (se aplicavel)

**ERP:**
- Tipo (HubSoft, MK, IXC, outro)
- URL da API
- Credenciais (Client ID, Secret, User, Password)
- IDs: id_origem, id_vendedor, id_servico

**Mensageria/WhatsApp:**
- Provedor (Uazapi, Evolution, etc)
- URL da instancia
- Token de autenticacao
- Numero do WhatsApp comercial

**Identidade visual:**
- Logo (PNG, fundo transparente)
- Cores primaria e secundaria (hex)
- Modelo de contrato (PDF ou texto)

---

## Fase 1: Criar o Tenant (15 minutos)

1. Acessar o painel Admin Aurora (/aurora-admin/)
2. Criar novo tenant com os dados da empresa
3. Marcar os modulos ativos e planos
4. Criar usuario admin do provedor
5. Definir senha temporaria e solicitar troca no primeiro acesso

**Verificar:** Login funciona, dashboard carrega, sidebar mostra apenas modulos contratados.

---

## Fase 2: Configurar Ambiente (30 minutos)

1. Configurar variaveis de ambiente (se necessario)
2. Rodar migrations (se houver pendentes)
3. Configurar SSL e dominio (se dedicado)
4. Rodar seeds: funcionalidades, perfis padrao

**Verificar:** Paginas carregam sem erro, HTTPS funciona.

---

## Fase 3: Popular Dados Iniciais (30 minutos)

### Obrigatorios
- **Planos de internet:** sincronizar com ERP ou cadastrar manualmente
- **Vencimentos:** dias de vencimento aceitos pelo provedor
- **Pipeline CRM:** criar estagios (ou usar padrao: Novo Lead, Primeiro Contato, Qualificacao, Proposta, Negociacao, Ganho, Perdido)

### Se modulo CS ativo
- **Niveis do clube:** configurar niveis e XP necessario
- **Regras de pontuacao:** definir quantos pontos por acao
- **Roleta:** configurar premios e probabilidades

---

## Fase 4: Configurar Modulos (1 hora)

### Comercial
- Configurar CRM: pipeline, estagios, SLA de atendimento
- Configurar cadastro digital: logo, cores, campos obrigatorios, documentos aceitos, template de contrato
- Configurar fluxo do bot (perguntas de qualificacao)

### Marketing (se contratado)
- Criar campanhas iniciais
- Configurar segmentos basicos
- Criar primeiras automacoes

### CS (se contratado)
- Configurar landing page do clube
- Cadastrar parceiros iniciais
- Configurar programa de indicacoes
- Personalizar carteirinha digital

---

## Fase 5: Integrar ERP (30 minutos)

1. Criar integracao no painel (Configuracoes > Integracoes)
2. Preencher credenciais
3. Testar conexao
4. Mapear IDs (origem, vendedor, servico)
5. Testar fluxo completo: criar lead → sincronizar com ERP

**Verificar:** Teste de conexao OK, planos sincronizados, prospecto criado no ERP.

---

## Fase 6: Integrar WhatsApp (30 minutos)

1. Criar integracao Uazapi/WhatsApp no painel
2. Configurar token e URL
3. Testar conexao
4. Configurar webhook no provedor de WhatsApp
5. Testar envio e recebimento de mensagem

**Verificar:** Mensagem chega no Inbox, resposta chega no WhatsApp.

---

## Fase 7: Configurar Usuarios e Equipe (30 minutos)

1. Criar usuarios para cada membro da equipe
2. Atribuir perfis de permissao (Vendedor, Supervisor, Gerente, etc)
3. Criar equipes de vendas (se CRM Pro)
4. Definir metas por vendedor (se aplicavel)

---

## Fase 8: Personalizar Visual (15 minutos)

1. Upload do logo na configuracao da empresa
2. Definir cores primaria e secundaria
3. Personalizar landing page do cadastro digital
4. Personalizar landing page do clube (se CS ativo)
5. Configurar template de contrato

---

## Fase 9: Validacao e Go-Live (30 minutos)

### Checklist final

**Infraestrutura:**
- [ ] SSL ativo
- [ ] Variaveis de ambiente configuradas
- [ ] Migrations rodadas
- [ ] Seeds executados (funcionalidades, perfis)
- [ ] Backup configurado

**Funcionalidade:**
- [ ] Login funciona
- [ ] Dashboard carrega
- [ ] Cadastro digital funciona (criar lead de teste)
- [ ] Bot responde no WhatsApp
- [ ] CRM exibe pipeline (se Pro)
- [ ] Tarefas podem ser criadas
- [ ] Relatorios carregam

**Integracoes:**
- [ ] ERP conectado e testado
- [ ] WhatsApp conectado e testado
- [ ] Envio de mensagem funciona
- [ ] Recebimento de mensagem funciona
- [ ] Lead sincronizado com ERP

**Multi-tenancy:**
- [ ] Dados isolados (nao ve dados de outro provedor)
- [ ] Uploads isolados
- [ ] Sidebar filtrada por permissoes

**CS (se ativo):**
- [ ] Landing page do clube acessivel
- [ ] Cadastro de membro funciona
- [ ] OTP funciona
- [ ] Roleta funciona
- [ ] Cupons visiveis

**Tempo total estimado: 3 a 4 horas**""",
    },

    # ═══════════════════════════════════════════
    # TECNICO
    # ═══════════════════════════════════════════
    {
        'cat': 'Técnico', 'destaque': False,
        'titulo': 'Arquitetura do Sistema',
        'resumo': 'Stack tecnologica, apps, multi-tenancy, APIs e infraestrutura',
        'tags': 'tecnico, arquitetura, stack, django, api, multi-tenancy',
        'conteudo': """## Stack Tecnologica

| Componente | Tecnologia |
|-----------|-----------|
| Backend | Python 3.11, Django 5.2 |
| API | Django REST Framework (DRF) |
| Banco de dados | PostgreSQL |
| Servidor web | Gunicorn + Nginx |
| Tarefas | Cron jobs + Django signals |
| Mensageria | Uazapi (WhatsApp), SMTP (e-mail) |
| Orquestracao | N8N |
| Frontend | Django Templates + JavaScript vanilla |
| Editor visual | Drawflow.js (automacoes) |
| PDF | WeasyPrint (contratos) |
| Realtime | Django Channels (WebSocket) |
| CI/CD | GitHub Actions |

## Estrutura de Apps (15 apps)

```
apps/
├── sistema/          → Tenant, PerfilUsuario, configs SaaS, base.html, middleware, decorators
├── comercial/
│   ├── leads/        → LeadProspecto, score, qualificacao
│   ├── atendimento/  → Bot conversacional, fluxos, questoes
│   ├── cadastro/     → Landing page, planos, contrato digital
│   ├── viabilidade/  → Cobertura por CEP
│   └── crm/          → Pipeline, oportunidades, tarefas, metas, equipes
├── marketing/
│   ├── campanhas/    → Campanhas de trafego, deteccao
│   └── automacoes/   → Editor visual, gatilhos, acoes, engine
├── cs/
│   ├── clube/        → Gamificacao, roleta, pontos, niveis
│   ├── parceiros/    → Rede de parceiros, cupons
│   ├── indicacoes/   → Programa de indicacoes
│   └── carteirinha/  → Cartao digital com QR code
├── inbox/            → Chat omnichannel, providers, widget
├── suporte/          → Tickets SLA, base de conhecimento
├── integracoes/      → ERP, WhatsApp, N8N, services
├── dashboard/        → Dashboard principal
├── notificacoes/     → Sistema de notificacoes
└── admin_aurora/     → Painel de gestao do SaaS
```

## Multi-Tenancy

O sistema utiliza multi-tenancy logico (banco compartilhado, dados isolados).

**Componentes:**
- **Tenant model:** representa cada provedor (nome, slug, modulos ativos, plano)
- **TenantMixin:** mixin para todos os models, adiciona FK para Tenant
- **TenantManager:** manager que filtra automaticamente pelo tenant do request
- **TenantMiddleware:** identifica o tenant pela URL/sessao e seta no request

**Isolamento:** todo model que herda TenantMixin so retorna dados do tenant atual. Isso e transparente para as views — basta usar `Model.objects` normalmente.

## API REST

APIs organizadas em 3 camadas:

### 1. APIs Internas (AJAX)
- Autenticacao: SessionAuth (cookie do Django)
- Usadas pelo frontend para operacoes do Inbox, CRM, etc
- Prefixo: varia por app

### 2. APIs V1 (DRF)
- Autenticacao: TokenAuth
- Documentacao: Swagger em /api/docs/
- Prefixo: /api/v1/
- Usadas por integrações externas

### 3. APIs N8N
- Autenticacao: TokenAuth (header Authorization)
- Prefixo: /api/n8n/
- Usadas pelos workflows do N8N

## Provider Pattern (Mensageria)

A mensageria usa o padrao Provider para suportar multiplos provedores de WhatsApp:

```
BaseProvider (ABC)
├── UazapiProvider    → Uazapi (ativo)
├── WebhookProvider   → Webhook generico (N8N)
├── EvolutionProvider → Evolution API (futuro)
├── MetaCloudProvider → Meta Cloud API (futuro)
└── TwilioProvider    → Twilio (futuro)
```

Cada provider implementa: enviar_texto, enviar_imagem, enviar_documento, enviar_audio, parse_webhook.

Para adicionar um novo provider: criar um arquivo em `apps/inbox/providers/`, implementar os metodos e registrar. Zero mudancas no core.

## Permissoes

3 camadas:
1. **Modulo:** acesso sim/nao por modulo
2. **Funcionalidade:** 35 checkboxes granulares
3. **Escopo:** meus dados / equipe / todos

Enforcement via PermissaoMiddleware (URL-based) + template tags + decorators.

## Seguranca

- Secrets em variaveis de ambiente (nunca no codigo)
- EncryptedCharField para credenciais sensiveis
- PIIFilter no logging (remove CPF, telefone dos logs)
- @api_token_required para APIs externas
- @login_required para painel
- @permissao_required para controle granular
- Validacao de uploads (tipo, tamanho)
- Isolamento de tenant em uploads
- CSRF protection em todos os forms
- Rate limiting em APIs publicas""",
    },
    {
        'cat': 'Técnico', 'destaque': False,
        'titulo': 'Guia de Configuracao — Administrador',
        'resumo': 'Todas as configuracoes disponiveis no painel e como ajusta-las',
        'tags': 'configuracao, admin, painel, settings, ajustes',
        'conteudo': """## Configuracoes da Empresa

Acesse: **Configuracoes > Empresa**

- Nome fantasia e razao social
- CNPJ
- Logo (PNG, fundo transparente, recomendado 200x200px)
- Cor primaria e secundaria (hex)
- Endereco e telefone de contato
- E-mail de suporte

## Usuarios

Acesse: **Configuracoes > Usuarios**

### Criar usuario
1. Clique em "Novo Usuario"
2. Preencha: nome, e-mail, senha, perfil de permissao
3. Salve

### Perfis de Permissao
1. Acesse **Configuracoes > Usuarios > Perfis**
2. Crie ou edite perfis
3. Marque as funcionalidades desejadas
4. Atribua o perfil aos usuarios

## Integracoes

Acesse: **Configuracoes > Integracoes**

### Adicionar integracao
1. Clique em "Nova Integracao"
2. Selecione o tipo (HubSoft, Uazapi, N8N, Webhook)
3. Preencha credenciais
4. Teste conexao
5. Salve

### Gerenciar
- **Testar:** verifica se a conexao esta funcionando
- **Editar:** altera credenciais ou configuracoes
- **Ativar/Desativar:** liga ou desliga a integracao sem remover
- **Remover:** exclui permanentemente
- **Logs:** visualiza historico de chamadas e erros

## CRM (Comercial Pro)

Acesse: **Comercial > CRM > Configuracoes**

### Pipeline
- Estagios: criar, reordenar, renomear, definir cor
- SLA por estagio (dias maximo para mover)
- Estagio padrao para novos leads

### Equipes
- Criar equipes de vendas
- Definir supervisor
- Adicionar membros
- Distribuicao automatica de leads (round-robin)

### Metas
- Definir meta mensal por vendedor
- Tipo: quantidade de vendas ou valor total
- Dashboard de acompanhamento

## Cadastro Digital

Acesse: **Comercial > Cadastro > Configuracoes**

- Personalizar visual da landing page (logo, cores, banner)
- Definir campos obrigatorios
- Configurar tipos de documento aceitos
- Editar template do contrato
- Definir planos visiveis
- Definir vencimentos disponiveis

## Inbox

Acesse: **Suporte > Configuracoes**

### Canais
- Gerenciar canais de atendimento (WhatsApp, Widget, etc)
- Configurar horarios de atendimento
- Configurar mensagem fora do horario

### Equipes de atendimento
- Criar equipes
- Definir membros
- Configurar filas de atendimento
- Regras de roteamento automatico

### Respostas rapidas
- Criar templates de resposta
- Categorizar por tipo
- Atalho: digitando "/" no chat

### Etiquetas
- Criar etiquetas com nome e cor
- Usar para categorizar conversas

## Automacoes (Marketing)

Acesse: **Marketing > Automacoes**

- Criar fluxos no editor visual
- Ativar/desativar automacoes
- Ver logs de execucao
- Monitorar erros

## Clube de Beneficios (CS)

Acesse: **CS > Clube > Configuracoes**

- Configurar landing page (banner, cores, textos)
- Definir niveis e XP necessario
- Configurar regras de pontuacao
- Configurar roleta (premios, probabilidades)
- Gerenciar parceiros e cupons
- Configurar programa de indicacoes""",
    },

    # ═══════════════════════════════════════════
    # PERGUNTAS FREQUENTES
    # ═══════════════════════════════════════════
    {
        'cat': 'Perguntas Frequentes', 'destaque': False,
        'titulo': 'Perguntas Frequentes (FAQ)',
        'resumo': 'Respostas para as duvidas mais comuns sobre a Aurora',
        'tags': 'faq, duvidas, perguntas, suporte',
        'conteudo': """## Geral

**O que e a AuroraISP?**
A Aurora e um hub de tecnologia com IA para provedores de internet. Automatiza vendas, marketing e fidelizacao de clientes.

**A Aurora substitui meu ERP?**
Nao. A Aurora complementa o ERP. Integramos com HubSoft, MK, IXC e outros para que o fluxo seja automatizado de ponta a ponta.

**Preciso ter HubSoft para usar?**
Nao. A integracao mais profunda e com o HubSoft, mas a Aurora funciona com outros ERPs via API ou de forma independente.

**Quanto tempo leva para implementar?**
Em media 3 a 4 horas. Configuramos tudo junto: tenant, integracoes, visual, usuarios e dados iniciais.

**Tem periodo de teste?**
Sim, 14 dias gratuitos para provedores com HubSoft.

---

## Comercial

**Como os leads chegam na Aurora?**
Via WhatsApp (bot automatico), landing page de cadastro, importacao manual ou API externa.

**O bot funciona sozinho ou precisa de alguem?**
O bot qualifica automaticamente. So precisa de intervencao humana quando o lead tem duvidas especificas ou solicita atendimento.

**Posso personalizar as perguntas do bot?**
Sim. O fluxo do bot e totalmente configuravel: perguntas, ordem, validacoes e acoes pos-resposta.

**O CRM esta disponivel em todos os planos?**
O CRM Kanban completo (pipeline, tarefas, metas, equipes) esta disponivel no plano Pro. Starter e Start tem gestao basica de leads.

---

## Marketing

**Como funciona a deteccao de campanhas?**
Voce configura palavras-chave por campanha. Quando um lead menciona essa palavra no WhatsApp, e automaticamente vinculado a campanha.

**Posso criar automacoes sem saber programar?**
Sim. O editor visual e drag-and-drop. Voce arrasta blocos (gatilhos, condicoes, acoes) e conecta. Nao precisa de codigo.

**As automacoes funcionam em tempo real?**
Sim para eventos como "lead criado" ou "oportunidade movida" (via signals). Condicoes temporais como "lead sem contato ha 3 dias" sao verificadas a cada 5 minutos via cron.

---

## Customer Success

**O que e o Clube de Beneficios?**
Um programa de fidelizacao gamificado. Clientes ganham pontos, sobem de nivel, resgatam cupons de parceiros e giram a roleta premiada.

**Como os clientes acessam o clube?**
Pela landing page publica (link no boleto, WhatsApp, etc). Se cadastram com nome e CPF, validam por OTP e acessam os beneficios.

**Preciso de parceiros locais?**
E recomendado, mas nao obrigatorio. Os cupons podem ser de descontos do proprio provedor (ex: 10% na proxima mensalidade).

**O programa de indicacoes funciona como?**
Cada membro do clube recebe um link/codigo unico. Quando alguem se cadastra por esse link e se torna cliente, ambos ganham pontos.

---

## Tecnico

**A Aurora e multi-tenant?**
Sim. Cada provedor tem seus dados completamente isolados. Um provedor nao ve dados de outro.

**Qual a disponibilidade do sistema?**
O sistema roda em infraestrutura dedicada com backup automatico. SLA de disponibilidade conforme plano contratado.

**Os dados sao seguros?**
Sim. Credenciais sao criptografadas, logs nao contem dados pessoais (PIIFilter), uploads sao isolados por tenant, e todas as APIs requerem autenticacao.

**Posso usar minha propria instancia de WhatsApp?**
Sim. Voce configura a integracao com o seu provedor de WhatsApp (Uazapi, Evolution, etc). A Aurora nao fornece numero.

---

## Precos

**Quanto custa a Aurora?**
Depende dos modulos contratados. O Comercial Starter comeca em R$ 297/mes. Veja a tabela completa no artigo "Tabela de Precos e Planos".

**Tem taxa por venda?**
Nos planos Start e Pro do modulo Comercial, sim: R$ 7 por venda finalizada e validada no ERP. O Starter nao tem taxa variavel.

**Posso contratar apenas um modulo?**
Sim. Cada modulo e independente. Voce pode comecar com o Comercial e depois adicionar Marketing e CS.

**Tem desconto para pagamento anual?**
Condicoes especiais para pagamento anual estao em definicao. Consulte o comercial.""",
    },
]

# ──────────────────────────────────────────────
# Inserir / Atualizar artigos
# ──────────────────────────────────────────────
for a in artigos:
    cat = cats[a['cat']]
    slug = slugify(a['titulo'])
    art, cr = ArtigoConhecimento.all_tenants.update_or_create(
        tenant=tenant, slug=slug,
        defaults={
            'categoria': cat,
            'titulo': a['titulo'],
            'conteudo': a['conteudo'].strip(),
            'resumo': a['resumo'],
            'tags': a['tags'],
            'autor': user,
            'publicado': True,
            'destaque': a.get('destaque', False),
        }
    )
    print(f"  [{a['cat']}] {a['titulo']} - {'criado' if cr else 'atualizado'}")

total = ArtigoConhecimento.all_tenants.filter(tenant=tenant).count()
print(f"\nTotal: {total} artigos na base de conhecimento")
