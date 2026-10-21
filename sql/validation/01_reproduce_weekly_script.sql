-- Reproduces the team's weekly Python script in SQL (validated: 8 of 8 figures for one week).
-- Rules copied from the script: join items to the ID catalogue, force four named add-ons to Combo 3P,
-- exclude package-named items with no ID, treat the remaining unmatched items as up-selling.
-- Note: the ID tab has no header row in BigQuery, so it is read by column position
-- (string_field_0 package, 1 family, 2 ID, 3 name). See TECHNICAL.md, known risks.
WITH ids AS (
  SELECT TRIM(string_field_2) id, TRIM(string_field_0) paq, TRIM(string_field_1) fam
  FROM `PROJECT_ID.DATASET.ext_ids_articulos`
  WHERE string_field_2 IS NOT NULL AND TRIM(string_field_2) NOT IN ('-', '', 'id_articulo')
  QUALIFY ROW_NUMBER() OVER (PARTITION BY TRIM(string_field_2)) = 1),
art AS (
  SELECT TRIM(CAST(id_articulo AS STRING)) id, TRIM(nombre_articulo) nombre,
    SAFE_CAST(REPLACE(CAST(transacciones AS STRING), ',', '') AS FLOAT64) tx
  FROM `PROJECT_ID.DATASET.ext_articulos_comprados`
  WHERE LOWER(TRIM(CAST(semana AS STRING))) = @semana),
m AS (
  SELECT a.*,
    IF(i.paq IS NULL AND REGEXP_CONTAINS(LOWER(a.nombre), r'nba league pass|picardía nacional|stingray karaoke|stingray qello'), 'Combo', i.paq) paq,
    IF(i.paq IS NULL AND REGEXP_CONTAINS(LOWER(a.nombre), r'nba league pass|picardía nacional|stingray karaoke|stingray qello'), '3P', i.fam) fam
  FROM art a LEFT JOIN ids i USING (id))
SELECT
  SUM(IF(paq = 'Base' AND fam = '2P', tx, 0)) base_2p_sin_app,
  SUM(IF(paq NOT IN ('Base', 'Combo', 'Surround') AND fam = '2P', tx, 0)) base_2p_con_app,
  SUM(IF(paq = 'Base' AND fam = '3P', tx, 0)) base_3p_sin_app,
  SUM(IF(paq NOT IN ('Base', 'Combo', 'Surround') AND fam = '3P', tx, 0)) base_3p_con_app,
  SUM(IF(paq = 'Combo' AND fam = '2P', tx, 0)) combo_2p,
  SUM(IF(paq = 'Combo' AND fam = '3P', tx, 0)) combo_3p,
  SUM(IF(paq = 'Surround', tx, 0)) surround,
  SUM(IF(paq IS NOT NULL, tx, 0)) total_paquetes,
  SUM(IF(paq IS NULL AND REGEXP_CONTAINS(LOWER(nombre), r'^(tv\s*\+\s*internet|internet)\s*-\s*\d+\s*megas'), tx, 0)) excluidos_sin_id,
  SUM(IF(paq IS NULL AND NOT REGEXP_CONTAINS(LOWER(nombre), r'^(tv\s*\+\s*internet|internet)\s*-\s*\d+\s*megas'), tx, 0)) upselling,
  SUM(tx) total_articulos
FROM m;
-- Reconciliation for the validated week: total_articulos = total_paquetes + excluidos_sin_id + upselling
-- (4,073 = 2,917 + 18 + 1,138).
