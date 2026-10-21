-- On which pages package cards are selected and added to cart, by speed.
SELECT
  REGEXP_EXTRACT((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'^https?://[^/]+(/[^?#]*)') pagina,
  REGEXP_EXTRACT(i.item_name, r'(\d+)\s*megas') velocidad,
  event_name, COUNT(*) eventos
FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`, UNNEST(items) i
WHERE _TABLE_SUFFIX BETWEEN @desde AND @hasta
  AND event_name IN ('select_item', 'add_to_cart')
  AND i.item_list_name = 'Lista de paquetes principales'
GROUP BY 1, 2, 3 ORDER BY eventos DESC LIMIT 40;
