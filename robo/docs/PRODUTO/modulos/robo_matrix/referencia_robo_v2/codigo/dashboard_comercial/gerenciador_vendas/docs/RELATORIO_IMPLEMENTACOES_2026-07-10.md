# Relatório de Implementações — Robô de Vendas V2 (HubSoft)

**Data:** 10/07/2026
**Escopo:** hub de métricas (Análises), URA estruturada na API do engine, usuários
unificados com o Portal TecHub + Gestão de Usuários, e melhorias de UI/correções.
**Ambiente:** PRODUÇÃO — banco isolado `robovendas_v2`.
**Período coberto:** 08–10/07/2026 (continuação do relatório de 07/07).

---

## 1. Análises — hub único de métricas (08/07)

- `/analytics/` consolidou os relatórios: **4 blocos novos** — Indicações (total,
  conversão, ranking de indicadores, funil por estágio), Automação HubSoft (taxa de
  sucesso, por processo, últimas falhas), Operação do CRM (tempo médio por estágio,
  oportunidades paradas 7+ dias, carga por responsável) e Atrito do Robô (% de
  respostas inválidas por pergunta + recontatos).
- Páginas duplicadas/obsoletas aposentadas com redirect: `/relatorios/`,
  `/novo-dashboard/` e `/relatorio/conversoes/` (esta tinha números de exemplo).
- **Semântica corrigida:** "cliente convertido" = lead com **cadastro criado no
  HubSoft** (`id_hubsoft`) — antes o vínculo com a tabela de clientes inflava o
  número contando clientes já existentes apenas reconhecidos pelo CPF.
- Página reescrita no **padrão visual do projeto** (tema claro + sidebar) e gate
  RBAC `ver_analises` aplicado (página e API).
- Auditoria: 20 verificações payload × recomputação independente, todas OK.

**Arquivos:** `vendas_web/services/analytics.py`, `vendas_web/templates/vendas_web/
analytics.html`, `vendas_web/views.py`, `base.html` (sidebar).

## 2. URA estruturada no /proximo-passo (08/07)

Campo **aditivo** `ura` no retorno: quando a pergunta é de múltipla escolha, devolve
`{tipo, titulo (question_id), pergunta, opcoes:[{numero, texto}], total_opcoes,
respostas_validas}` — parseado da própria mensagem (funciona para URAs fixas E
dinâmicas: menu, planos com preço, datas, retomada). Pergunta aberta → `ura: null`.
Contrato antigo intacto. Referência: `docs/API_IA_VALIDACAO.md` §4.2b.

**Arquivos:** `ia_validacao/src/onboarding.py` (`montar_ura`), `ia_validacao/src/app.py`.

## 3. Usuários unificados com o Portal TecHub + Gestão de Usuários (10/07)

- **Sem perfil = sem acesso:** usuário autenticado sem Perfil de Acesso (e não
  admin) vê a página "Seu acesso ainda não foi liberado" em qualquer tela
  (bloqueio global no middleware). O acesso é liberado atribuindo um perfil.
- **Sincronização com o portal:** endpoint + botão que importa/atualiza as contas
  do TecHub (`/api/listar-usuarios/` com a mesma chave do SSO). Primeira execução:
  **623 usuários** (603 novos). Criados com senha inutilizável (login só via SSO)
  e sem perfil (pendentes).
- **Página Gestão de Usuários** (`/crm/usuarios/`, capacidade `gerenciar_usuarios`):
  busca instantânea, filtros Todos/Pendentes/Com acesso/Admins, KPIs, chips de
  perfil com adicionar/remover em 1 clique.

**Arquivos:** `vendas_web/rbac.py` (CAP_PADRAO vazio), `vendas_web/middleware.py`,
`vendas_web/templates/vendas_web/sem_acesso.html`, `crm/views.py`
(`usuarios_view`, `api_usuario_perfil`, `api_usuarios_sincronizar`),
`crm/templates/crm/usuarios.html`.

## 4. UI e correções

- **Oportunidade:** cards Oportunidade/Dados do Lead/Indicação/Hubsoft agora em
  **faixa horizontal acima da timeline** (campos internos em 2 colunas, responsivo).
- **"Outro CPF" limpa tudo:** ao escolher outro CPF na confirmação, o robô zera o
  cadastro anterior — antes, lead com cadastro completo transbordava indevidamente.
- **Confirmação vazia = sem mensagem:** confirmação de resposta deixada em branco
  na Central de Mensagens não envia nada (antes caía no fallback "Anotei!").
- **Nome higienizado** na saudação (ex.: "Thiago:" → "Thiago"); recontato sem
  emojis (viravam "?" no canal) e **sem loop** após a pausa.
- Varredura de O.S./atendimentos de teste: O.S. todas fechadas; 4 atendimentos de
  teste VENDA-VAREJO identificados como abertos (aguardando decisão de fechamento).

## 5. Documentação atualizada (10/07)

Central de Ajuda (guias Administrador/Gerente/Robô) cobrindo Gestão de Usuários,
Mensagens do Robô, Análises, recontato/retomada/viabilidade; `API_IA_VALIDACAO.md`
(campo `ura`); `RELATORIO_EXECUTIVO_ROBO_V2.md` (itens 2.17–2.19);
`DOCUMENTACAO_CRM_TECHUB.md` v1.1.
