# Collection Postman da Matrix (Chatbots & IA API)

A collection oficial da Matrix Brasil **deve viver como arquivo `Chatbots-IA-API.postman_collection.json` nesta mesma pasta**.

## Como atualizar

1. Exportar a collection no Postman: `Chatbots & IA API` -> botao `...` -> `Export` -> formato `Collection v2.1`.
2. Salvar como `Chatbots-IA-API.postman_collection.json` nesta pasta (substituindo a versao anterior).
3. Commit com mensagem do tipo `docs(matrix): atualiza collection postman (vYYYY-MM-DD)`.
4. Atualizar a linha "Versao da collection" no [README.md](README.md) com a data.

## Por que nao versionar inline aqui

A collection tem ~25k linhas. Pra evitar ruido no diff e estourar limite de visualizacao, mantemos so a doc legivel (`01-*.md`, `02-*.md`, etc) na pasta. A collection bruta serve como **fonte da verdade** quando ha divergencia entre o que escrevemos e o que a Matrix retorna; se uma rota nao existir na collection, ela nao existe.

## Estrutura esperada do JSON

A collection segue o padrao Postman v2.1.0:

```
Chatbots & IA - V1/
├── Atendimento/
├── Contato/
├── Blacklist/
├── Relatorios/
├── HSM/
├── Agente/
├── Conta/
└── Opt-in/
Chatbots & IA - V2/
├── Agentes/
├── Atendimento/
├── Autenticacao/
├── Blacklist/
├── Blocklist/
├── Canais/
├── Catalogo/
├── Contato/
├── Destino/
├── Dialogo WhatsApp/
├── Export/
├── Flow/
├── Grupos/
├── HSM/
├── Integracao Voz/
├── Janela Sessao/
├── Logs/
├── Relatorios/
├── Tabela Generica/
├── Workplace/
└── Opt-in/
```

## Variaveis da collection

| Variavel | Valor padrao | Descricao |
|---|---|---|
| `baseUrl` | `https://seu-dominio` | URL da instancia Matrix do tenant |
| `token` | `API Key` | Token v1 |
| `Bearer` | `Bearer token` | Token v2 (JWT) |
| `cod_conta` | `1` | Conta padrao |
| `cod_pesquisa` | `1` | Pesquisa padrao |
