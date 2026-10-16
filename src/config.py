import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

BASE_URL = "https://www.asturfutbol.es"
URL_JORNADA = f"{BASE_URL}/pnfg/NPcd/NFG_CmpJornada"
URL_CLASIFICACION = f"{BASE_URL}/pnfg/NPcd/NFG_VisClasificacion"
URL_ACTA = f"{BASE_URL}/pnfg/NPcd/NFG_CmpPartido"
URL_GOLEADORES = f"{BASE_URL}/pnfg/NPcd/NFG_CMP_Goleadores"

DEFAULT_PARAMS = {
    "cod_primaria": 1000120,
    "CodCompeticion": 22880369,
    "CodGrupo": 23110224,
    "CodTemporada": 22,
}

# Parámetros de la página de máximos goleadores del grupo
GOLEADORES_PARAMS = {
    "cod_primaria": 1000120,
    "codcompeticion": 22880369,
    "codgrupo": 23110224,
    "codtemporada": 22,
}

MI_EQUIPO_ID = os.getenv("MI_EQUIPO_ID", "5400")
MI_EQUIPO_NOMBRE = os.getenv("MI_EQUIPO_NOMBRE", 'Efro "B"')

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "efro-b-notificaciones-miguel")
ENABLE_NTFY = os.getenv("ENABLE_NTFY", "false").lower() in ("true", "1", "yes")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "miguelmierc@gmail.com")
USER_AGENT_EMAIL = os.getenv("USER_AGENT_EMAIL", "miguelmierc@gmail.com")

USER_AGENT = (
    f"Mozilla/5.0 (compatible; EfroBResultadosBot/1.0; "
    f"personal-use; contacto: {USER_AGENT_EMAIL})"
)

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
ESTADO_FILE = Path(os.getenv("ESTADO_FILE", "estado.json"))
