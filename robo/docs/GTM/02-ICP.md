# 02. ICP — Ideal Customer Profile

**Status:** 🔧 Em construção
**Última atualização:** 26/03/2026

---

## Objetivo

Definir com precisão quem é o cliente ideal da Hubtrix: o perfil da empresa, os decisores e as personas que interagem com o produto.

---

## Perfil da empresa (ICP primário)

| Critério | Descrição |
|----------|-----------|
| Segmento | Provedor regional de internet (ISP) |
| ERP utilizado | HubSoft |
| Porte | 1.000 a 50.000+ assinantes ativos |
| Time comercial | 2 a 20 vendedores |
| Localização | Brasil (foco inicial: interior e cidades médias) |
| Maturidade digital | Usa WhatsApp como canal principal de vendas |
| Dor principal | Perda de leads, processo manual, falta de visibilidade (varia por porte — ver matriz abaixo) |

---

## Segmentação por porte — dores, decisor e plano

O ICP se comporta muito diferente conforme o porte. Dor, decisor, ticket aceitável e argumento de venda mudam. A matriz abaixo guia **com quem falar, como falar e qual plano oferecer**.

| Dimensão | **Pequeno** (até 10k) | **Médio** (10k–30k) | **Grande** (+30k) |
|----------|-----------------------|----------------------|-----------------------|
| **Perfil da empresa** | Dono operacional, estrutura enxuta, foco em crescer | Gestão formalizada, time comercial estruturado, busca método | Operação complexa, múltiplas áreas, busca escala e governança |
| **Decisor** | Dono / proprietário (decisor único) | Gerente ou diretor influencia, dono decide (2 pessoas no ciclo) | Múltiplos stakeholders: dono, diretor comercial, CTO, CFO |
| **Dor central** | Perde lead por não atender a tempo, sem processo, sem visibilidade de nada | Crescendo sem método, time trabalha cada um do seu jeito, não consegue cobrar resultado, começou a perder dinheiro com desorganização | Escala sem qualidade, precisa de dados pra decisão estratégica, churn impacta receita de forma material, expansão e upsell são prioridade |
| **Volume típico** | 20–200 leads/mês, 1–3 vendedores | 200–1.000 leads/mês, 3–10 vendedores | 1.000+ leads/mês, 10–20+ vendedores |
| **Ticket Hubtrix aceitável** | Até ~R$ 1.000/mês (stack completo) | R$ 2.000 a R$ 5.000/mês | R$ 5.000+ sem problema |
| **O que convence** | Indicação de outro ISP + preço baixo + setup rápido | ROI quantificável + case + demonstração de automação | Demo técnica + integrações + SLA + NRR + maturidade de produto |
| **Objeção comum** | "É caro pro meu tamanho" / "Minha planilha funciona" | "Já tentei Pipedrive/RD, saí" / "Qual o ganho real?" | "Segurança e compliance", "Suporta nosso volume?", "Integração custom" |
| **Plano recomendado** | Comercial Starter (+ Marketing Starter depois) | Comercial Pro + Marketing Pro | Comercial Advanced + Marketing Advanced + CS Advanced |
| **Tempo de venda esperado** | 1–2 semanas | 3–8 semanas | 2–6 meses |
| **Canal de aquisição** | Indicação + WhatsApp + grupos de ISP | Indicação + LinkedIn + eventos do setor | Outbound direto + eventos + parceiros estratégicos |

### Observações por porte

**Pequeno (até 10k):** preço é o principal filtro. Não vale investir em demo complexa — deixa cliente testar o Starter e cresce depois. O dono decide por intuição, então case de ISP amigo pesa mais que planilha de ROI.

**Médio (10k–30k):** o ponto doce da venda. Gerente formaliza o processo, dono bate o martelo. Precisa de ROI claro (aqui brilha a métrica "redução de até 70% do trabalho manual no comercial"). Ticket suporta o stack completo com folga.

