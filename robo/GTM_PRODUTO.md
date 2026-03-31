# TecHub — Análise do Produto

> Documento de contexto para go-to-market. Descreve o que o sistema faz hoje, como funciona tecnicamente e quais são seus diferenciais.

---

## 1. O que é o sistema

O **TecHub** (nome comercial do Rob-Vendas) é uma plataforma de gestão comercial construída especificamente para **provedores de internet (ISPs)**. Ele resolve o problema mais crítico do processo de vendas de um ISP: a jornada entre o lead entrando pelo WhatsApp e o cliente sendo ativado no sistema de gestão (ERP).

Essa jornada normalmente envolve 5 ferramentas separadas sem integração:
- WhatsApp Business (contato inicial)
- Planilha ou bloco de notas (cadastro do lead)
- E-mail ou grupo de WhatsApp (coleta de documentos)
- ERP/Billing (HubSoft, Ispfy, etc.) para ativação
- Pasta de arquivos ou Drive (guarda dos contratos)

O TecHub substitui tudo isso com **uma única plataforma integrada**.

---

## 2. Ciclo completo implementado

```
[LEAD ENTRA]
     │
     ▼
WhatsApp ──(N8N)──► Bot qualifica o lead
                         │
                         ▼
                   Sistema registra lead (leads_prospectos)
                   com nome, telefone, CPF, endereço, plano desejado
                         │
                         ▼
                   Fluxo de atendimento inteligente
                   (perguntas configuráveis, validação por IA, roteamento condicional)
                         │
                         ▼
                   Lead é convertido → documentos solicitados via WhatsApp
                         │
                         ▼
                   Documentos recebidos e salvos (foto frente/verso CNH, selfie, comprovante)
                         │
                         ▼
                   Time de vendas valida documentos no painel de Vendas
                   (timer ao vivo mostra há quanto tempo está pendente)
                         │
                         ▼
                   Sistema gera automaticamente:
                   ├── HTML da conversa completa do atendimento (via API Matrix)
                   └── PDF do contrato (via WeasyPrint)
                         │
                         ▼
                   Tudo enviado automaticamente para o HubSoft:
                   ├── Documentos anexados ao contrato do cliente
                   └── Contrato aceito digitalmente via API
                         │
                         ▼
                   [CLIENTE ATIVADO NO HUBSOFT]
```

---

## 3. Módulos atuais

### 3.1 Marketing — Leads
- Listagem de todos os leads com status, origem, valor, data/hora
- Filtros por status, origem, data, valor, canal
- Visualização da conversa completa do atendimento (iframe + PDF)
- Score de qualificação calculado automaticamente (0-100)
- Histórico de tentativas de contato

**Dados do banco (16/03/2026):** 341+ leads cadastrados

### 3.2 Comercial — Vendas
- Listagem de clientes sincronizados com o HubSoft
- Plano contratado, valor, tecnologia, velocidade
- Status de documentação em tempo real com timer ao vivo
- Ações: ver conversa, validar documentos

**Timer de alerta:** fica vermelho piscando se documento estiver pendente há mais de 2 horas

### 3.3 Marketing — Campanhas
- Cadastro de campanhas de tráfego pago (Facebook, Google, Instagram, etc.)
- Detecção automática de palavras-chave nas mensagens de entrada
- Atribuição automática de origem ao lead (qual campanha gerou)
- Métricas por campanha (leads gerados, taxa de conversão)

### 3.4 Configurações — Fluxos de Atendimento
- Criação de fluxos conversacionais sem código
- 20 tipos de questão: texto, número, CPF/CNPJ, CEP, planos, vencimentos, select, IA validation, condicional complexa
- Roteamento condicional entre questões
- Validação por IA para respostas abertas
- Múltiplos fluxos simultâneos (residencial, empresarial, retenção)

### 3.5 Relatórios
- Leads por período
- Clientes ativos
- Atendimentos com métricas de conversão
- Funil de conversão (leads → prospectos → clientes)

### 3.6 Configurações Gerais
- Gestão de usuários
- Notificações (WhatsApp, webhook) por tipo de evento
- Planos de internet e datas de vencimento
- Configuração visual da empresa (logo, cores)

---

## 4. Integrações nativas

