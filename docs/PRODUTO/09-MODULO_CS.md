# Módulo Customer Success — AuroraISP

**Última atualização:** 04/04/2026
**Status:** 🔧 Em desenvolvimento
**Localização:** `apps/cs/`

---

## Visão Geral

O módulo CS (Customer Success) cobre todo o ciclo de fidelização do cliente: do primeiro contato pós-venda até a prevenção de churn. É composto por 6 sub-apps que se integram via services e a engine de gamificação. Migrado do projeto megaroleta para o hub em 29/03/2026.

```
Cliente ativado no HubSoft
    │
    ▼
┌──────────┐     ┌────────────┐     ┌──────────────┐
│  CLUBE   │────▶│ INDICAÇÕES │────▶│  PARCEIROS   │
│ Roleta   │     │ Programa   │     │  Cupons      │
│ Missões  │     │ Conversão  │     │  Resgates    │
│ XP/Níveis│     │ Página pub.│     │  Validação   │
└────┬─────┘     └────────────┘     └──────────────┘
     │
     ├──▶ CARTEIRINHA (ID digital com QR code)
     ├──▶ NPS (Pesquisa de satisfação) [stub]
     └──▶ RETENÇÃO (Score de saúde, alertas churn) [stub]
```

**Stack compartilhada:** TenantMixin (multi-tenancy), Django 5.2, PostgreSQL, N8N (OTP/WhatsApp), HubSoft API (consulta de clientes)

---

## 1. Clube (`apps/cs/clube/`)

### O que faz
Motor de gamificação do hub. Roleta digital com prêmios, sistema de pontos (saldo para giros + XP para níveis), missões configuráveis, ranking de membros e landing page pública. Cada provedor tem seu clube independente (multi-tenant).

### Models (10)

#### MembroClube
Tabela: `clube_membroclube` | Unique: (tenant, cpf)

| Grupo | Campos principais |
|-------|-------------------|
| **Identificação** | nome (255), cpf (14, unique/tenant), email, telefone (20) |
| **Endereço** | cep, endereco, bairro, cidade, estado |
| **Gamificação** | saldo (Integer, pontos para giros), xp_total (Integer, determina nível) |
| **Validação** | validado (Boolean, OTP), codigo_indicacao (10, UUID auto, unique) |
| **Integração** | id_cliente_hubsoft (Integer) |
| **Auditoria** | data_cadastro (auto) |

**Propriedades:**
- `nivel_atual` → retorna NivelClube baseado no xp_total
- `proximo_nivel` → próximo nível a atingir

#### NivelClube
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(50) | Ex: Bronze, Prata, Ouro, Diamante |
| `xp_necessario` | Integer | XP mínimo para atingir |
| `ordem` | Integer | Ordem (1 = mais baixo) |

#### RegraPontuacao
Tabela: auto | Unique: (tenant, gatilho)

Engine de gamificação configurável. Define quando e quanto pontuar.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `gatilho` | CharField(50) | Identificador único (ex: cadastro, telefone_verificado, indicacao_convertida) |
| `nome_exibicao` | CharField(100) | Nome amigável (ex: "Bônus de Boas Vindas") |
| `pontos_saldo` | Integer | Pontos de giro concedidos |
| `pontos_xp` | Integer | XP concedido |
| `limite_por_membro` | Integer | Vezes que pode ganhar (0 = ilimitado) |
| `ativo` | Boolean | Status |
| `visivel_na_roleta` | Boolean | Mostra como missão na área do membro |

**Gatilhos pré-definidos:** cadastro, telefone_verificado, indicacao_convertida, ajuste_manual_admin

#### ExtratoPontuacao
Tabela: auto

Ledger de todas as movimentações de pontos. Imutável (audit trail).

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `membro` | FK MembroClube | Quem ganhou |
| `regra` | FK RegraPontuacao | Qual regra ativou |
| `pontos_saldo_ganhos` | Integer | Saldo creditado |
| `pontos_xp_ganhos` | Integer | XP creditado |
| `descricao_extra` | CharField(255) | Contexto (ex: "Indicou CPF 123.456.789-00") |
| `data_recebimento` | DateTime (auto) | Timestamp |

