-- Real column names before writing a query (external tables without headers come back as string_field_N).
SELECT table_name, STRING_AGG(column_name, ', ' ORDER BY ordinal_position) columnas
FROM `PROJECT_ID.DATASET.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN UNNEST(@tablas)
GROUP BY table_name;
