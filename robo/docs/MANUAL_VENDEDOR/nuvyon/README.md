# Manual do Vendedor — Nuvyon

> Guia rápido pra usar o Hubtrix no dia a dia da Nuvyon.
> Última atualização: 22/06/2026 — v1.1.

## Sumário

0. [O que é o Hubtrix](#0-o-que-é-o-hubtrix)
1. [Seu primeiro dia no Hubtrix](#1-seu-primeiro-dia-no-hubtrix)
2. [Login e tela inicial](#2-login-e-tela-inicial)
3. [Fluxo completo de um lead](#3-fluxo-completo-de-um-lead)
4. [Atendendo um lead no horário comercial](#4-atendendo-um-lead-no-horário-comercial)
5. [Tarefas e notas](#5-tarefas-e-notas)
6. [Casos comuns no dia a dia](#6-casos-comuns-no-dia-a-dia)
7. [Problemas e quem chamar](#7-problemas-e-quem-chamar)

---

## 0. O que é o Hubtrix

**Lead entra no WhatsApp, contrato chega no HubSoft. Sem digitar duas vezes.** Essa é a parte que importa.

O Hubtrix faz a parte chata da sua venda. Recebe o lead, organiza o funil, lembra de cobrar documento, envia tudo pro HubSoft no momento certo. Você fica com a parte que importa: fechar.

Por isso o sistema não é um CRM "a mais". Ele é o **único lugar onde Matrix Brasil (onde o cliente conversa) e HubSoft (onde o cliente é cadastrado) se falam sem ninguém precisar copiar dados de uma tela pra outra**.

### Como o Hubtrix divide o trabalho com você

```
Cliente fala no WhatsApp
       ↓
Bot do WhatsApp coleta dados básicos
       ↓
Hubtrix organiza tudo num card no funil (CRM)
       ↓
[VOCÊ ATUA AQUI] valida documentos, aceita contrato no HubSoft
       ↓
Hubtrix sincroniza com HubSoft e dispara a instalação
```

**Sem o Hubtrix no meio:** vendedor anota CPF num papel, abre HubSoft, digita tudo de novo, perde foto que cliente mandou no WhatsApp, esquece de cobrar documento, descobre depois de 3 dias que CPF tem restrição. **Com o Hubtrix:** você abre o card, todo dado já está lá, você só decide.

---

## 1. Seu primeiro dia no Hubtrix

> Faça esses 7 itens **antes de tentar atender o primeiro lead real**. Demora 20 minutos. Sem isso, você vai bater em paredes invisíveis.

### Checklist Dia 1

- [ ] **1.** Logar no Hubtrix em `https://app.hubtrix.com.br/login/` com seu email Nuvyon (pedir senha pra Gabi se ainda não tem)
- [ ] **2.** Conferir se seu **login do Matrix Brasil** está vinculado ao seu perfil Hubtrix (Configurações → Meu perfil → campo "Login Matrix"). Se estiver vazio, **pedir pra Gabi preencher antes de continuar.** Sem isso, leads que você pega na Matrix não vão aparecer atribuídos a você no Hubtrix.
- [ ] **3.** Abrir o **CRM** no menu lateral e olhar como o kanban está organizado hoje (colunas e cards atuais)
- [ ] **4.** Identificar a coluna **"Análises - Doc & Score"** — é nela que você vai atuar o dia inteiro
- [ ] **5.** Com a Gabi do lado, abrir um card real (ou de teste) e clicar em **"Atribuir a mim"** pra entender a UI
- [ ] **6.** Abrir o painel do **HubSoft** em outra aba e fazer login com seu acesso HubSoft (mesma senha do Hubtrix? confirma com a Gabi). Mantenha aberto o dia inteiro.
- [ ] **7.** Ler as seções 3 (Fluxo do lead) e 4 (Atendendo no horário comercial) deste manual antes de pegar lead real

### Sinal de que você está pronto

Você consegue responder estas 3 perguntas sem consultar ninguém:

1. **Em qual coluna do CRM eu atuo?** (Análises - Doc & Score)
2. **Onde eu aceito o contrato do cliente?** (Painel HubSoft, fora do Hubtrix)
3. **Se eu pegar uma conversa na Matrix, em quanto tempo o card vai virar meu no Hubtrix?** (10-15 minutos, automático)

Se respondeu as 3 → bora atender 🚀.

---

## 2. Login e tela inicial

### Acessando o sistema

- Endereço: `https://app.hubtrix.com.br/login/`
- Use seu **email Nuvyon** e a senha que a Gabi te entregou
- Se esquecer a senha, peça pra Gabi resetar (ela tem permissão de admin)

### Endereços que você usa todo dia

Deixa esses 4 fixados nos favoritos do navegador:

| Pra que serve | Endereço |
|---|---|
| **Hubtrix CRM** (kanban dos leads) | `https://app.hubtrix.com.br/crm/` |
| **Hubtrix Inbox** (conversas) | `https://app.hubtrix.com.br/inbox/` |
| **HubSoft Nuvyon** (painel admin) | `<URL HubSoft Nuvyon — confirmar com Gabi>` |
| **Matrix Brasil** (atendimento WhatsApp) | `<URL Matrix Brasil — confirmar com Gabi>` |

### O que tem na tela inicial

Depois do login, você vê o **menu lateral** com as principais áreas:

| Menu | Pra que serve |
|---|---|
| **Início** | Dashboard com seus números do dia (leads em aberto, tarefas pendentes) |
| **CRM** | O funil de vendas, onde você passa a maior parte do tempo |
| **Inbox** | Conversas de WhatsApp e outros canais (uso eventual) |
| **Tarefas** | Lista de tarefas suas pendentes |
| **Suporte** | Tickets de problemas (quando virar cliente Nuvyon ativo) |

> 💡 **Atalho:** clique no logo Hubtrix no canto superior esquerdo pra voltar pra Início de qualquer tela.

---

## 3. Fluxo completo de um lead

### 3.1. Como o lead chega

**Você não cria leads no Hubtrix manualmente.** Eles chegam automaticamente quando o cliente fala com o bot de atendimento no WhatsApp da Nuvyon. O bot:

1. Coleta nome, telefone, CPF
2. Pergunta endereço (CEP, número)
3. Mostra os planos disponíveis e o cliente escolhe um
4. Pede 3 fotos: selfie, frente do documento, verso
5. Pede pra cliente assinar contrato no app HubSoft

Conforme o cliente avança, o **card dele no CRM move sozinho** pelo funil.

### 3.2. O funil (Kanban)

O CRM da Nuvyon tem **10 estágios**. O Hubtrix move o card automaticamente entre eles. Você só atua em 1 estágio (o de número 7).

| # | Estágio | O que o Hubtrix faz | O que VOCÊ faz |
|---|---|---|---|
| 1 | Novo Lead | Cria o card automaticamente | Nada |
| 2 | Em Atendimento | Move quando bot entra em conversa | Nada |
| 3 | Endereço Validado | Move quando cliente manda CEP/número | Nada |
| 4 | Plano Escolhido | Move quando cliente escolhe plano | Nada |
| 5 | Dados Completos | Move quando CPF + email + nascimento estão OK | Nada |
| 6 | Aguardando Documentos | Espera cliente mandar as 3 fotos | Nada |
| **7** | **Análises - Doc & Score** | Move quando cliente começou a enviar fotos | **VOCÊ ATUA AQUI no horário comercial** |
| 8 | Contrato Assinado | Move quando contrato é aceito no HubSoft | Acompanha (você foi quem aceitou) |
| 9 | Ativação Confirmada | Move quando HubSoft ativa o serviço | Lead virou cliente. Tudo certo. |
| 10 | Perdido | Você move quando cliente desistiu | Marca motivo |

### 3.3. Regra de ouro: a diferença entre ATRIBUIR e MOVER

Essas 2 coisas são diferentes e o vendedor tem permissão diferente em cada uma:

| Ação | Quando você pode fazer |
|---|---|
| **Atribuir responsável** ("Atribuir a mim" / "Atribuir") | **SEMPRE**, em qualquer estágio. Não quebra nada. |
| **Mover card de estágio** (arrastar entre colunas) | **NUNCA, exceto pra "Perdido"**. O Hubtrix move sozinho conforme o cliente avança. |

> ⚠️ **Por que isso importa:** se você arrasta um card de estágio 4 (Plano Escolhido) pra estágio 8 (Contrato Assinado) "pra adiantar", o Hubtrix vai considerar que o cliente já assinou contrato e pode disparar processo de instalação errado. **Move só pra Perdido. O resto é com o sistema.**

---

## 4. Atendendo um lead no horário comercial

> **Horário comercial Nuvyon: Segunda a Sexta, 08h às 18h.**
> Fora desse horário, o Hubtrix faz tudo automático. Você atua apenas no horário comercial.

### 4.1. Pegando um lead

Você tem **2 caminhos** pra virar responsável de um lead:

**Caminho 1 — Você pega na Matrix (automático).** Quando você assume uma conversa no Matrix Brasil, o Hubtrix detecta isso a cada 10-15 minutos e te atribui como responsável do card automaticamente. **Você não precisa fazer nada aqui no Hubtrix.** Esse é o caminho mais comum.

**Caminho 2 — Direto pelo Hubtrix.** Útil quando o lead apareceu sem responsável e ninguém o assumiu na Matrix:

1. Abra **CRM** no menu
2. Olha a coluna **Análises - Doc & Score** (estágio 7) — esses são os leads esperando ação humana
3. Clique no card pra abrir o detalhe
4. No header tem um botão **"Atribuir a mim"** (ou "Atribuir" se for outro vendedor)
5. Lead agora é seu — aparece também na sua aba "Meus leads"

> 💡 **Atribuir é SEMPRE seguro** (em qualquer estágio). Já mover o card de estágio, só pra Perdido. Veja seção 3.3.

### 4.2. Verificando os dados do lead

Quando você abre o card, vê:

- **Header:** nome, telefone, CPF, estágio atual
- **Sidebar direita:** dados completos (endereço, plano escolhido, dia vencimento)
- **Timeline:** histórico do que aconteceu (cada mensagem do bot, cada etapa concluída)
- **Documentos:** fotos que o cliente enviou (selfie, frente, verso)

### 4.3. Completando dados que faltam

Se o bot não conseguiu coletar tudo (ex: cliente desistiu antes de mandar email), use o botão **"Completar dados"** no header.

Abre um modal com **12 campos obrigatórios**:

- **Dados pessoais:** nome, CPF, email, data nascimento, RG, telefone
- **Endereço:** CEP, rua, número, bairro, cidade, estado, complemento (opcional)
- **Comercial:** plano, dia vencimento

> 💡 **Dica:** Quando você preenche o CEP, o Hubtrix busca rua/bairro/cidade no ViaCEP automaticamente. Só precisa digitar número e complemento.

**Depois que você salva, o Hubtrix avisa o HubSoft sozinho.** Você não precisa ir lá atualizar o prospect.

### 4.4. Validando documentos e aceitando o contrato

> Este é o passo mais importante do horário comercial.

1. Abra a aba **Documentos** do card
2. Confira as 3 fotos:
   - Selfie segurando documento (rosto + RG visíveis, sem óculos escuros, sem boné)
   - Frente do RG/CNH (legível, dados visíveis, sem brilho que apague texto)
   - Verso do RG/CNH (legível, número visível)
3. Confira se os dados do documento **batem** com o que o cliente declarou no bot (CPF, nome, data de nascimento)
4. Se tudo OK, abra o painel HubSoft em outra aba:
   - Faça login com seu acesso HubSoft
   - Procure o prospect pelo CPF do cliente
   - Clique em **"Aceitar Contrato"**
   - Abra a OS de instalação pra o dia que o cliente confirmou
5. Volte pro Hubtrix. O card vai mover pra "Contrato Assinado" em até 1 minuto (sincronia automática).

### 4.5. O que NÃO fazer no horário comercial

| ❌ Não faça | Por quê |
|---|---|
| Arrastar card de uma coluna pra outra | Sistema move sozinho. Arrastar quebra o processo. |
| Aceitar contrato no HubSoft sem ver as 3 fotos | Pode ser fraude / CPF restrito |
| Aceitar contrato se dados do doc não batem com declarado | Cliente pode ter mandado documento de outra pessoa |
| Mexer no card de outro vendedor sem combinar | Vai roubar lead dele |
| Apagar lead achando que é teste | Pode ser cliente real |

---

## 5. Tarefas e notas

### 5.1. Criando uma tarefa

Tarefa = lembrete pra você ou outro vendedor fazer algo num lead específico.

1. Abra o card do lead
2. Aba **Tarefas** → botão **+ Nova Tarefa**
3. Preencha: título, prazo, responsável, descrição
4. Salvar

Aparece também na tela **Tarefas** do menu principal.

### 5.2. Marcando como concluída

Na aba Tarefas (do card OU da tela geral), clique no ✅ ao lado da tarefa.

### 5.3. Notas internas

Nota = anotação só pro time interno ver (cliente nunca vê).

1. Abra o card do lead
2. Aba **Notas** → botão **+ Nova Nota**
3. Escreva. Pode fixar pra aparecer no topo (se for crítico)

> **Quando usar nota?** Quando você descobre algo importante que outro vendedor precisa saber. Exemplo: "Cliente ligou 3x irritado, prefere ser atendido pela manhã".

---

## 6. Casos comuns no dia a dia

### 6.1. "Cliente diz que não escolheu plano nenhum"

**Causa provável:** bot não captou bem a resposta.

**O que fazer:**
1. Abra o card, vá na aba **Histórico**
2. Procure pela última mensagem do bot perguntando o plano
3. Confirme com o cliente no WhatsApp pessoal (use o número que já está no card)
4. Use **"Completar dados"** pra registrar o plano correto

### 6.2. "Cliente quer mudar de plano antes do contrato"

**O que fazer:**
1. Use **"Completar dados"** e troque o plano
2. Salve. O Hubtrix atualiza o prospect no HubSoft automaticamente
3. Avise o cliente no WhatsApp que ajustou

### 6.3. "Lead duplicado — mesmo CPF, dois cards"

**Causa provável:** cliente falou de 2 números diferentes.

**O que fazer:**
1. Verifique qual card está mais avançado no funil
2. Marque o outro como **Perdido** com motivo "duplicado"
3. Se ambos têm dados completos, escolha o mais recente

### 6.4. "CPF aparece com restrição no HubSoft"

**O que fazer:**
1. **Não aceite o contrato no HubSoft.**
2. Volte pro Hubtrix, marque o card como **Perdido** com motivo "CPF restrito"
3. Avise o cliente pelo WhatsApp educadamente: "Identificamos uma pendência no seu CPF. Pra prosseguir, recomendamos regularizar com a Serasa antes."

### 6.5. "Cliente reclama da promoção R$39,90"

**Resposta sugerida (educada e firme):**

> "Olá, [Nome]! A promoção de R$39,90 era por tempo limitado e foi encerrada em [data]. Nossa oferta atual é [plano X] por R$XX/mês com [vantagem]. Posso te explicar melhor essa nova condição?"

Se for caso pontual e o cliente já estava em conversa quando a promoção saiu do ar, escale com a Gabi.

### 6.6. "Cliente confirmou data de instalação, mas o sistema não abriu OS"

**Causa provável:** cliente ainda não foi cadastrado no HubSoft (acontece em horário comercial).

**O que fazer:**
1. Abra HubSoft em outra aba
2. Verifique se o prospect ainda está como "Aguardando Assinatura"
3. Se sim: aceite contrato → abra OS manualmente pra a data que o cliente confirmou
4. Avise o cliente pelo WhatsApp confirmando o dia

---

## 7. Problemas e quem chamar

### Esqueci minha senha
→ Pedir reset pra **Gabi** (admin Nuvyon)

### Não consigo entrar no Hubtrix (sistema fora do ar)
→ Avisar **Gabi** no grupo. Se urgente, ela escala pro time Hubtrix.

### Lead não está aparecendo no meu kanban
→ Provável: lead não foi atribuído a você. Procure na aba **Não atribuídos** e clique em "Atribuir a mim".

### Lead que eu peguei na Matrix está sem responsável no Hubtrix mesmo depois de 30min
→ Provável: seu **login Matrix** não está vinculado ao seu perfil Hubtrix. Pedir pra **Gabi** conferir (Configurações → Meu perfil → campo Login Matrix).

### Card aparece duplicado ou em estágio estranho
→ Anote o **ID do lead** (visível na URL: `/crm/oportunidades/1635/` → ID é 1635). Avisa **Gabi** com o ID.

### Sistema apresentou erro X ao salvar
→ Tirar **screenshot da tela inteira** (incluindo URL). Mandar pra **Gabi** com:
  - O que estava tentando fazer
  - ID do lead (se aplicável)
  - Horário aproximado

### Cliente pergunta algo técnico (Wi-Fi, configuração)
→ Não responder. Transferir pra **Suporte Técnico Nuvyon** (fora do escopo do vendedor).

---

## Próximas versões

Este manual está em **v1.1**. Próximas versões vão incluir:

- [ ] Screenshots de cada tela mencionada
- [ ] Vídeo curto (3-5 min) do fluxo completo
- [ ] Glossário de termos
- [ ] FAQ "perguntas do cliente": prazo, fidelidade, multa, mudança de endereço
- [ ] Seção LGPD pro vendedor
- [ ] Critérios detalhados de aceitação/recusa de documentos
- [ ] Versão impressa em PDF
- [ ] Atalhos avançados pra vendedor experiente

**Sugestões e correções:** mandar pra Gabi ou anotar numa nota no card "Manual Vendedor" no Workspace.
