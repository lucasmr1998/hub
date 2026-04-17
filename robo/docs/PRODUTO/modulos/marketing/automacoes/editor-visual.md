# Automacoes — Editor Visual

Editor Drawflow especifico das automacoes. Distinto do editor de [fluxos/](../../fluxos/editor-visual.md) (que e para fluxos de atendimento).

**URL:** `/marketing/automacoes/<pk>/fluxo/`
**Biblioteca:** Drawflow v0.0.59 (CDN)

---

## Paleta de nos

| Categoria | Nos disponiveis | Inputs/Outputs |
|-----------|-----------------|----------------|
| **Gatilhos** | 11 eventos (lead_criado, venda_aprovada, etc.) | 0 in / 1 out |
| **Condicoes** | Verificar Campo (campo + operador + valor) | 1 in / 2 out (sim/nao) |
| **Acoes** | WhatsApp, E-mail, Notificacao, Criar Tarefa, Mover Estagio, Atribuir Responsavel, Dar Pontos, Webhook | 1 in / 1 out |
| **Controle** | Atraso (minutos/horas/dias) | 1 in / 1 out |

Detalhes dos nos e configuracoes em [engine.md](engine.md#8-tipos-de-acao).

---

## Painel de configuracao por tipo

### Gatilhos

- **Oportunidade movida:** Pipeline (select), estagio de (select filtrado), estagio para (select filtrado)
- **Lead sem contato:** Dias sem contato (numero)
- **Entrou em segmento:** Segmento (select com segmentos do CRM)
- **Mensagem recebida:** Canal (select: WhatsApp/Email/Widget)
- Outros gatilhos: informativo (disparam sempre)

### Condicoes

- **Campo:** select com optgroups (Lead: origem/score/cidade/estado/valor/status/email/cpf | CRM: estagio/pipeline/responsavel | Temporal: dias sem contato)
- **Operador:** igual, diferente, contem, maior, menor, maior ou igual, menor ou igual
- **Valor:** campo dinamico que muda conforme o campo selecionado:
  - Origem → select com origens (site, facebook, whatsapp...)
  - Status → select com status do lead
  - Estagio → select com estagios de todos os pipelines
  - Pipeline → select com pipelines
  - Responsavel → select com usuarios staff
  - Estado → select com UFs
  - Demais → input texto livre

### Acoes

- **Enviar WhatsApp:** Mensagem com variaveis `{{lead_nome}}`, `{{lead_telefone}}`...
- **Enviar Email:** Assunto + corpo com variaveis
- **Notificacao:** Titulo + mensagem
- **Criar Tarefa:** Titulo, tipo (ligacao/followup/visita/whatsapp/email), prioridade (baixa/normal/alta/urgente)
- **Mover Estagio:** Pipeline (select), estagio destino (select filtrado por pipeline)
- **Atribuir Responsavel:** Modo (round-robin/fixo), responsavel (select com usuarios staff)
- **Dar Pontos:** Quantidade + motivo
- **Webhook:** URL, metodo (POST/GET), payload JSON

### Controle

- **Atraso:** Tempo + unidade (minutos/horas/dias)

Todos os nos tem botao "Remover no".

---

## Persistencia

Estado do Drawflow salvo como JSON em `regra.fluxo_json`. Nodos e conexoes persistidos como records no banco (`NodoFluxo`, `ConexaoNodo`) para o engine processar.

Se `fluxo_json` estiver vazio mas existirem nodos no banco, o editor reconstroi o grafo automaticamente.

---

## Por que um editor separado?

Os fluxos de atendimento ([fluxos/](../../fluxos/)) e as automacoes sao conceitos diferentes:

| Aspecto | Fluxos | Automacoes |
|---------|--------|------------|
| Gatilho | Mensagem do lead | Evento do sistema (signal/cron) |
| Execucao | Conversacional (pausa, espera) | Fire-and-forget (trigger → acoes) |
| Estado | Sessao ativa por lead | Stateless (execucao unica) |
| Tools | IA + respostas | 8 acoes fixas |

Usar o mesmo editor forcaria abstrair conceitos muito diferentes. Manter separados deixa cada editor focado no seu proposito.
