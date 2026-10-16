import re
import unicodedata
from datetime import datetime, timedelta
from bs4 import BeautifulSoup, NavigableString, Tag
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

        # Escudos
        escudo_local = ""
        escudo_visitante = ""
        img_loc = t.select_one(".escudo_widgetL img") or t.select_one(".escudo_widget img")
        img_vis = t.select_one(".escudo_widgetV img") or t.select_one(".escudo_widget2 img")
        if img_loc and img_loc.get("src"):
            escudo_local = img_loc["src"]
        if img_vis and img_vis.get("src"):
            escudo_visitante = img_vis["src"]

        partidos.append({
            "acta": cod_acta,
            "local": local_nombre,
            "local_id": local_id,
            "escudo_local": escudo_local,
            "visitante": visitante_nombre,
            "visitante_id": visitante_id,
            "escudo_visitante": escudo_visitante,
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


def normalizar_nombre(nombre: str) -> str:
    """
    Normaliza el nombre de un equipo para poder compararlo entre páginas distintas:
    elimina comillas, tildes, puntos y colapsa espacios (ej. 'Efro "B"' -> 'efro b').
    """
    if not nombre:
        return ""
    base = unicodedata.normalize("NFKD", nombre)
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    base = re.sub(r"[^a-z0-9]+", " ", base)
    return re.sub(r"\s+", " ", base).strip()


def parse_clasificacion_completa(soup: BeautifulSoup) -> list[dict]:
    """
    Extrae la tabla de clasificación completa con todos los equipos del grupo.
    Soporta el formato detallado (16 columnas: casa/fuera) y el simplificado.
    Devuelve los equipos ordenados por posición.
    """
    equipos = []
    vistos = set()

    for tr in soup.select("table tr"):
        link = tr.select_one('a[href*="codequipo="], a[href*="Codigo_Equipo="]')
        if not link:
            continue

        cleaned = [td.get_text(strip=True) for td in tr.select("td")]
        nombre = link.get_text(" ", strip=True)
        clave = (nombre, cleaned[1] if len(cleaned) > 1 else "")
        if clave in vistos:
            continue

        fila = None
        # Formato detallado (casa + fuera): pos, nombre, pts, pj_c, pg_c, pe_c, pp_c, pj_f, pg_f, pe_f, pp_f, gf, gc
        if len(cleaned) >= 14:
            try:
                fila = {
                    "posicion": int(cleaned[1]),
                    "equipo": nombre,
                    "puntos": int(cleaned[3]),
                    "pj": int(cleaned[4]) + int(cleaned[8]),
                    "pg": int(cleaned[5]) + int(cleaned[9]),
                    "pe": int(cleaned[6]) + int(cleaned[10]),
                    "pp": int(cleaned[7]) + int(cleaned[11]),
                    "gf": int(cleaned[12]),
                    "gc": int(cleaned[13]),
                }
            except (ValueError, IndexError):
                fila = None

        # Formato simplificado: pos, nombre, pts, pj, pg, pe, pp
        if fila is None and len(cleaned) >= 8:
            try:
                fila = {
                    "posicion": int(cleaned[1]),
                    "equipo": nombre,
                    "puntos": int(cleaned[3]),
                    "pj": int(cleaned[4]),
                    "pg": int(cleaned[5]),
                    "pe": int(cleaned[6]),
                    "pp": int(cleaned[7]),
                    "gf": 0,
                    "gc": 0,
                }
            except (ValueError, IndexError):
                fila = None

        if fila is None:
            continue

        fila["dif"] = fila["gf"] - fila["gc"]
        equipos.append(fila)
        vistos.add(clave)

    equipos.sort(key=lambda x: x["posicion"])
    return equipos


def _mapa_digitos(root, d_table: list[int]) -> tuple[dict, set]:
    """
    Construye el mapa id->dígito a partir de las ofuscaciones ntype() y reglas CSS,
    y el conjunto de ids cuyo contenido está oculto (honeypots).
    """
    mapa = {}
    ocultos = set()

    for script in root.find_all("script"):
        texto = script.string or ""
        m = re.search(r'ntype\(\s*["\']([\w]+)["\']\s*,\s*(\d+)\s*,\s*(\d+)', texto)
        if m:
            idx = int(m.group(3)) * 10 + int(m.group(2))
            if 0 <= idx < len(d_table):
                mapa[m.group(1)] = str(d_table[idx])

    for style in root.find_all("style"):
        texto = style.string or ""
        m = re.search(r"#([\w]+):(?:before|after)\s*\{([^}]*)\}", texto)
        if not m:
            continue
        sid, regla = m.group(1), m.group(2)
        m_content = re.search(r'content:\s*["\'](.*?)["\']', regla)
        if not m_content:
            continue
        valor = m_content.group(1)
        if valor.startswith("\\"):
            try:
                valor = chr(int(valor.lstrip("\\0"), 16))
            except ValueError:
                valor = ""
        if "display:none" in regla.replace(" ", "").lower():
            ocultos.add(sid)
        elif valor.isdigit():
            mapa[sid] = valor

    return mapa, ocultos


def _decodificar_numero(elemento, d_table: list[int]) -> str:
    """
    Reconstruye el número (de uno o varios dígitos) de un fragmento de marcador,
    descartando los dígitos trampa ocultos mediante display:none.
    """
    fragmento = BeautifulSoup(str(elemento), "html.parser")
    mapa, ocultos = _mapa_digitos(fragmento, d_table)

    for tag in fragmento.find_all(["script", "style"]):
        tag.decompose()
    for tag in fragmento.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()

    digitos = []
    for node in fragmento.descendants:
        if isinstance(node, Tag):
            nid = node.get("id")
            if nid and nid in mapa and nid not in ocultos:
                digitos.append(mapa[nid])
        elif isinstance(node, NavigableString):
            texto = str(node).strip()
            if texto.isdigit():
                digitos.append(texto)

    return "".join(digitos)


def parse_goles_acta(soup_acta: BeautifulSoup) -> list[dict]:
    """
    Extrae la lista REAL de goles de un acta oficial (NFG_CmpPartido).

    En fútbol base el marcador visible del acta está limitado a 5 goles de diferencia,
    pero el listado de goles contiene todos los tantos. Este parser reconstruye el
    resultado real y atribuye cada gol a su equipo (local/visitante) comparando el
    marcador corrido que acompaña a cada gol.

    Devuelve una lista ordenada cronológicamente:
    [{ "minuto": int, "jugador": str, "tipo": "gol"|"pp",
       "equipo": "local"|"visitante", "equipo_autor": "local"|"visitante",
       "marcador": "X - Y" }]
    """
    goles = []
    if soup_acta is None:
        return goles

    d_table = extract_d_table(soup_acta)
    prev_local, prev_visit = 0, 0

    for tr in soup_acta.select("tr"):
        icono = tr.select_one("a.lgol, a.lgolpp")
        minuto_el = tr.select_one("span.font-blue")
        if not icono or not minuto_el:
            continue

        m_min = re.search(r"\((\d+)'\)", minuto_el.get_text(strip=True))
        if not m_min:
            continue

        td_autor = minuto_el.find_parent("td")
        jugador = ""
        if td_autor:
            jugador = re.sub(r"\(\d+'\)", "", td_autor.get_text(" ", strip=True)).strip()

        tipo = "pp" if "lgolpp" in (icono.get("class") or []) else "gol"

        # Marcador corrido: dos <i class="fa-solid"> (excluyendo el icono del balón)
        marcador_local = marcador_visit = None
        td_marcador = icono.find_parent("td")
        if td_marcador:
            partes = [
                i for i in td_marcador.select("i.fa-solid")
                if "fa-futbol" not in (i.get("class") or [])
            ]
            if len(partes) >= 2:
                l_str = _decodificar_numero(partes[0], d_table)
                v_str = _decodificar_numero(partes[1], d_table)
                if l_str.isdigit() and v_str.isdigit():
                    marcador_local, marcador_visit = int(l_str), int(v_str)

        equipo = ""
        marcador_txt = ""
        if marcador_local is not None and marcador_visit is not None:
            marcador_txt = f"{marcador_local} - {marcador_visit}"
            if marcador_local == prev_local + 1 and marcador_visit == prev_visit:
                equipo = "local"
            elif marcador_visit == prev_visit + 1 and marcador_local == prev_local:
                equipo = "visitante"
            if marcador_local >= prev_local and marcador_visit >= prev_visit:
                prev_local, prev_visit = marcador_local, marcador_visit

        # Equipo al que pertenece el autor (en propia puerta es el contrario)
        equipo_autor = equipo
        if tipo == "pp" and equipo:
            equipo_autor = "visitante" if equipo == "local" else "local"

        goles.append({
            "minuto": int(m_min.group(1)),
            "jugador": jugador,
            "tipo": tipo,
            "equipo": equipo,
            "equipo_autor": equipo_autor,
            "marcador": marcador_txt,
        })

    return goles


def marcador_real_desde_goles(goles: list[dict]) -> str:
    """Devuelve el marcador real 'L - V' reconstruido a partir del último gol conocido."""
    for gol in reversed(goles or []):
        if gol.get("marcador"):
            return gol["marcador"]
    return ""


def parse_tabla_goleadores(
    soup_goleadores: BeautifulSoup,
    nombre_equipo: str = None,
) -> list[dict]:
    """
    Extrae la tabla de máximos goleadores del grupo (NFG_CMP_Goleadores).
    Si se indica `nombre_equipo`, filtra solo los jugadores de ese equipo
    (comparación normalizada, ej. 'Efro "B"' == 'Efro B').
    """
    goleadores = []
    if soup_goleadores is None:
        return goleadores

    objetivo = normalizar_nombre(nombre_equipo) if nombre_equipo else None

    for tr in soup_goleadores.select("table tr"):
        tds = tr.select("td")
        if len(tds) < 5:
            continue
        jugador = tds[0].get_text(" ", strip=True)
        equipo = tds[1].get_text(" ", strip=True)
        if not jugador or not equipo:
            continue
        try:
            pj = int(tds[3].get_text(strip=True))
            goles = int(tds[4].get_text(strip=True))
        except (ValueError, IndexError):
            continue

        if objetivo and normalizar_nombre(equipo) != objetivo:
            continue

        goleadores.append({
            "jugador": jugador,
            "equipo": equipo,
            "pj": pj,
            "goles": goles,
        })

    goleadores.sort(key=lambda x: (-x["goles"], x["jugador"]))
    return goleadores
