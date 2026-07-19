# Snapshot de referencia do robo_v2 (nao executavel)

Copia do codigo-fonte do robo_v2 (projeto techub) trazida para o Hubtrix como
material de referencia do porte. NAO faz parte do app do Hubtrix, nao roda, nao
entra em INSTALLED_APPS e fica fora da arvore do projeto Django (mora em docs/).

Serve so para consulta: a logica do engine deterministico (ia_validacao/src),
o contrato da API e o CRM antigo (dashboard_comercial) que originaram o adaptador
`apps/comercial/robo_matrix`.

## O que foi removido antes de versionar (seguranca / LGPD)
. Banco sqlite de producao (817 MB, PII de clientes reais) e o .zst. Excluidos.
. Arquivo `.env` com credenciais. Excluido.
. Payloads capturados com CPF real (`posvenda_hubsoft/api_interna/templates/*.json`).
  Diretorio excluido.
. Docs com PII de cliente real (`docs/ROADMAP_AUTOMACAO_HUBSOFT.md`,
  `docs/RELATORIO_IMPLEMENTACOES_2026-06-24.md`). Removidos.
. Segredos hardcoded (senha HubSoft, senha do Postgres de producao, client_secret,
  usuario de API, IP do banco de producao) substituidos por `***REMOVIDO***` em
  `setup_hubsoft.py`, `settings.py`, `README.md` e `templates/vendas_web/documentacao.html`.
. venvs e __pycache__ excluidos.

Exemplos que permaneceram sao sinteticos (CPF de teste 11144477735, telefones
placeholder). Se precisar rodar o robo_v2 de verdade, use o repositorio techub
original, nao este snapshot.