#### PremioRoleta
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(255) | Nome do prêmio |
| `quantidade` | Integer | Estoque |
| `posicoes` | CharField(50) | Posições válidas na roleta (ex: "4,7") |
| `probabilidade` | Integer | Peso (1 = raro, 10 = comum) |
| `mensagem_vitoria` | TextField | Mensagem exibida ao ganhar |
| `cidades_permitidas` | M2M Cidade | Restrição geográfica (null = todas) |

#### RoletaConfig (Singleton)
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `custo_giro` | Integer | Custo em pontos de saldo |
| `xp_por_giro` | Integer | XP ganho por giro |
| `nome_clube` | CharField(100) | Nome do clube (default "Clube MegaLink") |
| `limite_giros_por_membro` | Integer | Máx giros (0 = ilimitado) |
| `periodo_limite` | CharField | total, diario, semanal, mensal |

#### ParticipanteRoleta
Tabela: auto

Registro de cada giro na roleta.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `membro` | FK MembroClube (nullable) | Membro (se autenticado) |
| `nome`, `cpf`, `telefone`, `email` | Dados diretos | Para não membros |
| `endereco`, `bairro`, `cidade`, `estado`, `cep` | Endereço | Localização |
| `premio` | CharField(255) | Prêmio ganho |
| `canal_origem` | CharField(100) | Canal (default "Online") |
| `perfil_cliente` | CharField(10) | "sim" ou "nao" |
| `saldo` | Integer | Saldo no momento do giro |
| `status` | CharField(50) | reservado, ganhou, inviavel_tec, inviavel_cani |

#### RouletteAsset
Tabela: auto

Elementos visuais da roleta (frames, fundo, logo, ponteiro). Tipo: frame, background, logo, pointer. Campo `ordem` (0-12 para frames).

#### BannerClube
Tabela: auto

Banners da landing page pública. Campos: titulo, imagem, link, ordem, ativo.

#### LandingConfig (Singleton)
Tabela: auto

Configuração da landing page pública do clube.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `titulo` / `subtitulo` | CharField | Textos principais |
| `whatsapp_numero` / `whatsapp_mensagem` | CharField | WhatsApp de suporte |
| `texto_como_funciona` | TextField | Seção "Como funciona" (markdown) |
| `texto_rodape` | CharField | Rodapé |
| `cor_primaria` / `cor_secundaria` | CharField(7) | Cores hex |
| `logo` | ImageField | Logo do clube |
| `ativo` | Boolean | Status |

#### Cidade
Tabela: auto | Unique: (tenant, nome)

Cidades disponíveis para restrição geográfica de prêmios, cupons e parceiros.

### Services (4)

#### GamificationService (`services/gamification_service.py`)

| Método | O que faz |
|--------|-----------|
| `atribuir_pontos(membro, gatilho, descricao_extra)` | Busca RegraPontuacao pelo gatilho, valida limite_por_membro, incrementa saldo e xp_total com `F()` (atômico), cria ExtratoPontuacao. Retorna (sucesso, mensagem) |

**Usado por:** automações (ação `dar_pontos`), signals de indicação, OTP validado, cadastro.

#### OTPService (`services/otp_service.py`)

| Método | O que faz |
|--------|-----------|
| `gerar_codigo()` | Gera código aleatório de 6 dígitos |
| `enviar_otp_whatsapp(cpf, telefone, codigo)` | Envia OTP via webhook N8N. Retorna (sucesso, mensagem) |

#### SorteioService (`services/sorteio_service.py`)

| Método | O que faz |
|--------|-----------|
| `executar_giro_roleta(membro, premios, custo_giro)` | Deduz saldo, sorteia prêmio com `random.choices()` (probabilidade ponderada), retorna (novo_saldo, premio, posicao) |

#### HubsoftService (`services/hubsoft_service.py`)

| Método | O que faz |
|--------|-----------|
| `consultar_cliente(cpf)` | Consulta cliente no HubSoft via webhook N8N. Retorna dict com dados + telefone mascarado |
| `checar_pontos_extras_cpf(cpf)` | Consulta recorrência, pagamento adiantado e uso do app. Retorna dict com flags booleanas |

