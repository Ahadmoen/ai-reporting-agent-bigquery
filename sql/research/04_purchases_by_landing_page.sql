-- Hypothesis test: purchases by session landing page and speed. Rejected (did not match the team's figures).
WITH s AS (
  SELECT user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') sid,
    REGEXP_EXTRACT((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'), r'^https?://[^/]+(/[^?#]*)') landing
  FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`
  WHERE _TABLE_SUFFIX BETWEEN @desde_menos_1 AND @hasta AND event_name = 'session_start'),
p AS (
  SELECT user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') sid,
    REGEXP_EXTRACT(i.item_name, r'(\d+)\s*megas') velocidad, i.quantity q
  FROM `PROJECT_ID.analytics_PROPERTY_ID.events_*`, UNNEST(items) i
  WHERE _TABLE_SUFFIX BETWEEN @desde AND @hasta AND event_name = 'purchase'
    AND i.item_list_name = 'Lista de paquetes principales')
SELECT IFNULL(s.landing, '(sin landing)') landing, p.velocidad, COUNT(*) compras, SUM(p.q) articulos
FROM p LEFT JOIN s USING (user_pseudo_id, sid)
GROUP BY 1, 2 ORDER BY compras DESC LIMIT 30;
