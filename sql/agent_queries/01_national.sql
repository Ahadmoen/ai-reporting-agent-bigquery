-- National sales and installations for any grain and date window.
-- The (todos) row with fila_es_total = TRUE is the official national total (sheet Total row).
SELECT subcanal, ventas, instalaciones, tasa_instalacion_pct, periodo_completo, cuadra
FROM `PROJECT_ID.DATASET.agente_telco_nacional`
WHERE grano = @grano
  AND periodo_inicio <= @fecha_fin
  AND periodo_fin >= @fecha_inicio
ORDER BY periodo_inicio, subcanal;
