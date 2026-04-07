# Analise Fluxo N8N — Consultoria Atendimento V1

**Data:** 06/04/2026
**Participantes:** Lucas, Claude
**Contexto:** Analise de um fluxo N8N real de atendimento comercial via WhatsApp (FATEPI/FAESPI) para referencia na evolucao dos fluxos visuais da Aurora.

---

## Resumo

Fluxo de atendimento comercial via WhatsApp para uma faculdade. Usa Uazapi (WhatsApp), Redis (memoria temporaria), Supabase (CRM/banco), OpenAI (IA conversacional com agente GPT-4o).

## Arquitetura

```
1. Webhook Uazapi (WhatsApp)
2. Normaliza variaveis (telefone, texto, tipo, fromMe)
3. Filtro de grupos/testes
4. Descarta mensagens proprias (fromMe)
5. Gera/consulta sessionID no Supabase
6. Switch por tipo de mensagem:
   - Texto → salva Redis
   - Audio → transcreve (OpenAI Whisper) → salva Redis
   - PDF → extrai texto → salva Redis
   - Imagem → analisa (GPT-4o-mini) → salva Redis
   - Video/Reacao → ignora
7. Concatenacao de mensagens picadas (Wait 7s + compara)
8. Limpa memoria Redis temporaria
9. Busca lead no Supabase + CRM externo (ConsultePlus API)
   - Nao existe → cria lead
   - Existe → verifica se esta pausado
10. Switch por status do lead:
    - Novo/Qualificacao → Agente "Qualificacao" (OpenAI)
    - Qualificado/Agendado → Agente "Agendamento" (OpenAI)
11. Agente IA com system prompt detalhado:
    - Tabela de cursos, precos, horarios
    - Tools: Update Supabase (salva nome, curso, forma ingresso)
    - Memoria de chat via Redis
12. Pos-processamento: split paragrafos, separa URLs
13. Loop de envio com delay "digitando" proporcional
14. Salva historico no Supabase
15. Follow-up automatico (cron a cada 2 dias)
```

## Conceitos para o sistema Aurora

| Conceito N8N | Equivalente Aurora | Status |
|---|---|---|
| Concatenacao mensagens picadas (Redis + Wait 7s) | Signal no Inbox ja agrupa | Implementado |
| Agente IA com system prompt + tools | Novo tipo de no "Agente IA" | A desenvolver |
| Switch por status do lead | No de condicao (campo_check) | Implementado |
| Pausar/Ativar bot (reacao) | Nao temos | A desenvolver |
| Follow-up automatico (cron) | No de delay + cron pendentes | Implementado |
| Delay "digitando" proporcional | Nao temos | A desenvolver |
| Transcricao de audio | Depende de integracao IA | A desenvolver |
| Analise de imagem | Depende de integracao IA | A desenvolver |
| CRM externo via API | Nosso CRM e interno | Implementado |

## Conclusao

A principal diferenca e que o fluxo N8N usa um **agente de IA conversacional** como cerebro central (LLM com system prompt extenso e tools), enquanto nosso sistema usa perguntas estruturadas com validacao. Para alcançar esse nivel, precisariamos de um no "Agente IA" que recebe system prompt, conecta a uma integracao de IA, e tem tools configuraveis.

## Proximos passos (a discutir)

1. Criar no "Agente IA" no editor visual
2. Implementar pausar/ativar bot por reacao
3. Delay "digitando" proporcional ao tamanho da mensagem
4. Suporte a audio (transcricao) e imagem (analise) nos nos de interacao