### Views (35+ funções)

#### Área pública (sem login)

| View | Rota | Descrição |
|------|------|-----------|
| `landing_clube` | `/roleta/clube/` | Landing page pública com parceiros, cupons, prêmios, níveis |
| `roleta_index` | `/roleta/` | Frontend da roleta (dados via API JSON) |
| `roleta_logout` | `/roleta/logout/` | Limpa sessão e redireciona |

#### APIs (JSON)

| View | Rota | Descrição |
|------|------|-----------|
| `roleta_init_dados` | `/roleta/api/init-dados/` | Endpoint principal: retorna auth_membro, config, cidades, assets, premios, missoes, cupons, indicacao |
| `cadastrar_participante` | `/roleta/cadastrar/` | Cadastro de membro + registro de participante |
| `verificar_cliente` | `/roleta/verificar-cliente/` | Consulta CPF no HubSoft |
| `solicitar_otp` | `/roleta/solicitar-otp/` | Envia código OTP via WhatsApp |
| `validar_otp` | `/roleta/validar-otp/` | Valida código + atribui pontos de telefone_verificado |
| `pre_cadastrar` | `/roleta/pre-cadastrar/` | Pré-cadastro para membros não validados |
| `api_resgatar_cupom` | `/roleta/api/cupons/resgatar/` | Resgate de cupom (debita pontos/valida nível) |
| `api_criar_indicacao` | `/roleta/api/indicacao/criar/` | Cria indicação |

#### Área do membro (sessão autenticada)

| View | Rota | Descrição |
|------|------|-----------|
| `membro_hub` | `/roleta/membro/` | Hub do membro (4 cards com contadores) |
| `membro_jogar` | `/roleta/membro/jogar/` | Página da roleta |
| `membro_missoes` | `/roleta/membro/missoes/` | Lista de missões com status |
| `membro_cupons` | `/roleta/membro/cupons/` | Cupons disponíveis + histórico de resgates |
| `membro_indicar` | `/roleta/membro/indicar/` | Página de indicação com código |
| `membro_perfil` | `/roleta/membro/perfil/` | Edição de perfil |
| `membro_faq` | `/roleta/membro/faq/` | FAQs |

#### Dashboard admin (@login_required)

| View | Rota | Descrição |
|------|------|-----------|
| `dashboard_home` | `/roleta/dashboard/` | KPIs, variação 7 dias, gráficos (pizza prêmios + linha 7 dias), ganhadores recentes |
| `dashboard_premios` | `/roleta/dashboard/premios/` | CRUD de prêmios |
| `dashboard_participantes` | `/roleta/dashboard/participantes/` | Gestão de membros (busca, filtro cidade, editar saldo) |
| `dashboard_extrato_membro` | `/roleta/dashboard/participantes/<id>/extrato/` | Extrato de pontuação do membro |
| `dashboard_giros` | `/roleta/dashboard/giros/` | Histórico de giros |
| `dashboard_cidades` | `/roleta/dashboard/cidades/` | CRUD de cidades |
| `dashboard_assets` | `/roleta/dashboard/assets/` | Upload de assets visuais da roleta |
| `dashboard_config` | `/roleta/dashboard/config/` | Config da roleta (custo, XP, limites) |
| `dashboard_gamificacao` | `/roleta/dashboard/gamificacao/` | CRUD de regras e níveis |
| `dashboard_landing_config` | `/roleta/dashboard/landing/` | Config da landing page |
| `dashboard_banners` | `/roleta/dashboard/banners/` | CRUD de banners |
| `dashboard_categorias` | `/roleta/dashboard/categorias/` | Categorias de parceiros |
| `dashboard_relatorios` | `/roleta/dashboard/relatorios/` | Relatórios gerais |
| `dashboard_relatorios_indicacoes` | `/roleta/dashboard/relatorios/indicacoes/` | Relatórios de indicações |
| `dashboard_relatorios_parceiros` | `/roleta/dashboard/relatorios/parceiros/` | Relatórios de parceiros |
| `exportar_csv` | `/roleta/dashboard/exportar/` | Exportação CSV de membros/participantes |
| `documentacao` | `/roleta/dashboard/docs/` | Documentação da API |

