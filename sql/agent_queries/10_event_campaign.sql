-- Event campaign layer has no total row: aggregate in SQL over an explicit date range,
-- never present an undated total (low traffic continues after the event).
SELECT SUM(sessions) AS sesiones
FROM `PROJECT_ID.DATASET.ga4_event_sesiones`
WHERE date BETWEEN @fecha_inicio AND @fecha_fin;
