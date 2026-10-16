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


def test_notificar_cambio_marcador():
    state = {
        "actas": {
            "1001": {"marcador": "2 - 1", "estado": "provisional"}
        }
    }
    # Ha subido a 3 - 1
    assert debe_notificar_resultado(state, "1001", "3 - 1", "provisional") is True


def test_notificar_cambio_de_provisional_a_cerrada():
    state = {
        "actas": {
            "1001": {"marcador": "3 - 1", "estado": "provisional"}
        }
    }
    # Marcador igual pero ahora es definitivo
    assert debe_notificar_resultado(state, "1001", "3 - 1", "cerrada") is True


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