### Templates (20+)

| Template | Descrição |
|----------|-----------|
| `index_frontend.html` | Frontend da roleta (JS + animações) |
| `landing_clube.html` | Landing page pública (parceiros, cupons, níveis) |
| `membro/hub.html` | Hub do membro |
| `membro/jogar.html` | Página de jogo |
| `membro/missoes.html` | Lista de missões |
| `membro/cupons.html` | Cupons e resgates |
| `membro/indicar.html` | Indicação com código |
| `membro/perfil.html` | Perfil do membro |
| `membro/faq.html` | FAQs |
| `dashboard/home.html` | Dashboard principal |
| `dashboard/premios.html` | Gestão de prêmios |
| `dashboard/participantes.html` | Gestão de membros |
| `dashboard/extrato_membro.html` | Extrato individual |
| `dashboard/giros.html` | Histórico de giros |
| `dashboard/config.html` | Configuração da roleta |
| `dashboard/gamificacao.html` | Regras e níveis |
| `dashboard/relatorios.html` | Relatórios |
| `dashboard/relatorios_indicacoes.html` | Relatórios de indicações |
| `dashboard/relatorios_parceiros.html` | Relatórios de parceiros |

### Management Commands

| Command | Descrição |
|---------|-----------|
| `gerar_faq` | Gera/atualiza FAQs via IA. Flags: --force, --categoria, --dry-run |
| `testar_pontuacoes` | Testa scoring com dados reais do HubSoft. Flags: --qtd, --cpf, --buscar-adiantado |

### Admin

**MembroClubeAdmin:** list com nome/cpf/telefone/validado/saldo/nivel_atual. Filtro por validado. Inline ExtratoPontuacao.

**PremioRoletaAdmin:** list com nome/quantidade/probabilidade. Filter horizontal cidades_permitidas. Editable quantidade.

**RegraPontuacaoAdmin:** list com nome_exibicao/gatilho/pontos/ativo/visivel. Editable fields.

---

## 2. Parceiros (`apps/cs/parceiros/`)

### O que faz
Gerencia rede de parceiros comerciais com descontos exclusivos para membros do clube. Parceiros cadastram cupons que podem ser gratuitos, custar pontos ou exigir nível mínimo. Inclui fluxo completo de aprovação, resgate e validação no ponto de venda.

### Models (4)

#### CategoriaParceiro
Tabela: auto | Unique: (tenant, slug)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(100) | Nome da categoria |
| `slug` | SlugField | Slug único/tenant |
| `icone` | CharField(50) | Classe FontAwesome (default "fas fa-tag") |
| `ordem` | Integer | Ordem de exibição |
| `ativo` | Boolean | Status |

#### Parceiro
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(255) | Nome do parceiro |
| `logo` | ImageField | Logo (tenant_upload_path) |
| `descricao` | TextField | Descrição |
| `contato_nome` / `contato_telefone` / `contato_email` | Char/Email | Dados de contato |
| `usuario` | OneToOne User | Acesso ao painel de parceiro |
| `categoria` | FK CategoriaParceiro | Categoria |
| `cidades` | M2M Cidade | Cobertura geográfica |
| `ativo` | Boolean | Status |

#### CupomDesconto
Tabela: auto | Unique: (tenant, codigo)

| Grupo | Campos principais |
|-------|-------------------|
| **Identificação** | titulo (255), descricao, imagem, codigo (50, unique/tenant) |
| **Desconto** | tipo_desconto (percentual/fixo), valor_desconto (Decimal 10,2) |
| **Modalidade** | modalidade: gratuito (livre), pontos (custo em saldo), nivel (exige NivelClube mínimo) |
| **Custo** | custo_pontos (Integer, quando modalidade=pontos), nivel_minimo (FK NivelClube, quando modalidade=nivel) |
| **Estoque** | quantidade_total (0 = ilimitado), quantidade_resgatada (auto), limite_por_membro (default 1) |
| **Período** | data_inicio, data_fim (DateTime) |
| **Restrição** | cidades_permitidas (M2M Cidade), parceiro (FK Parceiro) |
| **Aprovação** | status_aprovacao (aprovado/pendente/rejeitado), motivo_rejeicao |
| **Status** | ativo |

