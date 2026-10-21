import os
import re
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from google.cloud import bigquery
import google.auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reporting-agent-api")

PROJECT_ID = os.environ.get("GCP_PROJECT", "PROJECT_ID")
TABLE_NACIONAL = "PROJECT_ID.DATASET.agente_telco_nacional"
TABLE_MERCADO = "PROJECT_ID.DATASET.agente_telco_mercado"
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GRANOS_VALIDOS = {"diario", "semanal", "quincenal", "mensual", "mes_a_la_fecha", "mes_anterior_mismo_corte"}

SCOPES = [
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/cloud-platform",
]

credentials, _ = google.auth.default(scopes=SCOPES)
bq_client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

app = FastAPI(
    title="telco Salesforce Tool - Enterprise API",
    description="Consulta ventas e instalaciones Salesforce telco desde las tablas semanticas del agente.",
    version="3.3.0",
)


def _validar_fecha(nombre: str, valor: str) -> date:
    if not DATE_REGEX.match(valor):
        raise HTTPException(
            status_code=400,
            detail=f"Parametro '{nombre}' invalido. Formato requerido: YYYY-MM-DD. Recibido: '{valor}'.",
        )
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Parametro '{nombre}' no es una fecha valida: '{valor}'.",
        )


def _nivel(row) -> str:
    return getattr(row, "nivel", None) or "distrito"


def _advertencias_de_fila(row) -> list:
    advertencias = []
    if getattr(row, "periodo_completo", None) is False:
        advertencias.append("Este periodo no esta completo. Pueden faltar dias de datos.")
    if getattr(row, "cuadra", None) is False:
        advertencias.append("La cifra nacional no concilia con la suma de mercados para este periodo.")
    if getattr(row, "es_cifra_auditada", None) is False:
        advertencias.append("Esta cifra de mercado no ha sido auditada.")
    return advertencias


def _fila_a_total(row) -> dict:
    return {
        "ventas": int(row.ventas or 0),
        "instalaciones": int(row.instalaciones or 0),
        "tasa_instalacion_pct": float(row.tasa_instalacion_pct or 0.0),
    }


def _fila_subcanal(row, alcance: str) -> dict:
    entrada = {
        "subcanal": row.subcanal,
        "ventas": int(row.ventas or 0),
        "instalaciones": int(row.instalaciones or 0),
        "tasa_instalacion_pct": float(row.tasa_instalacion_pct or 0.0),
    }
    if alcance == "mercado":
        entrada["plaza"] = getattr(row, "plaza", None)
        entrada["distrito"] = getattr(row, "distrito", None)
    return entrada


@app.get("/health")
def health():
    return {"status": "ok", "service": "reporting-agent-api", "version": "3.3.0"}


