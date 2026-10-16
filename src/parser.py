import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from src.decoder import extract_d_table, decode_marcador


def parse_jornadas_disponibles(soup: BeautifulSoup) -> list[dict]:
    """Extrae la lista de jornadas y sus fechas del selector <select id='jornada'>."""
    jornadas = []
    select = (
        soup.select_one("select#jornada")
        or soup.select_one('select[name="CodJornada"]')
        or soup.select_one('select[name="jornada"]')
    )
    if not select:
        return jornadas

    for opt in select.select("option"):
        text = opt.get_text(strip=True)
        # Formato habitual: "3 - 17-10-2026"
        m = re.match(r"^\s*(\d+)\s*-\s*(\d{2}-\d{2}-\d{4})", text)
        if m:
            num = int(m.group(1))
            fecha_str = m.group(2)
            try:
                f_dt = datetime.strptime(fecha_str, "%d-%m-%Y")
            except ValueError:
                f_dt = None
            jornadas.append({
                "jornada": num,
                "fecha": fecha_str,
                "fecha_dt": f_dt,
            })
    return jornadas


def seleccionar_jornada_actual(
    jornadas: list[dict],
    fecha_ref: datetime = None,
    dias_adelanto: int = 3,
    dias_atras: int = 1,
) -> int | None:
    """
    Determina la jornada a consultar según la fecha de referencia (por defecto hoy).
    Busca una jornada cuya fecha esté entre fecha_ref - 1 día y fecha_ref + 3 días.
    Si no encuentra ninguna en ventana, escoge la más cercana en el tiempo.
    """
    if not jornadas:
        return None

    if fecha_ref is None:
        fecha_ref = datetime.now()

    # 1. Ventana inmediata de fin de semana
    for j in jornadas:
        f_dt = j["fecha_dt"]
        if f_dt and (f_dt - timedelta(days=dias_atras) <= fecha_ref <= f_dt + timedelta(days=dias_adelanto)):
            return j["jornada"]

    # 2. Si no coincide, buscar la de menor diferencia temporal
    con_fecha = [j for j in jornadas if j["fecha_dt"]]
    if con_fecha:
        mas_cercana = min(con_fecha, key=lambda x: abs(x["fecha_dt"] - fecha_ref))
        return mas_cercana["jornada"]

    return jornadas[0]["jornada"]


def parse_partidos(soup: BeautifulSoup) -> list[dict]:
    """
    Parsea todos los partidos de una jornada a partir del HTML de NFG_CmpJornada.
    Descarta equipos que descansan y decodifica marcadores y estados.
    """
    d_table = extract_d_table(soup)
    partidos = []

    for t in soup.select('table[width="100%"]'):
        acta_tag = t.select_one('a[href*="CodActa="]')
        if not acta_tag:
            continue

        acta_m = re.search(r"CodActa=(\d+)", acta_tag["href"])
        if not acta_m:
            continue
        cod_acta = acta_m.group(1)

        enlaces_equipos = t.select('a[href*="Codigo_Equipo="]')
        if len(enlaces_equipos) < 2:
            continue

        ids = []
        nombres = []
        for a in enlaces_equipos:
            m_id = re.search(r"Codigo_Equipo=(\d+)", a["href"])
            if m_id:
                ids.append(m_id.group(1))
                nombres.append(a.get_text(" ", strip=True))

        if len(ids) < 2:
            continue

        local_nombre = nombres[0]
        visitante_nombre = nombres[-1]
        local_id = ids[0]
        visitante_id = ids[-1]

        # Estado del partido según clases CSS
        classes_str = " ".join(t.get("class", []))
        # También buscar en hijos
        for el in t.find_all(class_=True):
            classes_str += " " + " ".join(el.get("class", []))

        if "wid2_resultado_cerrada" in classes_str or "cubo_cerrada" in classes_str:
            estado = "cerrada"
        elif "wid2_resultado_prov" in classes_str or "cubo_provisional" in classes_str:
            estado = "provisional"
        elif "wid2_resultado_enjuego" in classes_str or "cubo_noacaba" in classes_str:
            estado = "en_juego"
        else:
            estado = "sin_jugar"

        # Marcador
        marcador_el = t.select_one("td[align=center] h4 strong") or t.select_one("td[align=center] h4")
        marcador = decode_marcador(marcador_el, d_table) if estado != "sin_jugar" else ""

        # Horario
        horarios = [h.get_text(strip=True) for h in t.select(".horario")]
        fecha_partido = " ".join(horarios)

        # Campo
        campo_tag = t.select_one('a[href*="Codigo_Campo="]')
        campo_nombre = campo_tag.get_text(" ", strip=True) if campo_tag else ""

        # Árbitro
        arbitro = ""
        full_text = t.get_text(" ", strip=True)
        m_arb = re.search(r"[ÁA]rbitro:\s*([^<\n\r]+)", full_text, re.IGNORECASE)
        if m_arb:
            arbitro = m_arb.group(1).split("  ")[0].strip()

        partidos.append({
            "acta": cod_acta,
            "local": local_nombre,
            "local_id": local_id,
            "visitante": visitante_nombre,
            "visitante_id": visitante_id,
            "ids": [local_id, visitante_id],
            "marcador": marcador,
            "estado": estado,
            "fecha": fecha_partido,
            "campo": campo_nombre,
            "arbitro": arbitro,
        })

    return partidos


