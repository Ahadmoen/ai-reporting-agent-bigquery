-- How many periods reconcile: audited national Total row against the sum of plazas.
-- Result after the source fix: 168 of 168.
SELECT COUNTIF(cuadra) AS periodos_que_cuadran, COUNT(*) AS periodos
FROM `PROJECT_ID.DATASET.agente_telco_nacional`
WHERE subcanal = '(todos)';
