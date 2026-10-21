import vertexai
from vertexai import agent_engines
from google.adk.agents import Agent

PROJECT_ID = "PROJECT_ID"
LOCATION = "us-central1"
STAGING_BUCKET = "gs://STAGING_BUCKET"
RESOURCE_NAME = "projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID"

vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

def obtener_datos_salesforce_telco(
    fecha_inicio: str,
    fecha_fin: str,
    grano: str,
    alcance: str,
    plaza: str,
    distrito: str,
) -> str:
    """Consulta ventas e instalaciones Salesforce telco.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD. Ejemplo: 2026-08-03.
        fecha_fin: Fecha final YYYY-MM-DD. Ejemplo: 2026-08-09.
        grano: semanal, diario, quincenal, mensual, mes_a_la_fecha o mes_anterior_mismo_corte (mes anterior cortado al mismo dia que el ultimo dato cargado, para comparar contra mes_a_la_fecha). Usar semanal por defecto.
        alcance: nacional o mercado. Usar nacional por defecto.
        plaza: Nombre exacto de la plaza cuando alcance es mercado. String vacio si no aplica.
        distrito: Nombre exacto del distrito cuando alcance es mercado. String vacio si no aplica.

    Returns:
        JSON string con periodos, total_oficial, desglose_subcanal y advertencias.
    """
    import json
    import requests

    URL = "https://REPORTING_API_HOST/api/v1/salesforce"
    AUD = "https://REPORTING_API_HOST"

    token = ""
    err_meta = ""
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
            params={"audience": AUD, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        r.raise_for_status()
        token = r.text.strip()
    except Exception as e:
        err_meta = f"{type(e).__name__}: {e}"

    if not token:
        try:
            import google.auth.transport.requests
            import google.oauth2.id_token
            auth_req = google.auth.transport.requests.Request()
            token = google.oauth2.id_token.fetch_id_token(auth_req, AUD)
        except Exception as e:
            return json.dumps({"error": f"auth fallo. metadata: {err_meta} | fetch_id_token: {type(e).__name__}: {e}"})

    try:
        params = {
            "grano": grano if grano else "semanal",
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "alcance": alcance if alcance else "nacional",
        }
        if plaza:
            params["plaza"] = plaza
        if distrito:
            params["distrito"] = distrito
        r = requests.get(URL, headers={"Authorization": "Bearer " + token}, params=params, timeout=25)
        r.raise_for_status()
        data = r.json()
        if grano == "mes_a_la_fecha" and not data.get("periodos"):
            import datetime as _dt
            fi = _dt.date.fromisoformat(fecha_inicio)
            fi_prev = (fi.replace(day=1) - _dt.timedelta(days=1)).replace(day=1)
            ff_prev = fi.replace(day=1) - _dt.timedelta(days=1)
            params["fecha_inicio"] = fi_prev.isoformat()
            params["fecha_fin"] = ff_prev.isoformat()
            r2 = requests.get(URL, headers={"Authorization": "Bearer " + token}, params=params, timeout=25)
            r2.raise_for_status()
            data2 = r2.json()
            if data2.get("periodos"):
                data2["nota_fallback"] = "El mes solicitado no tiene datos; se devuelve el mes a la fecha del ultimo mes con datos."
                return json.dumps(data2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})



def generar_grafica_telco(
    tipo: str,
    fecha_referencia: str = "",
    alcance: str = "nacional",
    plaza: str = "",
) -> str:
    """Genera una grafica oficial de telco y devuelve la URL temporal de la imagen.

    Args:
        tipo: mensual (ventas e instalaciones del mes vs el mismo corte del mes
            anterior, por subcanal), diaria (cronica de ventas diaria por subcanal
            del mes), semanal (panorama de la ultima semana completa vs la
            anterior), plazas (tabla de avance mensual por plaza con semaforo).
        fecha_referencia: opcional, YYYY-MM-DD para anclar el corte. Vacio usa
            automaticamente el ultimo dia con datos.
        alcance: nacional (default) o mercado. mercado aplica a mensual y diaria.
        plaza: nombre exacto de la plaza cuando alcance es mercado. Vacio si no aplica.

    Returns:
        JSON string con titulo y url de la imagen PNG. La url expira en 24 horas.
    """
    import json
    import requests
    import google.auth.transport.requests
    import google.oauth2.id_token

    URL = "https://REPORTING_API_HOST/api/v1/chart"
    AUD = "https://REPORTING_API_HOST"

    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, AUD)
        params = {"tipo": tipo}
        if fecha_referencia:
            params["fecha_referencia"] = fecha_referencia
        if alcance:
            params["alcance"] = alcance
        if plaza:
            params["plaza"] = plaza
        r = requests.get(URL, headers={"Authorization": "Bearer " + token},
                         params=params, timeout=90)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})


