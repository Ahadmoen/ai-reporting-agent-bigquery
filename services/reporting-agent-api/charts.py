import io
import uuid
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery, storage
import google.auth
from google.auth.transport import requests as ga_requests

router = APIRouter()

PROJECT_ID = "PROJECT_ID"
T_NAC = "PROJECT_ID.DATASET.agente_telco_nacional"
T_MER = "PROJECT_ID.DATASET.agente_telco_mercado"
BUCKET = "telco-agent-charts"
TZ = ZoneInfo("America/Mexico_City")

# Paleta del deck the agency
C_EC = "#A421EE"      # E-commerce magenta
C_CC = "#1B1BB3"      # Call Center azul
C_BANNER = "#5C2E91"  # banda morada
C_PINK = "#EE2FBE"    # resalte rosa
C_BG = "#F1F1F2"
C_NAVY = "#10103C"
C_GRAY = "#B9B9C4"
C_GREEN = "#3CB55E"
C_YELLOW = "#F2C14E"
C_RED = "#E5484D"

SCOPES = ["https://www.googleapis.com/auth/bigquery",
          "https://www.googleapis.com/auth/drive.readonly",
          "https://www.googleapis.com/auth/cloud-platform"]
_creds, _ = google.auth.default(scopes=SCOPES)
_bq = bigquery.Client(project=PROJECT_ID, credentials=_creds)
_gcs = storage.Client(project=PROJECT_ID, credentials=_creds)

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _rows(sql, params):
    cfg = bigquery.QueryJobConfig(query_parameters=params)
    return [dict(r) for r in _bq.query(sql, job_config=cfg).result()]


def _fetch(grano, p_ini, alcance, plaza):
    tabla = T_NAC if alcance == "nacional" else T_MER
    extra = ""
    params = [
        bigquery.ScalarQueryParameter("g", "STRING", grano),
        bigquery.ScalarQueryParameter("pi", "DATE", p_ini),
    ]
    if alcance == "mercado":
        extra = " AND nivel = 'plaza' AND plaza = @pl"
        params.append(bigquery.ScalarQueryParameter("pl", "STRING", plaza))
    sql = f"""SELECT * FROM `{tabla}`
              WHERE grano = @g AND periodo_inicio = @pi{extra}"""
    return _rows(sql, params)


def _split(rows):
    tot = next((r for r in rows if r.get("fila_es_total")), None)
    sub = {r["subcanal"]: r for r in rows if not r.get("fila_es_total")}
    return tot, sub


def _upload(fig, nombre):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=C_BG)
    plt.close(fig)
    buf.seek(0)
    blob = _gcs.bucket(BUCKET).blob(
        f"{nombre}-{dt.datetime.now(TZ):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.png")
    blob.upload_from_file(buf, content_type="image/png")
    try:
        _creds.refresh(ga_requests.Request())
        return blob.generate_signed_url(
            version="v4",
            expiration=dt.timedelta(hours=24),
            method="GET",
            service_account_email=getattr(_creds, "service_account_email", None),
            access_token=_creds.token,
        )
    except Exception as e:
        return f"gs://{BUCKET}/{blob.name} (URL firmada no disponible: {type(e).__name__})"


def _fmt(n):
    return f"{int(n):,}"


def _seg_bar(ax, x, cc, ec, etiqueta_cc, etiqueta_ec, ancho=0.8):
    ax.bar(x, cc, ancho, color=C_CC, zorder=3)
    ax.bar(x, ec, ancho, bottom=cc, color=C_EC, zorder=3)
    ax.text(x, cc + ec + (cc + ec) * 0.02, _fmt(cc + ec), ha="center",
            fontsize=11, fontweight="bold", color=C_NAVY)
    ax.text(x, cc / 2, f"{_fmt(cc)}\n{etiqueta_cc}", ha="center", va="center",
            fontsize=8, color="white", fontweight="bold")
    ax.text(x, cc + ec / 2, f"{_fmt(ec)}\n{etiqueta_ec}", ha="center",
            va="center", fontsize=8, color="white", fontweight="bold")


