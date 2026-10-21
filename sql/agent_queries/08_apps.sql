-- Apps included in packages. Counts overlap between apps and are never added together.
SELECT semana, familia, app, transacciones_con_app, advertencia
FROM `PROJECT_ID.DATASET.vw_app_frequency_telco`
WHERE fecha_inicio_sem <= @fecha_fin
  AND fecha_fin_sem >= @fecha_inicio
ORDER BY fecha_inicio_sem DESC, transacciones_con_app DESC;
