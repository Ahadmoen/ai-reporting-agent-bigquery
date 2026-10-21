-- Acquisition official total per period. For breakdowns use fila_es_total = FALSE
-- with filters on canal, campaign_name or source; detail rows add up exactly to the total.
SELECT periodo_inicio, periodo_fin, sessions, users, digital_purchases, revenue, avg_ticket
FROM `PROJECT_ID.DATASET.agente_telco_flujo_c`
WHERE grano = @grano
  AND capa = 'acquisition'
  AND fila_es_total = TRUE
  AND periodo_inicio <= @fecha_fin
  AND periodo_fin >= @fecha_inicio
ORDER BY periodo_inicio;