@router.get("/api/v1/chart")
def chart(
    tipo: str = Query(..., description="mensual, diaria, semanal, plazas"),
    fecha_referencia: Optional[str] = Query(None, description="YYYY-MM-DD, default hoy CDMX"),
    alcance: str = Query("nacional"),
    plaza: Optional[str] = Query(None),
):
    if tipo not in ("mensual", "diaria", "semanal", "plazas"):
        raise HTTPException(400, "tipo invalido: mensual, diaria, semanal, plazas")
    if alcance not in ("nacional", "mercado"):
        raise HTTPException(400, "alcance invalido")
    if alcance == "mercado" and not plaza and tipo != "plazas":
        raise HTTPException(400, "alcance=mercado requiere plaza")

    if fecha_referencia:
        ref = dt.date.fromisoformat(fecha_referencia)
    else:
        try:
            ult = _rows(f"SELECT MAX(periodo_fin) AS f FROM `{T_NAC}` WHERE grano = 'diario'", [])
            ref = ult[0]["f"] or dt.datetime.now(TZ).date()
        except Exception:
            ref = dt.datetime.now(TZ).date()
    ambito = "Nacional" if alcance == "nacional" else plaza

    try:
        if tipo == "mensual":
            url, titulo = _chart_mensual(ref, alcance, plaza, ambito)
        elif tipo == "diaria":
            url, titulo = _chart_diaria(ref, alcance, plaza, ambito)
        elif tipo == "semanal":
            url, titulo = _chart_semanal(ref, alcance, plaza, ambito)
        else:
            url, titulo = _chart_plazas(ref)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error generando grafica: {type(e).__name__}: {e}")

    return {"tipo": tipo, "ambito": ambito, "titulo": titulo, "url": url,
            "nota": "URL valida 24 horas. Cifras oficiales de las tablas del agente."}


def _chart_mensual(ref, alcance, plaza, ambito):
    ini_act = ref.replace(day=1)
    fin_ant = ini_act - dt.timedelta(days=1)
    ini_ant = fin_ant.replace(day=1)

    act = _fetch("mes_a_la_fecha", ini_act, alcance, plaza)
    ant = _fetch("mes_anterior_mismo_corte", ini_ant, alcance, plaza) or _fetch("mensual", ini_ant, alcance, plaza)
    if not act or not ant:
        raise HTTPException(404, "Sin datos para los meses solicitados")
    t_a, s_a = _split(act)
    t_p, s_p = _split(ant)

    def vals(sub, campo):
        cc = int(sub.get("Call Center", {}).get(campo, 0) or 0)
        ec = int(sub.get("E-commerce", {}).get(campo, 0) or 0)
        return cc, ec

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)

    grupos = [
        (0.0, vals(s_a, "ventas"), "ventas", f"Ventas {MESES[ini_act.month].capitalize()}"),
        (1.0, vals(s_a, "instalaciones"), "inst", f"Instalaciones {MESES[ini_act.month].capitalize()}"),
        (2.5, vals(s_p, "ventas"), "ventas", f"Ventas {MESES[ini_ant.month].capitalize()}"),
        (3.5, vals(s_p, "instalaciones"), "inst", f"Instalaciones {MESES[ini_ant.month].capitalize()}"),
    ]
    etiquetas = []
    for x, (cc, ec), modo, nombre in grupos:
        total = cc + ec
        if modo == "ventas":
            l_cc = f"Representación {round(cc/total*100)}%" if total else ""
            l_ec = f"Representación {round(ec/total*100)}%" if total else ""
        else:
            sub = s_a if x < 2 else s_p
            vcc = int(sub.get("Call Center", {}).get("ventas", 0) or 0)
            vec = int(sub.get("E-commerce", {}).get("ventas", 0) or 0)
            l_cc = f"Tasa de inst/vent: {round(cc/vcc*100)}%" if vcc else ""
            l_ec = f"Tasa de inst/vent: {round(ec/vec*100)}%" if vec else ""
        _seg_bar(ax, x, cc, ec, l_cc, l_ec)
        etiquetas.append((x, nombre))

    ax.set_xticks([e[0] for e in etiquetas])
    ax.set_xticklabels([e[1] for e in etiquetas], fontsize=9, color=C_NAVY)
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=C_EC),
                       plt.Rectangle((0, 0), 1, 1, color=C_CC)],
              labels=["E-commerce", "Call Center"], loc="upper center",
              ncol=2, frameon=False, fontsize=9)
    if (t_a.get("cuadra") is False) or (t_p.get("cuadra") is False):
        ax.text(0.5, 1.02, "CIFRAS NO CONCILIADAS: el total nacional no cuadra con la suma de mercados. Revisar hoja origen.",
                transform=ax.transAxes, ha="center", va="bottom", fontsize=9,
                color="white", fontweight="bold",
                bbox=dict(facecolor=C_RED, edgecolor="none", pad=5))
    pa_i, pa_f = t_a["periodo_inicio"], t_a["periodo_fin"]
    pp_i, pp_f = t_p["periodo_inicio"], t_p["periodo_fin"]
    titulo = "VENTAS E INSTALACIONES TOTALES"
    sub = (f"Del {pa_i.day} al {pa_f.day} de {MESES[pa_f.month]} de {pa_f.year} · {ambito} · "
           f"vs. {pp_i.day} al {pp_f.day} de {MESES[pp_f.month]}")
    fig.suptitle(titulo, fontsize=18, fontweight="bold", color=C_NAVY, x=0.12, ha="left")
    ax.set_title(sub, fontsize=10, color=C_NAVY, loc="left")
    return _upload(fig, f"mensual-{alcance}"), f"{titulo} · {sub}"


