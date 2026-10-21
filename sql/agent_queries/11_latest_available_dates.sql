-- Latest loaded date of each source. Never take MAX(periodo_fin) over every grain:
-- monthly and half month rows end on the last day of the period, which can be in the future.
SELECT 'operational_sheet' AS fuente, MAX(periodo_fin) AS ultimo
FROM `PROJECT_ID.DATASET.agente_telco_nacional` WHERE grano = 'diario'
UNION ALL
SELECT 'sales_and_leads_sheet', MAX(fecha)
FROM `PROJECT_ID.DATASET.ventas_leads_diario`
WHERE bloque = 'ventas' AND tipo = 'total_call_center' AND valor > 0
UNION ALL
SELECT 'ga4_for_cut', MAX(periodo_fin)
FROM `PROJECT_ID.DATASET.vw_ga4_corte` WHERE grano = 'diario';