| Sistema | Tipo | O que faz |
|---------|------|-----------|
| **HubSoft** | ERP para ISPs | Sincroniza clientes, planos e contratos; envia documentos e aceita contratos via API |
| **N8N** | Automação | Recebe webhooks de WhatsApp e dispara o bot de qualificação; recebe eventos do CRM |
| **Matrix (Megalink)** | API WhatsApp | Busca o histórico completo da conversa de atendimento para gerar o HTML/PDF |
| **ViaCEP** | API pública | Consulta cidade/UF a partir de CEP para verificar viabilidade técnica |
| **WeasyPrint** | Gerador PDF | Converte HTML da conversa em PDF enviado ao contrato no HubSoft |

---

## 5. Stack técnica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Django 5.2.4 |
| Banco de dados | PostgreSQL 15+ |
| Servidor | Gunicorn + Nginx |
| Frontend | Django Templates + Vanilla JS (SPA-like via fetch) |
| CSS | Design system próprio (Inter font, variáveis CSS, FontAwesome 6) |
| PDF | WeasyPrint |
| Automação | N8N (self-hosted) |
| Static files | WhiteNoise |
| Autenticação | Django session-based com LoginRequiredMiddleware |

---

## 6. Arquitetura do banco de dados

### Tabelas existentes (27 models)

| Tabela | Função |
|--------|--------|
| `leads_prospectos` | âncora central — todo cliente começa aqui |
| `historico_contato` | cada interação (WhatsApp, chat, telefone) |
| `clientes_hubsoft` | espelho dos clientes ativados no ERP |
| `servicos_cliente_hubsoft` | plano contratado, velocidade, status |
| `prospectos` | workflow de processamento do lead |
| `fluxos_atendimento` | definição dos fluxos conversacionais |
| `questoes_fluxo` | questões individuais dentro dos fluxos |
| `atendimentos_fluxo` | sessão de atendimento de um lead |
| `respostas_questao` | respostas coletadas no atendimento |
| `documentos_lead` | documentos enviados pelo lead |
| `imagens_lead_prospecto` | URLs das imagens de documentos |
| `campanha_trafego` | campanhas de mídia paga cadastradas |
| `deteccoes_campanha` | atribuição de campanha por palavra-chave |
| `notificacoes` | histórico de notificações enviadas |
| `planos_internet` | catálogo de planos |
| `configuracoes_empresa` | configuração visual e dados da empresa |
| `logs_sistema` | auditoria de todas as operações |

### Tabelas a criar — módulo CRM (ver GTM_ROADMAP_CRM.md)

6 novas tabelas: `pipelines`, `pipeline_etapas`, `deals`, `deal_historico_etapas`, `deal_automacoes`, `atividades`, `notas`

---

## 7. Diferenciais técnicos

1. **Lead como âncora única** — um `lead_id` conecta WhatsApp, CRM, ERP e documentação. Zero duplicação de dados.

2. **Fluxos configuráveis sem código** — o time de negócio cria perguntas, validações e roteamentos pelo painel, sem precisar de dev.

3. **Automação pelo N8N** — eventos do sistema disparam workflows: lead novo → notifica time; documento aprovado → inicia envio ao HubSoft.

4. **Timeline completa do cliente** — da primeira mensagem no WhatsApp até o contrato assinado, tudo rastreado em uma única tela.

5. **Personalização total** — logo, cores, nome da empresa, planos, vencimentos, fluxos — tudo configurável pelo admin sem tocar em código.

6. **Multi-tenancy pronto para SaaS** — a arquitetura atual suporta adicionar um campo `empresa_id` e separar dados por cliente com esforço mínimo.

---

## 8. Números em produção (Megalink Telecom — Teresina/PI)

| Métrica | Valor (mar/2026) |
|---------|-----------------|
| Leads cadastrados | 341+ |
| Fluxos de atendimento | Ativos |
| Leads com HTML de conversa | 14 |
| Leads com documentação validada | 13 |
| Leads com contrato enviado ao HubSoft | 12 |
| Leads com contrato aceito | 5 |
| Logs de integração registrados | 90+ |
| Campanhas de tráfego rastreadas | Ativas |

---

## 9. Estado atual vs. visão produto

| Hoje | Próximo passo |
|------|---------------|
| Gestão de leads e fluxo de vendas | + CRM com pipeline kanban |
| Validação manual de documentos | + Validação automática por IA |
| Painel de relatórios básico | + Relatórios de conversão por etapa |
| Um único tenant (Megalink) | + Multi-tenant (SaaS para outros ISPs) |
| Automações via N8N externo | + Motor de automações interno (deal_automacoes) |