def _chart_diaria(ref, alcance, plaza, ambito):
    ini = ref.replace(day=1)
    tabla = T_NAC if alcance == "nacional" else T_MER
    extra = " AND nivel = 'plaza' AND plaza = @pl" if alcance == "mercado" else ""
    params = [bigquery.ScalarQueryParameter("a", "DATE", ini),
              bigquery.ScalarQueryParameter("b", "DATE", ref)]
    if alcance == "mercado":
        params.append(bigquery.ScalarQueryParameter("pl", "STRING", plaza))
    sql = f"""SELECT periodo_inicio AS fecha, subcanal, ventas, fila_es_total
              FROM `{tabla}`
              WHERE grano = 'diario' AND periodo_inicio BETWEEN @a AND @b{extra}
              ORDER BY fecha"""
    rows = _rows(sql, params)
    if not rows:
        raise HTTPException(404, "Sin datos diarios en el rango")

    dias, cc, ec, tot = [], [], [], []
    for f in sorted({r["fecha"] for r in rows}):
        del_dia = [r for r in rows if r["fecha"] == f]
        dias.append(f.day)
        cc.append(next((int(r["ventas"]) for r in del_dia if r["subcanal"] == "Call Center"), 0))
        ec.append(next((int(r["ventas"]) for r in del_dia if r["subcanal"] == "E-commerce"), 0))
        tot.append(next((int(r["ventas"]) for r in del_dia if r["fila_es_total"]), 0))

    fig, ax = plt.subplots(figsize=(12, 5.5))
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    ax.plot(dias, tot, color=C_GRAY, lw=1.5, marker="o", ms=3, label="Ventas totales")
    ax.plot(dias, ec, color=C_EC, lw=2, marker="o", ms=4, label="E-commerce")
    ax.fill_between(dias, ec, color=C_EC, alpha=0.35)
    ax.plot(dias, cc, color=C_CC, lw=2, marker="o", ms=4, label="Call Center")
    for xs, ys, col in ((dias, tot, C_NAVY), (dias, ec, C_EC), (dias, cc, C_CC)):
        for x, y in zip(xs, ys):
            ax.annotate(_fmt(y), (x, y), textcoords="offset points",
                        xytext=(0, 5), ha="center", fontsize=6.5, color=col)

    lunes = ref - dt.timedelta(days=ref.weekday())
    if lunes.month == ref.month:
        ax.add_patch(Rectangle((lunes.day - 0.5, 0), ref.day - lunes.day + 1,
                               max(tot + [1]) * 1.12, fill=False,
                               edgecolor=C_PINK, lw=2, zorder=5))
    ax.set_ylim(0, max(tot + [1]) * 1.2)
    ax.set_yticks([])
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.legend(loc="upper center", ncol=3, frameon=False, fontsize=8)
    titulo = "CRÓNICA DE VENTAS DIARIA POR SUBCANAL"
    sub = f"Del 1 al {ref.day} de {MESES[ref.month]} de {ref.year} · {ambito}"
    fig.suptitle(titulo, fontsize=17, fontweight="bold", color=C_NAVY, x=0.12, ha="left")
    ax.set_title(sub, fontsize=10, color=C_NAVY, loc="left")
    return _upload(fig, f"diaria-{alcance}"), f"{titulo} · {sub}"


