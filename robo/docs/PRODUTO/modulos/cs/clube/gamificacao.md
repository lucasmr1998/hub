# Clube — Gamificacao

Sistema de pontos (saldo) + experiencia (XP) com niveis configuraveis.

---

## NivelClube

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(50) | Ex: Bronze, Prata, Ouro, Diamante |
| `xp_necessario` | Integer | XP minimo para atingir |
| `ordem` | Integer | Ordem (1 = mais baixo) |

O nivel atual do membro e calculado dinamicamente via `MembroClube.nivel_atual` a partir do `xp_total`.

---

## RegraPontuacao

**Unique:** `(tenant, gatilho)`

Engine de gamificacao configuravel. Define quando e quanto pontuar.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `gatilho` | CharField(50) | Identificador unico (ex: cadastro, telefone_verificado, indicacao_convertida) |
| `nome_exibicao` | CharField(100) | Nome amigavel (ex: "Bonus de Boas Vindas") |
| `pontos_saldo` | Integer | Pontos de giro concedidos |
| `pontos_xp` | Integer | XP concedido |
| `limite_por_membro` | Integer | Vezes que pode ganhar (0 = ilimitado) |
| `ativo` | Boolean | Status |
| `visivel_na_roleta` | Boolean | Mostra como missao na area do membro |

**Gatilhos pre-definidos:** `cadastro`, `telefone_verificado`, `indicacao_convertida`, `ajuste_manual_admin`

---

## ExtratoPontuacao

**Ledger imutavel** (audit trail) de todas as movimentacoes de pontos.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `membro` | FK MembroClube | Quem ganhou |
| `regra` | FK RegraPontuacao | Qual regra ativou |
| `pontos_saldo_ganhos` | Integer | Saldo creditado |
| `pontos_xp_ganhos` | Integer | XP creditado |
| `descricao_extra` | CharField(255) | Contexto (ex: "Indicou CPF 123.456.789-00") |
| `data_recebimento` | DateTime (auto) | Timestamp |

---

## GamificationService

Arquivo: `apps/cs/clube/services/gamification_service.py`

| Metodo | O que faz |
|--------|-----------|
| `atribuir_pontos(membro, gatilho, descricao_extra)` | Busca `RegraPontuacao` pelo gatilho, valida `limite_por_membro`, incrementa saldo e xp_total com `F()` (atomico), cria `ExtratoPontuacao`. Retorna `(sucesso, mensagem)` |

**Usado por:**

- Automacoes (acao `dar_pontos` — ver [marketing/automacoes/engine.md](../../marketing/automacoes/engine.md))
- Signals de indicacao (quando `confirmar_conversao`)
- OTP validado (gatilho `telefone_verificado`)
- Cadastro novo (gatilho `cadastro`)
- Botao de ajuste manual no dashboard admin

---

## Atomicidade

O incremento de saldo/xp usa `F()` expression do Django para evitar race conditions. Dois giros simultaneos nao conseguem gastar o mesmo saldo.
