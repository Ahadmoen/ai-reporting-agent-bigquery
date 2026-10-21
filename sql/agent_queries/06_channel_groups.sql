-- GA4 default channel groups for a range and its comparison.
-- nivel: total, grupo and (with @desglose) fuente_medio. Groups add up exactly to the total row.
-- The users column is a sum of rows, not unique users.
SELECT periodo, nivel, grupo_canales, fuente_medio, sessions, users, digital_purchases, revenue
FROM `PROJECT_ID.DATASET.tf_canales_rango`(@fecha_inicio, @fecha_fin, @desplazamiento, @desglose)
ORDER BY periodo, nivel DESC, sessions DESC;
