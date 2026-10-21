-- Orders, order lines and items per week from the order tab, to compare with the GA4 Data API.
-- Dates and quantities are stored as text in the sheet: filter on the week label, never on text dates
-- (a text date filter silently dropped three weeks in testing).
SELECT semana,
  COUNT(DISTINCT id_transaccion) pedidos,
  COUNT(*) filas,
  SUM(SAFE_CAST(REPLACE(transacciones, ',', '') AS INT64)) items,
  COUNTIF(SAFE_CAST(REPLACE(transacciones, ',', '') AS INT64) IS NULL) filas_no_numericas
FROM `PROJECT_ID.DATASET.ext_origen_up_sell`
GROUP BY semana
ORDER BY semana;
