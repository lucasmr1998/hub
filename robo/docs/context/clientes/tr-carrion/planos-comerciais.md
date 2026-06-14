# Planos comerciais — TR Carrion (Brayo)

A partir de 13/06/2026 a TR Carrion opera com a marca **Brayo** e atende **somente** as cidades abaixo. Conversa que vier de fora dessa lista cai em **transbordo humano** (cidade fora da área).

## Cidades atendidas

- Lençóis Paulista
- Macatuba
- Pederneiras

## Planos de internet

| # | Plano | Preço (PIX recorrente / débito automático / boleto) |
|---|---|---|
| 1 | 400 Mega | R$ 74,99 |
| 2 | 600 Mega | R$ 89,99 |
| 3 | 1000 Mega | R$ 99,99 |

PIX = boleto (sem diferença de preço).

## Acréscimos opcionais (acumulativos)

Após o cliente escolher o plano de internet, o bot oferece os adicionais. Pode escolher **mais de um**.

| # | Acréscimo | Valor |
|---|---|---|
| 1 | Wi-Fi 6 | R$ 10,00 |
| 2 | Linha Fixa | R$ 19,99 |
| 3 | Repetidor de Sinal | R$ 29,99 |
| 4 | Continuar somente com o plano de internet | — |

> **Status:** Fase 1 + Fase 2 implementadas em 13/06/2026 no workflow Vero. JSON pronto pra importar em [`snapshots/_proposta_brayo_fase2_13-06-2026.json`](snapshots/_proposta_brayo_fase2_13-06-2026.json).

## Jornada completa do bot (após Fase 2)

1. Cliente entra → bot coleta CEP/endereço
2. Bot oferece os 3 planos (400/600/1000 Mega)
3. Cliente escolhe (ex: "2" → 600 Mega)
4. **Bot oferece extras:** "Quase lá! Quer turbinar seu plano? 1️⃣ Wi-Fi 6 R$10, 2️⃣ Linha Fixa R$19,99, 3️⃣ Repetidor R$29,99, 4️⃣ Seguir só com a internet. *Pode escolher mais de um. Ex: 1,2*"
5. Cliente responde "1,2" (ou "4" se não quer extras, ou "1" só etc)
6. **Bot mostra resumo:** plano + extras + total → "1️⃣ Sim, pode seguir / 2️⃣ Quero alterar os adicionais"
7. Se confirmar → segue pro CPF (jornada original)
8. Se alterar → volta à etapa 4

## Cidade fora da área

Cliente fora de Lençóis Paulista/Macatuba/Pederneiras → cai em transbordo humano (`Step Aguarda Humano`).

## Histórico (planos antigos Vero — descontinuados em 13/06/2026)

Os planos da era Vero (550/800 Mega, cidades Agudos/Piratininga/Americana/Bauru/Limeira/etc, preços diferenciados pix vs boleto) saíram do contexto. Snapshot pré-migração preservado em [`snapshots/_baseline_brayo_pre_migracao_13-06-2026.json`](snapshots/_baseline_brayo_pre_migracao_13-06-2026.json).
