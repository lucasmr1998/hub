# Recontato automático de leads "Sem retorno" — como funciona (para aprovação)

> Material para a conversa com a Gabi (Nuvyon). Explica exatamente o que a automação faz,
> quem recebe mensagem, o que acontece depois, e o que precisa da decisão dela.
> Estado hoje: **construído, testado e DESLIGADO**. Nada é enviado até ela aprovar.

---

## 1. O problema que isso resolve

Hoje, quando um lead some no meio do atendimento, a oportunidade é marcada como perdida
por "Sem retorno" e **acaba ali**. Ninguém volta nesse lead: não há tempo, e não há uma
lista organizada de quem valeria a pena chamar de novo.

Só que "sem retorno" quase nunca quer dizer "não quero". Na maioria das vezes é
distração, o cliente estava ocupado, ou ficou esperando uma resposta que demorou.
São vendas que ficam na mesa.

**Números reais do CRM da Nuvyon hoje:** 426 oportunidades perdidas no total. Só no
recorte "Sem retorno", há **94 leads perdidos há mais de 7 dias** e **29 há mais de 15 dias**
que nunca receberam um segundo contato.

---

## 2. Como funciona, passo a passo

**Uma vez por dia**, o sistema:

1. **Procura** as oportunidades perdidas com o motivo **"Sem retorno"** (o motivo do
   catálogo de vocês, marcado pela própria vendedora ou pela análise automática),
   que estejam perdidas há mais de **X dias** (X = decisão da Gabi, ver seção 5).
2. **Pula** quem já recebeu esse recontato antes. Cada lead recebe **no máximo uma
   mensagem, uma única vez na vida**. Nunca insiste, nunca manda de novo.
3. **Envia uma mensagem de WhatsApp** (template oficial, aprovado pela Meta e pela Gabi)
   perguntando se a pessoa ainda tem interesse.
4. **Anota tudo no CRM**: registra na oportunidade que o recontato foi feito, com data
   e horário, visível na linha do tempo do card.

**Teto de segurança:** no máximo **15 mensagens por dia**. Se houver 94 elegíveis, o
sistema leva ~7 dias pra passar por todos, em ritmo controlado. Nada de disparo em massa.

### O que acontece se a pessoa responder

A resposta chega no atendimento normal da Nuvyon (Matrix), como qualquer conversa. E, em
paralelo, o sistema automaticamente:

- **Reabre a oportunidade** no CRM (ela sai de "Perdido" e volta para o funil ativo);
- **Mantém a mesma vendedora** que atendia antes (ela não perde o lead dela);
- **Registra na linha do tempo**: "Lead respondeu ao recontato. Oportunidade reaberta."

Ou seja: a vendedora abre o CRM e o lead "ressuscitado" já está lá esperando por ela,
com o histórico completo.

### O que acontece se a pessoa NÃO responder

**Nada.** A oportunidade continua perdida, o lead fica marcado como já recontatado e
**nunca mais recebe mensagem desse fluxo**. Sem insistência, sem sequência, sem spam.

---

## 3. As garantias (o que NÃO vai acontecer)

| Preocupação | Garantia |
|---|---|
| "Vai virar spam?" | 1 mensagem por lead, **uma vez só**. Teto de 15/dia. Sem sequência de follow-up. |
| "Vai mandar pra quem já é cliente?" | Não. Só entra quem está em oportunidade **perdida** com motivo **"Sem retorno"**. Quem foi perdido por "Já é cliente" não entra. |
| "Vai mandar mensagem errada?" | O texto é **template fixo**, aprovado pela Gabi e pela Meta antes de qualquer envio. O sistema não escreve nada por conta própria. |
| "Se der problema, como paro?" | Um botão. Desligar o fluxo é instantâneo e nenhuma mensagem a mais sai. |
| "Como sei o que foi enviado?" | Cada envio fica registrado na oportunidade (linha do tempo) e no log do sistema. Auditável lead a lead. |
| "Vai atrapalhar a vendedora?" | Não. O lead só volta pro funil **se responder** e volta pra ela mesma, com contexto. |

---

## 4. Sugestões de texto da mensagem (a Gabi escolhe / ajusta)

O WhatsApp exige **template oficial aprovado** (HSM) para primeira mensagem ativa.
Três direções, do mais suave ao mais direto. `{{1}}` = primeiro nome do cliente.

**Opção A — Retomar a conversa (recomendada: soft, sem cara de promoção)**
> Oi, {{1}}! Aqui é da Nuvyon. 😊
> Vi que a gente começou a conversar sobre internet pra sua casa e a conversa acabou
> ficando pelo caminho.
> Ainda tem interesse? É só responder aqui que um consultor retoma de onde paramos.
> Se preferir não receber mais mensagens, responda SAIR.

**Opção B — Novidade / cobertura**
> Oi, {{1}}! Aqui é da Nuvyon.
> Desde a última vez que conversamos, temos novidades nos planos da sua região.
> Quer que eu te mostre o que dá pra fazer hoje pelo seu endereço?
> Se preferir não receber mais mensagens, responda SAIR.

**Opção C — Pergunta única (mais direta, maior taxa de resposta, menos elegante)**
> Oi, {{1}}! Aqui é da Nuvyon.
> Você ainda está procurando internet pra sua casa?
> Responda SIM que um consultor te chama agora.
> Se preferir não receber mais mensagens, responda SAIR.

*Observação: a linha do SAIR é boa prática (e exigência das regras de mensagem ativa).*

---

## 5. O que precisamos DELA para ligar

1. **Aprovar a mecânica** (o que está descrito acima).
2. **Escolher/ajustar o texto** e providenciar o **template aprovado** (HSM) + a **conta**
   do Matrix que vai enviar.
3. **Definir a janela.** ⚠️ Ponto importante: hoje, com a janela de **30 dias**, o fluxo
   enviaria **zero** mensagens — porque o CRM da Nuvyon começou em 21/06 e nenhuma perda
   tem 30 dias ainda. As opções:

| Janela | Leads elegíveis hoje | Leitura |
|---|---|---|
| 7 dias | **94** | Recontato "quente", enquanto a necessidade ainda existe. Mais volume. |
| 15 dias | **29** | Meio-termo. Dá tempo do lead esfriar sem esquecer a marca. |
| 30 dias | **0 hoje** (cresce com o tempo) | Conservador. Só começa a ter volume em agosto. |

Recomendação: **começar com 15 dias** (29 leads, lote controlado a 15/dia = 2 dias de
piloto), medir a resposta, e só então decidir entre abrir pra 7 dias ou manter.

---

## 6. Como será o piloto (proposta)

1. Ligamos com o teto baixo (15/dia) e a janela combinada.
2. Acompanhamos **1 semana**: quantos receberam, quantos responderam, quantas
   oportunidades reabriram, alguma reclamação.
3. Reunião curta com o resultado: se a taxa de resposta compensar, mantemos e abrimos o
   volume; se não, desligamos (custo: nenhum, o fluxo simplesmente para).

**Métrica de sucesso sugerida:** qualquer coisa acima de **5% de resposta** já paga o
esforço (5 respostas em 100 recontatos = 5 oportunidades reabertas que estavam mortas).

---

## Resumo em uma frase

> Uma vez por dia, o sistema manda **uma única** mensagem de WhatsApp para leads que
> sumiram há mais de X dias, perguntando se ainda têm interesse. Quem responde volta
> automaticamente para o funil, com a mesma vendedora. Quem não responde nunca mais é
> incomodado. Teto de 15 por dia, desligável a qualquer momento.
