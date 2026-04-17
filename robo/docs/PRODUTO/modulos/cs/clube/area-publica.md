# Clube — Area publica

Paginas sem login + APIs publicas usadas pelo frontend da roleta.

---

## Views publicas

| View | Rota | Descricao |
|------|------|-----------|
| `landing_clube` | `/roleta/clube/` | Landing page publica com parceiros, cupons, premios, niveis |
| `roleta_index` | `/roleta/` | Frontend da roleta (dados via API JSON) |
| `roleta_logout` | `/roleta/logout/` | Limpa sessao e redireciona |

---

## APIs (JSON)

| View | Rota | Descricao |
|------|------|-----------|
| `roleta_init_dados` | `/roleta/api/init-dados/` | Endpoint principal: retorna auth_membro, config, cidades, assets, premios, missoes, cupons, indicacao |
| `cadastrar_participante` | `/roleta/cadastrar/` | Cadastro de membro + registro de participante |
| `verificar_cliente` | `/roleta/verificar-cliente/` | Consulta CPF no HubSoft |
| `solicitar_otp` | `/roleta/solicitar-otp/` | Envia codigo OTP via WhatsApp |
| `validar_otp` | `/roleta/validar-otp/` | Valida codigo + atribui pontos de `telefone_verificado` |
| `pre_cadastrar` | `/roleta/pre-cadastrar/` | Pre-cadastro para membros nao validados |
| `api_resgatar_cupom` | `/roleta/api/cupons/resgatar/` | Resgate de cupom (debita pontos/valida nivel) |
| `api_criar_indicacao` | `/roleta/api/indicacao/criar/` | Cria indicacao |

Ver [area-membro.md](area-membro.md) para OTP e area autenticada.

---

## LandingConfig (Singleton)

Configuracao da landing page publica do clube.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `titulo` / `subtitulo` | CharField | Textos principais |
| `whatsapp_numero` / `whatsapp_mensagem` | CharField | WhatsApp de suporte |
| `texto_como_funciona` | TextField | Secao "Como funciona" (markdown) |
| `texto_rodape` | CharField | Rodape |
| `cor_primaria` / `cor_secundaria` | CharField(7) | Cores hex |
| `logo` | ImageField | Logo do clube |
| `ativo` | Boolean | Status |

---

## BannerClube

Banners da landing page publica. Campos: `titulo`, `imagem`, `link`, `ordem`, `ativo`.

---

## Templates

- `index_frontend.html` — Frontend da roleta (JS + animacoes)
- `landing_clube.html` — Landing page publica (parceiros, cupons, niveis)