def obtener_datos_flujo_c(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    grano: str = "",
    capa: str = "",
    canal: str = "",
    campaign_name: str = "",
    etapa_funnel: str = "",
    plataforma: str = "",
    desglose: bool = False,
) -> str:
    """Consulta el layer digital de telco Residencial (Flow C) desde BigQuery.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD.
        fecha_fin: Fecha final YYYY-MM-DD.
        grano: semanal, quincenal, mensual o mes_a_la_fecha. Default mensual.
        capa: media (gasto, impresiones, vistas, clics, conversiones por campana),
            acquisition (sesiones, usuarios, compras digitales, revenue, ticket promedio
            por fuente y campana), behaviour (eventos por etapa del funnel, eventos clave,
            interacciones con contenido y productos), gaming_fest (sesiones y campanas
            del evento event campaign Event campaign, octubre a noviembre 2025, fuente GA4
            property EVENT_PROPERTY_ID). Default acquisition.
        canal: E-commerce, Call Center, YouTube, Call Center / E-commerce. Opcional.
        campaign_name: nombre o parte del nombre de campana. Opcional.
        etapa_funnel: Traffic acquisition, Engagement, Awareness, Consideration,
            Intent, Lead conversion, Digital conversion. Solo para capa behaviour.
        plataforma: Google o Meta. Solo para capa media.

    Returns:
        JSON string con capa, grano, filtros aplicados, total_filas y periodos
        con las metricas disponibles segun la capa. Las metricas de GA4 y las de
        Salesforce son universos separados: no calcular tasas de conversion entre
        compras digitales y ventas Salesforce.
    """
    import json
    import requests
    import google.auth.transport.requests
    import google.oauth2.id_token

    URL = "https://REPORTING_API_HOST/api/v1/flujo_c"
    AUD = "https://REPORTING_API_HOST"

    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, AUD)
        params = {
            "grano": grano or "mensual",
            "capa": capa or "acquisition",
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
        }
        if canal:
            params["canal"] = canal
        if campaign_name:
            params["campaign_name"] = campaign_name
        if etapa_funnel:
            params["etapa_funnel"] = etapa_funnel
        if plataforma:
            params["plataforma"] = plataforma
        if desglose:
            params["desglose"] = "true"
        r = requests.get(URL, headers={"Authorization": "Bearer " + token},
                         params=params, timeout=30)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})


def obtener_datos_region_telco(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    grano: str = "",
    region: str = "",
) -> str:
    """Consulta ventas e instalaciones de telco por region comercial.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD.
        fecha_fin: Fecha final YYYY-MM-DD.
        grano: semanal, quincenal, mensual o mes_a_la_fecha. Default semanal.
        region: Oriente, Sur, Bajio, Noreste, Pacifico, Occidente, Centro,
            Frontera o Norte. Vacio devuelve todas las regiones.

    Returns:
        JSON con total_oficial por region y desglose por subcanal.
        Los totales regionales se derivan de plazas oficiales.
        Nunca sumar regiones entre si para obtener un nacional.
        El total nacional oficial esta en agente_telco_nacional.
    """
    import json
    import requests
    import google.auth.transport.requests
    import google.oauth2.id_token

    URL = "https://REPORTING_API_HOST/api/v1/region"
    AUD = "https://REPORTING_API_HOST"

    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, AUD)
        params = {
            "grano": grano or "semanal",
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
        }
        if region:
            params["region"] = region
        r = requests.get(URL, headers={"Authorization": "Bearer " + token},
                         params=params, timeout=25)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})


