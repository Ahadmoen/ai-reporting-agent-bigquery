-- Top add-ons bought together with each package for one week.
WITH ids AS (
  SELECT DISTINCT TRIM(string_field_2) AS id_articulo
  FROM `PROJECT_ID.DATASET.ext_ids_articulos`
  WHERE string_field_2 IS NOT NULL AND string_field_2 != 'id_articulo'
),
lineas AS (
  SELECT o.id_transaccion, o.nombre_articulo,
         (i.id_articulo IS NOT NULL OR LOWER(o.nombre_articulo) LIKE '%internet%') AS es_paquete
  FROM `PROJECT_ID.DATASET.ext_origen_up_sell` o
  LEFT JOIN ids i ON TRIM(o.id_articulo) = i.id_articulo
  WHERE o.semana = @semana AND o.id_transaccion IS NOT NULL
)
SELECT p.nombre_articulo AS paquete, a.nombre_articulo AS addon, COUNT(DISTINCT p.id_transaccion) AS pedidos
FROM lineas p
JOIN lineas a ON a.id_transaccion = p.id_transaccion AND NOT a.es_paquete
WHERE p.es_paquete
GROUP BY 1, 2
ORDER BY pedidos DESC
LIMIT 15;
