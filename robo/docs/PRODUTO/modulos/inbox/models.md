# Inbox — Models

17 models organizados em 5 areas. Todos herdam de `TenantMixin` (multi-tenancy automatico).

---

## Core

| Model | Tabela | Descricao |
|-------|--------|-----------|
| `CanalInbox` | `inbox_canais` | Configuracao do canal: tipo (whatsapp/widget/email/interno) + webhook URLs |
| `EtiquetaConversa` | `inbox_etiquetas` | Labels/tags com cor para classificar conversas |
| `Conversa` | `inbox_conversas` | Conversa principal: canal, lead, agente, equipe, fila, status, etiquetas |
| `Mensagem` | `inbox_mensagens` | Mensagem individual: remetente, tipo de conteudo, lida, entrega, erro |
| `RespostaRapida` | `inbox_respostas_rapidas` | Templates de resposta com atalhos (ex: `/ola`) |
| `NotaInternaConversa` | `inbox_notas_internas` | Notas visiveis apenas para agentes |

---

## Equipes e filas

| Model | Tabela | Descricao |
|-------|--------|-----------|
| `EquipeInbox` | `inbox_equipes` | Equipe de atendimento com lider, cor, membros |
| `MembroEquipeInbox` | `inbox_membros_equipe` | M2M: agente pode estar em multiplas equipes (agente/supervisor/gerente) |
| `PerfilAgenteInbox` | `inbox_perfis_agente` | Status do agente (online/ausente/offline) + capacidade maxima |
| `FilaInbox` | `inbox_filas` | Fila com modo de distribuicao (round-robin / menor carga / manual) |
| `RegraRoteamento` | `inbox_regras_roteamento` | Regra de roteamento por canal, etiqueta ou horario → direciona para fila |
| `HistoricoTransferencia` | `inbox_historico_transferencia` | Audit trail de transferencias entre agentes/equipes/filas |

---

## Configuracao

| Model | Tabela | Descricao |
|-------|--------|-----------|
| `HorarioAtendimento` | `inbox_horario_atendimento` | Dias/horas de funcionamento por tenant |
| `ConfiguracaoInbox` | `inbox_configuracao` | Singleton: mensagem fora do horario, distribuicao padrao |

---

## FAQ

| Model | Tabela | Descricao |
|-------|--------|-----------|
| `CategoriaFAQ` | `inbox_faq_categorias` | Categoria de artigos: nome, slug, icone, cor |
| `ArtigoFAQ` | `inbox_faq_artigos` | Artigo: titulo, conteudo HTML, visualizacoes |

---

## Widget

| Model | Tabela | Descricao |
|-------|--------|-----------|
| `WidgetConfig` | `inbox_widget_config` | Singleton: token publico UUID, cores, posicao, FAQ, campos obrigatorios, dominios |

---

## Campos importantes de `Conversa`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `numero` | PositiveIntegerField | Auto-increment por tenant |
| `canal` | FK → CanalInbox | Canal de origem |
| `lead` | FK → LeadProspecto | Vinculado automaticamente por telefone/email |
| `contato_nome` / `contato_telefone` / `contato_email` | CharField | Denormalizados para exibicao |
| `status` | CharField | aberta / pendente / resolvida / arquivada |
| `prioridade` | CharField | baixa / normal / alta / urgente |
| `agente` | FK → User | Atendente atribuido |
| `equipe` | FK → EquipeInbox | Equipe atribuida |
| `fila` | FK → FilaInbox | Fila de atendimento |
| `etiquetas` | M2M → EtiquetaConversa | Labels visuais |
| `ticket` | FK → Ticket | Link com suporte |
| `oportunidade` | FK → OportunidadeVenda | Link com CRM |
| `identificador_externo` | CharField | WhatsApp thread ID ou visitor_id do widget |
| `ultima_mensagem_em` / `ultima_mensagem_preview` | DateTime / Char | Para lista sem join |
| `mensagens_nao_lidas` | PositiveIntegerField | Badge |
| `tempo_primeira_resposta_seg` | PositiveIntegerField | SLA |
| `modo_atendimento` | CharField | bot / humano / finalizado_bot (ver [services.md](services.md)) |

---

## Indices

**Conversa:** `(status, agente)`, `(canal, status)`, `(ultima_mensagem_em)`, `(contato_telefone)`, `(equipe, status)`, `(fila, status)`
**Mensagem:** `(conversa, data_envio)`, `(identificador_externo)`
