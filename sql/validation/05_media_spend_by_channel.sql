-- Re-derives a documented spend table from live data before trusting an older document.
SELECT canal, ROUND(SUM(spend)) AS spend
FROM `PROJECT_ID.DATASET.agente_telco_flujo_c`
WHERE capa = 'media' AND grano = 'mensual' AND periodo_inicio = @mes
GROUP BY canal
ORDER BY spend DESC;