def parse_clasificacion(soup: BeautifulSoup, cod_equipo: str = "5400") -> dict | None:
    """
    Extrae los datos de clasificación del equipo especificado (posicion, puntos, pj, pg, pe, pp, gf, gc).
    """
    for tr in soup.select("table tr"):
        link = tr.select_one(f'a[href*="codequipo={cod_equipo}"], a[href*="Codigo_Equipo={cod_equipo}"]')
        if not link:
            continue

        tds = tr.select("td")
        cleaned_cells = [td.get_text(strip=True) for td in tds]

        # Verificar si es la tabla completa detallada (15 o 16 columnas)
        if len(cleaned_cells) >= 14:
            try:
                posicion = int(cleaned_cells[1])
                nombre = link.get_text(" ", strip=True)
                puntos = int(cleaned_cells[3])
                # Casa
                pj_casa = int(cleaned_cells[4])
                pg_casa = int(cleaned_cells[5])
                pe_casa = int(cleaned_cells[6])
                pp_casa = int(cleaned_cells[7])
                # Fuera
                pj_fuera = int(cleaned_cells[8])
                pg_fuera = int(cleaned_cells[9])
                pe_fuera = int(cleaned_cells[10])
                pp_fuera = int(cleaned_cells[11])
                # Goles
                gf = int(cleaned_cells[12])
                gc = int(cleaned_cells[13])

                return {
                    "posicion": posicion,
                    "equipo": nombre,
                    "puntos": puntos,
                    "pj": pj_casa + pj_fuera,
                    "pg": pg_casa + pg_fuera,
                    "pe": pe_casa + pe_fuera,
                    "pp": pp_casa + pp_fuera,
                    "gf": gf,
                    "gc": gc,
                }
            except (ValueError, IndexError):
                pass

        # Fallback para tabla simplificada (ej. vista móvil con 9 o 10 columnas)
        if len(cleaned_cells) >= 8:
            try:
                posicion = int(cleaned_cells[1])
                nombre = link.get_text(" ", strip=True)
                puntos = int(cleaned_cells[3])
                pj = int(cleaned_cells[4])
                pg = int(cleaned_cells[5])
                pe = int(cleaned_cells[6])
                pp = int(cleaned_cells[7])
                return {
                    "posicion": posicion,
                    "equipo": nombre,
                    "puntos": puntos,
                    "pj": pj,
                    "pg": pg,
                    "pe": pe,
                    "pp": pp,
                    "gf": 0,
                    "gc": 0,
                }
            except (ValueError, IndexError):
                pass

    return None
