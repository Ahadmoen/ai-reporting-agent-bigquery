import datetime as dt

import google.auth
from google.auth.transport.requests import AuthorizedSession
from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from charts import _bq, TZ

router = APIRouter()

PROPIEDAD = "PROPERTY_ID"
TABLA = "PROJECT_ID.DATASET.ga4_api_telco"
URL = f"https://analyticsdata.googleapis.com/v1beta/properties/{PROPIEDAD}:runReport"
METRICAS = [{"name": "sessions"}, {"name": "activeUsers"}, {"name": "sessionKeyEventRate:purchase"}]

_cred, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/analytics.readonly"])
_ses = AuthorizedSession(_cred)


def _report(ini, fin, diario):
    body = {"dateRanges": [{"startDate": str(ini), "endDate": str(fin)}], "metrics": METRICAS}
    if diario:
        body["dimensions"] = [{"name": "date"}]
        body["limit"] = 1000
    r = _ses.post(URL, json=body, timeout=60)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GA4 API {r.status_code}: {r.text[:400]}")
    out = []
    for row in r.json().get("rows", []):
        m = [float(x["value"]) for x in row["metricValues"]]
        f = dt.datetime.strptime(row["dimensionValues"][0]["value"], "%Y%m%d").date() if diario else ini
        out.append({"fecha": f, "sesiones": int(m[0]), "usuarios_activos": int(m[1]), "tasa": m[2]})
    return sorted(out, key=lambda x: x["fecha"])


def _fila(grano, ini, fin, r, completo, ahora):
    return {
        "grano": grano,
        "periodo_inicio": str(ini),
        "periodo_fin": str(fin),
        "sesiones": r["sesiones"],
        "usuarios_activos": r["usuarios_activos"],
        "sesiones_con_compra": int(round(r["tasa"] * r["sesiones"])),
        "tasa_cierre_pct": round(r["tasa"] * 100, 2),
        "periodo_completo": completo,
        "actualizado_en": ahora,
    }


@router.get("/api/v1/ga4_prueba")
def ga4_prueba(inicio: str = Query(...), fin: str = Query(...)):
    ini, f = dt.date.fromisoformat(inicio), dt.date.fromisoformat(fin)
    total = _report(ini, f, False)
    diario = _report(ini, f, True)
    for x in total + diario:
        x["fecha"] = str(x["fecha"])
    return {"propiedad": PROPIEDAD, "total": total, "diario": diario}


@router.get("/api/v1/ga4_sync")
def ga4_sync(dias: int = Query(60)):
    hoy = dt.datetime.now(TZ).date()
    fin = hoy - dt.timedelta(days=1)
    ini = fin - dt.timedelta(days=dias)
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    filas = [_fila("diario", r["fecha"], r["fecha"], r, True, ahora) for r in _report(ini, fin, True)]
    lunes = ini + dt.timedelta(days=(7 - ini.weekday()) % 7)
    semanas = 0
    while lunes <= fin:
        fin_sem = min(lunes + dt.timedelta(days=6), fin)
        tot = _report(lunes, fin_sem, False)
        if tot:
            filas.append(_fila("semanal", lunes, lunes + dt.timedelta(days=6), tot[0],
                               fin_sem == lunes + dt.timedelta(days=6), ahora))
            semanas += 1
        lunes += dt.timedelta(days=7)
    esquema = [
        bigquery.SchemaField("grano", "STRING"),
        bigquery.SchemaField("periodo_inicio", "DATE"),
        bigquery.SchemaField("periodo_fin", "DATE"),
        bigquery.SchemaField("sesiones", "INT64"),
        bigquery.SchemaField("usuarios_activos", "INT64"),
        bigquery.SchemaField("sesiones_con_compra", "INT64"),
        bigquery.SchemaField("tasa_cierre_pct", "FLOAT64"),
        bigquery.SchemaField("periodo_completo", "BOOL"),
        bigquery.SchemaField("actualizado_en", "TIMESTAMP"),
    ]
    job = _bq.load_table_from_json(filas, TABLA, job_config=bigquery.LoadJobConfig(
        schema=esquema, write_disposition="WRITE_TRUNCATE"))
    job.result()
    return {"tabla": TABLA, "filas_diarias": len(filas) - semanas, "filas_semanales": semanas,
            "desde": str(ini), "hasta": str(fin)}


DIM_MODOS = {
    "articulos": ["itemId", "itemName"],
    "canal": ["itemId", "itemName", "sessionDefaultChannelGroup", "sessionSourceMedium", "sessionCampaignName"],
    "pedidos": ["transactionId", "itemId", "itemName"],
}


@router.get("/api/v1/ga4_items_prueba")
def ga4_items_prueba(inicio: str = Query(...), fin: str = Query(...), modo: str = Query("articulos")):
    if modo not in DIM_MODOS:
        raise HTTPException(status_code=400, detail=f"modo debe ser uno de {list(DIM_MODOS)}")
    dims = DIM_MODOS[modo]
    body = {
        "dateRanges": [{"startDate": inicio, "endDate": fin}],
        "dimensions": [{"name": d} for d in dims],
        "metrics": [{"name": "itemsPurchased"}],
        "limit": 250000,
    }
    r = _ses.post(URL, json=body, timeout=120)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GA4 API {r.status_code}: {r.text[:600]}")
    rows = []
    for row in r.json().get("rows", []):
        v = int(float(row["metricValues"][0]["value"]))
        if v:
            rows.append({**{d: x["value"] for d, x in zip(dims, row["dimensionValues"])}, "items": v})
    total = sum(x["items"] for x in rows)
    out = {"modo": modo, "inicio": inicio, "fin": fin, "filas": len(rows), "items_total": total}
    if modo == "pedidos":
        out["pedidos"] = len({x["transactionId"] for x in rows if x["transactionId"] not in ("", "(not set)")})
        out["filas_sin_pedido"] = sum(x["items"] for x in rows if x["transactionId"] in ("", "(not set)"))
    if modo == "canal":
        por_grupo = {}
        for x in rows:
            por_grupo[x["sessionDefaultChannelGroup"]] = por_grupo.get(x["sessionDefaultChannelGroup"], 0) + x["items"]
        out["por_grupo"] = dict(sorted(por_grupo.items(), key=lambda kv: -kv[1]))
    por_articulo = {}
    for x in rows:
        k = x["itemName"]
        por_articulo[k] = por_articulo.get(k, 0) + x["items"]
    out["top_articulos"] = dict(sorted(por_articulo.items(), key=lambda kv: -kv[1])[:15])
    return out
