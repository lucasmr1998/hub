# Execution log — módulo CRM

Trilha do que foi executado no módulo CRM (incidentes, decisões,
mudanças que afetaram prod). Append-only, entrada mais nova no fim.

---

## 2026-06-29 — Bug regras #28/#29/#30 "Vincular plano escolhido como item"

**Acao:** Desativadas em prod 3 regras do tenant Nuvyon (id=12):
  - #28 "Vincular plano escolhido como item" (estagio: Dados Completos)
  - #29 "Vincular plano escolhido como item" (estagio: Aguardando Documentos)
  - #30 "Vincular plano escolhido como item" (estagio: Analises - Doc & Score)

**Causa raiz:** Motor de regras (`apps/comercial/crm/services/automacao_pipeline.py:97-99`)
**sempre move a op pro estagio da regra** quando dispara — mesmo
quando a unica acao da regra eh `adicionar_item_oportunidade` (que
nao deveria mover).

Resultado: leads novos que escolhiam plano caiam direto em
"Analises - Doc & Score" (estagio que pressupoe documentos enviados
e analise feita) sem ter passado pela coleta de doc/score.

**Caso real que evidenciou:** Op 1861 (lead 1702 Johnny). Cliente foi
transferido pra humano ao digitar CEP (incompatibilidade cobertura),
mas op estava em "Analises - Doc & Score" — operador comercial
ficaria confuso vendo a op em estagio que pressupoe analise feita.

**Decisao:** Desativar as 3 regras incorretas, manter so a #27
(estagio = Plano Escolhido, que faz sentido). Perda funcional eh
pequena: leads onde `id_plano_rp` aparece DEPOIS da op ja ter
avancado de "Plano Escolhido" perdem o item vinculado automatico.
Operador adiciona manualmente nesses raros casos.

**Numeros antes do fix:**
  - Regra #30 disparou 49 vezes (49 ops Nuvyon caem indevidamente
    em "Analises - Doc & Score" desde a criacao)
  - Regras #28 e #29 disparou 0 vezes (estagios menos comuns)
  - Regra #27 (correta) disparou 0 — provavel desempate por ID
    priorizou #30 quando ambas batiam

**Fix definitivo (pendente — medio prazo):** Refactor do motor pra
introduzir `tipo_regra=acao_pura` que executa a acao SEM mover a op.
Permite re-ativar as regras com seguranca.

**Como executei:**
```python
RegraPipelineEstagio.all_tenants.filter(
    id__in=[28, 29, 30], tenant_id=12
).update(ativo=False)
```
Output: "Update aplicado: 3 regras"

**Status:** completed. Acompanhar nas proximas 24h se algum lead
novo escolhe plano e VAI para "Plano Escolhido" corretamente (em vez
de pular pra "Analises - Doc & Score").

**Reverter (se necessario):** UPDATE ativo=True nos mesmos ids.

**Correcao em massa das ops afetadas (2026-06-29):**
37 ops foram movidas de "Analises - Doc & Score" -> "Em Atendimento"
porque tinham caido aqui pela regra #30 sem ter documentacao
completa. Mantidas em "Analises - Doc & Score":
- Op 1755 Maikebinkan: regra correta #25 (tag aguardando_validacao)
- Op 1736 Gabriel: movida manualmente (motivo vazio)
- Op 1787 Tiago: score=aprovado, deixar vendedor decidir
- Op 1790 Antonio: score=aprovado, deixar vendedor decidir
HistoricoPipelineEstagio registrado pra cada uma com motivo
"Correcao em massa". Notificacoes disparadas pros responsaveis.

---

## 2026-06-29 — Motivo de perda obrigatorio + bug 2 estagios "Perdido"

**Acao 1 (codigo):** commit `320f83c` adiciona 2 campos novos no
catalogo `CAMPOS_DISPONIVEIS` em
`apps/comercial/crm/services/requisitos_estagio.py`:
- `oportunidade.motivo_perda_categoria` (categoria — escolha estruturada)
- `oportunidade.motivo_perda` (texto livre)

Permite marcar como obrigatorios em qualquer estagio via UI
`/crm/configuracoes/`.

**Acao 2 (UPDATE em prod, tenant 12 nuvyon):**
1. Estagio id=84 ("Perdido"): tipo='novo' -> 'perdido' (era bug
   irmão do que vimos com "Ativacao Confirmada" — quebrava analises
   automaticas filtradas por tipo).
2. Estagios id=73 e id=84: `campos_obrigatorios` agora inclui
   `oportunidade.motivo_perda_categoria`. Vendedora nao consegue
   mais mover pra "Perdido" sem categorizar a perda.

**Diagnostico que motivou:** Dos 22 leads enriquecidos pelo Sprint 4
que viraram perdidos, 17 (77%) estavam sem motivo registrado. Todos
movidos por vendedoras humanas (thais.moreira lidera com 12).

**Pendencia:** Existem 2 estagios "Perdido" no pipeline Nuvyon
(id=73 vazio + id=84 com 22 ops). Aguardando decisao do Lucas pra
consolidar (mover ops 84->73 + deletar 84) OU manter ambos.

---