@app.get("/api/v1/salesforce")
def read_salesforce(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    grano: str = Query("semanal", description="diario, semanal, quincenal, mensual, mes_a_la_fecha"),
    alcance: str = Query("nacional", description="nacional o mercado"),
    plaza: Optional[str] = Query(None, description="Nombre de plaza, solo para alcance=mercado"),
    distrito: Optional[str] = Query(None, description="Nombre de distrito, solo para alcance=mercado"),
):
    if grano not in GRANOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Grano invalido: '{grano}'. Valores permitidos: {sorted(GRANOS_VALIDOS)}.")
    if alcance not in ("nacional", "mercado"):
        raise HTTPException(status_code=400, detail=f"Alcance invalido: '{alcance}'. Valores permitidos: nacional, mercado.")

    d_inicio = _validar_fecha("fecha_inicio", fecha_inicio)
    d_fin = _validar_fecha("fecha_fin", fecha_fin)

    if d_inicio > d_fin:
        raise HTTPException(status_code=400, detail=f"fecha_inicio ({fecha_inicio}) no puede ser mayor a fecha_fin ({fecha_fin}).")

    tabla = TABLE_NACIONAL if alcance == "nacional" else TABLE_MERCADO

    params = [
        bigquery.ScalarQueryParameter("grano", "STRING", grano),
        bigquery.ScalarQueryParameter("fecha_inicio", "DATE", d_inicio),
        bigquery.ScalarQueryParameter("fecha_fin", "DATE", d_fin),
    ]

    filtros_extra = ""
    filtros_aplicados = {"grano": grano, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin, "alcance": alcance}

    if alcance == "mercado" and plaza:
        filtros_extra += " AND plaza = @plaza"
        params.append(bigquery.ScalarQueryParameter("plaza", "STRING", plaza))
        filtros_aplicados["plaza"] = plaza

    if alcance == "mercado" and distrito:
        filtros_extra += " AND distrito = @distrito"
        params.append(bigquery.ScalarQueryParameter("distrito", "STRING", distrito))
        filtros_aplicados["distrito"] = distrito

    query = f"""
    SELECT *
    FROM `{tabla}`
    WHERE grano = @grano
      AND periodo_inicio <= @fecha_fin
      AND periodo_fin >= @fecha_inicio
      {filtros_extra}
    ORDER BY periodo_inicio ASC, subcanal ASC
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.exception("Fallo la consulta a BigQuery")
        raise HTTPException(status_code=500, detail=f"Error consultando BigQuery: {type(e).__name__}")

    logger.info("Consulta: alcance=%s grano=%s %s a %s filas=%d", alcance, grano, fecha_inicio, fecha_fin, len(rows))

    try:
        max_date_query = f"SELECT MAX(periodo_fin) AS ultimo_dato FROM `{tabla}` WHERE grano = 'diario'"
        max_rows = list(bq_client.query(max_date_query).result())
        ultimo_dato = str(max_rows[0].ultimo_dato) if max_rows else None
    except Exception:
        ultimo_dato = None

    base = {
        "alcance": alcance,
        "grano": grano,
        "filtros_aplicados": filtros_aplicados,
        "fuente": tabla,
        "ultimo_dato_disponible": ultimo_dato,
        "regla_agregacion": "El backend no calcula ni agrega. Solo lee y devuelve filas oficiales.",
    }

    if not rows:
        return {**base, "periodos": []}

    periodos_map = {}
    for row in rows:
        key = (str(row.periodo_inicio), str(row.periodo_fin))
        periodos_map.setdefault(key, []).append(row)

    consulta_plaza = alcance == "mercado" and bool(plaza) and not distrito

    periodos_out = []
    for (p_inicio, p_fin), all_rows in sorted(periodos_map.items()):
        plaza_rows = [r for r in all_rows if _nivel(r) == "plaza"]
        distrito_rows = [r for r in all_rows if _nivel(r) == "distrito"]

        periodo = {"periodo_inicio": p_inicio, "periodo_fin": p_fin}

        if consulta_plaza and plaza_rows:
            fila_total = next((r for r in plaza_rows if getattr(r, "fila_es_total", False)), None)
            if fila_total is None:
                periodo["es_cifra_definitiva"] = False
                periodo["advertencias"] = ["No se encontro fila oficial de plaza para este periodo."]
                periodo["total_oficial"] = None
            else:
                periodo_completo = getattr(fila_total, "periodo_completo", None)
                auditada = getattr(fila_total, "es_cifra_auditada", None)
                periodo["es_cifra_definitiva"] = bool(periodo_completo) and bool(auditada)
                periodo["advertencias"] = _advertencias_de_fila(fila_total)
                periodo["total_oficial"] = _fila_a_total(fila_total)
                periodo["total_oficial"]["nivel"] = "plaza"
                periodo["total_oficial"]["plaza"] = getattr(fila_total, "plaza", None)

            periodo["desglose_subcanal"] = [
                _fila_subcanal(r, alcance) for r in plaza_rows if not getattr(r, "fila_es_total", False)
            ]

            totales_distrito = []
            for fila in sorted(
                (r for r in distrito_rows if getattr(r, "fila_es_total", False)),
                key=lambda r: str(getattr(r, "distrito", "")),
            ):
                entrada = _fila_a_total(fila)
                entrada["distrito"] = getattr(fila, "distrito", None)
                entrada["periodo_completo"] = bool(getattr(fila, "periodo_completo", False))
                totales_distrito.append(entrada)
            periodo["totales_distrito"] = totales_distrito

            periodos_out.append(periodo)
            continue

        filas_total = [r for r in distrito_rows if getattr(r, "fila_es_total", False)] if alcance == "mercado" \
            else [r for r in all_rows if getattr(r, "fila_es_total", False)]
        desglose = [r for r in (distrito_rows if alcance == "mercado" else all_rows) if not getattr(r, "fila_es_total", False)]

        if len(filas_total) == 1:
            fila = filas_total[0]
            periodo_completo = getattr(fila, "periodo_completo", None)
            cuadra = getattr(fila, "cuadra", None)
            auditada = getattr(fila, "es_cifra_auditada", None)
            periodo["es_cifra_definitiva"] = bool(periodo_completo) and (
                bool(cuadra) if cuadra is not None else bool(auditada)
            )
            periodo["advertencias"] = _advertencias_de_fila(fila)
            periodo["total_oficial"] = _fila_a_total(fila)
            if alcance == "mercado":
                periodo["total_oficial"]["plaza"] = getattr(fila, "plaza", None)
                periodo["total_oficial"]["distrito"] = getattr(fila, "distrito", None)
        elif len(filas_total) > 1:
            totales_distrito = []
            advertencias = [
                "No existe un total auditado a nivel plaza en esta capa. "
                "Se presentan los totales oficiales por distrito. No deben sumarse."
            ]
            for fila in sorted(filas_total, key=lambda r: str(getattr(r, "distrito", ""))):
                entrada = _fila_a_total(fila)
                entrada["plaza"] = getattr(fila, "plaza", None)
                entrada["distrito"] = getattr(fila, "distrito", None)
                entrada["es_cifra_auditada"] = bool(getattr(fila, "es_cifra_auditada", False))
                entrada["periodo_completo"] = bool(getattr(fila, "periodo_completo", False))
                totales_distrito.append(entrada)
                for adv in _advertencias_de_fila(fila):
                    etiqueta = f"{entrada['distrito']}: {adv}"
                    if etiqueta not in advertencias:
                        advertencias.append(etiqueta)
            periodo["es_cifra_definitiva"] = all(
                bool(getattr(f, "periodo_completo", False)) and bool(getattr(f, "es_cifra_auditada", False))
                for f in filas_total
            )
            periodo["advertencias"] = advertencias
            periodo["total_oficial"] = None
            periodo["totales_distrito"] = totales_distrito
        else:
            periodo["es_cifra_definitiva"] = False
            periodo["advertencias"] = ["No se encontro fila oficial (fila_es_total) para este periodo."]
            periodo["total_oficial"] = None

        periodo["desglose_subcanal"] = [_fila_subcanal(r, alcance) for r in desglose]
        periodos_out.append(periodo)

    return {**base, "periodos": periodos_out}


@app.get("/api/v1/flujo_c")
def read_flujo_c(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    grano: str = Query("mensual", description="semanal, quincenal, mensual, mes_a_la_fecha"),
    capa: str = Query("acquisition", description="media, acquisition, behaviour"),
    canal: Optional[str] = Query(None),
    campaign_name: Optional[str] = Query(None),
    etapa_funnel: Optional[str] = Query(None),
    plataforma: Optional[str] = Query(None),
    desglose: bool = Query(False, description="True para desglose por fuente y campana, False para total agregado"),
):
    GRANOS = {"semanal", "quincenal", "mensual", "mes_a_la_fecha"}
    CAPAS = {"media", "acquisition", "behaviour", "gaming_fest"}
    if grano not in GRANOS:
        raise HTTPException(status_code=400, detail=f"Grano invalido: {grano}")
    if capa not in CAPAS:
        raise HTTPException(status_code=400, detail=f"Capa invalida: {capa}")

    d_inicio = _validar_fecha("fecha_inicio", fecha_inicio)
    d_fin = _validar_fecha("fecha_fin", fecha_fin)

    params = [
        bigquery.ScalarQueryParameter("grano", "STRING", grano),
        bigquery.ScalarQueryParameter("capa", "STRING", capa),
        bigquery.ScalarQueryParameter("fecha_inicio", "DATE", d_inicio),
        bigquery.ScalarQueryParameter("fecha_fin", "DATE", d_fin),
    ]

    filtros_extra = ""
    filtros_aplicados = {
        "grano": grano, "capa": capa,
        "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin
    }

    if canal:
        filtros_extra += " AND canal = @canal"
        params.append(bigquery.ScalarQueryParameter("canal", "STRING", canal))
        filtros_aplicados["canal"] = canal
    if campaign_name:
        filtros_extra += " AND LOWER(campaign_name) LIKE LOWER(@campaign_name)"
        params.append(bigquery.ScalarQueryParameter("campaign_name", "STRING", f"%{campaign_name}%"))
        filtros_aplicados["campaign_name"] = campaign_name
    if etapa_funnel:
        filtros_extra += " AND etapa_funnel = @etapa_funnel"
        params.append(bigquery.ScalarQueryParameter("etapa_funnel", "STRING", etapa_funnel))
        filtros_aplicados["etapa_funnel"] = etapa_funnel
    if plataforma:
        filtros_extra += " AND plataforma = @plataforma"
        params.append(bigquery.ScalarQueryParameter("plataforma", "STRING", plataforma))
        filtros_aplicados["plataforma"] = plataforma

    limit_rows = 500
    if capa == "acquisition":
        if desglose or campaign_name or canal:
            filtros_extra += " AND fila_es_total = FALSE"
            limit_rows = 2000
        else:
            filtros_extra += " AND fila_es_total = TRUE"

    if capa == "gaming_fest":
        query = f"""
        SELECT
          date AS periodo_inicio,
          date AS periodo_fin,
          source,
          campaign,
          sessions,
          totalusers AS users,
          newusers AS new_users,
          conversions_generate_lead AS leads_generate_lead,
          conversions_lead_desde_chat_karalundi AS leads_chat,
          conversions_purchase AS digital_purchases,
          purchase_revenue AS revenue,
          ROUND(SAFE_DIVIDE(purchase_revenue, NULLIF(conversions_purchase, 0)), 2) AS avg_ticket
        FROM `PROJECT_ID.DATASET.ga4_event_sesiones`
        WHERE date BETWEEN @fecha_inicio AND @fecha_fin
        ORDER BY date ASC, sessions DESC
        LIMIT 500
        """
    else:
        query = f"""
        SELECT *
        FROM `PROJECT_ID.DATASET.agente_telco_flujo_c`
        WHERE grano = @grano
          AND capa = @capa
          AND periodo_inicio <= @fecha_fin
          AND periodo_fin >= @fecha_inicio
          {filtros_extra}
        ORDER BY periodo_inicio ASC, canal ASC
        LIMIT {limit_rows}
        """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.exception("Fallo consulta flujo_c")
        raise HTTPException(status_code=500, detail=f"Error BigQuery: {type(e).__name__}")

    logger.info("flujo_c: capa=%s grano=%s %s a %s filas=%d",
                capa, grano, fecha_inicio, fecha_fin, len(rows))

    return {
        "capa": capa,
        "grano": grano,
        "filtros_aplicados": filtros_aplicados,
        "ultimo_dato_disponible": _ultimo_dia_completo_ga4("PROJECT_ID.DATASET.ga4_residencial_sesiones"),
        "definicion_ultimo_dato": "Ultimo dia completo en hora de Mexico. El dia en curso no se incluye como corte.",
        "fuente": "agente_telco_flujo_c",
        "regla_agregacion": "El backend no calcula ni agrega. Solo lee y devuelve filas oficiales.",
        "total_filas": len(rows),
        "periodos": [dict(r) for r in rows],
    }


@app.get("/api/v1/region")
def read_region(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    grano: str = Query("semanal", description="semanal, quincenal, mensual, mes_a_la_fecha"),
    region: Optional[str] = Query(None, description="Oriente, Sur, Bajio, Noreste, Pacifico, Occidente, Centro, Frontera, Norte"),
):
    if grano not in GRANOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Grano invalido: {grano}")

    d_inicio = _validar_fecha("fecha_inicio", fecha_inicio)
    d_fin = _validar_fecha("fecha_fin", fecha_fin)

    params = [
        bigquery.ScalarQueryParameter("grano", "STRING", grano),
        bigquery.ScalarQueryParameter("fecha_inicio", "DATE", d_inicio),
        bigquery.ScalarQueryParameter("fecha_fin", "DATE", d_fin),
    ]

    filtros_extra = ""
    filtros_aplicados = {"grano": grano, "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin}

    if region:
        filtros_extra += " AND region = @region"
        params.append(bigquery.ScalarQueryParameter("region", "STRING", region))
        filtros_aplicados["region"] = region

    query = f"""
    SELECT *
    FROM `PROJECT_ID.DATASET.agente_telco_region`
    WHERE grano = @grano
      AND periodo_inicio <= @fecha_fin
      AND periodo_fin >= @fecha_inicio
      {filtros_extra}
    ORDER BY periodo_inicio ASC, region ASC, subcanal ASC
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.exception("Fallo consulta region")
        raise HTTPException(status_code=500, detail=f"Error BigQuery: {type(e).__name__}")

    logger.info("region: grano=%s %s a %s region=%s filas=%d",
                grano, fecha_inicio, fecha_fin, region, len(rows))

    periodos_map = {}
    for row in rows:
        key = (str(row.periodo_inicio), str(row.periodo_fin))
        periodos_map.setdefault(key, []).append(dict(row))

    periodos_out = []
    for (p_inicio, p_fin), filas in sorted(periodos_map.items()):
        total = next((f for f in filas if f.get("fila_es_total")), None)
        desglose = [f for f in filas if not f.get("fila_es_total")]
        periodos_out.append({
            "periodo_inicio": p_inicio,
            "periodo_fin": p_fin,
            "total_oficial": {
                "ventas": total["ventas"] if total else None,
                "instalaciones": total["instalaciones"] if total else None,
                "tasa_instalacion_pct": total["tasa_instalacion_pct"] if total else None,
                "region": total["region"] if total else region,
            } if total else None,
            "periodo_completo": total["periodo_completo"] if total else False,
            "desglose_subcanal": desglose,
        })

    try:
        mx = list(bq_client.query(
            f"SELECT MAX(periodo_fin) AS ultimo FROM `{TABLE_NACIONAL}` WHERE grano = 'diario'"
        ).result())
        ultimo_dato = str(mx[0].ultimo) if mx and mx[0].ultimo else None
    except Exception:
        ultimo_dato = None

    return {
        "grano": grano,
        "filtros_aplicados": filtros_aplicados,
        "ultimo_dato_disponible": ultimo_dato,
        "fuente": "agente_telco_region",
        "regla_agregacion": "Totales regionales derivados de plazas oficiales. Nunca sumar regiones entre si.",
        "periodos": periodos_out,
    }


