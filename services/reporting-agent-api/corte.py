import datetime as dt
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from charts import _bq, _upload, TZ, C_EC, C_CC, C_BG, C_NAVY

router = APIRouter()

TF = "PROJECT_ID.DATASET.tf_corte_ventas"
T_PROD = "PROJECT_ID.DATASET.vw_product_telco_v3"
WOW_POS, WOW_NEG, WOW_NEU = "#00B050", "#C00000", "#595959"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_txt(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month]}"


def _corta(d):
    return f"{DIAS[d.weekday()].capitalize()} {d.day}"


def _rango_txt(a, b):
    if a.month == b.month:
        return f"del {a.day} al {b.day} de {MESES[b.month]}"
    return f"del {a.day} de {MESES[a.month]} al {b.day} de {MESES[b.month]}"


def _lista_fechas(fechas):
    partes = [_fecha_txt(f) for f in fechas]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def _n(v):
    return "s/d" if v is None else f"{int(round(v)):,}"


def _pct(v):
    if v is None:
        return "s/d"
    if v == 0:
        return "0%"
    return f"{'+' if v > 0 else ''}{v:.1f}%"


def _pp(v):
    if v is None:
        return "s/d"
    return f"{'+' if v > 0 else ''}{v:.2f} pp"


def _var_n(v):
    return "s/d" if v is None else f"{'+' if v > 0 else ''}{int(round(v)):,}"


def _abs_n(v):
    return "s/d" if v is None else f"{abs(int(round(v))):,}"


def _abs_pct(v):
    return "s/d" if v is None else f"{abs(v):.1f}%"


def _color(v):
    if not v:
        return WOW_NEU
    return WOW_POS if v > 0 else WOW_NEG


def _lista(items):
    partes = [f"{s['metrica']} ({_var_n(s['variacion'])})" for s in items]
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def _cargar(ini, fin):
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("i", "DATE", ini),
        bigquery.ScalarQueryParameter("f", "DATE", fin),
    ])
    rows = [dict(r) for r in _bq.query(f"SELECT * FROM `{TF}`(@i, @f)", job_config=cfg).result()]
    idx = {(r["nivel"], r["fecha"], r["grupo"], r["metrica"]): r for r in rows}
    return rows, idx


def _paquetes(ini):
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("i", "DATE", ini)])
    sql = f"""
      SELECT nombre_articulo, familia, SUM(transacciones) AS articulos
      FROM `{T_PROD}`
      WHERE fecha_inicio_sem = @i AND familia IN ('2P', '3P')
      GROUP BY nombre_articulo, familia
      ORDER BY articulos DESC
      LIMIT 2
    """
    try:
        return [dict(r) for r in _bq.query(sql, job_config=cfg).result()]
    except Exception:
        return []


