-- Any date range, summed inside BigQuery, with the same range shifted back @desplazamiento days.
-- 7 = same weekdays of the previous week. A full week computed this way equals the weekly row.
SELECT periodo, periodo_inicio, periodo_fin, subcanal, ventas, instalaciones,
       tasa_instalacion_pct, periodo_completo
FROM `PROJECT_ID.DATASET.tf_rango_personalizado`(@fecha_inicio, @fecha_fin, @alcance, @plaza, @desplazamiento)
ORDER BY periodo, subcanal;
