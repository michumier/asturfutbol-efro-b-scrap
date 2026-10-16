from src.validator import (
    validate_marcador,
    validate_partido,
    validate_clasificacion,
)


def test_validate_marcador():
    assert validate_marcador("7 - 2") is True
    assert validate_marcador("0 - 0") is True
    assert validate_marcador("10 - 1") is True
    assert validate_marcador("") is False
    assert validate_marcador("7-2") is True
    assert validate_marcador("abc") is False
    assert validate_marcador("7 - ") is False


def test_validate_partido():
    valido = {
        "acta": "25767758",
        "local": 'Efro "B"',
        "local_id": "5400",
        "visitante": 'C.D. San Ignacio Oviedo "C"',
        "visitante_id": "5483",
        "ids": ["5400", "5483"],
        "marcador": "7 - 2",
        "estado": "cerrada",
    }
    ok, err = validate_partido(valido)
    assert ok is True
    assert err == "OK"

    # Partido sin jugar
    sin_jugar = {
        "acta": "25767765",
        "local": 'La Corredoria "A"',
        "local_id": "3468",
        "visitante": 'Efro "B"',
        "visitante_id": "5400",
        "ids": ["3468", "5400"],
        "marcador": "",
        "estado": "sin_jugar",
    }
    ok, err = validate_partido(sin_jugar)
    assert ok is True

    # Error: falta acta
    invalido = dict(valido, acta="")
    ok, err = validate_partido(invalido)
    assert ok is False

    # Error: marcador malformado
    invalido_m = dict(valido, marcador="7 a 2")
    ok, err = validate_partido(invalido_m)
    assert ok is False


def test_validate_clasificacion():
    clasif_ok = {
        "posicion": 5,
        "equipo": 'Efro "B"',
        "puntos": 3,
        "pj": 1,
        "pg": 1,
        "pe": 0,
        "pp": 0,
        "gf": 7,
        "gc": 2,
    }
    ok, err = validate_clasificacion(clasif_ok)
    assert ok is True

    # Incoherencia: PJ != PG + PE + PP
    incoherente = dict(clasif_ok, pj=2)
    ok, err = validate_clasificacion(incoherente)
    assert ok is False
    assert "Incoherencia" in err

    # Posición inválida
    pos_invalida = dict(clasif_ok, posicion=0)
    ok, err = validate_clasificacion(pos_invalida)
    assert ok is False
