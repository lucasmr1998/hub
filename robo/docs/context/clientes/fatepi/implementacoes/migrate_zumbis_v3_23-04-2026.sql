-- ============================================================================
-- FATEPI v3 — finalizar atendimentos zumbis (nodo_atual_id = NULL)
-- ============================================================================
-- Contexto: 5 atendimentos em 15-16/04 ficaram com nodo_atual_id=NULL apos
-- refatoracao do fluxo v3 (nodos antigos 473/475/484 foram substituidos por
-- 521/523/532). Esses atendimentos nao vao avancar. Melhor finalizar com
-- motivo claro.
--
-- Rodar no DBShell do Postgres em producao:
--   docker exec -i <container-postgres> psql -U admin_hub -d hub -f este-arquivo.sql
-- Ou colar direto na UI do Hostinger/EasyPanel.
--
-- ATENCAO: rodar PRIMEIRO o SELECT de validacao abaixo pra confirmar que
-- sao exatamente 5 atendimentos e quais sao. SO ENTAO rodar o UPDATE.
-- ============================================================================

-- 1. VALIDAR: lista os zumbis antes de qualquer write
SELECT id, lead_id, data_inicio, questoes_respondidas, motivo_finalizacao
FROM atendimentos_fluxo
WHERE tenant_id = 7
  AND fluxo_id = 6
  AND nodo_atual_id IS NULL
  AND status = 'iniciado'
ORDER BY data_inicio DESC;

-- Esperado: 5 rows, IDs 132, 133, 134, 135, 136 (15-16/04/2026).

-- 2. UPDATE: finaliza com motivo explicito
-- DESCOMENTAR APENAS APOS CONFIRMAR O SELECT ACIMA.
--
-- BEGIN;
-- UPDATE atendimentos_fluxo
-- SET status = 'finalizado',
--     motivo_finalizacao = 'fluxo_refatorado',
--     data_conclusao = NOW(),
--     data_ultima_atividade = NOW()
-- WHERE tenant_id = 7
--   AND fluxo_id = 6
--   AND nodo_atual_id IS NULL
--   AND status = 'iniciado';
--
-- Verificar count:
-- SELECT COUNT(*) FROM atendimentos_fluxo
-- WHERE tenant_id=7 AND fluxo_id=6 AND motivo_finalizacao='fluxo_refatorado';
--
-- Se retornou 5 → COMMIT; se nao → ROLLBACK;
