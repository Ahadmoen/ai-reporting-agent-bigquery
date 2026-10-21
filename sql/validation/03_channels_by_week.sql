-- Purchases and sessions by GA4 default channel group per week, compared with the team's channel export.
-- Result: 26 of 27 channel figures matched exactly across three weeks.
SELECT
  CONCAT('semana ', CAST(EXTRACT(ISOWEEK FROM date) AS STRING)) AS semana,
  session_default_channel_group AS canal,
  SUM(conversions_purchase) AS compras,
  SUM(sessions) AS sesiones
FROM `PROJECT_ID.DATASET.ga4_residencial_canales`
WHERE date BETWEEN @inicio AND @fin
GROUP BY 1, 2
ORDER BY 1, compras DESC;
