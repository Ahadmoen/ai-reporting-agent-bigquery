-- What fires on the home page. Finding: only view_promotion, no select_item,
-- so a purchase cannot be linked to a home card from standard GA4 data.
SELECT event_name, i.item_list_name lista, REGEXP_EXTRACT(i.item_name, r'(\d+)\s*megas') velocidad, COUNT(*) eventos
FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`, UNNEST(items) i
WHERE _TABLE_SUFFIX BETWEEN @desde AND @hasta
  AND REGEXP_EXTRACT((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'^https?://[^/]+(/[^?#]*)') IN ('/', '/index.html', '/home')
GROUP BY 1, 2, 3 ORDER BY eventos DESC LIMIT 30;
