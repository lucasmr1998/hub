# Clube — Area do membro

Area autenticada (sessao do membro, nao do staff). Fluxo de autenticacao via OTP WhatsApp.

---

## OTPService

Arquivo: `apps/cs/clube/services/otp_service.py`

| Metodo | O que faz |
|--------|-----------|
| `gerar_codigo()` | Gera codigo aleatorio de 6 digitos |
| `enviar_otp_whatsapp(cpf, telefone, codigo)` | Envia OTP via webhook N8N. Retorna `(sucesso, mensagem)` |

### Fluxo de autenticacao

```
1. Usuario informa CPF → /roleta/verificar-cliente/
2. Sistema consulta HubSoft → retorna telefone mascarado
3. Usuario confirma → /roleta/solicitar-otp/ (OTPService.enviar_otp_whatsapp)
4. N8N envia WhatsApp com codigo
5. Usuario digita codigo → /roleta/validar-otp/
6. Se valida: cria sessao + atribui pontos (gatilho telefone_verificado)
7. Usuario redirecionado para /roleta/membro/
```

---

## Views autenticadas (sessao membro)

| View | Rota | Descricao |
|------|------|-----------|
| `membro_hub` | `/roleta/membro/` | Hub do membro (4 cards com contadores) |
| `membro_jogar` | `/roleta/membro/jogar/` | Pagina da roleta |
| `membro_missoes` | `/roleta/membro/missoes/` | Lista de missoes com status |
| `membro_cupons` | `/roleta/membro/cupons/` | Cupons disponiveis + historico de resgates |
| `membro_indicar` | `/roleta/membro/indicar/` | Pagina de indicacao com codigo |
| `membro_perfil` | `/roleta/membro/perfil/` | Edicao de perfil |
| `membro_faq` | `/roleta/membro/faq/` | FAQs |
| `membro_carteirinha` | `/roleta/membro/carteirinha/` | Carteirinha digital (ver [../carteirinha.md](../carteirinha.md)) |

---

## Templates

- `membro/hub.html` — Hub do membro
- `membro/jogar.html` — Pagina de jogo
- `membro/missoes.html` — Lista de missoes
- `membro/cupons.html` — Cupons e resgates
- `membro/indicar.html` — Indicacao com codigo
- `membro/perfil.html` — Perfil do membro
- `membro/faq.html` — FAQs

---

## Dashboard admin (@login_required do staff, nao do membro)

Views administrativas do clube — para o staff do provedor gerenciar.

| View | Rota | Descricao |
|------|------|-----------|
| `dashboard_home` | `/roleta/dashboard/` | KPIs, variacao 7 dias, graficos (pizza premios + linha 7 dias), ganhadores recentes |
| `dashboard_premios` | `/roleta/dashboard/premios/` | CRUD de premios |
| `dashboard_participantes` | `/roleta/dashboard/participantes/` | Gestao de membros (busca, filtro cidade, editar saldo) |
| `dashboard_extrato_membro` | `/roleta/dashboard/participantes/<id>/extrato/` | Extrato de pontuacao |
| `dashboard_giros` | `/roleta/dashboard/giros/` | Historico de giros |
| `dashboard_cidades` | `/roleta/dashboard/cidades/` | CRUD de cidades |
| `dashboard_assets` | `/roleta/dashboard/assets/` | Upload de assets visuais |
| `dashboard_config` | `/roleta/dashboard/config/` | Config da roleta |
| `dashboard_gamificacao` | `/roleta/dashboard/gamificacao/` | CRUD de regras e niveis |
| `dashboard_landing_config` | `/roleta/dashboard/landing/` | Config da landing page |
| `dashboard_banners` | `/roleta/dashboard/banners/` | CRUD de banners |
| `dashboard_categorias` | `/roleta/dashboard/categorias/` | Categorias de parceiros |
| `dashboard_relatorios` | `/roleta/dashboard/relatorios/` | Relatorios gerais |
| `dashboard_relatorios_indicacoes` | `/roleta/dashboard/relatorios/indicacoes/` | Relatorios de indicacoes |
| `dashboard_relatorios_parceiros` | `/roleta/dashboard/relatorios/parceiros/` | Relatorios de parceiros |
| `exportar_csv` | `/roleta/dashboard/exportar/` | Exportacao CSV de membros/participantes |
| `documentacao` | `/roleta/dashboard/docs/` | Documentacao da API |