def _ultimo_dia_completo_ga4(tabla):
    try:
        mx = list(bq_client.query(
            f"SELECT MAX(date) AS ultimo FROM `{tabla}` "
            "WHERE date < CURRENT_DATE('America/Mexico_City')"
        ).result())
        return str(mx[0].ultimo) if mx and mx[0].ultimo else None
    except Exception:
        return None


def _fmt_int(v):
    return f"{int(v or 0):,}"


def _fmt_money(v):
    return f"${float(v or 0):,.2f}"


def _tabla_canales(filas, periodo):
    rows = [f for f in filas if f.get("periodo") == periodo]
    if not rows:
        return None
    total = [f for f in rows if f.get("nivel") == "total"]
    grupos = sorted([f for f in rows if f.get("nivel") == "grupo"], key=lambda f: -(f.get("sessions") or 0))
    detalle = [f for f in rows if f.get("nivel") == "fuente_medio"]
    lines = ["| Grupo de canales | Fuente / medio | Sesiones | Compras digitales | Revenue |",
             "|---|---|---:|---:|---:|"]
    def linea(f):
        return (f"| {f.get('grupo_canales')} | {f.get('fuente_medio')} | {_fmt_int(f.get('sessions'))} | "
                f"{_fmt_int(f.get('digital_purchases'))} | {_fmt_money(f.get('revenue'))} |")
    for f in total:
        lines.append(linea(f))
    for g in grupos:
        lines.append(linea(g))
        subs = sorted([d for d in detalle if d.get("grupo_canales") == g.get("grupo_canales")],
                      key=lambda d: -(d.get("sessions") or 0))
        for d in subs:
            lines.append(linea(d))
    return "\n".join(lines)