def obtener_datos_rango_telco(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    alcance: str = "nacional",
    plaza: str = "",
    desplazamiento_dias: int = 7,
) -> str:
    """Consulta ventas e instalaciones Salesforce para un rango de fechas personalizado
    (por ejemplo lunes a miercoles, o del 1 al 20 de agosto) y su periodo de comparacion.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD.
        fecha_fin: Fecha final YYYY-MM-DD.
        alcance: nacional o mercado.
        plaza: Nombre exacto de la plaza del catalogo. Obligatorio si alcance=mercado.
        desplazamiento_dias: Dias hacia atras para el periodo de comparacion.
            7 = mismos dias de la semana anterior (default).
            Para comparar contra el mismo rango del mes anterior usa el numero de dias
            que tenga el mes anterior (por ejemplo 31 para agosto vs julio).

    Returns:
        JSON con filas periodo=actual y periodo=comparacion. La fila subcanal=(todos)
        es el total oficial del rango. Todas las sumas vienen calculadas desde BigQuery.
    """
    import json
    import requests

    URL = "https://REPORTING_API_HOST/api/v1/rango"
    AUD = "https://REPORTING_API_HOST"

    token = ""
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
            params={"audience": AUD, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        r.raise_for_status()
        token = r.text.strip()
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"alcance": alcance or "nacional", "desplazamiento_dias": desplazamiento_dias}
    if fecha_inicio:
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        params["fecha_fin"] = fecha_fin
    if plaza:
        params["plaza"] = plaza

    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def obtener_datos_canales_telco(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    desplazamiento_dias: int = 7,
    desglose: bool = False,
) -> str:
    """Consulta sesiones, usuarios, compras digitales y revenue de GA4 Residencial por
    grupo de canales predeterminado (Cross-network, Organic Search, Direct, Referral,
    Paid Social, etc.), el mismo campo Grupo de canales que usa el dashboard de Looker.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD.
        fecha_fin: Fecha final YYYY-MM-DD.
        desplazamiento_dias: Dias hacia atras para el periodo de comparacion.
            7 para semana anterior, numero de dias del mes anterior para mes anterior.
        desglose: True agrega filas de fuente / medio dentro de cada grupo.

    Returns:
        JSON con filas nivel=total, nivel=grupo y opcionalmente nivel=fuente_medio,
        para periodo=actual y periodo=comparacion.
    """
    import json
    import requests

    URL = "https://REPORTING_API_HOST/api/v1/canales"
    AUD = "https://REPORTING_API_HOST"

    token = ""
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
            params={"audience": AUD, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        r.raise_for_status()
        token = r.text.strip()
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"desplazamiento_dias": desplazamiento_dias}
    if fecha_inicio:
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        params["fecha_fin"] = fecha_fin
    if desglose:
        params["desglose"] = "true"

    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def obtener_corte_telco(
    tipo: str = "diario",
    fecha: str = "",
) -> str:
    """Genera el corte de ventas diario o semanal que el equipo reporta al cliente:
    cifras conciliadas, grafica y texto de analisis por subcanal.

    Args:
        tipo: diario (un dia contra el mismo dia de la semana anterior) o semanal
            (lunes a domingo, siete dias contra la semana anterior).
        fecha: YYYY-MM-DD. Diario: el dia a reportar (por defecto ayer).
            Semanal: cualquier dia de la semana a reportar (por defecto la ultima semana completa).

    Returns:
        JSON con texto (listo para enviar), grafica_url, notas, cifras_preliminares
        y explicacion_subcanal_permitida.
    """
    import json
    import requests

    URL = "https://REPORTING_API_HOST/api/v1/corte"
    AUD = "https://REPORTING_API_HOST"

    token = ""
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
            params={"audience": AUD, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        r.raise_for_status()
        token = r.text.strip()
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"tipo": tipo or "diario"}
    if fecha:
        params["fecha"] = fecha

    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=180)
        if resp.status_code >= 400:
            return json.dumps({"error": resp.json().get("detail", resp.text)}, ensure_ascii=False)
        d = resp.json()
        d.pop("datos", None)
        return json.dumps(d, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def obtener_datos_app_telco(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    familia: str = "",
) -> str:
    """Consulta la frecuencia de apps incluidas en paquetes comprados de telco Residencial.

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD.
        fecha_fin: Fecha final YYYY-MM-DD.
        familia: 2P o 3P. Opcional, si no se especifica devuelve ambas.

    IMPORTANTE: Los conteos por app se superponen. Un paquete con Netflix + Universal + Apple
    suma 1 transaccion a cada app. Nunca presentar los conteos de apps como suma aditiva.
    Siempre incluir la advertencia de superposicion en la respuesta.
    """
    import json
    import requests

    URL = "https://REPORTING_API_HOST/api/v1/apps"
    AUD = "https://REPORTING_API_HOST"

    token = ""
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
            params={"audience": AUD, "format": "full"},
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        r.raise_for_status()
        token = r.text.strip()
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {}
    if fecha_inicio:
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        params["fecha_fin"] = fecha_fin
    if familia:
        params["familia"] = familia

    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def obtener_datos_producto_telco(
    fecha_inicio: str = "",
    fecha_fin: str = "",
    familia: str = "",
    item_name: str = "",
    item_category: str = "",
) -> str:
    """Consulta transacciones digitales de telco por paquete, velocidad y familia.

    Datos disponibles desde semana 29 (julio 2026). Fuente: base madre telco (articulos_comprados).

    Args:
        fecha_inicio: Fecha inicial YYYY-MM-DD. Minimo 2026-09-07.
        fecha_fin: Fecha final YYYY-MM-DD.
        familia: 2P (internet solo), 3P (internet + TV), Addon (servicios adicionales).
            Vacio devuelve todas las familias.
        item_name: nombre o parte del nombre del paquete. Ej: "150 megas", "Internet".
        item_category: categoria del producto. Ej: "Internet", "Internet + telco".

    Returns:
        JSON con lista de productos ordenados por transacciones, con item_name,
        item_category, familia, velocidad_megas, transacciones, revenue_total
        y precio_promedio. Fuente: GA4 export nativo, property PROPERTY_ID.
    """
    import json
    import requests
    import google.auth.transport.requests
    import google.oauth2.id_token

    URL = "https://REPORTING_API_HOST/api/v1/producto"
    AUD = "https://REPORTING_API_HOST"

    try:
        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, AUD)
        params = {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
        }
        if familia:
            params["familia"] = familia
        if item_name:
            params["item_name"] = item_name
        if item_category:
            params["item_category"] = item_category
        r = requests.get(URL, headers={"Authorization": "Bearer " + token},
                         params=params, timeout=30)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)}"})


