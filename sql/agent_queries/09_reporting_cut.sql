-- Daily cut: @nivel = 'dia' with one date. Weekly cut: @nivel = 'rango' with Monday and Sunday.
SELECT grupo, metrica, actual, anterior, variacion, variacion_pct,
       provisional_actual, explicacion_subcanal_permitida
FROM `PROJECT_ID.DATASET.tf_corte_ventas`(@inicio, @fin)
WHERE nivel = @nivel
ORDER BY orden_grupo, metrica;
