-- Which GA4 item fields carry card or list information, per event (one week of the GA4 export).
SELECT event_name, COUNT(*) eventos,
  COUNTIF(i.promotion_name IS NOT NULL AND i.promotion_name != '(not set)') con_promotion_name,
  COUNTIF(i.creative_slot IS NOT NULL AND i.creative_slot != '(not set)') con_creative_slot,
  COUNTIF(i.item_list_name IS NOT NULL AND i.item_list_name != '(not set)') con_item_list,
  ARRAY_AGG(DISTINCT i.promotion_name IGNORE NULLS LIMIT 5) ejemplos_promotion,
  ARRAY_AGG(DISTINCT i.item_list_name IGNORE NULLS LIMIT 5) ejemplos_lista
FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`, UNNEST(items) i
WHERE _TABLE_SUFFIX BETWEEN @desde AND @hasta
  AND event_name IN ('view_promotion', 'select_promotion', 'select_item', 'add_to_cart', 'purchase')
GROUP BY event_name ORDER BY eventos DESC;
