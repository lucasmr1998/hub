# Clube — Roleta

Sistema de roleta digital. Membros usam saldo para girar e ganhar premios.

---

## Models

### PremioRoleta

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(255) | Nome do premio |
| `quantidade` | Integer | Estoque |
| `posicoes` | CharField(50) | Posicoes validas na roleta (ex: `4,7`) |
| `probabilidade` | Integer | Peso (1 = raro, 10 = comum) |
| `mensagem_vitoria` | TextField | Mensagem exibida ao ganhar |
| `cidades_permitidas` | M2M Cidade | Restricao geografica (null = todas) |

### RoletaConfig (Singleton)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `custo_giro` | Integer | Custo em pontos de saldo |
| `xp_por_giro` | Integer | XP ganho por giro |
| `nome_clube` | CharField(100) | Nome do clube |
| `limite_giros_por_membro` | Integer | Max giros (0 = ilimitado) |
| `periodo_limite` | CharField | total / diario / semanal / mensal |

### ParticipanteRoleta

Registro de cada giro na roleta.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `membro` | FK MembroClube (nullable) | Membro (se autenticado) |
| `nome`, `cpf`, `telefone`, `email` | Dados diretos | Para nao membros |
| `endereco`, `bairro`, `cidade`, `estado`, `cep` | Endereco | Localizacao |
| `premio` | CharField(255) | Premio ganho |
| `canal_origem` | CharField(100) | Canal (default "Online") |
| `perfil_cliente` | CharField(10) | "sim" ou "nao" |
| `saldo` | Integer | Saldo no momento do giro |
| `status` | CharField(50) | reservado / ganhou / inviavel_tec / inviavel_cani |

### RouletteAsset

Elementos visuais da roleta (frames, fundo, logo, ponteiro).

- `tipo`: frame / background / logo / pointer
- `ordem`: 0-12 para frames

---

## SorteioService

Arquivo: `apps/cs/clube/services/sorteio_service.py`

| Metodo | O que faz |
|--------|-----------|
| `executar_giro_roleta(membro, premios, custo_giro)` | Deduz saldo, sorteia premio com `random.choices()` (probabilidade ponderada), retorna `(novo_saldo, premio, posicao)` |

---

## Fluxo de um giro

1. Membro abre `/roleta/membro/jogar/`
2. Click no botao "Girar"
3. Frontend chama API que invoca `SorteioService.executar_giro_roleta`
4. Service valida saldo, deduz custo, sorteia premio (respeitando posicoes e probabilidade)
5. Cria `ParticipanteRoleta` com status `ganhou`
6. Gera XP via gatilho implicito (`xp_por_giro`)
7. Retorna premio para animacao visual

---

## Restricao geografica

Premios podem ter `cidades_permitidas` (M2M). No sorteio, o service filtra premios considerando a cidade do membro. Permite que um clube nacional tenha premios especificos por regiao.
