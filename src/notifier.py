import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from src.config import NTFY_TOPIC, NOTIFICATION_EMAIL, ENABLE_NTFY

logger = logging.getLogger(__name__)


def estado_legible(estado: str) -> str:
    """Mapea el identificador interno de estado a texto comprensible."""
    mapeo = {
        "cerrada": "Definitivo",
        "provisional": "Provisional",
        "en_juego": "En juego",
        "sin_jugar": "Sin jugar",
    }
    return mapeo.get(estado, estado)


def format_mensaje_resultado(
    partido: dict,
    clasificacion: dict = None,
    jornada: int = None,
) -> tuple[str, str]:
    """Construye el título y el cuerpo del mensaje de resultado."""
    est_txt = estado_legible(partido.get("estado", ""))
    j_str = f"J{jornada}" if jornada else ""
    
    local = partido["local"]
    visitante = partido["visitante"]
    marcador = partido["marcador"]

    linea_principal = f"{local} {marcador} {visitante}"
    if j_str:
        linea_principal += f" ({j_str})"

    detalles = [linea_principal]
    
    if clasificacion:
        pos = clasificacion.get("posicion")
        pts = clasificacion.get("puntos")
        pj = clasificacion.get("pj", 0)
        pg = clasificacion.get("pg", 0)
        pe = clasificacion.get("pe", 0)
        pp = clasificacion.get("pp", 0)
        gf = clasificacion.get("gf", 0)
        gc = clasificacion.get("gc", 0)
        
        info_clasif = f"Clasificación: {pos}º · {pts} pts ({pj}PJ: {pg}G-{pe}E-{pp}P) · {est_txt}"
        detalles.append(info_clasif)
        detalles.append(f"Goles: {gf} a favor, {gc} en contra (Diferencia: {gf - gc:+d})")
    else:
        detalles.append(f"Estado: {est_txt}")

    if partido.get("campo"):
        detalles.append(f"Campo: {partido['campo']}")
    if partido.get("fecha"):
        detalles.append(f"Horario: {partido['fecha']}")
    if partido.get("arbitro"):
        detalles.append(f"Árbitro: {partido['arbitro']}")

    titulo = f"Efro B: {marcador} vs {visitante if '5400' in partido.get('ids', [])[:1] else local} [{est_txt}]"
    cuerpo = "\n".join(detalles)
    return titulo, cuerpo


def format_mensaje_previo(partido: dict, jornada: int = None) -> tuple[str, str]:
    """Construye el mensaje de aviso previo al fin de semana con fecha, hora y campo."""
    j_str = f" (Jornada {jornada})" if jornada else ""
    titulo = f"Próximo partido Efro B{j_str}"
    lineas = [
        f"{partido['local']} vs {partido['visitante']}",
        f"Horario: {partido.get('fecha', 'Por determinar')}",
        f"Campo: {partido.get('campo', 'Por determinar')}",
    ]
    if partido.get("arbitro"):
        lineas.append(f"Árbitro: {partido['arbitro']}")
    return titulo, "\n".join(lineas)


def notificar_ntfy(
    titulo: str,
    cuerpo: str,
    topic: str = NTFY_TOPIC,
    tags: list[str] = None,
    prioridad: str = "default",
) -> bool:
    """Envía notificación push inmediata a ntfy.sh."""
    if tags is None:
        tags = ["soccer", "sports"]

    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": titulo.encode("utf-8"),
        "Priority": prioridad,
        "Tags": ",".join(tags),
    }

    # Si el usuario dispone de cuenta o token en ntfy, lo soporta
    ntfy_token = os.getenv("NTFY_TOKEN")
    if ntfy_token:
        headers["Authorization"] = f"Bearer {ntfy_token}"
        if NOTIFICATION_EMAIL:
            headers["X-Email"] = NOTIFICATION_EMAIL

    try:
        resp = requests.post(
            url,
            data=cuerpo.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"Notificación push ntfy enviada con éxito a {url}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar notificación a ntfy ({url}): {e}")
        return False


def notificar_email(
    titulo: str,
    cuerpo: str,
    destinatario: str = NOTIFICATION_EMAIL,
) -> bool:
    """
    Envía correo electrónico vía SMTP (ej. Gmail con contraseña de aplicación o cualquier servidor).
    Requiere las variables de entorno:
    SMTP_HOST (ej. smtp.gmail.com)
    SMTP_USER (tu correo de gmail remitente)
    SMTP_PASS (tu contraseña de aplicación de 16 caracteres)
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not (smtp_user and smtp_pass):
        logger.warning(
            "Para recibir el correo electrónico directo, configura SMTP_USER y SMTP_PASS "
            "(contraseña de aplicación de Google) en tu archivo .env o en los secretos de GitHub."
        )
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = f"Avisos Efro B <{smtp_user}>"
        msg["To"] = destinatario
        msg["Subject"] = titulo
        msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Correo electrónico enviado exitosamente a {destinatario}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo SMTP a {destinatario}: {e}")
        return False


def notificar(
    titulo: str,
    cuerpo: str,
    topic: str = NTFY_TOPIC,
    email: str = NOTIFICATION_EMAIL,
    prioridad: str = "default",
) -> tuple[bool, bool]:
    """
    Punto de entrada de notificación global.
    Emite notificación push móvil (ntfy) y correo electrónico (si SMTP está configurado).
    Retorna (exito_push, exito_email).
    """
    exito_push = False
    if ENABLE_NTFY:
        exito_push = notificar_ntfy(titulo, cuerpo, topic=topic, prioridad=prioridad)
    exito_email = notificar_email(titulo, cuerpo, destinatario=email)
    return exito_push, exito_email
