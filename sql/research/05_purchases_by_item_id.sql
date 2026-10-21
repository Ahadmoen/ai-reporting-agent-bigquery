-- Hypothesis test: card placement encoded as distinct item IDs. Rejected (no ID combination matched).
SELECT i.item_id, i.item_name, COUNT(*) compras, SUM(i.quantity) articulos
FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`, UNNEST(items) i
WHERE _TABLE_SUFFIX BETWEEN @desde AND @hasta
  AND event_name = 'purchase'
  AND REGEXP_CONTAINS(i.item_name, r'^Internet - (100|150|350) megas$')
GROUP BY 1, 2 ORDER BY 2, compras DESC;
