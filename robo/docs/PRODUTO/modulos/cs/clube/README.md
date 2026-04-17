# CS — Clube

**App:** `apps/cs/clube/`

Motor de gamificacao do hub. Roleta digital com premios, sistema de pontos (saldo para giros + XP para niveis), missoes configuraveis, ranking de membros e landing page publica. Cada provedor tem seu clube independente (multi-tenant).

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [gamificacao.md](gamificacao.md) | GamificationService, regras, pontuacao, niveis, extrato |
| [roleta.md](roleta.md) | RoletaConfig, SorteioService, participantes, premios, assets |
| [area-publica.md](area-publica.md) | Landing + views sem login + APIs publicas |
| [area-membro.md](area-membro.md) | OTPService + area autenticada (hub, jogar, missoes, cupons) |

---

## 10 Models (resumo)

| Model | Descricao |
|-------|-----------|
| `MembroClube` | Dono do clube (cpf, saldo, xp_total, nivel_atual, codigo_indicacao) |
| `NivelClube` | Bronze/Prata/Ouro/Diamante com xp_necessario |
| `RegraPontuacao` | Gatilhos que concedem pontos (cadastro, telefone_verificado, etc.) |
| `ExtratoPontuacao` | Ledger imutavel de movimentacoes |
| `PremioRoleta` | Premios com posicoes, probabilidade, cidades_permitidas |
| `RoletaConfig` | Singleton com custo_giro, xp_por_giro, limites |
| `ParticipanteRoleta` | Registro de cada giro |
| `RouletteAsset` | Assets visuais (frames, fundo, logo, ponteiro) |
| `BannerClube` | Banners da landing |
| `LandingConfig` | Singleton da landing page |
| `Cidade` | Para restricao geografica de premios/cupons/parceiros |

### MembroClube (detalhe)

**Tabela:** `clube_membroclube` | **Unique:** `(tenant, cpf)`

| Grupo | Campos principais |
|-------|-------------------|
| **Identificacao** | nome (255), cpf (14, unique/tenant), email, telefone (20) |
| **Endereco** | cep, endereco, bairro, cidade, estado |
| **Gamificacao** | saldo (Integer, pontos para giros), xp_total (Integer, determina nivel) |
| **Validacao** | validado (Boolean, OTP), codigo_indicacao (10, UUID auto, unique) |
| **Integracao** | id_cliente_hubsoft (Integer) |

**Propriedades:** `nivel_atual`, `proximo_nivel` (calculadas a partir de `xp_total`).

---

## Integracao HubSoft

### HubsoftService

Arquivo: `apps/cs/clube/services/hubsoft_service.py`

| Metodo | O que faz |
|--------|-----------|
| `consultar_cliente(cpf)` | Consulta cliente no HubSoft via webhook N8N. Retorna dict com dados + telefone mascarado |
| `checar_pontos_extras_cpf(cpf)` | Consulta recorrencia, pagamento adiantado e uso do app. Retorna dict com flags booleanas |

---

## Management commands

| Command | Descricao |
|---------|-----------|
| `gerar_faq` | Gera/atualiza FAQs via IA. Flags: `--force`, `--categoria`, `--dry-run` |
| `testar_pontuacoes` | Testa scoring com dados reais do HubSoft. Flags: `--qtd`, `--cpf`, `--buscar-adiantado` |

---

## Admin

- **MembroClubeAdmin:** list com nome/cpf/telefone/validado/saldo/nivel_atual. Filtro por validado. Inline ExtratoPontuacao.
- **PremioRoletaAdmin:** list com nome/quantidade/probabilidade. Filter horizontal cidades_permitidas. Editable quantidade.
- **RegraPontuacaoAdmin:** list com nome_exibicao/gatilho/pontos/ativo/visivel. Editable fields.

---

## Landing page publica

Landing publica em `/roleta/clube/` — apresenta parceiros, cupons, premios e niveis. Config em `LandingConfig` (singleton).

Ver [area-publica.md](area-publica.md).