def _chart_semanal(ref, alcance, plaza, ambito):
    lunes = ref - dt.timedelta(days=ref.weekday())
    if ref.weekday() != 6:
        lunes = lunes - dt.timedelta(days=7)   # ultima semana completa
    lunes_prev = lunes - dt.timedelta(days=7)
    act = _fetch("semanal", lunes, alcance, plaza)
    ant = _fetch("semanal", lunes_prev, alcance, plaza)
    if not act or not ant:
        raise HTTPException(404, "Sin datos para las semanas solicitadas")
    t_a, s_a = _split(act)
    t_p, s_p = _split(ant)
    iso = lunes.isocalendar()[1]
    iso_p = lunes_prev.isocalendar()[1]

    def pct(cur, prev):
        return (cur - prev) / prev * 100 if prev else 0.0

    fig = plt.figure(figsize=(12, 6))
    fig.patch.set_facecolor(C_BG)
    ban = fig.add_axes([0.05, 0.82, 0.9, 0.13])
    ban.set_facecolor(C_BANNER)
    ban.set_xticks([]); ban.set_yticks([])
    var_tot = pct(int(t_a["ventas"]), int(t_p["ventas"]))
    ban.text(0.5, 0.62, f"{_fmt(t_a['ventas']).replace(',', '.')} Ventas Totales", ha="center",
             va="center", fontsize=20, fontweight="bold", color="white")
    ban.text(0.5, 0.2, f"({var_tot:+.0f}%) vs. la semana {iso_p}", ha="center",
             va="center", fontsize=10, color="white")

    for idx, canal in enumerate(("E-commerce", "Call Center")):
        ax = fig.add_axes([0.07 + idx * 0.5, 0.12, 0.36, 0.6])
        ax.set_facecolor(C_BG)
        a, p = s_a.get(canal, {}), s_p.get(canal, {})
        v, i = int(a.get("ventas", 0) or 0), int(a.get("instalaciones", 0) or 0)
        vp, ip = int(p.get("ventas", 0) or 0), int(p.get("instalaciones", 0) or 0)
        ax.bar(0, v, 0.6, color=C_EC, zorder=3)
        ax.bar(1, i, 0.6, color=C_CC, zorder=3)
        ax.text(0, v * 1.02, _fmt(v), ha="center", fontsize=10, fontweight="bold", color=C_NAVY)
        ax.text(1, i * 1.02, _fmt(i), ha="center", fontsize=10, fontweight="bold", color=C_NAVY)
        ax.text(0, v * 0.5, f"({pct(v, vp):+.0f}% WoW)", ha="center", fontsize=9,
                color="white", fontweight="bold")
        ax.text(1, i * 0.5, f"({pct(i, ip):+.0f}% WoW)", ha="center", fontsize=9,
                color="white", fontweight="bold")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["Venta", "Instalación"], fontsize=9)
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(canal, fontsize=12, fontweight="bold", color=C_NAVY, y=-0.18)
        tasa = i / v * 100 if v else 0
        ax.text(2.08, v * 0.70 if v else 1,
                f"{tasa:.0f}%\nTasa de instalación\n{canal}", fontsize=9,
                ha="center", va="center", color=C_NAVY, fontweight="bold",
                bbox=dict(facecolor="white", edgecolor=C_PINK, lw=2, pad=6))
        ax.set_xlim(-0.6, 2.95)

    titulo = f"PANORAMA SEMANA {iso} vs. SEMANA {iso_p}"
    fig.suptitle(titulo + f" · {ambito}", fontsize=16, fontweight="bold",
                 color=C_NAVY, x=0.05, y=0.995, ha="left")
    return _upload(fig, "semanal"), titulo


