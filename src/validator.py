import re
import logging

logger = logging.getLogger(__name__)


def validate_marcador(marcador: str) -> bool:
    """Valida que el marcador tenga el formato numérico esperado 'X - Y'."""
    if not marcador or not isinstance(marcador, str):
        return False
    return bool(re.match(r"^\d+\s*-\s*\d+$", marcador.strip()))


def validate_partido(partido: dict) -> tuple[bool, str]:
    """
    Valida la integridad de los datos de un partido.
    Retorna (es_valido, motivo_error).
    """
    if not isinstance(partido, dict):
        return False, "El objeto partido no es un diccionario"

    acta = partido.get("acta")
    if not acta or not str(acta).isdigit():
        return False, f"CodActa inválido o ausente: {acta}"

    local = partido.get("local")
    visitante = partido.get("visitante")
    if not local or not visitante:
        return False, f"Equipos incompletos (local='{local}', visitante='{visitante}')"

    ids = partido.get("ids", [])
    if not ids or len(ids) < 2:
        return False, f"IDs de equipos incompletos: {ids}"

    marcador = partido.get("marcador", "")
    estado = partido.get("estado", "")

    # Si hay marcador, debe tener formato correcto y estado válido
    if marcador:
        if not validate_marcador(marcador):
            return False, f"Formato de marcador inválido: '{marcador}'"
        if estado not in {"cerrada", "provisional", "en_juego"}:
            return False, f"Estado desconocido para partido con marcador: '{estado}'"

    return True, "OK"


def validate_clasificacion(clasif: dict) -> tuple[bool, str]:
    """
    Valida la coherencia de los datos de clasificación.
    Retorna (es_valido, motivo_error).
    """
    if not isinstance(clasif, dict):
        return False, "La clasificación no es un diccionario"

    required_keys = ["posicion", "puntos", "pj", "pg", "pe", "pp", "gf", "gc"]
    for key in required_keys:
        if key not in clasif:
            return False, f"Campo obligatorio ausente en clasificación: {key}"
        if not isinstance(clasif[key], int):
            return False, f"El campo {key} debe ser entero: {clasif[key]}"

    # Coherencia matemática básica
    if clasif["posicion"] <= 0:
        return False, f"Posición inválida: {clasif['posicion']}"
    if clasif["pj"] != (clasif["pg"] + clasif["pe"] + clasif["pp"]):
        return False, (
            f"Incoherencia en partidos: PJ={clasif['pj']} != "
            f"PG({clasif['pg']}) + PE({clasif['pe']}) + PP({clasif['pp']})"
        )

    return True, "OK"
