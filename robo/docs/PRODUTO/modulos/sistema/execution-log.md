# Execution Log — Modulo Sistema (tenants, usuarios, permissoes)

Entrada mais nova embaixo.

> **PII — LEIA:** este repositorio e **PUBLICO**. Nao registrar aqui nome, login,
> email ou telefone de pessoa de cliente. Descrever por PAPEL e QUANTIDADE; quem
> precisa do detalhe consulta o banco.

## 2026-07-14 — Provisionamento de usuarios da Nuvyon + 3 comandos novos

- **Contexto**: a Nuvyon pediu acesso pra 6 pessoas do comercial. O pedido chegou por mensagem e **nao existia em lugar nenhum do sistema** (sem tarefa no Workspace, sem doc), entao ninguem tinha onde conferir o que foi ou nao atendido.
- **Executado em prod** (autorizado nominalmente pelo dono): **4 usuarios criados** (2 com perfil Vendedor, 2 com Gerente Comercial) e **2 promovidos** de Vendedor pra Gerente Comercial. Nomes e logins ficam no banco, nao aqui.
- **Senha dos criados**: senha de onboarding definida pelo dono (`--senha`), com `senha_temporaria=True` — troca obrigatoria no primeiro login, entao a senha compartilhada nao sobrevive ao primeiro acesso. **Promovidos NAO tiveram a senha tocada.**
- **ARMADILHA (o motivo de existir um comando separado)**: o pedido veio como "cria esses 3 como gestores", mas **2 dos 3 JA EXISTIAM** como Vendedor, com carteira no nome. `criar_usuario` e idempotente por email: rodar nele um usuario existente **PULA em silencio**, e quem pediu acharia que promoveu. Promover e outra operacao, entao virou outro comando.
- **Efeito colateral que virou chamado**: quem e promovido continua com a **senha antiga**. Uma das promovidas nao acessava havia ~10 dias, tentou entrar com a senha de onboarding (que so vale pros criados) e nao conseguiu — de fora parecia "o acesso nao foi feito". Dai nasceu o `resetar_senha`.
- **Comandos criados** (versionados, com `--dry-run`, em vez de rodar script solto no shell de prod — o gate bloqueia isso, e com razao):
  - `criar_usuario --tenant <slug> --email <e> --perfil "<Perfil>" [--cargo <c>] [--equipe <nome>] [--senha <s>]` — User via Django (senha hasheada), PerfilUsuario (vinculo com o tenant), PermissaoUsuario e, opcional, PerfilVendedor (o que faz a pessoa entrar no filtro por time e no scorecard).
  - `promover_usuario --tenant <slug> --email <e> --perfil "<Perfil>" [--cargo <c>] [--equipe <nome>]` — troca perfil/cargo de quem ja existe. Mostra ANTES/DEPOIS, avisa quando a pessoa ainda tem carteira (**promover nao redistribui**), recusa usuario de OUTRO tenant (seria vazamento de acesso entre clientes) e nao mexe em senha.
  - `resetar_senha --tenant <slug> --email <e> [--senha <s>]` — reseta a senha com `senha_temporaria=True`.
- **PENDENTE (acao do cliente, nao nossa)**:
  1. **Nenhum dos 6 tem time.** So existe 1 equipe cadastrada (2 membros). Sem `PerfilVendedor.equipe` a pessoa nao entra no filtro por time do dashboard. Falta a Nuvyon definir a divisao.
  2. **Os 2 promovidos continuam com carteira** (1 e 4 oportunidades). Se sairam da operacao, precisa redistribuir.
- **Status**: completed (os 6 em prod, conferidos no banco).
