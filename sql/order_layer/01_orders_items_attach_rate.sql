-- Orders, items, items per order and add-on attach rate by week, from the order tab.
-- Text dates are parsed with Spanish month names mapped to English.
WITH ids AS (
  SELECT DISTINCT TRIM(string_field_2) AS id_articulo
  FROM `PROJECT_ID.DATASET.ext_ids_articulos`
  WHERE string_field_2 IS NOT NULL AND string_field_2 != 'id_articulo'
),
lineas AS (
  SELECT o.semana, o.fecha_inicio_sem, o.id_transaccion, o.nombre_articulo,
         SAFE_CAST(o.transacciones AS INT64) AS cantidad,
         (i.id_articulo IS NOT NULL OR LOWER(o.nombre_articulo) LIKE '%internet%') AS es_paquete
  FROM `PROJECT_ID.DATASET.ext_origen_up_sell` o
  LEFT JOIN ids i ON TRIM(o.id_articulo) = i.id_articulo
  WHERE o.id_transaccion IS NOT NULL
),
pedidos AS (
  SELECT semana, ANY_VALUE(fecha_inicio_sem) AS f, id_transaccion,
         SUM(cantidad) AS articulos, LOGICAL_OR(NOT es_paquete) AS con_addon
  FROM lineas GROUP BY semana, id_transaccion
)
SELECT semana,
       COUNT(*) AS pedidos,
       SUM(articulos) AS articulos,
       ROUND(SUM(articulos) / COUNT(*), 2) AS articulos_por_pedido,
       COUNTIF(con_addon) AS pedidos_con_addon,
       ROUND(100 * COUNTIF(con_addon) / COUNT(*), 1) AS attach_rate_pct
FROM pedidos
GROUP BY semana
ORDER BY MIN(PARSE_DATE('%d %b %Y', REPLACE(REPLACE(REPLACE(REPLACE(LOWER(f),'ago','aug'),'sept','sep'),'dic','dec'),'ene','jan')));
