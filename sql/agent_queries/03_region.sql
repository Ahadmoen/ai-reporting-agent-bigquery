-- Commercial regions, built only from plaza rows. Never add regions to get a national figure.
SELECT region, subcanal, ventas, instalaciones, tasa_instalacion_pct
FROM `PROJECT_ID.DATASET.agente_telco_region`
WHERE grano = @grano
  AND region = @region
  AND periodo_inicio <= @fecha_fin
  AND periodo_fin >= @fecha_inicio
ORDER BY periodo_inicio, region, subcanal;
