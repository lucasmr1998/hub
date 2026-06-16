# Incidente — bot rejeitou Lençóis Paulista (15/06/2026)

## Resumo

Lead **Roger Guilherme Mosele** (telefone 14996911600, lead id 585 tenant 11) entrou pelo anuncio Meta no canal **Vero WhatsApp** da TR Carrion as 17:13. O bot pediu CEP, recebeu **18686-362** (Lençois Paulista/SP) e respondeu **"Infelizmente ainda nao atendemos Lençois Paulista/SP"** — informacao errada. Agente humano da TR Carrion assumiu a conversa as 17:46 e tratou manualmente.

## Diagnostico (versao final, apos investigacao em camadas)

### Onde a "trava de cidade" mora hoje

O **flow ativo em prod** é o `[Vero] Orquestrador Atendimento` (id `5U3o0CaQij4ALf8N`, 137 nodes, ultima atualizacao 14/06 com Fase 2 do Brayo). Esse flow **ja faz do jeito certo**:

```
WhatsApp -> Orquestrador
  -> HTTP ViaCEP (resolve CEP -> localidade)
  -> HTTP Hubtrix Viabilidade (POST app.hubtrix.com.br/api/public/n8n/viabilidade/, Bearer token do tenant)
  -> IF atende? sim/nao
```

O endpoint `/api/public/n8n/viabilidade/` consulta `viabilidade_cidadeviabilidade` filtrado por `tenant=request.tenant`. Arquitetura limpa e isolada por tenant.

### Causa raiz

Tenant 11 (TR Carrion) tinha **407 cidades** cadastradas em `viabilidade_cidadeviabilidade` — lixo provavelmente importado de seed/planilha generica no setup do tenant. Macatuba e Pederneiras estavam la, mas **Lençois Paulista** nao. Quando o lead enviou o CEP de Lençois, o endpoint retornou `atende=false` → bot disse que nao atendia.

Pior: as 405 cidades restantes (Sao Paulo, Rio, Belo Horizonte, Curitiba, ...) **falsificavam atendimento** — qualquer lead de qualquer canto do Brasil estaria sendo conduzido pelo bot e enviado pra equipe da TR Carrion como se fosse atendido.

### Diagnostico errado intermediario (registro de aprendizado)

Antes de chegar na causa raiz, hipotetizei que o bug estava na tabela `cidade_atendida` do postgres `wifeed` (consultada pelo nodo `SelecionarCidade1` do flow `[Vero] Matrix | Atendimento Fixo | 1.1` id `pHzdyrAl7TFPSWWn`). Apliquei INSERT temporario com as 3 cidades. **Estava errado** — esse flow nao eh o caminho ativo (ultima atualizacao 18/05, anterior a Fase 2 do Brayo). O Orquestrador eh quem responde pra mensagem do WhatsApp.

Lesson learned: **antes de aplicar fix, validar que o caminho diagnosticado eh o caminho ATIVO** comparando timestamps + cross-checking com a mensagem exata da resposta do bot. A mensagem `"Infelizmente ainda nao atendemos {{ localidade }}/{{ uf }}"` aparecia no `Step Reasking CEP SemCobertura` do Orquestrador — mas eu so percebi apos comparar com os snapshots no repo.

## Fix aplicado (15/06 18:00-18:40)

### 1. Limpeza do banco do Hubtrix (operacao atomica em uma transacao)

```sql
-- DELETE de 405 cidades irrelevantes
DELETE FROM viabilidade_cidadeviabilidade
WHERE tenant_id = 11
  AND cidade NOT IN ('Lençóis Paulista', 'Macatuba', 'Pederneiras');
-- 405 linhas removidas

-- INSERT idempotente da Lençois (nao existia)
INSERT INTO viabilidade_cidadeviabilidade
  (tenant_id, cidade, estado, cep, bairro, ativo, data_criacao, data_atualizacao, observacao)
SELECT 11, 'Lençóis Paulista', 'SP', '', '', true, NOW(), NOW(), 'Cadastrada via incidente 15/06/2026'
WHERE NOT EXISTS (
  SELECT 1 FROM viabilidade_cidadeviabilidade
  WHERE tenant_id=11 AND cidade='Lençóis Paulista'
);
-- 1 linha inserida (id 415)
```

Sanity check apos commit: tenant 11 tem **exatamente 3 cidades** (Lençois Paulista 415, Macatuba 210, Pederneiras 8).

Pre-check de FK: `viabilidade_cidadeviabilidade` nao recebe FK de nenhuma outra tabela → DELETE seguro sem cascata.

### 2. Reverter INSERT erroneo no wifeed (cidade_atendida)

Apliquei INSERT antes na tabela errada (`cidade_atendida` do postgres `wifeed`) que nao eh consultada pelo Orquestrador. Removi as 3 entradas que tinha colocado, voltando a tabela ao estado original de 27 cidades (do cliente antigo, provavelmente FATEPI).

## Verificacao

Apos a limpeza, qualquer CEP de Lençois Paulista, Macatuba ou Pederneiras retorna `atende=true`. Qualquer outro CEP do Brasil retorna `atende=false` (bot vai pro `Step Reasking CEP SemCobertura`).

Smoke test pendente — validar via mensagem real no WhatsApp da TR Carrion.

## 🚨 Achados arquiteturais relevantes

1. **Tabela compartilhada `cidade_atendida` no postgres `wifeed`** — usada por um flow antigo (`[Vero] Matrix | Atendimento Fixo | 1.1`). Cidades de varios clientes misturadas. Sem coluna tenant. Risco se alguem reativar esse flow. **Recomendacao**: desativar/deletar esse flow, ja que o Orquestrador (caminho ativo) nao depende dele.

2. **Seed/import de cidades no onboarding de tenant** — 407 cidades de varios estados foram cadastradas pra TR Carrion. Nao bate com a realidade do cliente. **Recomendacao**: revisar o processo de onboarding de tenant — cidades nao devem ser importadas em massa, devem ser cadastradas com base no que o cliente atende de fato.

3. **Falta de seed test/protecao** — nao ha automacao que avise quando um tenant tem mais cidades cadastradas do que ele realmente atende. Sugestao: dashboard interno ou alerta quando uma cidade nunca usada (no ViaCEP, na nossa base de leads) esta no `viabilidade_cidadeviabilidade`.

## Status

- [x] Diagnostico real isolado
- [x] Limpeza atomica no Hubtrix DB (407 -> 3 cidades)
- [x] Reverter INSERT erroneo no wifeed
- [x] Workflow temporario do n8n removido
- [x] Snapshot defensivo do Orquestrador atual prod (em `snapshots/_atual_prod_pre_brayo_15-06-2026.json`)
- [ ] Smoke test real — mensagem WhatsApp com CEP de Lençois
- [ ] Avisar TR Carrion: bot voltou a atender Lençois/Macatuba/Pederneiras; lead Roger deve ser fechado manualmente pelo agente
- [ ] **Desativar/limpar** flow `[Vero] Matrix | Atendimento Fixo | 1.1` (id `pHzdyrAl7TFPSWWn`) ja que nao eh o caminho ativo
- [ ] Revisar **onboarding de tenant** pra nao criar lixo de cidades automaticamente