def _textos(rows, idx, nivel, fecha, ref_txt):
    def g(grupo, m):
        return idx.get((nivel, fecha, grupo, m)) or {}

    tot, eco, cc = g("Ventas", "Total"), g("Ventas", "E-commerce"), g("Ventas", "Call Center")
    ses, usu, tasa = g("GA4", "Sesiones"), g("GA4", "Usuarios activos"), g("GA4", "Tasa de cierre (%)")

    tasa_txt = "s/d" if tasa.get("actual") is None else f"{tasa['actual']:.2f}%"
    kpis = [
        f"Ventas generales: {_n(tot.get('actual'))} ({_pct(tot.get('variacion_pct'))})",
        f"Ventas E-commerce: {_n(eco.get('actual'))} ({_pct(eco.get('variacion_pct'))})",
        f"Ventas Call Center: {_n(cc.get('actual'))} ({_pct(cc.get('variacion_pct'))})",
        f"Sesiones: {_n(ses.get('actual'))} ({_pct(ses.get('variacion_pct'))})",
        f"Usuarios: {_n(usu.get('actual'))} ({_pct(usu.get('variacion_pct'))})",
        f"Tasa de cierre: {tasa_txt} ({_pp(tasa.get('variacion'))})",
    ]

    analisis, notas = [], []

    vt = tot.get("variacion")
    if vt is not None:
        if vt == 0:
            analisis.append(f"Las ventas generales se mantuvieron sin cambio frente {ref_txt}.")
        else:
            canales = [("E-commerce", eco.get("variacion") or 0), ("Call Center", cc.get("variacion") or 0)]
            motor = max(canales, key=lambda c: c[1] if vt > 0 else -c[1])
            verbo = "subieron" if vt > 0 else "bajaron"
            analisis.append(
                f"Las ventas generales {verbo} {_abs_n(vt)} ({_pct(tot.get('variacion_pct'))}) "
                f"frente {ref_txt}, principalmente por {motor[0]}.")

    ve = eco.get("variacion")
    if ve is not None:
        verbo = "creció" if ve > 0 else ("cayó" if ve < 0 else "se mantuvo")
        linea = (f"E-commerce {verbo} {_abs_pct(eco.get('variacion_pct'))} "
                 f"({_abs_n(ve)} {'venta' if abs(round(ve)) == 1 else 'ventas'} {'más' if ve > 0 else 'menos'})." if ve else "E-commerce se mantuvo sin cambio.")
        if ses.get("variacion_pct") is not None and tasa.get("actual") is not None and tasa.get("anterior") is not None:
            linea += (f" Las sesiones variaron {_pct(ses.get('variacion_pct'))} y la tasa de cierre "
                      f"pasó de {tasa['anterior']:.2f}% a {tasa['actual']:.2f}%.")
        analisis.append(linea)

    permitido = bool(cc.get("explicacion_subcanal_permitida"))
    difs = []
    for canal, k_n, k_p in (("Call Center", "dif_cc_vs_operativo", "dif_cc_pct"),
                            ("E-commerce", "dif_ecommerce_vs_operativo", "dif_ecommerce_pct")):
        dn = cc.get(k_n)
        if dn:
            difs.append(f"{canal} {_var_n(dn)} ({cc.get(k_p)}%)")
    if difs:
        notas.append("Diferencia de la hoja de ventas y leads frente a la hoja operativa: " + ", ".join(difs) + ".")
    if cc.get("dif_subcanales_vs_cc"):
        notas.append("Diferencia entre la suma de subcanales y el total de Call Center en la hoja de ventas y leads: "
                     f"{_var_n(cc['dif_subcanales_vs_cc'])}.")

    vc = cc.get("variacion")
    if vc is not None:
        verbo = "subió" if vc > 0 else ("bajó" if vc < 0 else "se mantuvo")
        linea = (f"Call Center {verbo} {_abs_pct(cc.get('variacion_pct'))} "
                 f"({_abs_n(vc)} {'venta' if abs(round(vc)) == 1 else 'ventas'} {'más' if vc > 0 else 'menos'})" if vc else "Call Center se mantuvo sin cambio")
        if not permitido:
            linea += (". No se presenta el detalle por subcanal porque, en el periodo reportado o en el de "
                      "comparación, la suma de subcanales o la diferencia entre hojas supera el 1% "
                      "del total de Call Center.")
        else:
            subs = [r for r in rows if r["nivel"] == nivel and r["fecha"] == fecha
                    and r["grupo"] == "Ventas Call Center" and (r["variacion"] or 0) != 0]
            if vc != 0:
                misma = sorted([s for s in subs if (s["variacion"] > 0) == (vc > 0)], key=lambda s: -abs(s["variacion"]))
                contra = sorted([s for s in subs if (s["variacion"] > 0) != (vc > 0)], key=lambda s: -abs(s["variacion"]))
            else:
                misma, contra = sorted(subs, key=lambda s: -abs(s["variacion"])), []
            if misma:
                linea += (", principalmente por " if vc != 0 else ", con movimientos en ") + _lista(misma[:2])
            if contra:
                linea += "; en sentido contrario, " + _lista(contra[:2])
            linea += "."
            if misma:
                top = misma[0]["metrica"]
                ld = g("Leads Call Center", top)
                if ld.get("variacion_pct") is not None:
                    linea += (f" En {top}, los leads pasaron de {_n(ld.get('anterior'))} "
                              f"a {_n(ld.get('actual'))} ({_pct(ld['variacion_pct'])}).")
        analisis.append(linea)

    if tot.get("provisional_actual") or tot.get("provisional_anterior"):
        notas.append("Cifras de ventas preliminares: el total oficial aún no está cargado en la hoja "
                     "operativa para todos los días del corte; se usa la hoja de ventas y leads.")
    if ses.get("actual") is None:
        notas.append("Los datos de GA4 del periodo aún no están disponibles.")

    return kpis, analisis, notas, permitido


