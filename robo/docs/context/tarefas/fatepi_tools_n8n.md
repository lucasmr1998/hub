# Tools N8N — Agente Pedro FATEPI

Configuracao das HTTP Request Tools conectadas ao no do agente IA.

---

## Tool 1: Atualizar Lead

- Nome: Atualizar Lead
- Descricao do no: Salva informacoes do candidato como nome completo, email, cidade e estado. Chame esta tool sempre que coletar um dado pessoal novo do candidato durante a conversa.
- Method: PUT
- URL: https://SEU-DOMINIO/api/v1/n8n/leads/{{ $json._aurora.lead_id || $json.lead_id }}/
- Headers: Authorization = Bearer qB0L0dkBULVQd6KlMlg24HV1hGxxQqIoFUrzZVN6yEU
- Send Body: ON
- Body Content Type: JSON
- Specify Body: Using Fields Below
- Body Parameters:

| Name | Value | Description |
|------|-------|-------------|
| nome_razaosocial | Defined automatically by the model | Nome completo do candidato |
| email | Defined automatically by the model | Email do candidato |
| cidade | Defined automatically by the model | Cidade do candidato |
| estado | Defined automatically by the model | UF do estado, exemplo: PI, SP, RJ |
| cpf_cnpj | Defined automatically by the model | CPF do candidato se informado |

---

## Tool 2: Atualizar Oportunidade

- Nome: Atualizar Oportunidade
- Descricao do no: Salva o curso de interesse, forma de ingresso e move o estagio do candidato no funil de vendas. Chame esta tool quando o candidato definir o curso, forma de ingresso ou avancar no processo.
- Method: PUT
- URL: https://SEU-DOMINIO/api/v1/n8n/crm/oportunidades/{{ $json._aurora.oportunidade_id }}/
- Headers: Authorization = Bearer qB0L0dkBULVQd6KlMlg24HV1hGxxQqIoFUrzZVN6yEU
- Send Body: ON
- Body Content Type: JSON
- Specify Body: Using Fields Below
- Body Parameters:

| Name | Value | Description |
|------|-------|-------------|
| estagio_slug | Defined automatically by the model | Estagio atual do candidato. Valores: novo, qualificacao, qualificado, agendado, matriculado, perdido |
| dados_custom.curso_interesse | Defined automatically by the model | Apenas o nome do curso. Exemplo: Direito, Enfermagem, Psicologia |
| dados_custom.forma_ingresso | Defined automatically by the model | Apenas a forma de ingresso. Valores: ENEM, Prova Online, Transferencia |
| dados_custom.status_matricula | Defined automatically by the model | Status da matricula. Valores: aguardando, pagamento_realizado, desistiu |

---

## Notas

- SEMPRE terminar a URL com / (barra final), senao o Django retorna 404
- Substituir SEU-DOMINIO pela URL do ngrok ou dominio de producao
- O lead_id e oportunidade_id vem no payload que nosso sistema envia ao N8N (campo _aurora)
- A API aceita campos flat com prefixo "dados_custom." e converte para JSON aninhado automaticamente
- Campos vazios sao ignorados pela API
- O no do agente IA deve ser versao 2.0+ (recriar o no se estiver na versao 1.x)
