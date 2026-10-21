-- Items purchased by family. transacciones counts items: one order with three items counts 3.
SELECT semana, COALESCE(familia, '(sin familia)') AS familia, SUM(transacciones) AS articulos
FROM `PROJECT_ID.DATASET.vw_product_telco_v3`
WHERE fecha_inicio_sem <= @fecha_fin
  AND fecha_fin_sem >= @fecha_inicio
GROUP BY semana, familia
ORDER BY semana, articulos DESC;
