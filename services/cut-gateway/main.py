import hmac
import os
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI(title="telco cortes para n8n")

API_KEY = os.environ["API_KEY"]
BACKEND = "https://REPORTING_API_HOST"


def _token():
    r = requests.get(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
        params={"audience": BACKEND, "format": "full"},
        headers={"Metadata-Flavor": "Google"},
        timeout=5,
    )
    r.raise_for_status()
    return r.text.strip()


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.get("/corte")
def corte(
    tipo: str = Query("diario"),
    fecha: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
):
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API key invalida o ausente")
    if tipo not in ("diario", "semanal"):
        raise HTTPException(status_code=400, detail="tipo debe ser diario o semanal")
    params = {"tipo": tipo}
    if fecha:
        params["fecha"] = fecha
    try:
        r = requests.get(f"{BACKEND}/api/v1/corte", params=params,
                         headers={"Authorization": f"Bearer {_token()}"}, timeout=280)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar el servicio de cortes: {type(e).__name__}")
    try:
        body = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Respuesta invalida del servicio de cortes")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=body.get("detail", "Error al generar el corte"))
    body.pop("datos", None)
    body.setdefault("estado", "ok")
    return body