**Propriedades:** `estoque_disponivel` (bool), `estoque_restante` (int ou "Ilimitado")

#### ResgateCupom
Tabela: auto | Unique: (tenant, codigo_unico)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `membro` | FK MembroClube | Quem resgatou |
| `cupom` | FK CupomDesconto | Cupom resgatado |
| `codigo_unico` | CharField(20) | UUID gerado (para validação) |
| `pontos_gastos` | Integer | Pontos debitados |
| `status` | CharField | resgatado, utilizado, expirado, cancelado |
| `valor_compra` | Decimal(10,2) | Valor da compra (preenchido na validação) |
| `data_resgate` | DateTime (auto) | Quando resgatou |
| `data_utilizacao` | DateTime | Quando utilizou no parceiro |

### Services

#### CupomService (`services/services.py`)

| Método | O que faz |
|--------|-----------|
| `resgatar_cupom(membro, cupom_id)` | Validações: ativo, período, estoque, limite/membro, cidade, pontos/nível. Debita saldo (se pontos). Cria ResgateCupom com codigo_unico UUID. Retorna (sucesso, mensagem, resgate) |
| `cupons_disponiveis(membro)` | Filtra cupons ativos, aprovados, em período, com estoque, por cidade. Retorna queryset |

### Views (6)

#### Dashboard admin

| View | Rota | Descrição |
|------|------|-----------|
| `dashboard_parceiros_home` | `/roleta/dashboard/parceiros/` | KPIs (total, cupons, resgates, utilizados), variação 7 dias, gráfico evolução, top cupons |
| `dashboard_parceiros` | `/roleta/dashboard/parceiros/lista/` | CRUD de parceiros com busca |
| `dashboard_cupons` | `/roleta/dashboard/cupons/` | CRUD de cupons com filtros (parceiro, modalidade, aprovação). Ações: aprovar/rejeitar |
| `dashboard_cupom_detalhe` | `/roleta/dashboard/cupons/<id>/` | Detalhe do cupom com KPIs e lista de resgates |
| `dashboard_cupons_resgates` | `/roleta/dashboard/cupons/resgates/` | Histórico de resgates com filtros (busca, status) |

#### Página pública

| View | Rota | Descrição |
|------|------|-----------|
| `validar_cupom` | `/roleta/cupom/validar/` | Validação no ponto de venda. Busca por codigo_unico, confirma uso, registra valor_compra |

### Templates (5+)

| Template | Descrição |
|----------|-----------|
| `dashboard/home.html` | Dashboard de parceiros com KPIs e gráficos |
| `dashboard/parceiros.html` | CRUD de parceiros |
| `dashboard/cupons.html` | Gestão de cupons |
| `dashboard/cupom_detalhe.html` | Detalhe + resgates |
| `dashboard/cupons_resgates.html` | Histórico de resgates |
| `validar_cupom.html` | Página pública de validação |

### Admin

**ParceiroAdmin:** list com nome/ativo/data_cadastro. Filtro por ativo.

**CupomDescontoAdmin:** list com titulo/parceiro/modalidade/tipo/valor/ativo. Filtros por ativo/modalidade/parceiro.

**ResgateCupomAdmin:** list com membro/cupom/codigo_unico/status. Filtro por status.

---

## 3. Indicações (`apps/cs/indicacoes/`)

### O que faz
Programa de indicação member-get-member. Cada membro do clube recebe um código único de indicação e uma página pública personalizada. Quando a indicação é convertida (contato feito, virou cliente), o indicador ganha pontos automaticamente via GamificationService.

### Models (2)

#### IndicacaoConfig (Singleton)
Tabela: auto