def _barras(ax, xs, ecos, ccs, ancho):
    ax.bar(xs, ecos, color=C_EC, width=ancho, label="E-commerce")
    ax.bar(xs, ccs, bottom=ecos, color=C_CC, width=ancho, label="Call Center")
    tope = max([e + c for e, c in zip(ecos, ccs)] or [1])
    for x, e, c in zip(xs, ecos, ccs):
        if e:
            ax.text(x, e / 2, _n(e), ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        if c:
            ax.text(x, e + c / 2, _n(c), ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        ax.text(x, e + c + tope * 0.02, _n(e + c), ha="center", va="bottom", color=C_NAVY, fontsize=10, fontweight="bold")
    return tope


def _estilo(fig, ax, titulo, nota=None):
    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_title(titulo, color=C_NAVY, fontsize=12, fontweight="bold", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False)
    if nota:
        fig.text(0.01, -0.04, nota, fontsize=9, color=WOW_NEG, ha="left", va="top")


def _grafica_diaria(idx, d, dc, nota=None):
    def v(grupo, m, campo):
        return (idx.get(("dia", d, grupo, m)) or {}).get(campo)

    ecos = [v("Ventas", "E-commerce", "anterior") or 0, v("Ventas", "E-commerce", "actual") or 0]
    ccs = [v("Ventas", "Call Center", "anterior") or 0, v("Ventas", "Call Center", "actual") or 0]
    fig, ax = plt.subplots(figsize=(8, 5))
    tope = _barras(ax, [0, 1], ecos, ccs, 0.55)
    ax.set_xticks([0, 1], [f"{_corta(dc)} (semana anterior)", _corta(d)])
    y = tope
    for etiqueta, m in (("Total", "Total"), ("E-commerce", "E-commerce"), ("Call Center", "Call Center")):
        p = v("Ventas", m, "variacion_pct")
        ax.text(1.45, y, f"{etiqueta}: {_pct(p)} WoW", color=_color(p), fontsize=11, fontweight="bold", va="top")
        y -= tope * 0.12
    ax.set_xlim(-0.6, 2.3)
    ax.set_ylim(0, tope * 1.15)
    _estilo(fig, ax, f"Ventas {_fecha_txt(d)} vs {_fecha_txt(dc)}", nota)
    return _upload(fig, f"corte-diario-{d:%Y%m%d}")


def _grafica_semanal(idx, ini, nota=None):
    dias = [ini + dt.timedelta(days=i) for i in range(7)]

    def v(d, grupo, m, campo):
        return (idx.get(("dia", d, grupo, m)) or {}).get(campo)

    ecos = [v(d, "Ventas", "E-commerce", "actual") or 0 for d in dias]
    ccs = [v(d, "Ventas", "Call Center", "actual") or 0 for d in dias]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    xs = list(range(7))
    tope = _barras(ax, xs, ecos, ccs, 0.65)
    for x, d, e, c in zip(xs, dias, ecos, ccs):
        p = v(d, "Ventas", "Total", "variacion_pct")
        ax.text(x, e + c + tope * 0.09, f"{_pct(p)} WoW", ha="center", color=_color(p), fontsize=9, fontweight="bold")
    ax.set_xticks(xs, [_corta(d) for d in dias])
    ax.set_ylim(0, tope * 1.25)
    fin = dias[-1]
    _estilo(fig, ax, f"Ventas {_rango_txt(ini, fin)} vs semana anterior", nota)
    return _upload(fig, f"corte-semanal-{ini:%Y%m%d}")


def _serializar(rows):
    out = []
    for r in rows:
        f = dict(r)
        for k in ("fecha", "fecha_comp"):
            if f.get(k) is not None:
                f[k] = str(f[k])
        out.append(f)
    return out


@router.get("/api/v1/corte")
def corte(
    tipo: str = Query("diario", description="diario o semanal"),
    fecha: Optional[str] = Query(None, description="diario: dia a reportar. semanal: cualquier dia de la semana. YYYY-MM-DD"),
    incluir_grafica: bool = Query(True),
):
    hoy = dt.datetime.now(TZ).date()
    try:
        base = dt.date.fromisoformat(fecha) if fecha else None
    except ValueError:
        raise HTTPException(status_code=400, detail="fecha debe tener formato YYYY-MM-DD")

    if tipo == "diario":
        ini = fin = base or (hoy - dt.timedelta(days=1))
        nivel = "dia"
    elif tipo == "semanal":
        ref = base or (hoy - dt.timedelta(days=7))
        ini = ref - dt.timedelta(days=ref.weekday())
        fin = ini + dt.timedelta(days=6)
        nivel = "rango"
    else:
        raise HTTPException(status_code=400, detail="tipo debe ser diario o semanal")

    if fin >= hoy:
        raise HTTPException(status_code=400, detail="El corte solo cubre dias completos. Usa una fecha anterior a hoy.")

    try:
        rows, idx = _cargar(ini, fin)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error BigQuery: {type(e).__name__}")
    if not rows:
        raise HTTPException(status_code=404, detail="Sin datos para el periodo solicitado.")

    comp_ini = ini - dt.timedelta(days=7)
    comp_fin = fin - dt.timedelta(days=7)
    if tipo == "diario":
        ref_txt = f"al {_fecha_txt(comp_ini)}"
        titulo = f"Corte de ventas del {_fecha_txt(ini)} vs {_fecha_txt(comp_ini)}"
    else:
        ref_txt = "a la semana anterior"
        titulo = f"Corte de ventas {_rango_txt(ini, fin)} vs {_rango_txt(comp_ini, comp_fin)}"

    kpis, analisis, notas, permitido = _textos(rows, idx, nivel, ini, ref_txt)

    dias_periodo = [ini + dt.timedelta(days=i) for i in range((fin - ini).days + 1)]
    faltan = [d for d in dias_periodo
              if (idx.get(("dia", d, "Ventas", "Total")) or {}).get("actual") is None]
    faltan_comp = [d - dt.timedelta(days=7) for d in dias_periodo
                   if (idx.get(("dia", d, "Ventas", "Total")) or {}).get("anterior") is None]
    ses_corte = idx.get((nivel, ini, "GA4", "Sesiones")) or {}
    if faltan_comp:
        notas.insert(0, "Corte incompleto: no hay datos de ventas en el periodo de comparación para "
                     + _lista_fechas(faltan_comp) + ".")
    if faltan:
        notas.insert(0, "Corte incompleto: no hay datos de ventas para " + _lista_fechas(faltan)
                     + ". Las variaciones no son comparables y el corte no debe publicarse hasta que se carguen.")
    incompleto = bool(faltan or faltan_comp or ses_corte.get("actual") is None)

    if tipo == "semanal":
        paq = _paquetes(ini)
        if paq:
            nombres = " y ".join(f"{p['nombre_articulo']} {p['familia']}" for p in paq)
            analisis.append(f"Los paquetes con más artículos comprados en la semana fueron {nombres}.")
        else:
            notas.append("Los paquetes de esta semana aún no están cargados en la base de artículos.")

    texto = titulo + "\n\n" + "\n".join(kpis) + "\n\n" + "\n\n".join(analisis)
    if notas:
        texto += "\n\nNotas:\n" + "\n".join(notas)

    texto_md = f"**{titulo}**\n\n" + "\n".join(f"- {k}" for k in kpis) + "\n\n" + "\n\n".join(analisis)
    if notas:
        texto_md += "\n\n*Notas:*\n" + "\n".join(f"- {n}" for n in notas)

    tot_corte = idx.get((nivel, ini, "Ventas", "Total")) or {}
    nota_grafica = ("Cifras preliminares: el total oficial aún no está cargado en la hoja operativa."
                    if tot_corte.get("provisional_actual") or tot_corte.get("provisional_anterior") else None)

    if faltan or faltan_comp:
        nota_grafica = "Corte incompleto: hay días sin datos de ventas. No publicar."

    grafica = None
    if incluir_grafica:
        try:
            grafica = (_grafica_diaria(idx, ini, comp_ini, nota_grafica) if tipo == "diario"
                       else _grafica_semanal(idx, ini, nota_grafica))
        except Exception as e:
            notas.append(f"No se pudo generar la gráfica: {type(e).__name__}")

    tot = idx.get((nivel, ini, "Ventas", "Total")) or {}
    return {
        "tipo": tipo,
        "periodo": {"inicio": str(ini), "fin": str(fin)},
        "comparacion": {"inicio": str(comp_ini), "fin": str(comp_fin)},
        "texto": texto,
        "texto_markdown": texto_md,
        "grafica_url": grafica,
        "kpis": kpis,
        "analisis": analisis,
        "notas": notas,
        "cifras_preliminares": bool(tot.get("provisional_actual") or tot.get("provisional_anterior")),
        "explicacion_subcanal_permitida": permitido,
        "regla": "Todas las cifras vienen de BigQuery (tf_corte_ventas). El texto se construye con reglas fijas sobre esas cifras.",
        "estado": "incompleto" if incompleto else "ok",
        "dias_sin_datos": [str(d) for d in faltan],
        "dias_sin_datos_comparacion": [str(d) for d in faltan_comp],
        "datos": _serializar(rows),
    }