@app.get("/api/v1/canales")
def read_canales(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    desplazamiento_dias: int = Query(7, description="Dias hacia atras para el periodo de comparacion"),
    desglose: bool = Query(False, description="True agrega fuente/medio dentro de cada grupo de canales"),
):
    try:
        query = """
        SELECT *
        FROM `PROJECT_ID.DATASET.tf_canales_rango`(
          @fecha_inicio, @fecha_fin, @desplazamiento, @desglose)
        ORDER BY periodo, fila_es_total DESC, sessions DESC
        LIMIT 2000
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
            bigquery.ScalarQueryParameter("desplazamiento", "INT64", desplazamiento_dias),
            bigquery.ScalarQueryParameter("desglose", "BOOL", desglose),
        ])
        rows = list(bq_client.query(query, job_config=job_config).result())
        if not rows:
            return {"mensaje": "No se encontraron datos de canales para el rango solicitado.", "filas": []}
        filas = []
        for r in rows:
            f = dict(r)
            for k in ("periodo_inicio", "periodo_fin"):
                if f.get(k) is not None:
                    f[k] = str(f[k])
            filas.append(f)
        ultimo_dato = _ultimo_dia_completo_ga4("PROJECT_ID.DATASET.ga4_residencial_canales")
        return {
            "ultimo_dato_disponible": ultimo_dato,
            "definicion_ultimo_dato": "Ultimo dia completo en hora de Mexico. El dia en curso no se incluye como corte.",
            "tabla_markdown_actual": _tabla_canales(filas, "actual"),
            "tabla_markdown_comparacion": _tabla_canales(filas, "comparacion"),
            "fuente": "GA4 Residencial por grupo de canales predeterminado (mismo campo que Grupo de canales en Looker)",
            "nota": "El total de esta vista es la suma exacta de sus grupos. Su total de sesiones puede ser hasta 1% menor que el total general de sesiones porque GA4 recalcula sesiones al agregar grupo de canales y medio. Las compras coinciden en julio y agosto y pueden diferir en unas pocas compras en septiembre, porque son dos consultas distintas a GA4.",
            "filas": filas,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rango")
def read_rango(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    alcance: str = Query("nacional", description="nacional o mercado"),
    plaza: Optional[str] = Query(None, description="Nombre de plaza si alcance=mercado"),
    desplazamiento_dias: int = Query(7, description="Dias hacia atras para el periodo de comparacion"),
):
    try:
        if alcance == "mercado" and not plaza:
            raise HTTPException(status_code=400, detail="plaza es obligatoria cuando alcance=mercado")
        query = """
        SELECT *
        FROM `PROJECT_ID.DATASET.tf_rango_personalizado`(
          @fecha_inicio, @fecha_fin, @alcance, @plaza, @desplazamiento)
        ORDER BY periodo, subcanal
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
            bigquery.ScalarQueryParameter("alcance", "STRING", alcance),
            bigquery.ScalarQueryParameter("plaza", "STRING", plaza),
            bigquery.ScalarQueryParameter("desplazamiento", "INT64", desplazamiento_dias),
        ])
        rows = list(bq_client.query(query, job_config=job_config).result())
        if not rows:
            return {"mensaje": "No se encontraron datos para el rango o plaza solicitados.", "filas": []}
        filas = []
        for r in rows:
            f = dict(r)
            for k in ("periodo_inicio", "periodo_fin", "ultimo_dato_disponible"):
                if f.get(k) is not None:
                    f[k] = str(f[k])
            filas.append(f)
        return {
            "grano": "rango_personalizado",
            "ultimo_dato_disponible": filas[0].get("ultimo_dato_disponible"),
            "nota": "Cifras calculadas en BigQuery sumando dias completos. Si periodo_completo es false, el rango incluye dias sin datos cargados.",
            "filas": filas,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/apps")
def read_apps(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    familia: Optional[str] = Query(None, description="2P o 3P"),
):
    try:
        params = [
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
        ]
        filtro_familia = ""
        if familia:
            filtro_familia = "AND familia = @familia"
            params.append(bigquery.ScalarQueryParameter("familia", "STRING", familia))

        query = f"""
        SELECT semana, fecha_inicio_sem, fecha_fin_sem, familia, app,
               transacciones_con_app, advertencia
        FROM `PROJECT_ID.DATASET.vw_app_frequency_telco`
        WHERE fecha_inicio_sem <= @fecha_fin
          AND fecha_fin_sem >= @fecha_inicio
          {filtro_familia}
        ORDER BY fecha_inicio_sem DESC, transacciones_con_app DESC
        LIMIT 500
        """
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(bq_client.query(query, job_config=job_config).result())

        if not rows:
            return {"mensaje": "No se encontraron datos para el periodo solicitado.", "filas": []}

        filas = []
        for r in rows:
            filas.append({
                "app": r.app,
                "familia": r.familia,
                "transacciones_con_app": r.transacciones_con_app,
            })
        try:
            max_rows = list(bq_client.query(
                "SELECT MAX(fecha_fin_sem) AS ultimo FROM `PROJECT_ID.DATASET.vw_product_telco_v3`"
            ).result())
            ultimo_dato = str(max_rows[0].ultimo) if max_rows and max_rows[0].ultimo else None
        except Exception:
            ultimo_dato = None
        return {
            "ultimo_dato_disponible": ultimo_dato,
            "fuente": "articulos_comprados (base madre), actualizado semanalmente por el equipo",
            "metrica": "Articulos comprados que incluyen cada app. No son transacciones ni compras de GA4.",
            "total_filas": len(filas),
            "advertencia_general": "Los conteos por app se superponen. No sumar entre apps.",
            "filas": filas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _ultimo_producto():
    try:
        mx = list(bq_client.query(
            "SELECT MAX(fecha_fin_sem) AS ultimo FROM `PROJECT_ID.DATASET.vw_product_telco_v3`"
        ).result())
        return str(mx[0].ultimo) if mx and mx[0].ultimo else None
    except Exception:
        return None


@app.get("/api/v1/producto")
def read_producto(
    fecha_inicio: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha final YYYY-MM-DD"),
    familia: Optional[str] = Query(None, description="2P, 3P, Addon"),
    item_name: Optional[str] = Query(None, description="Nombre del paquete"),
    item_category: Optional[str] = Query(None, description="Categoria del producto"),
):
    d_inicio = _validar_fecha("fecha_inicio", fecha_inicio)
    d_fin = _validar_fecha("fecha_fin", fecha_fin)

    params = [
        bigquery.ScalarQueryParameter("fecha_inicio", "DATE", d_inicio),
        bigquery.ScalarQueryParameter("fecha_fin", "DATE", d_fin),
    ]

    filtros_extra = ""
    filtros_aplicados = {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin}

    if familia:
        filtros_extra += " AND familia = @familia"
        params.append(bigquery.ScalarQueryParameter("familia", "STRING", familia))
        filtros_aplicados["familia"] = familia
    if item_name:
        filtros_extra += " AND LOWER(nombre_articulo) LIKE LOWER(@item_name)"
        params.append(bigquery.ScalarQueryParameter("item_name", "STRING", f"%{item_name}%"))
        filtros_aplicados["item_name"] = item_name
    if item_category:
        filtros_extra += " AND LOWER(paquete) LIKE LOWER(@item_category)"
        params.append(bigquery.ScalarQueryParameter("item_category", "STRING", f"%{item_category}%"))
        filtros_aplicados["item_category"] = item_category

    query = f"""
    SELECT
      fecha_inicio_sem,
      fecha_fin_sem,
      semana,
      canales,
      fuente_medio,
      campana,
      id_articulo,
      nombre_articulo,
      transacciones,
      paquete,
      familia,
      paquete_familia
    FROM `PROJECT_ID.DATASET.vw_product_telco_v3`
    WHERE fecha_inicio_sem <= @fecha_fin
      AND fecha_fin_sem >= @fecha_inicio
      {filtros_extra}
    ORDER BY fecha_inicio_sem ASC, transacciones DESC
    LIMIT 1000
    """

    job_config = bigquery.QueryJobConfig(query_parameters=params)

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as e:
        logger.exception("Fallo consulta producto")
        raise HTTPException(status_code=500, detail=f"Error BigQuery: {type(e).__name__}")

    logger.info("producto: %s a %s filas=%d", fecha_inicio, fecha_fin, len(rows))

    resumen_semana, resumen_familia, resumen_articulo, tablas_producto = [], [], [], {}
    try:
        base_sql = f"""
          FROM `PROJECT_ID.DATASET.vw_product_telco_v3`
          WHERE fecha_inicio_sem <= @fecha_fin AND fecha_fin_sem >= @fecha_inicio {filtros_extra}
        """
        q_sem = f"SELECT semana, MIN(fecha_inicio_sem) AS ini, MAX(fecha_fin_sem) AS fin, SUM(transacciones) AS articulos {base_sql} GROUP BY semana ORDER BY ini"
        q_fam = f"SELECT semana, COALESCE(familia, '(sin familia)') AS familia, SUM(transacciones) AS articulos {base_sql} GROUP BY semana, familia ORDER BY semana, articulos DESC"
        q_art = f"SELECT semana, COALESCE(familia, '(sin familia)') AS familia, nombre_articulo, COALESCE(NULLIF(TRIM(paquete), ''), '(sin paquete)') AS paquete, SUM(transacciones) AS articulos {base_sql} GROUP BY semana, familia, nombre_articulo, paquete ORDER BY semana, articulos DESC"
        resumen_semana = [dict(r) for r in bq_client.query(q_sem, job_config=job_config).result()]
        resumen_familia = [dict(r) for r in bq_client.query(q_fam, job_config=job_config).result()]
        resumen_articulo = [dict(r) for r in bq_client.query(q_art, job_config=job_config).result()]
        for s in resumen_semana:
            s["ini"], s["fin"] = str(s["ini"]), str(s["fin"])
            sem = s["semana"]
            fam_lines = ["| Familia | Articulos comprados |", "|---|---:|",
                         f"| Total {sem} | {int(s['articulos'] or 0):,} |"]
            for f in [f for f in resumen_familia if f["semana"] == sem]:
                fam_lines.append(f"| {f['familia']} | {int(f['articulos'] or 0):,} |")
            art_lines = ["| Familia | Articulo | Paquete | Articulos comprados |", "|---|---|---|---:|"]
            for a in [a for a in resumen_articulo if a["semana"] == sem]:
                art_lines.append(f"| {a['familia']} | {a['nombre_articulo']} | {a['paquete']} | {int(a['articulos'] or 0):,} |")
            tablas_producto[sem] = {
                "periodo": f"{s['ini']} al {s['fin']}",
                "tabla_familias": "\n".join(fam_lines),
                "tabla_articulos": "\n".join(art_lines),
            }
    except Exception:
        logger.exception("Fallo resumen producto")

    resumen = {}
    for row in rows:
        key = (row.nombre_articulo, row.familia, row.paquete)
        if key not in resumen:
            resumen[key] = {
                "item_name": row.nombre_articulo,
                "item_category": row.paquete_familia,
                "familia": row.familia,
                "paquete": row.paquete,
                "transacciones": 0,
            }
        resumen[key]["transacciones"] += int(row.transacciones or 0)

    productos = sorted(resumen.values(), key=lambda x: x["transacciones"], reverse=True)

    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "filtros_aplicados": filtros_aplicados,
        "fuente": "articulos_comprados (base madre telco, semana 29 en adelante)",
        "metrica": "Articulos comprados: un registro por articulo, un pedido con 3 articulos cuenta 3. No son transacciones ni compras de GA4.",
        "ultimo_dato_disponible": _ultimo_producto(),
        "resumen_semana": resumen_semana,
        "resumen_familia": resumen_familia,
        "tablas_producto": tablas_producto,
        "regla": "Usa resumen_semana y resumen_familia como totales oficiales. No sumes las filas de detalle.",
        "total_transacciones": sum(p["transacciones"] for p in productos),
        "productos": productos,
    }

from charts import router as charts_router
app.include_router(charts_router)
from corte import router as corte_router
app.include_router(corte_router)
from ga4_api import router as ga4_router
app.include_router(ga4_router)
