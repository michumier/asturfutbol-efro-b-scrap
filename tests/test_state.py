from src.state import (
    load_state,
    save_state,
    debe_notificar_resultado,
    registrar_notificacion,
    debe_notificar_aviso_previo,
    registrar_aviso_previo,
)


def test_debe_notificar_nuevo_resultado():
    state = {"actas": {}, "avisos_previos": {}}
    assert debe_notificar_resultado(state, "1001", "3 - 1", "provisional") is True


def test_no_notificar_resultado_repetido():
    state = {
        "actas": {
            "1001": {"marcador": "3 - 1", "estado": "cerrada"}
        }
    }
    assert debe_notificar_resultado(state, "1001", "3 - 1", "cerrada") is False


def test_no_notificar_cambios_de_marcador_provisional():
    state = {
        "actas": {
            "1001": {"marcador": "1 - 0", "estado": "provisional"}
        }
    }
    # Ya avisamos del provisional: los cambios de marcador no generan más correos
    assert debe_notificar_resultado(state, "1001", "2 - 0", "provisional") is False
    assert debe_notificar_resultado(state, "1001", "2 - 1", "provisional") is False
    assert debe_notificar_resultado(state, "1001", "3 - 1", "en_juego") is False


def test_notificar_cambio_de_provisional_a_cerrada():
    state = {
        "actas": {
            "1001": {"marcador": "3 - 1", "estado": "provisional"}
        }
    }
    # Marcador igual pero ahora es definitivo
    assert debe_notificar_resultado(state, "1001", "3 - 1", "cerrada") is True


def test_no_notificar_cerrada_repetida():
    state = {
        "actas": {
            "1001": {"marcador": "5 - 0", "estado": "cerrada"}
        }
    }
    assert debe_notificar_resultado(state, "1001", "5 - 0", "cerrada") is False
    # Aunque cambie el marcador corregido, ya no se vuelve a avisar
    assert debe_notificar_resultado(state, "1001", "6 - 0", "cerrada") is False


def test_solo_dos_avisos_en_toda_la_jornada():
    """Simula la secuencia real de ayer: 1-0 -> 2-0 -> 1-0 -> cerrada 5-0."""
    state = {"actas": {}, "avisos_previos": {}}
    avisos = 0

    secuencia = [
        ("1 - 0", "provisional"),
        ("2 - 0", "provisional"),
        ("1 - 0", "provisional"),
        ("5 - 0", "cerrada"),
    ]
    for marcador, estado in secuencia:
        if debe_notificar_resultado(state, "1001", marcador, estado):
            avisos += 1
            registrar_notificacion(state, "1001", marcador, estado)

    assert avisos == 2  # 1 provisional + 1 definitivo
    assert state["actas"]["1001"]["estado"] == "cerrada"


def test_aviso_previo_state():
    state = {"actas": {}, "avisos_previos": {}}
    assert debe_notificar_aviso_previo(state, "2001") is True

    registrar_aviso_previo(state, "2001")
    assert debe_notificar_aviso_previo(state, "2001") is False


def test_save_and_load_state(tmp_path):
    f = tmp_path / "estado.json"
    state = {"actas": {}, "avisos_previos": {}}
    registrar_notificacion(state, "555", "4 - 2", "cerrada")
    registrar_aviso_previo(state, "555")
    save_state(state, f)

    loaded = load_state(f)
    assert "555" in loaded["actas"]
    assert loaded["actas"]["555"]["marcador"] == "4 - 2"
    assert "555" in loaded["avisos_previos"]
