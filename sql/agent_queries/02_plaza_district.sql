-- Plaza level. For districts use nivel = 'distrito' and filter distrito = @distrito.
-- Plaza and district rows describe the same sales: never add them together.
SELECT plaza, subcanal, ventas, instalaciones, tasa_instalacion_pct
FROM `PROJECT_ID.DATASET.agente_telco_mercado`
WHERE grano = @grano
  AND nivel = 'plaza'
  AND plaza = @plaza
  AND periodo_inicio <= @fecha_fin
  AND periodo_fin >= @fecha_inicio
ORDER BY periodo_inicio, subcanal;
