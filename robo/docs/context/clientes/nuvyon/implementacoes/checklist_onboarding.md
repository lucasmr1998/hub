---
name: "Checklist de Onboarding — Nuvyon"
description: "Lista do que precisamos da Nuvyon pra executar o setup de implementacao. Arquitetura especifica: Matrix no atendimento + Hubtrix no backend (CRM/Marketing/Clube)"
---

# Checklist de Onboarding — Nuvyon

**Contrato:** SaaS Comercial PRO + Marketing Advanced
**Arquitetura:** Matrix (front de atendimento) → APIs Hubtrix (CRM / Marketing / dados)
**Status do projeto:** Não iniciado

---

## Arquitetura de integração

```
Consumidor ──▶ Matrix (atendimento, fluxos, bot)
                 │
                 └─(APIs)──▶ Hubtrix (CRM, Marketing, Clube, dados)
```

A Nuvyon usa o Matrix como front de atendimento. Hubtrix é o backend de dados e regras. Por isso, **Inbox, Fluxos visuais e módulo de Suporte nativos do Hubtrix ficam fora do escopo de setup.** O esforço concentra em CRM + Marketing + integração de APIs.

---

## Bloco 1 — Acessos críticos (bloqueantes)

### HubSoft
- [ ] Credenciais de API (client_id, client_secret ou usuário/senha)
- [ ] URL do servidor HubSoft (instância deles)
- [ ] Endpoints liberados (consulta de cliente, criação de contrato, consulta de fatura, etc.)
- [ ] Ambiente de homologação (se existir)
- [ ] Ambiente de produção
- [ ] **Ponto focal técnico do HubSoft na Nuvyon** (quem sabe mexer)

### Matrix (sistema deles)
- [ ] Confirmar versão/variante do Matrix em uso
- [ ] Ponto focal técnico do Matrix na Nuvyon (quem vai consumir as APIs do Hubtrix)
- [ ] Lista preliminar de casos de uso Matrix → Hubtrix (o que eles vão integrar)

### IA provider
- [ ] Provider escolhido (OpenAI / Anthropic / Groq / Google AI)
- [ ] API key fornecida (quem paga? cliente ou Hubtrix repassa?)
- [ ] Modelo preferido (ex: gpt-4o-mini, claude-haiku)

### WhatsApp (só se Hubtrix for disparar mensagens via automação; Matrix pode fazer isso)
- [ ] Confirmar: Matrix ou Hubtrix envia as mensagens de automação (régua de marketing, lembretes)?
- [ ] Se Hubtrix → provider (Uazapi/Evolution), número, instância

---

## Bloco 2 — Configuração inicial (pra parametrizar)

### Identidade visual
- [ ] Logo (PNG/SVG, alta resolução, fundo transparente)
- [ ] Cores da marca (primária + secundária, hex)
- [ ] Nome comercial exato
- [ ] Site oficial

### Pessoas e papéis
- [ ] Ponto focal do projeto (quem decide pelo lado Nuvyon)
- [ ] Lista do time comercial: nome, e-mail, telefone, perfil (vendedor / supervisor / gerente)
- [ ] Admin do Hubtrix (geralmente dono/diretor)
- [ ] Quem vai operar o Marketing (criar automações, segmentos, campanhas)

### CRM
- [ ] Pipeline desejado (nome dos estágios, SLA por estágio)
- [ ] Produtos/planos que vendem (lista com valores, SKU, recorrência)
- [ ] Equipes ou territórios (por região, por segmento, por canal?)
- [ ] Regras de atribuição (round-robin? por região? manual?)

---

## Bloco 3 — Integração Matrix ↔ Hubtrix (específica desta conta)

### Autenticação e acesso
- [ ] Gerar API token do Hubtrix dedicado ao Matrix
- [ ] Documentar quais endpoints o Matrix vai consumir
- [ ] Definir rate limit esperado (dimensionar pelo volume: ~10k leads × chamadas por lead)

### Mapeamento de dados
- [ ] Matrix → Hubtrix: quando Matrix marca X, o que acontece no Hubtrix
  - [ ] Primeira mensagem de consumidor → cria Lead
  - [ ] Qualificação concluída → atualiza score/status do Lead
  - [ ] Transferência pra vendedor → cria OportunidadeVenda
  - [ ] Venda fechada → move oportunidade pra ganho (dispara integração HubSoft)
  - [ ] Outros eventos (a mapear com o time da Nuvyon)