**Grande (+30k):** ciclo longo mas ticket grande. Precisa de case robusto (atualmente Megalink, ISP com 30k+ assinantes). Múltiplos decisores exigem materiais diferentes (dono quer narrativa; CTO quer arquitetura; CFO quer ROI). Setup costuma ser customizado.

## Perfil da empresa (ICP secundário — futuro)

| Critério | Descrição |
|----------|-----------|
| ERP utilizado | Voalle, SGP, MK-Auth ou outros |
| Expansão | Após consolidação com HubSoft |

---

## Personas

### Persona 1 — O Dono do Provedor

> Quem decide a compra.

| Campo | Descrição |
|-------|-----------|
| Cargo | Proprietário / CEO |
| Perfil | Empreendedor regional, fundou o provedor, operacional no dia a dia |
| Dor principal | "Meus vendedores perdem lead e eu não sei o que está acontecendo nas vendas" |
| O que quer | Visibilidade, controle e menos desperdício |
| Como decide | Por ROI e indicação de confiança |
| Canal preferido | WhatsApp, grupos de provedor, eventos do setor |

---

### Persona 2 — O Gerente Comercial

> Quem vai usar o produto para gerir o time.

| Campo | Descrição |
|-------|-----------|
| Cargo | Gerente Comercial / Supervisor de Vendas |
| Perfil | Responsável pelo time, quer dados para cobrar resultados |
| Dor principal | "Não consigo cobrar o time porque não tenho dado nenhum" |
| O que quer | Dashboard, relatórios, visibilidade de pipeline |
| Como decide | Influencia o dono, quer ferramenta que facilite a gestão |
| Canal preferido | WhatsApp, ferramentas de gestão |

---

### Persona 3 — O Vendedor

> Quem usa o produto no dia a dia.

| Campo | Descrição |
|-------|-----------|
| Cargo | Vendedor / Atendente comercial |
| Perfil | Atende via WhatsApp, coleta dados, pede documentos manualmente |
| Dor principal | "Fico perdido. Não sei qual lead devo ligar agora" |
| O que quer | Fila clara, lembretes automáticos, menos trabalho repetitivo |
| Como decide | Não decide, mas adota ou resiste. A experiência precisa ser simples |
| Canal preferido | WhatsApp, interface mobile |

---

### Persona 4 — O TI do Provedor

> Quem vai avaliar e implementar tecnicamente.

| Campo | Descrição |
|-------|-----------|
| Cargo | Analista de TI / Técnico de suporte |
| Perfil | Responsável por sistemas, não quer manutenção extra |
| Dor principal | "Não quero dar suporte em coisa que não é meu core" |
| O que quer | SaaS pronto, documentação clara, pouca manutenção |
| Como decide | Valida viabilidade técnica para o dono |
| Canal preferido | Documentação técnica, e-mail |

---

## Sinais de fit (quem tem mais chance de comprar)

- [ ] Usa HubSoft como ERP
- [ ] Tem time comercial ativo (mínimo 2 vendedores)
- [ ] Recebe leads pelo WhatsApp hoje
- [ ] Já perdeu lead por falta de acompanhamento
- [ ] Dono ou gerente sente falta de visibilidade do pipeline
- [ ] Não tem CRM estruturado (usa planilha ou nada)

## Sinais de não fit (quem provavelmente não vai comprar agora)

- [ ] ISP muito pequeno sem time comercial (vendas feitas só pelo dono)
- [ ] Usa outro ERP e não tem plano de migrar para HubSoft
- [ ] Já tem CRM estruturado e integrado
- [ ] Processo de vendas 100% presencial sem uso de WhatsApp

---

## Perguntas em aberto

- [ ] Qual o tamanho médio de time comercial dos provedores com HubSoft?
- [ ] Quantos leads por mês um ISP médio recebe?
- [ ] O dono costuma ser o decisor ou delega para gerente?