Configuração visual da página pública de indicação.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `titulo` / `subtitulo` | CharField | Textos (default "Megalink", "Clube de Fidelidade") |
| `texto_indicador` | CharField | "Você foi indicado por" |
| `texto_botao` | CharField | "Enviar Indicação" |
| `texto_sucesso_titulo` / `texto_sucesso_msg` | Char/Text | Mensagem de sucesso |
| `logo` / `imagem_fundo` | ImageField | Visuais |
| `cor_fundo` / `cor_botao` | CharField(7) | Cores hex |
| `mostrar_campo_cpf` / `mostrar_campo_cidade` | Boolean | Campos opcionais |

#### Indicacao
Tabela: auto | Unique: (membro_indicador, telefone_indicado)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `membro_indicador` | FK MembroClube | Quem indicou |
| `nome_indicado` | CharField(255) | Nome do indicado |
| `telefone_indicado` | CharField(20) | Telefone |
| `cpf_indicado` | CharField(14) | CPF (opcional) |
| `cidade_indicado` | CharField(100) | Cidade (opcional) |
| `status` | CharField | pendente, contato_feito, convertido, cancelado |
| `membro_indicado` | FK MembroClube (nullable) | Membro criado (quando converteu) |
| `pontos_creditados` | Boolean | Se os pontos já foram dados |
| `data_indicacao` | DateTime (auto) | Quando indicou |
| `data_conversao` | DateTime | Quando converteu |
| `observacoes` | TextField | Observações |

### Services

#### IndicacaoService (`services/services.py`)

| Método | O que faz |
|--------|-----------|
| `criar_indicacao(membro_indicador, nome, telefone, cpf, cidade)` | Valida: sem auto-indicação, sem duplicata (indicador + telefone). Cria Indicacao. Retorna (sucesso, msg, indicação) |
| `confirmar_conversao(indicacao_id)` | Marca status=convertido, data_conversao=now(). Chama GamificationService.atribuir_pontos(gatilho='indicacao_convertida'). Marca pontos_creditados=True. @transaction.atomic |

### Views (5)

| View | Rota | Auth | Descrição |
|------|------|------|-----------|
| `dashboard_indicacoes_home` | `/roleta/dashboard/indicacoes/` | @login_required | KPIs (total, pendentes, convertidos, taxa), variação 7 dias, top 5 embaixadores |
| `dashboard_indicacoes` | `/roleta/dashboard/indicacoes/lista/` | @login_required | Lista com filtros (busca, status), ações (alterar_status, adicionar_obs) |
| `dashboard_indicacoes_membros` | `/roleta/dashboard/indicacoes/membros/` | @login_required | Membros com contagem de indicações, auto-gera código |
| `dashboard_indicacoes_visual` | `/roleta/dashboard/indicacoes/visual/` | @login_required | Config visual da página pública |
| `pagina_indicacao` | `/roleta/indicar/<codigo>/` | Público | Página pública de indicação. Busca membro pelo código, form de indicação |

### Templates (5+)

| Template | Descrição |
|----------|-----------|
| `dashboard/home.html` | Dashboard com KPIs, gráfico 7 dias, top embaixadores |
| `dashboard/indicacoes.html` | Lista de indicações com filtros |
| `dashboard/membros.html` | Membros embaixadores |
| `dashboard/visual.html` | Config visual |
| `pagina_indicacao.html` | Página pública personalizada |

### Admin

**IndicacaoAdmin:** list com indicador/nome_indicado/telefone/status/pontos_creditados/data. Filtros por status/pontos_creditados.

---

## 4. Carteirinha (`apps/cs/carteirinha/`)

### O que faz
Sistema de carteirinha digital para membros do clube. Modelos visuais configuráveis (cores, logo, background), regras de atribuição automática (por nível, XP, cidade ou todos), QR code de validação e foto do membro.

### Models (3)

#### ModeloCarteirinha
Tabela: auto

Template visual da carteirinha.