SYSTEM_PROMPT = """Eres el Agente Validador de Datos de telco, analista de nivel directivo.

CALENDARIO ISO 8601 — 2026. NUNCA pidas fechas al usuario. Calculas tu mismo:
Semana 27: 2026-06-29 a 2026-07-05
Semana 28: 2026-07-06 a 2026-07-12
Semana 29: 2026-07-13 a 2026-07-19
Semana 30: 2026-07-20 a 2026-07-26
Semana 31: 2026-07-27 a 2026-08-02
Semana 32: 2026-08-03 a 2026-08-09
Semana 33: 2026-08-10 a 2026-08-16
Semana 34: 2026-08-17 a 2026-08-23
Semana 35: 2026-08-24 a 2026-08-30
Semana 36: 2026-08-31 a 2026-09-06

Para cualquier semana calcula el lunes y domingo de esa semana ISO en 2026 directamente desde el numero de semana, sin depender de la tabla anterior. La tabla es solo referencia rapida para las semanas mas frecuentes.

CATALOGO DE PLAZAS. El parametro plaza debe ser EXACTAMENTE uno de estos valores:
ACAPULCO, AGUASCALIENTES, CANCUN, CELAYA, CHIHUAHUA, CIUDAD DE MEXICO, CIUDAD JUAREZ, CIUDAD OBREGON / NAVOJOA, CIUDAD VICTORIA, COATZA / MINA, COLIMA / MANZANILLO, CORDOBA / ORIZABA, CUERNAVACA, CULIACAN, GUADALAJARA, GUANAJUATO, HERMOSILLO, IRAPUATO, LEON, MATAMOROS, MAZATLAN, MERIDA, MEXICALI, MONTERREY, MORELIA, NUEVO LAREDO, PACHUCA, PIEDRAS NEGRAS / MONCLOVA, POZA RICA, PUEBLA, PUERTO VALLARTA, QUERETARO, REYNOSA, SALTILLO, SAN LUIS POTOSI, TAMPICO, TEPIC, TIJUANA, TOLUCA, TORREON, TUXTLA, VERACRUZ, VILLAHERMOSA, XALAPA

ALIAS COMUNES que debes convertir al nombre exacto:
CDMX, DF, Ciudad de Mexico, Mexico City → CIUDAD DE MEXICO
GDL, Guadalajara → GUADALAJARA
MTY, Monterrey → MONTERREY
SLP → SAN LUIS POTOSI
Juarez → CIUDAD JUAREZ
Obregon o Navojoa → CIUDAD OBREGON / NAVOJOA
La Laguna → TORREON
Toluca o Lerma → TOLUCA
Coatzacoalcos o Minatitlan → COATZA / MINA
Colima o Manzanillo → COLIMA / MANZANILLO
Cordoba u Orizaba → CORDOBA / ORIZABA
Piedras Negras o Monclova → PIEDRAS NEGRAS / MONCLOVA

REGLAS DE DATOS:
1. Llama siempre a obtener_datos_salesforce_telco con las fechas calculadas. NUNCA pidas fechas al usuario.
2. Pasa siempre los seis parametros. grano semanal y alcance nacional por defecto, plaza y distrito string vacio si no aplican.
3. La herramienta devuelve un JSON string. La cifra oficial esta en total_oficial. Nunca sumes desglose_subcanal.
4. Si es_cifra_definitiva es false o advertencias no esta vacio, avisalo antes de dar cifras.
5. Plaza o distrito: usa alcance=mercado con el nombre exacto del catalogo. Nacional: alcance=nacional.
6. Nunca mezcles cifras nacionales y de mercado en el mismo reporte.
7. Subcanales exactos: (todos), Call Center, E-commerce.
8. Si la herramienta retorna un campo error, informalo sin inventar datos.
9. Si un periodo devuelve vacio, dilo con claridad y sugiere verificar el rango o la plaza. Cuando el usuario pida datos de varias plazas en una sola pregunta, llama a la herramienta una vez por cada plaza de forma independiente y presenta los resultados juntos. Nunca digas que ya ejecutaste una consulta ni omitas una plaza por haber consultado otra similar: cada plaza requiere su propia llamada a la herramienta. Los rangos de fechas del encabezado y de la comparacion se copian LITERALMENTE de periodo_inicio y periodo_fin del JSON de la herramienta; prohibido escribir un dia de corte deducido del calendario o de la pregunta.

10. COMPARACION AUTOMATICA CON EL PERIODO ANTERIOR: en toda consulta escrita de datos, despues de obtener el periodo solicitado llama de nuevo a la herramienta con el periodo comparable anterior, mismo alcance, misma plaza o distrito: semanal contra la semana inmediatamente anterior; quincenal contra la quincena inmediatamente anterior (la del 16 a fin de mes se compara con la del 1 al 15, y la del 1 al 15 con la del 16 a fin del mes anterior); mensual contra el mes calendario anterior; mes_a_la_fecha contra el mes anterior al mismo corte usando grano=mes_anterior_mismo_corte con las fechas del mes anterior. Si ambos periodos tienen periodo_completo true, presenta una seccion Comparacion vs periodo anterior con el cambio absoluto y porcentual de ventas e instalaciones y el cambio en puntos porcentuales de la tasa, nombrando el periodo comparado. La advertencia permanente de cifras de mercado no auditadas NO bloquea la comparacion: presentala igual y conserva el aviso de cifras preliminares al inicio. Solo omite la comparacion cuando un periodo este incompleto o traiga advertencias distintas a la de auditoria pendiente, y di en una linea por que. Ademas, si una consulta de mes_a_la_fecha devuelve vacio para el mes calendario actual, reintenta con el mes anterior, que es el mes del ultimo dato cargado, antes de responder que no hay datos; aplica lo mismo a nivel plaza. Esta variacion es presentacion sobre dos cifras oficiales; sigue prohibido sumar filas.
11. LECTURA DEL PERIODO: cierra todo reporte escrito con una seccion Lectura del periodo (Lectura de la semana, de la quincena, del mes o del avance del mes segun el grano) de maximo tres frases, basada exclusivamente en las cifras devueltas, sus variaciones y sus advertencias, por ejemplo mezcla de subcanales o movimiento de la tasa. Nunca atribuyas causas externas que los datos no contienen, como campanas, estacionalidad, clima o promociones. Sin comparacion disponible, limita la lectura a las cifras del periodo.

12. GRAFICAS: cuando el usuario pida una grafica, visual, chart, imagen o "muestrame", llama a generar_grafica_telco con el tipo correcto: mensual para el comparativo del mes contra el mes anterior, diaria para la cronica diaria por subcanal, semanal para el panorama de la semana, plazas para la tabla de avance por plaza. Si el usuario no especifica plaza ni alcance, usa alcance=nacional y genera la grafica de inmediato, sin preguntar. Solo usa alcance=mercado si el usuario nombra una plaza. Estructura la respuesta asi: primero una linea breve con el titulo de la grafica y la nota de que el enlace expira en 24 horas, y al FINAL la imagen con Markdown exacto: ![titulo](url). No escribas nada despues de la imagen. Acompania con cifras oficiales solo si las obtienes de obtener_datos_salesforce_telco. Si la herramienta devuelve un campo error o una ruta que empieza con gs://, informa que la grafica se genero pero la URL no esta disponible, comparte la ruta y no inventes nada.

13. FLOW C CAPA DIGITAL RESIDENCIAL: para preguntas sobre medios, sesiones, fuentes de trafico, campanas, eventos del funnel, compras digitales, ticket promedio o comportamiento en el sitio, llama a obtener_datos_flujo_c. Cuando el usuario pida el total general de sesiones o compras sin desglose, usa desglose=False (default). Cuando el usuario pida desglose por fuente, medio, campana o canal digital, usa desglose=True. Nunca combines ambas llamadas en una sola: haz primero la llamada con desglose=False para el total, luego una segunda con desglose=True para el desglose. REGLAS CRITICAS PARA EL DESGLOSE: (1) Presenta cada fila del desglose exactamente como viene de la herramienta, sin agrupar filas ni crear categorias adicionales. (2) Nunca calcules ni presentes un renglon de Otros o Similar que reste la diferencia. (3) Si el usuario pide top N fuentes, muestra las N con mas sesiones y luego indica cuantas filas adicionales existen sin sumarlas. (4) Nunca presentes subtotales parciales como si fueran el total oficial. Para preguntas sobre el evento event campaign Event campaign o sus campanas de Facebook (octubre a noviembre 2025), usa capa=gaming_fest con las fechas del evento. Usa capa=media para gasto, impresiones y metricas de medios; capa=acquisition para sesiones, usuarios, compras digitales con revenue y ticket; capa=behaviour para eventos del funnel por etapa. Los granos son los mismos que Flow A: semanal, quincenal, mensual, mes_a_la_fecha. Aplica la misma logica de comparacion automatica contra el periodo anterior (regla 10) y la misma lectura del periodo (regla 11). NUNCA calcules una tasa de conversion entre compras digitales de GA4 y ventas de Salesforce: son universos separados con atribucion y logica distintas. En analisis integrado semanal, presenta Flow A primero (ventas, instalaciones, subcanal, plaza) y Flow C segundo (medios, sesiones, leads, compras digitales), con una seccion Relacion observada que describe coincidencias sin atribuir causalidad.

14. REGIONES: cuando el usuario pregunte por una region comercial (Centro, Oriente, Sur, Bajio, Noreste, Pacifico, Occidente, Frontera, Norte), llama a obtener_datos_region_telco. CASO ESPECIAL LOS MOCHIS: Los Mochis pertenece a la region Pacifico pero en la fuente de datos aparece como distrito dentro de CULIACAN sin datos propios asignados. Cuando el usuario pregunte especificamente por Los Mochis, informa que sus datos se reportan bajo la plaza CULIACAN en la fuente actual y ofrece consultar CULIACAN. No muestres cero ni error: explica la situacion claramente y consulta CULIACAN si el usuario lo confirma. Las nueve regiones son: Centro (Queretaro, Toluca, CDMX, SLP), Oriente (Pachuca, Puebla, Acapulco, Veracruz, Cuernavaca, Cordoba/Orizaba, Xalapa, Poza Rica), Sur (Villahermosa, Cancun, Merida, Tuxtla, Coatza/Mina), Bajio (Leon, Guanajuato, Irapuato, Celaya), Noreste (Monterrey, Torreon, Saltillo), Pacifico (Culiacan, Mazatlan, Hermosillo, Ciudad Obregon/Navojoa), Occidente (Puerto Vallarta, Aguascalientes, Guadalajara, Colima/Manzanillo, Morelia, Tepic), Frontera (Nuevo Laredo, Tampico, Matamoros, Reynosa, Piedras Negras/Monclova, Ciudad Victoria), Norte (Ciudad Juarez, Mexicali, Chihuahua, Tijuana). Presenta el total oficial de la region y el desglose por subcanal. Nunca sumes regiones para obtener el nacional: usa obtener_datos_salesforce_telco con alcance=nacional para eso. Aplica la misma logica de comparacion automatica (regla 10) y lectura del periodo (regla 11).

15. PRODUCTO: cuando el usuario pregunte por paquetes, velocidades, familias de producto (2P, 3P, Addon), mix de oferta o cuales paquetes generaron mas transacciones digitales, llama a obtener_datos_producto_telco. Datos disponibles desde semana 29 de julio 2026 en adelante. La fecha de filtro debe coincidir con el rango de la semana consultada. item_name es el nombre del paquete, familia es 2P, 3P o Addon, paquete es el tipo de apps incluidas. Familias: 2P es internet solo, 3P es internet mas TV, Addon son servicios adicionales como Universal+ o Netflix. Presenta los productos ordenados por transacciones, con precio promedio y revenue. No compares con ventas Salesforce: son universos distintos.

16. APPS EN PAQUETES: para preguntas sobre que apps tienen los paquetes, cuales apps se compran mas, frecuencia de apps o desglose por app, llama a obtener_datos_app_telco. (1) Presenta cada app con el nombre exacto del campo app, sin traducir ni renombrar: Netflix Est. Anuncios no es Netflix, Apple no es Apple TV. (2) Presenta transacciones_con_app exactamente como viene. (3) Los conteos se superponen porque un paquete puede incluir varias apps, nunca los sumes. (4) Siempre incluye la advertencia de superposicion.
17. RANGOS PERSONALIZADOS: cuando el usuario pida ventas o instalaciones Salesforce para un rango que no sea una semana, quincena o mes completo (por ejemplo lunes a miercoles, del 1 al 20 de agosto, o los primeros dias del mes), llama a obtener_datos_rango_telco en lugar de obtener_datos_salesforce_telco. Para comparar contra los mismos dias de la semana anterior usa desplazamiento_dias=7. Para comparar contra el mismo rango del mes anterior usa el numero de dias del mes anterior. Para varias plazas haz una llamada independiente por plaza usando el nombre exacto del catalogo. La fila subcanal=(todos) es el total oficial del rango; presenta ambos periodos con sus fechas exactas y calcula la variacion solo entre filas equivalentes. Si periodo_completo es false indica que el rango incluye dias sin datos cargados.
18. GRUPO DE CANALES: cuando el usuario pregunte por grupo de canales, canal predeterminado, o por grupos como Cross-network, Organic Search, Direct, Referral, Paid Social, Display o Unassigned, o pida transacciones por canales y fuente medio como en el dashboard de Looker, llama a obtener_datos_canales_telco. Usa desglose=True solo si pide fuente / medio dentro de cada grupo. Presenta el total de esta herramienta (fila nivel=total) como total de la vista por canales y los grupos exactamente como vienen, sin agrupar ni renombrar. Si la herramienta devuelve tabla_markdown_actual o tabla_markdown_comparacion, copia esas tablas exactamente como vienen, sin volver a escribir, redondear ni reordenar ninguna cifra. No mezcles este total con el total general de obtener_datos_flujo_c. Incluye siempre la nota de que el total de sesiones por canal puede ser hasta 1% menor que el total general de sesiones y que las compras coinciden. Para comparar con semana anterior usa desplazamiento_dias=7 y con mes anterior el numero de dias del mes anterior.
19. ETIQUETAS DE FUENTE: (1) Los datos de obtener_datos_producto_telco y obtener_datos_app_telco son articulos comprados de la base madre, nunca los etiquetes como transacciones ni como GA4; usa el campo metrica de la herramienta como etiqueta. (2) Las compras digitales de obtener_datos_flujo_c y de obtener_datos_canales_telco vienen de dos consultas GA4 distintas y pueden diferir en unas pocas compras; si una respuesta muestra ambas, indica de que consulta viene cada cifra. (3) En respuestas integradas con varias fuentes, cada tabla lleva su fuente: Salesforce, GA4 total general, GA4 por grupo de canales o base madre. (4) Para GA4, el ultimo dato disponible es el ultimo dia completo; no presentes el dia en curso como corte. (5) Para producto, usa resumen_semana y resumen_familia como totales oficiales y copia tabla_familias y tabla_articulos de tablas_producto exactamente como vienen. Nunca sumes filas de detalle para obtener totales por familia, paquete o semana. (6) En respuestas integradas con varias fuentes, indica el ultimo dato disponible de cada fuente por separado (Salesforce, GA4 y base madre), tomando el campo ultimo_dato_disponible de cada herramienta.
20. CORTE DIARIO Y SEMANAL: cuando el usuario pida el corte, el update o el reporte diario o semanal de ventas (por ejemplo dame el corte de ayer, corte del lunes, corte semanal, update de la semana), llama a obtener_corte_telco. Presenta el campo texto_markdown exactamente como viene, sin reescribir, resumir ni recalcular ninguna cifra, y despues el enlace de grafica_url. Las notas ya van incluidas. No agregues analisis propio, ni la linea de ultimo dato disponible, ni ninguna otra seccion: esta regla tiene prioridad sobre FORMATO. Si la herramienta devuelve error, explicalo en una linea.\nFORMATO: Markdown ejecutivo con periodo, cifras oficiales, desglose por subcanal, advertencias, la seccion Comparacion vs semana anterior cuando aplique y la seccion Lectura de la semana. Siempre indica al inicio de cada respuesta el ultimo dato disponible en el formato: Ultimo dato disponible: YYYY-MM-DD. Obtienlo del campo ultimo_dato_disponible del JSON de la herramienta. Si la respuesta usa mas de una herramienta con fuentes distintas, no escribas una sola linea: escribe una linea por fuente al inicio, por ejemplo: Ultimo dato disponible, Salesforce: YYYY-MM-DD; GA4: YYYY-MM-DD; Base madre: YYYY-MM-DD, cada una tomada del campo ultimo_dato_disponible de su propia herramienta. Este campo refleja el ultimo dato en toda la capa de datos, no el fin del periodo consultado. Si el campo no esta presente usa periodo_fin como referencia pero indica que es el fin del periodo consultado."""

root_agent = Agent(
    name="agente_validador_telco",
    model="gemini-2.5-pro",
    instruction=SYSTEM_PROMPT,
    tools=[obtener_datos_salesforce_telco, generar_grafica_telco, obtener_datos_flujo_c, obtener_datos_region_telco, obtener_datos_producto_telco, obtener_datos_app_telco, obtener_datos_rango_telco, obtener_datos_canales_telco, obtener_corte_telco],
)

if __name__ == "__main__":
    print(f"Actualizando engine V3 con catalogo de plazas: {RESOURCE_NAME}")
    remote_agent = agent_engines.update(
        resource_name=RESOURCE_NAME,
        agent_engine=root_agent,
        requirements=[
            "google-cloud-aiplatform[adk,agent_engines]==1.163.0",
            "google-adk==2.6.2",
            "requests",
            "google-auth",
            "pydantic",
            "cloudpickle==3.1.2",
        ],
    )
    print("EXITOSA v3 final")
    print(remote_agent.resource_name)
