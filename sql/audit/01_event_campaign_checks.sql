-- Why a documented total could not be reproduced: date range, duplicates, monthly split, running total.
SELECT MIN(date) primera, MAX(date) ultima, COUNT(*) filas,
  COUNT(DISTINCT FORMAT('%t', t)) filas_unicas
FROM `PROJECT_ID.DATASET.ga4_event_sesiones` t;

SELECT FORMAT_DATE('%Y-%m', date) mes, SUM(sessions) sesiones
FROM `PROJECT_ID.DATASET.ga4_event_sesiones`
GROUP BY 1 ORDER BY 1;

SELECT * FROM (
  SELECT date, SUM(SUM(sessions)) OVER (ORDER BY date) acumulado
  FROM `PROJECT_ID.DATASET.ga4_event_sesiones`
  GROUP BY date)
WHERE acumulado BETWEEN @min AND @max
ORDER BY date;
