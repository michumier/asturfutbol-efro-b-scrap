import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Asegurar codificación utf-8 en terminales de Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.client import AsturfutbolClient
from src.config import (
    MI_EQUIPO_ID,
    MI_EQUIPO_NOMBRE,
    NOTIFICATION_EMAIL,
    NTFY_TOPIC,
    ESTADO_FILE,
)
from src.notifier import (
    format_mensaje_resultado,
    format_mensaje_previo,
    notificar,
)
from src.parser import (
    parse_jornadas_disponibles,
    seleccionar_jornada_actual,
    parse_partidos,
    parse_clasificacion,
    parse_clasificacion_completa,
    parse_goles_acta,
    marcador_real_desde_goles,
    parse_tabla_goleadores,
)
from src.state import (
    load_state,
    save_state,
    debe_notificar_resultado,
    registrar_notificacion,
    debe_notificar_aviso_previo,
    registrar_aviso_previo,
)
from src.validator import validate_partido, validate_clasificacion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mucho-efro")


def ejecutar_test_notificacion():
    """Envía un mensaje de prueba realista a ntfy y al correo configurado."""
    logger.info(f"Enviando notificación de prueba a ntfy (topic: {NTFY_TOPIC}) y email ({NOTIFICATION_EMAIL})...")
    partido_test = {
        "acta": "99999999",
        "local": 'Efro "B"',
        "local_id": "5400",
        "visitante": 'C.D. San Ignacio Oviedo "C"',
        "visitante_id": "5483",
        "ids": ["5400", "5483"],
        "marcador": "7 - 2",
        "estado": "cerrada",
        "fecha": "10-10-2026 10:00",
        "campo": "POLIDEPORTIVO FUNDOMA",
        "arbitro": "Lopez Ruiz, Jaime",
    }
    clasif_test = {
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

    titulo, cuerpo_texto, cuerpo_html = format_mensaje_resultado(partido_test, clasif_test, jornada=2)
    titulo = f"[PRUEBA] {titulo}"

    ok_push, ok_email = notificar(
        titulo, cuerpo_texto, cuerpo_html=cuerpo_html, topic=NTFY_TOPIC, email=NOTIFICATION_EMAIL
    )
    
    print("\n" + "=" * 60)
    if ok_push:
        print("[OK] Notificación push enviada con éxito a ntfy.sh!")
        print(f" -> Puedes verla en tu navegador o app: https://ntfy.sh/{NTFY_TOPIC}")
    else:
        print("[INFO] Notificación push al móvil pausada temporalmente.")

    if ok_email:
        print(f"[OK] Correo electrónico enviado exitosamente a {NOTIFICATION_EMAIL}!")
    else:
        print(f"[INFO] Correo directo a {NOTIFICATION_EMAIL}:")
        print(" -> Para activar el envío por email directo desde Gmail, añade tus credenciales")
        print("    SMTP_USER y SMTP_PASS (contraseña de aplicación) en el archivo .env o secretos de GitHub.")
    print("=" * 60 + "\n")
    return 0 if (ok_push or ok_email) else 1


def main():
    parser = argparse.ArgumentParser(
        description="Avisos de resultados y clasificación de Efro 'B' (Asturfutbol)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la ejecución sin enviar notificaciones ni alterar el archivo estado.json.",
    )
    parser.add_argument(
        "--fixture",
        nargs="?",
        const="tests/fixtures",
        help="Ejecuta en modo offline usando archivos HTML de prueba.",
    )
    parser.add_argument(
        "--test-email",
        "--test-ntfy",
        action="store_true",
        help="Envía una notificación de prueba a ntfy y al correo para verificar la recepción.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza el envío de la notificación ignorando si ya fue notificada en estado.json.",
    )
    parser.add_argument(
        "--jornada",
        type=int,
        help="Fuerza la consulta de una jornada específica (1..30).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Muestra información detallada de depuración.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.test_email:
        return ejecutar_test_notificacion()

    state = load_state(ESTADO_FILE)
    client = None
    soup_acta = None
    soup_goleadores = None

    # 1. Obtener HTML de jornada y clasificación (vía fixture o vía red)
    if args.fixture:
        fixtures_dir = Path(args.fixture)
        logger.info(f"Modo FIXTURE activado desde {fixtures_dir}")
        j_num = args.jornada or 2
        f_jornada = fixtures_dir / f"jornada_{j_num}_jugada.html"
        if not f_jornada.exists():
            f_jornada = fixtures_dir / f"jornada_{j_num}_sin_jugar.html"
        if not f_jornada.exists():
            f_jornada = fixtures_dir / "jornada_2_jugada.html"
            j_num = 2

        f_clasif = fixtures_dir / f"clasificacion_{j_num}.html"
        if not f_clasif.exists():
            f_clasif = fixtures_dir / "clasificacion_2.html"

        f_acta = fixtures_dir / f"acta_j{j_num}.html"
        if not f_acta.exists():
            f_acta = fixtures_dir / "acta_j2.html"
        f_goleadores = fixtures_dir / f"goleadores_j{j_num}.html"
        if not f_goleadores.exists():
            f_goleadores = fixtures_dir / "goleadores_j2.html"

        logger.info(f"Usando fixture de jornada: {f_jornada.name}")
        soup_jornada = BeautifulSoup(f_jornada.read_text(encoding="iso-8859-15"), "html.parser")
        soup_clasif = BeautifulSoup(f_clasif.read_text(encoding="iso-8859-15"), "html.parser")
        soup_acta = (
            BeautifulSoup(f_acta.read_bytes().decode("utf-8", "replace"), "html.parser")
            if f_acta.exists() else None
        )
        soup_goleadores = (
            BeautifulSoup(f_goleadores.read_bytes().decode("utf-8", "replace"), "html.parser")
            if f_goleadores.exists() else None
        )
        jornada_actual = j_num
    else:
        client = AsturfutbolClient()
        if args.jornada:
            jornada_actual = args.jornada
            logger.info(f"Consultando jornada forzada: {jornada_actual}")
        else:
            logger.info("Consultando jornadas disponibles en asturfutbol...")
            soup_inicial = client.get_jornada_soup(cod_jornada=1)
            jornadas = parse_jornadas_disponibles(soup_inicial)
            jornada_actual = seleccionar_jornada_actual(jornadas, fecha_ref=datetime.now())
            logger.info(f"Jornada seleccionada automáticamente: {jornada_actual}")

        soup_jornada = client.get_jornada_soup(cod_jornada=jornada_actual)
        soup_clasif = client.get_clasificacion_soup(cod_jornada=jornada_actual)

    # 2. Parsear partidos y encontrar a nuestro equipo
    partidos = parse_partidos(soup_jornada)
    mi_partido = next((p for p in partidos if MI_EQUIPO_ID in p.get("ids", [])), None)

    if not mi_partido:
        logger.warning(
            f"No se encontró partido para el equipo {MI_EQUIPO_ID} en la jornada {jornada_actual}. "
            "Es posible que descanse esta jornada."
        )
        return 0

    # 3. Validar integridad del partido
    es_valido, motivo = validate_partido(mi_partido)
    if not es_valido:
        logger.error(f"Error de validación en datos del partido: {motivo}. Cancelando notificación.")
        return 1

    # 4. Parsear y validar clasificación
    clasif = parse_clasificacion(soup_clasif, cod_equipo=MI_EQUIPO_ID)
    if clasif:
        c_valida, c_motivo = validate_clasificacion(clasif)
        if not c_valida:
            logger.warning(f"Clasificación con incoherencias ({c_motivo}), se omitirá del aviso.")
            clasif = None

    acta = mi_partido["acta"]
    marcador = mi_partido["marcador"]
    estado = mi_partido["estado"]

    # 4b. Datos ampliados: clasificación completa, goles del acta y goleadores del equipo
    clasif_completa = parse_clasificacion_completa(soup_clasif)
    goles = []
    goleadores_equipo = []

    if marcador:
        if soup_acta is None and not args.fixture and client is not None and acta:
            try:
                soup_acta = client.get_acta_soup(acta)
            except Exception as e:
                logger.warning(f"No se pudo descargar el acta {acta}: {e}")
        if soup_acta is not None:
            goles = parse_goles_acta(soup_acta)
            marcador_real = marcador_real_desde_goles(goles)
            if marcador_real:
                mi_partido["marcador_real"] = marcador_real
                if marcador_real != marcador:
                    logger.info(
                        f"Marcador real reconstruido del acta: {marcador_real} (oficial limitado: {marcador})"
                    )
            logger.info(f"Goles extraídos del acta: {len(goles)}")

    if soup_goleadores is None and not args.fixture and client is not None:
        try:
            soup_goleadores = client.get_goleadores_soup()
        except Exception as e:
            logger.warning(f"No se pudo descargar la tabla de goleadores: {e}")
    if soup_goleadores is not None:
        goleadores_equipo = parse_tabla_goleadores(soup_goleadores, nombre_equipo=MI_EQUIPO_NOMBRE)
        logger.info(f"Goleadores de {MI_EQUIPO_NOMBRE} en la tabla: {len(goleadores_equipo)}")

    logger.info(
        f"Partido J{jornada_actual}: {mi_partido['local']} vs {mi_partido['visitante']} | "
        f"Marcador: '{marcador}' | Estado: {estado}"
    )
    if clasif:
        logger.info(
            f"Clasificación Efro B: Pos {clasif['posicion']}º | {clasif['puntos']} pts | "
            f"{clasif['pj']} PJ ({clasif['pg']}G-{clasif['pe']}E-{clasif['pp']}P) | "
            f"Goles: {clasif['gf']}F - {clasif['gc']}C"
        )

    # 5. Detección de notificación
    # Caso A: Partido con resultado (Sábado o Domingo cuando termine el partido)
    if marcador:
        debe_enviar = args.force or debe_notificar_resultado(state, acta, marcador, estado)
        if debe_enviar:
            titulo, cuerpo_texto, cuerpo_html = format_mensaje_resultado(
                mi_partido,
                clasif,
                jornada=jornada_actual,
                goles=goles,
                clasificacion_completa=clasif_completa,
                goleadores_equipo=goleadores_equipo,
            )
            if args.dry_run:
                print("\n" + "=" * 50)
                print(f"[DRY-RUN] Notificación de resultado que se enviaría (email: {NOTIFICATION_EMAIL}):")
                print(f"Título: {titulo}")
                print("-" * 50)
                print(cuerpo_texto)
                print("=" * 50 + "\n")
            else:
                logger.info(f"Enviando notificación de resultado para acta {acta}...")
                prioridad = "high" if estado == "cerrada" else "default"
                ok_push, ok_email = notificar(
                    titulo,
                    cuerpo_texto,
                    cuerpo_html=cuerpo_html,
                    topic=NTFY_TOPIC,
                    email=NOTIFICATION_EMAIL,
                    prioridad=prioridad,
                )
                if ok_push or ok_email:
                    registrar_notificacion(state, acta, marcador, estado)
                    if not args.fixture:
                        save_state(state, ESTADO_FILE)
        else:
            logger.info("El resultado ya estaba notificado en estado.json y no ha cambiado (sin duplicados).")

    # Caso B: Partido sin jugar (Recordatorio solo los viernes de tarde o con --force)
    else:
        es_viernes = datetime.now().weekday() == 4
        if es_viernes or args.force:
            if debe_notificar_aviso_previo(state, acta) or args.force:
                titulo, cuerpo_texto, cuerpo_html = format_mensaje_previo(
                    mi_partido, jornada=jornada_actual
                )
                if args.dry_run:
                    print("\n" + "=" * 50)
                    print(f"[DRY-RUN] Recordatorio de viernes que se enviaría (email: {NOTIFICATION_EMAIL}):")
                    print(f"Título: {titulo}")
                    print("-" * 50)
                    print(cuerpo_texto)
                    print("=" * 50 + "\n")
                else:
                    logger.info(f"Enviando recordatorio de partido para acta {acta}...")
                    ok_push, ok_email = notificar(
                        titulo,
                        cuerpo_texto,
                        cuerpo_html=cuerpo_html,
                        topic=NTFY_TOPIC,
                        email=NOTIFICATION_EMAIL,
                        prioridad="low",
                    )
                    if ok_push or ok_email:
                        registrar_aviso_previo(state, acta)
                        if not args.fixture:
                            save_state(state, ESTADO_FILE)
            else:
                logger.info("El recordatorio previo del viernes ya fue enviado para este partido.")
        else:
            logger.info("Partido aún sin jugar. En fin de semana solo se notifica cuando finalice el encuentro.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
