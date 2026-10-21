-- Locates a weekly gap between the GA4 Data API and the manual export by article.
-- Fill the api CTE with the API's items per article for the same week.
-- A rule difference would move every article the same way; mixed signs point to export timing.
WITH api AS (
  SELECT * FROM UNNEST([
    STRUCT('Internet - 150 megas' AS art, 0 AS api_items)  -- replace with API values
  ])),
hoja AS (
  SELECT nombre_articulo art, SUM(SAFE_CAST(transacciones AS INT64)) hoja_items
  FROM `PROJECT_ID.DATASET.ext_origen_up_sell`
  WHERE semana = @semana GROUP BY 1)
SELECT COALESCE(a.art, h.art) articulo, h.hoja_items, a.api_items, h.hoja_items - a.api_items dif
FROM api a FULL JOIN hoja h ON a.art = h.art
ORDER BY ABS(IFNULL(h.hoja_items - a.api_items, 0)) DESC, h.hoja_items DESC;
