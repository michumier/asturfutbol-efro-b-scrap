import json
import logging
from datetime import datetime
from pathlib import Path
from src.config import ESTADO_FILE

logger = logging.getLogger(__name__)


def load_state(filepath: Path = ESTADO_FILE) -> dict:
    """Carga el estado previo desde el archivo JSON."""
    if not filepath.exists():
        return {"actas": {}, "avisos_previos": {}}
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        if "actas" not in data:
            # Compatibilidad si venía en formato simple {acta: marcador}
            data = {"actas": {k: {"marcador": v, "estado": "cerrada"} for k, v in data.items()}, "avisos_previos": {}}
        if "avisos_previos" not in data:
            data["avisos_previos"] = {}
        return data
    except Exception as e:
        logger.error(f"Error al leer archivo de estado {filepath}: {e}")
        return {"actas": {}, "avisos_previos": {}}


def save_state(state: dict, filepath: Path = ESTADO_FILE) -> None:
    """Guarda el estado actual en el archivo JSON con formato indentado."""
    try:
        filepath.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Error al guardar estado en {filepath}: {e}")


def debe_notificar_resultado(state: dict, cod_acta: str, marcador: str, estado: str) -> bool:
    """
    Determina si un marcador o cambio de estado requiere emitir una nueva notificación:
    - Partido nuevo con marcador.
    - Marcador que ha cambiado (ej. corrección o gol en vivo).
    - Cambio de estado provisional a definitivo (cerrada).
    """
    if not marcador:
        return False

    previo = state.get("actas", {}).get(str(cod_acta))
    if not previo:
        return True

    marcador_anterior = previo.get("marcador")
    estado_anterior = previo.get("estado")

    if marcador_anterior != marcador:
        return True

    # Notificar si antes era provisional o en_juego y ahora pasa a cerrada (definitivo)
    if estado_anterior in {"provisional", "en_juego"} and estado == "cerrada":
        return True

    return False


def registrar_notificacion(state: dict, cod_acta: str, marcador: str, estado: str) -> None:
    """Actualiza el estado con el último marcador y estado notificado."""
    if "actas" not in state:
        state["actas"] = {}
    state["actas"][str(cod_acta)] = {
        "marcador": marcador,
        "estado": estado,
        "updated_at": datetime.now().isoformat(),
    }


def debe_notificar_aviso_previo(state: dict, cod_acta: str) -> bool:
    """Indica si aún no se ha enviado el aviso previo de horario/campo para este acta."""
    return str(cod_acta) not in state.get("avisos_previos", {})


def registrar_aviso_previo(state: dict, cod_acta: str) -> None:
    """Registra que el aviso previo de este acta ya fue enviado."""
    if "avisos_previos" not in state:
        state["avisos_previos"] = {}
    state["avisos_previos"][str(cod_acta)] = datetime.now().isoformat()