def _chart_plazas(ref):
    ini = ref.replace(day=1)
    lunes = ref - dt.timedelta(days=ref.weekday())
    if ref.weekday() != 6:
        lunes = lunes - dt.timedelta(days=7)
    lunes_prev = lunes - dt.timedelta(days=7)

    sql = f"""
    WITH mtd AS (
      SELECT plaza, periodo_inicio, periodo_fin, ventas, instalaciones, tasa_instalacion_pct
      FROM `{T_MER}`
      WHERE grano = 'mes_a_la_fecha' AND periodo_inicio = @ini
        AND nivel = 'plaza' AND fila_es_total
    ),
    wk AS (
      SELECT plaza, periodo_inicio, ventas
      FROM `{T_MER}`
      WHERE grano = 'semanal' AND periodo_inicio IN (@l1, @l0)
        AND nivel = 'plaza' AND fila_es_total
    )
    SELECT m.plaza, m.periodo_inicio, m.periodo_fin, m.ventas, m.instalaciones, m.tasa_instalacion_pct,
           a.ventas AS v_act, p.ventas AS v_prev
    FROM mtd m
    LEFT JOIN wk a ON a.plaza = m.plaza AND a.periodo_inicio = @l0
    LEFT JOIN wk p ON p.plaza = m.plaza AND p.periodo_inicio = @l1
    ORDER BY m.ventas DESC"""
    rows = _rows(sql, [
        bigquery.ScalarQueryParameter("ini", "DATE", ini),
        bigquery.ScalarQueryParameter("l0", "DATE", lunes),
        bigquery.ScalarQueryParameter("l1", "DATE", lunes_prev),
    ])
    rows = [r for r in rows if r["plaza"] != "(sin plaza)"]
    if not rows:
        raise HTTPException(404, "Sin datos de plazas para el mes")

    tot = _fetch("mes_a_la_fecha", ini, "nacional", None)
    t_nac, _ = _split(tot)

    encabezado = ["Plaza", "Ventas MTD", "Instalaciones", "Tasa inst %", "WoW ventas %"]
    celdas, colores = [], []
    for r in rows:
        wow = ((int(r["v_act"]) - int(r["v_prev"])) / int(r["v_prev"]) * 100
               if r["v_prev"] else None)
        tasa = float(r["tasa_instalacion_pct"] or 0)
        celdas.append([r["plaza"], _fmt(r["ventas"]), _fmt(r["instalaciones"]),
                       f"{tasa:.0f}%", f"{wow:+.0f}%" if wow is not None else "s/d"])
        c_t = C_GREEN if tasa >= 75 else C_YELLOW if tasa >= 60 else C_RED
        c_w = (C_GREEN if wow is not None and wow > 0
               else C_YELLOW if wow is not None and wow >= -10 else C_RED)
        colores.append(["white", "white", "white", c_t, c_w])
    celdas.append(["TOTAL", _fmt(t_nac["ventas"]), _fmt(t_nac["instalaciones"]),
                   f"{float(t_nac['tasa_instalacion_pct']):.0f}%", ""])
    colores.append(([C_RED] if t_nac.get("cuadra") is False else [C_BANNER]) * 5)

    fig, ax = plt.subplots(figsize=(8.5, 0.34 * len(celdas) + 1.6))
    fig.patch.set_facecolor(C_BG)
    ax.axis("off")
    tabla = ax.table(cellText=celdas, colLabels=encabezado,
                     cellColours=colores, loc="center", cellLoc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(8)
    tabla.scale(1, 1.25)
    tabla.auto_set_column_width(col=list(range(5)))
    for (fila, col), celda in tabla.get_celld().items():
        if fila == 0:
            celda.set_facecolor(C_NAVY)
            celda.set_text_props(color="white", fontweight="bold")
        elif fila == len(celdas):
            celda.set_text_props(color="white", fontweight="bold")
    pi, pf = rows[0]["periodo_inicio"], rows[0]["periodo_fin"]
    titulo = "AVANCE DE PLAZAS MENSUAL"
    sub = f"Del {pi.day} al {pf.day} de {MESES[pf.month]} de {pf.year} · Total oficial nacional, plazas ordenadas por ventas"
    if t_nac.get("cuadra") is False:
        sub += "\nTOTAL NACIONAL NO CONCILIADO: revisar hoja origen antes de usar la fila TOTAL."
    ax.set_title(titulo + "\n" + sub, fontsize=10, fontweight="bold", color=C_NAVY, loc="left", pad=14)
    fig.tight_layout()
    return _upload(fig, "plazas"), f"{titulo} · {sub}"
