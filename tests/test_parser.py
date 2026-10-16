from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from src.parser import (
    parse_jornadas_disponibles,
    seleccionar_jornada_actual,
    parse_partidos,
    parse_clasificacion,
    parse_clasificacion_completa,
    parse_goles_acta,
    marcador_real_desde_goles,
    parse_tabla_goleadores,
    normalizar_nombre,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_jornadas_disponibles():
    html = (FIXTURES_DIR / "jornada_3_sin_jugar.html").read_text(encoding="iso-8859-15")
    soup = BeautifulSoup(html, "html.parser")
    jornadas = parse_jornadas_disponibles(soup)
    assert len(jornadas) >= 20
    assert jornadas[0]["jornada"] == 1
    assert jornadas[0]["fecha"] == "03-10-2026"
    assert jornadas[2]["jornada"] == 3
    assert jornadas[2]["fecha"] == "17-10-2026"


def test_seleccionar_jornada_actual():
    jornadas = [
        {"jornada": 1, "fecha": "03-10-2026", "fecha_dt": datetime(2026, 10, 3)},
        {"jornada": 2, "fecha": "10-10-2026", "fecha_dt": datetime(2026, 10, 10)},
        {"jornada": 3, "fecha": "17-10-2026", "fecha_dt": datetime(2026, 10, 17)},
    ]
    # Sábado 10 de octubre
    assert seleccionar_jornada_actual(jornadas, fecha_ref=datetime(2026, 10, 10, 12, 0)) == 2
    # Viernes 16 de octubre (víspera de jornada 3)
    assert seleccionar_jornada_actual(jornadas, fecha_ref=datetime(2026, 10, 16, 9, 0)) == 3
    # Lunes 19 de octubre (2 días después de jornada 3)
    assert seleccionar_jornada_actual(jornadas, fecha_ref=datetime(2026, 10, 19, 10, 0)) == 3


def test_parse_partidos_jornada_2_jugada():
    html = (FIXTURES_DIR / "jornada_2_jugada.html").read_text(encoding="iso-8859-15")
    soup = BeautifulSoup(html, "html.parser")
    partidos = parse_partidos(soup)
    
    # 7 partidos disputados en esa jornada
    assert len(partidos) >= 7

    efro_partido = next((p for p in partidos if "5400" in p["ids"]), None)
    assert efro_partido is not None
    assert efro_partido["acta"] == "25767758"
    assert efro_partido["local"] == 'Efro "B"'
    assert efro_partido["local_id"] == "5400"
    assert efro_partido["marcador"] == "7 - 2"
    assert efro_partido["estado"] == "cerrada"
    assert "FUNDOMA" in efro_partido["campo"]
    assert efro_partido["arbitro"] != ""


def test_parse_partidos_jornada_3_sin_jugar():
    html = (FIXTURES_DIR / "jornada_3_sin_jugar.html").read_text(encoding="iso-8859-15")
    soup = BeautifulSoup(html, "html.parser")
    partidos = parse_partidos(soup)

    efro_partido = next((p for p in partidos if "5400" in p["ids"]), None)
    assert efro_partido is not None
    assert efro_partido["acta"] == "25767765"
    assert efro_partido["visitante"] == 'Efro "B"'
    assert efro_partido["visitante_id"] == "5400"
    assert efro_partido["marcador"] == ""
    assert efro_partido["estado"] == "sin_jugar"
    assert "LA CARISA" in efro_partido["campo"]


def test_parse_clasificacion():
    html = (FIXTURES_DIR / "clasificacion_2.html").read_text(encoding="iso-8859-15")
    soup = BeautifulSoup(html, "html.parser")
    clasif = parse_clasificacion(soup, cod_equipo="5400")

    assert clasif is not None
    assert clasif["posicion"] == 5
    assert clasif["puntos"] == 3
    assert clasif["pj"] == 1
    assert clasif["pg"] == 1
    assert clasif["pe"] == 0
    assert clasif["pp"] == 0
    assert clasif["gf"] == 7
    assert clasif["gc"] == 2


def test_normalizar_nombre():
    assert normalizar_nombre('Efro "B"') == normalizar_nombre("Efro B")
    assert normalizar_nombre('C.D. Vallobin "B"') == normalizar_nombre("C.D. Vallobin B")
    assert normalizar_nombre("") == ""


def test_parse_clasificacion_completa():
    html = (FIXTURES_DIR / "clasificacion_2.html").read_text(encoding="iso-8859-15")
    soup = BeautifulSoup(html, "html.parser")
    equipos = parse_clasificacion_completa(soup)

    assert len(equipos) == 15
    assert equipos[0]["posicion"] == 1
    assert equipos == sorted(equipos, key=lambda e: e["posicion"])

    efro = next(e for e in equipos if normalizar_nombre(e["equipo"]) == normalizar_nombre('Efro "B"'))
    assert efro["posicion"] == 5
    assert efro["puntos"] == 3
    assert efro["pj"] == 1
    assert efro["gf"] == 7
    assert efro["gc"] == 2
    assert efro["dif"] == 5


def test_parse_goles_acta():
    raw = (FIXTURES_DIR / "acta_j2.html").read_bytes().decode("utf-8", "replace")
    soup = BeautifulSoup(raw, "html.parser")
    goles = parse_goles_acta(soup)

    # El acta de fútbol base limita el marcador a 7-2, pero hay 13 goles reales
    assert len(goles) == 13
    assert marcador_real_desde_goles(goles) == "11 - 2"

    # Atribución local/visitante coherente y cronológica
    assert [g["minuto"] for g in goles] == sorted(g["minuto"] for g in goles)
    assert goles[0]["jugador"] == "SÁNCHEZ SUÁREZ, NICOLÁS"
    assert goles[0]["equipo"] == "local"
    assert goles[0]["marcador"] == "1 - 0"

    locales = [g for g in goles if g["equipo"] == "local"]
    visitantes = [g for g in goles if g["equipo"] == "visitante"]
    assert len(locales) == 11
    assert len(visitantes) == 2

    # Goles en propia puerta detectados
    pps = [g for g in goles if g["tipo"] == "pp"]
    assert len(pps) == 2
    # El autor de una p.p. pertenece al equipo contrario al que se le acredita el gol
    for pp in pps:
        assert pp["equipo_autor"] != pp["equipo"]


def test_parse_tabla_goleadores_filtra_equipo():
    raw = (FIXTURES_DIR / "goleadores_j2.html").read_bytes().decode("utf-8", "replace")
    soup = BeautifulSoup(raw, "html.parser")
    goleadores = parse_tabla_goleadores(soup, nombre_equipo='Efro "B"')

    assert len(goleadores) == 6
    # Ordenados de más a menos goles
    assert goleadores == sorted(goleadores, key=lambda g: (-g["goles"], g["jugador"]))
    assert all(g["goles"] >= 1 for g in goleadores)

    bello = next(g for g in goleadores if g["jugador"] == "BELLO FERNANDES, ADRIÁN")
    assert bello["goles"] == 3


def test_parse_tabla_goleadores_sin_filtro():
    raw = (FIXTURES_DIR / "goleadores_j2.html").read_bytes().decode("utf-8", "replace")
    soup = BeautifulSoup(raw, "html.parser")
    goleadores = parse_tabla_goleadores(soup)
    assert len(goleadores) > 6
