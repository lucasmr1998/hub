# Pauta — Reunião de implementação Nuvyon

**Data:** 21/05/2026
**Tipo:** Discovery / implementação (configuração do bot de atendimento)
**Cliente:** Nuvyon (tenant `nuvyon`, id 12 — provisionado em prod)
**Objetivo:** definir o escopo e as regras do bot WhatsApp da Nuvyon antes da configuração

> Legenda: itens marcados decididos na reunião. Cada bloco precisa de uma resposta clara
> da Nuvyon pra destravar a configuração técnica.

---

## 1. Processo comercial atual (entender o as-is)

- [ ] Vocês têm algum processo comercial desenhado hoje? (script de vendas, etapas, quem faz o quê)
- [ ] Como o lead chega hoje? (site, indicação, WhatsApp manual, anúncios pagos)
- [ ] Quem atende hoje e quantos vendedores vão entrar na operação do bot?
- [ ] Volume estimado de atendimentos por dia que o bot vai receber

---

## 2. Identificação de quem chega (cliente x lead x débito)

> Define o roteamento logo na entrada. Sem isso o bot trata cliente inadimplente como lead novo.

- [ ] Como o bot identifica que quem chegou já é cliente? Consulta CPF ou telefone no HubSoft no início?

### 2a. Cliente ativo, sem débito
- [ ] O que o bot faz?
  - Transbordo direto pra atendente humano (suporte/CS)
  - Autoatendimento (2ª via, alterar vencimento, upgrade de plano)
  - Bot pergunta o que a pessoa quer e roteia
- [ ] Cliente existente pode contratar um novo ponto pelo bot?

### 2b. Cliente com débito (inadimplente)
- [ ] Qual fluxo seguir?
  - Bot informa o débito e envia linha digitável / PIX do boleto em aberto
  - Bot oferece negociação (parcelamento) ou transbordo pra cobrança
  - Bot só avisa da pendência e passa pra humano
- [ ] Cliente com débito que tenta contratar novo plano: bot bloqueia a venda até regularizar, ou deixa seguir?
- [ ] O bot terá acesso ao valor e vencimento do débito via HubSoft?

### 2c. Lead novo
- [ ] Segue o fluxo de venda (seção 5).

> **Pergunta de fundo:** o escopo contratado é só vendas, ou o bot também faz
> retenção / cobrança / suporte? Se for só vendas, o caminho simples é:
> identificou cliente, transborda pra humano.

---

## 3. Catálogo e planos

- [ ] Quais planos serão comercializados no bot? (o ERP tem centenas; precisamos do subconjunto comercial)
- [ ] O catálogo muda por cidade / região?
- [ ] Preço PIX vs boleto, valores promocionais, combos com streaming

---

## 4. Regras de negócio

- [ ] Quais datas de vencimento o cliente pode escolher?
- [ ] Tem fidelidade de 12 meses? O que muda se o cliente não quiser fidelidade?
- [ ] Formas de cobrança aceitas (PIX recorrente, débito em conta, boleto)
- [ ] Como funciona a viabilidade? O bot consulta cobertura por CEP antes de oferecer plano?
- [ ] Em quais cidades a Nuvyon atende?

---

## 5. Fluxo do bot (venda — lead novo)

- [ ] Dados que o bot coleta: nome, CEP, endereço, CPF, RG/CNH (foto), email, data de nascimento — confirmar a lista
- [ ] O bot valida documento por foto (IA) ou só coleta?
- [ ] Em que ponto o bot passa pra um humano? (qualificou, travou, cliente pediu)

---

## 6. Pós-venda: OS e agendamento

- [ ] Abertura / agendamento de OS — como querem proceder?
  - Bot consulta técnicos disponíveis e agenda no próximo horário livre
  - Bot só registra o pedido e um humano agenda
  - Bot oferece janelas (manhã / tarde) e o cliente escolhe
- [ ] O agendamento entra direto no HubSoft? Quem confirma com o cliente?

---

## 7. Documentação e contrato

- [ ] Na assinatura de contrato, o bot envia os documentos coletados + o resumo da conversa?
- [ ] Qual ferramenta de assinatura é usada?
- [ ] O contrato é gerado automaticamente com os dados coletados?

---

## 8. Integrações (técnico)

- [ ] HubSoft — credenciais, qual instância, o que o bot escreve (lead? cadastro? OS?)
- [ ] Matrix — o que o Matrix faz hoje e como conversa com o Hubtrix (token de API já gerado)
- [ ] WhatsApp — qual número, provider (Uazapi / Evolution), número novo ou existente
- [ ] Provider de IA (OpenAI / Anthropic / etc) e de quem é o billing

---

## 9. Operação e go-live

- [ ] Horário de atendimento (bot 24h? humano em qual janela?)
- [ ] Mensagem fora de horário
- [ ] Usuários do painel e perfil de cada um (admin `admin_nuvyon` já criado)
- [ ] Data alvo de go-live

---

## Estado atual da implementação (referência)

- Tenant `nuvyon` provisionado em produção (Comercial tier pro + Marketing tier start, sem CS)
- Usuário `admin_nuvyon` criado, perfil Admin, 11 perfis de permissão seedados
- Integração "Matrix Nuvyon" criada com token de API inbound
- Pendente: tudo desta pauta (escopo do bot ainda não definido)