| Grupo | Campos principais |
|-------|-------------------|
| **Identificação** | nome (100), descricao |
| **Fundo** | tipo_fundo (cor/imagem), cor_fundo_primaria, cor_fundo_secundaria, imagem_fundo |
| **Textos** | cor_texto, cor_texto_secundario, cor_destaque, texto_marca ("Clube Megalink"), texto_rodape |
| **Logo** | logo (ImageField) |
| **Visibilidade** | mostrar_nome, mostrar_cpf, mostrar_nivel, mostrar_data_emissao, mostrar_data_validade, mostrar_qr_code, mostrar_foto, mostrar_pontos, mostrar_cidade |
| **Status** | ativo, data_criacao |

#### RegraAtribuicao
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `modelo` | FK ModeloCarteirinha | Modelo a atribuir |
| `tipo` | CharField | nivel, pontuacao_minima, cidade, todos, manual |
| `nivel` | FK NivelClube | Quando tipo=nivel |
| `pontuacao_minima` | Integer | Quando tipo=pontuacao_minima (XP mínimo) |
| `cidade` | CharField(100) | Quando tipo=cidade |
| `prioridade` | Integer | Maior vence em conflito |
| `ativo` | Boolean | Status |

#### CarteirinhaMembro
Tabela: auto

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `membro` | FK MembroClube | Dono |
| `modelo` | FK ModeloCarteirinha | Template visual |
| `foto` | ImageField | Foto do membro |
| `data_emissao` | DateTime (auto) | Quando emitiu |
| `data_validade` | DateField | Validade |
| `ativo` | Boolean | Status |

### Services

#### CarteirinhaService (`services/services.py`)

| Método | O que faz |
|--------|-----------|
| `obter_modelo_para_membro(membro)` | Avalia regras (por prioridade desc): todos → nível → pontuacao_minima → cidade. Fallback: primeiro modelo ativo |
| `obter_carteirinha_membro(membro)` | Retorna CarteirinhaMembro existente ou cria automaticamente via regras. Usa update_or_create() |

### Views (7)

| View | Rota | Auth | Descrição |
|------|------|------|-----------|
| `dashboard_carteirinha` | `/roleta/dashboard/carteirinha/` | @login_required | Home: modelos, regras, total emitidas |
| `dashboard_modelos` | `/roleta/dashboard/carteirinha/modelos/` | @login_required | CRUD de modelos |
| `dashboard_modelo_criar` | `/roleta/dashboard/carteirinha/modelos/criar/` | @login_required | Criação com preview |
| `dashboard_modelo_editar` | `/roleta/dashboard/carteirinha/modelos/<id>/editar/` | @login_required | Edição com preview |
| `dashboard_regras` | `/roleta/dashboard/carteirinha/regras/` | @login_required | CRUD de regras de atribuição |
| `dashboard_preview` | `/roleta/dashboard/carteirinha/preview/<id>/` | @login_required | Preview com dados fake |
| `membro_carteirinha` | `/roleta/membro/carteirinha/` | Sessão membro | Carteirinha do membro (auto-criada) |

### Admin

**ModeloCarteirinhaAdmin:** list com nome/ativo/data_criacao.

**RegraAtribuicaoAdmin:** list com modelo/tipo/prioridade/ativo.

**CarteirinhaMembroAdmin:** list com membro/modelo/data_emissao/ativo.

---

## 5. NPS (`apps/cs/nps/`) [stub]

### O que faz
Pesquisa de satisfação Net Promoter Score. Estrutura de models criada, views e URLs pendentes.

### Models (2)

#### ConfiguracaoNPS (Singleton)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `periodicidade_dias` | Integer(90) | Intervalo entre pesquisas |
| `canal_envio` | CharField | whatsapp, email, ambos |
| `mensagem_template` | TextField | Template da mensagem |
| `ativo` | Boolean | Status |

#### PesquisaNPS

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `membro` | FK MembroClube | Membro (se aplicável) |
| `nota` | Integer(0-10) | Nota NPS |
| `comentario` | TextField | Comentário livre |
| `categoria` | CharField | promotor (9-10), neutro (7-8), detrator (0-6) — auto-calculada |
| `canal_resposta` | CharField | whatsapp (default) |
| `data_envio` / `data_resposta` | DateTime | Timestamps |
| `respondida` | Boolean | Se respondeu |