- [ ] Hubtrix → Matrix: webhooks de retorno (opcional)
  - [ ] Quando oportunidade muda de estágio, notifica Matrix?
  - [ ] Quando cliente vira ativo no HubSoft, notifica Matrix?
  - [ ] Quais eventos o Matrix quer receber

### Automação de marketing
- [ ] Definir quem dispara as réguas: Matrix ou Hubtrix?
  - Se Hubtrix: configurar regras de automação consumindo eventos do Matrix
  - Se Matrix: Hubtrix só registra os dados, não dispara mensagens
- [ ] Definir critério de "lead cadastrado" (base da cobrança variável)

### Testes
- [ ] Teste end-to-end: lead chega no Matrix → vira Lead no Hubtrix → vendedor fecha → Hubtrix dispara HubSoft
- [ ] Teste de volume: simular N chamadas simultâneas do Matrix pra validar performance
- [ ] Teste de falha: o que acontece se Hubtrix estiver indisponível? (Matrix faz fila? perde?)

---

## Bloco 4 — Automações de Marketing + Migração

### Automações prioritárias
- [ ] Régua de boas-vindas pós-ativação (sequência de mensagens nos primeiros 30 dias)
- [ ] Régua de lead frio (quem não respondeu há X dias)
- [ ] Régua de inadimplência (se vai ser tratado no Hubtrix ou direto no HubSoft)
- [ ] Régua de aniversário de contrato (1 ano, 2 anos)
- [ ] Outras que a Nuvyon quiser

### Segmentos dinâmicos
- [ ] Segmentos iniciais úteis pra Nuvyon (definir com eles):
  - [ ] Clientes em risco de churn
  - [ ] Clientes elegíveis pra upsell
  - [ ] Leads quentes da semana
  - [ ] Outros específicos

### Campanhas e atribuição
- [ ] Campanhas ativas (Google Ads / Meta / outras) — palavras-chave pra detecção
- [ ] UTMs padronizadas
- [ ] Orçamento mensal por canal (pra cálculo de ROI)

### Migração de dados (se aplicável)
- [ ] Lista de leads/contatos existentes pra importar (CSV)
- [ ] Produtos/planos pra catálogo CRM
- [ ] Dados históricos relevantes

---

## Bloco 5 — Clube de Benefícios (módulo Marketing Advanced)

- [ ] Config do Clube (gamificação, níveis, parceiros)
- [ ] Regras de pontuação (gatilhos que geram pontos)
- [ ] Prêmios da roleta (se vão usar)
- [ ] Programa de indicação: decidir se a Nuvyon vai usar
- [ ] Parceiros com cupons (se aplicável)

---

## Bloco 6 — Go-live

### Domínio e acesso
- [ ] Subdomínio próprio no painel? (ex: `painel.nuvyon.com.br`)
- [ ] SSL configurado
- [ ] DNS apontado

### Treinamento do time
- [ ] Quantos colaboradores
- [ ] Formato (presencial / remoto / gravado)
- [ ] Sessões de quanto tempo
- [ ] Material de apoio (reaproveitar [treinamento_parceiro](../../../../OPERACIONAL/materiais/treinamento_parceiro/))

### Aceite formal (dispara contagem do primeiro pagamento)
- [ ] Pessoa autorizada pra assinar o aceite de conclusão do setup
- [ ] Data prevista de go-live
- [ ] Critérios de "pronto pra produção" claros (checklist de teste final)

---

## Bloco 7 — Pós go-live (primeiros 60 dias)

- [ ] Acompanhamento semanal nas primeiras 4 semanas
- [ ] Revisão de primeiro ciclo de cobrança (validar apuração das variáveis)
- [ ] Ajustes nas automações baseado no uso real
- [ ] Pesquisa de satisfação (primeiro NPS informal)

---

## Observações gerais

- **Setup gratuito** conforme contrato. Trabalho adicional fora do escopo (ex: customização de API, integrações adicionais, relatórios sob demanda) deve ser cotado separadamente.
- **Ponto de atenção no contrato:** a cláusula 2.2.1 menciona Inbox e fluxos nativos, mas eles não serão usados. Se der problema depois, retomar a conversa sobre escopo da manutenção contínua das APIs (ver nota: escopo real é "integração Matrix↔Hubtrix + CRM + Marketing + Clube", não os módulos de atendimento nativos).
- **Cobrança variável (R$ 0,05/lead):** a definição de "lead cadastrado" precisa estar clara. No contexto Matrix, cada interação nova no Matrix que gerar registro no Hubtrix via API = 1 lead. Validar com o cliente que essa contagem bate com a expectativa deles.