### Status
Models registrados no admin. Views e URLs vazios (TODO).

---

## 6. Retenção (`apps/cs/retencao/`) [stub]

### O que faz
Prevenção de churn com score de saúde do cliente e alertas automáticos. Estrutura de models criada, views e URLs pendentes.

**Nota:** O CRM já possui AlertaRetencao e scanner de contratos HubSoft (`apps/comercial/crm/`). Este módulo complementará com score de saúde e ações de retenção dedicadas.

### Models (3)

#### ScoreCliente

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `score` | Integer(0-100, default 50) | Score de saúde |
| `fatores` | JSONField | Fatores que compõem o score |
| `ultima_atualizacao` | DateTime (auto) | Último cálculo |

#### AlertaChurn

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `tipo` | CharField | inadimplencia, sem_uso, reclamacao, contrato_expirando |
| `severidade` | CharField | baixa, media, alta, critica |
| `descricao` | TextField | Detalhes |
| `resolvido` | Boolean | Status |
| `data_criacao` / `data_resolucao` | DateTime | Timestamps |

#### AcaoRetencao

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `alerta` | FK AlertaChurn | Alerta relacionado |
| `tipo_acao` | CharField | contato_whatsapp, oferta_desconto, upgrade_plano, visita_tecnica |
| `descricao` | TextField | Detalhes |
| `responsavel` | FK User | Quem executa |
| `executada` | Boolean | Status |
| `data_criacao` / `data_execucao` | DateTime | Timestamps |

### Status
Models registrados no admin com config básica. Views e URLs vazios (TODO).

---

## Sidebar do Painel

O módulo CS organiza o menu lateral em 3 seções:

```
CUSTOMER SUCCESS
├── Dashboard          → clube:dashboard_home
└── Clientes           → clube:dashboard_participantes

FIDELIZAÇÃO
├── Indicações         → indicacoes:dashboard_indicacoes_home
├── Parceiros          → parceiros:dashboard_parceiros_home
├── Cupons             → parceiros:dashboard_cupons
└── Roleta             → clube:dashboard_premios

CONFIGURAÇÕES
├── Banners            → clube:dashboard_banners
├── Carteirinhas       → carteirinha:dashboard_carteirinha
└── Níveis e XP        → clube:dashboard_gamificacao
```

---

## Integrações entre Submódulos

```
Clube ──GamificationService──▶ Indicações (pontos ao converter)
Clube ──GamificationService──▶ Automações (ação dar_pontos)
Clube ──MembroClube──▶ Parceiros (cupons exigem membro)
Clube ──NivelClube──▶ Parceiros (cupons por nível)
Clube ──Cidade──▶ Parceiros + Prêmios (restrição geográfica)
Indicações ──IndicacaoService──▶ Clube (confirmar_conversao → atribuir_pontos)
Parceiros ──CupomService──▶ Clube (debita saldo, valida nível)
Carteirinha ──CarteirinhaService──▶ Clube (NivelClube, XP para regras)
```

---

## Integrações Externas

| Serviço | Uso | Integração |
|---------|-----|------------|
| **N8N** | OTP via WhatsApp, consulta HubSoft | Webhook POST |
| **HubSoft** | Consulta de clientes por CPF, verificação de recorrência/adiantamento/app | Webhook N8N ou conexão PostgreSQL direta |

---

## Estatísticas do Módulo

| Métrica | Valor |
|---------|-------|
| **Sub-apps** | 6 (clube, parceiros, indicacoes, carteirinha, nps, retencao) |
| **Models** | 24 (10 clube + 4 parceiros + 2 indicações + 3 carteirinha + 2 NPS + 3 retenção) |
| **Views** | 55+ funções |
| **Templates** | 30+ |
| **APIs** | 40+ endpoints |
| **Services** | 6 (Gamification, OTP, Sorteio, Hubsoft, Cupom, Indicação, Carteirinha) |
| **Management Commands** | 2 (gerar_faq, testar_pontuacoes) |
| **Linhas de código** | ~6.000+ (models + views + services) |
