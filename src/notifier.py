import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from src.config import NTFY_TOPIC, NOTIFICATION_EMAIL, ENABLE_NTFY, MI_EQUIPO_ID, MI_EQUIPO_NOMBRE
from src.parser import normalizar_nombre

logger = logging.getLogger(__name__)


def _lado_a_nombre(partido: dict, lado: str) -> str:
    """Traduce 'local'/'visitante' al nombre real del equipo en este partido."""
    if lado == "local":
        return partido.get("local", "Local")
    if lado == "visitante":
        return partido.get("visitante", "Visitante")
    return ""


def _es_equipo_propio(partido: dict, mi_equipo_id: str = None) -> bool:
    """Indica si nuestro equipo juega como local en el partido dado."""
    objetivo = mi_equipo_id or MI_EQUIPO_ID
    ids = partido.get("ids", [])
    return bool(ids) and ids[0] == objetivo


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
    goles: list[dict] = None,
    clasificacion_completa: list[dict] = None,
    goleadores_equipo: list[dict] = None,
    mi_equipo_id: str = None,
) -> tuple[str, str, str]:
    """Construye el título, el cuerpo de texto plano y el HTML visual del mensaje de resultado."""
    est_txt = estado_legible(partido.get("estado", ""))
    j_str = f"J{jornada}" if jornada else ""
    
    local = partido["local"]
    visitante = partido["visitante"]
    marcador = partido["marcador"]
    # Marcador real reconstruido del acta (el visible puede estar limitado a 5 goles de diferencia)
    marcador_real = partido.get("marcador_real") or marcador
    escudo_local = partido.get("escudo_local") or ""
    escudo_visitante = partido.get("escudo_visitante") or ""
    campo = partido.get("campo", "")
    fecha = partido.get("fecha", "")
    arbitro = partido.get("arbitro", "")
    acta = partido.get("acta", "")
    goles = goles or []
    clasificacion_completa = clasificacion_completa or []
    goleadores_equipo = goleadores_equipo or []
    es_efro_local = _es_equipo_propio(partido, mi_equipo_id)

    # 1. Versión Texto Plano
    linea_principal = f"{local} {marcador_real} {visitante}"
    if j_str:
        linea_principal += f" ({j_str})"

    detalles = [linea_principal]
    if marcador_real != marcador:
        detalles.append(
            f"(Marcador oficial del acta limitado a 5 goles de diferencia: {marcador})"
        )

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

    if campo:
        detalles.append(f"Campo: {campo}")
    if fecha:
        detalles.append(f"Horario: {fecha}")
    if arbitro:
        detalles.append(f"Árbitro: {arbitro}")

    if goles:
        detalles.append("")
        detalles.append(f"⚽ Goles del partido ({len(goles)}):")
        for gol in goles:
            marca_pp = " (p.p.)" if gol.get("tipo") == "pp" else ""
            detalles.append(
                f"  {gol.get('minuto', '')}' {gol.get('jugador', '')}{marca_pp} "
                f"— {_lado_a_nombre(partido, gol.get('equipo'))}"
            )

    if goleadores_equipo:
        detalles.append("")
        detalles.append(f"🎯 Goleadores {MI_EQUIPO_NOMBRE}:")
        for i, go in enumerate(goleadores_equipo, 1):
            unidad = "gol" if go["goles"] == 1 else "goles"
            detalles.append(f"  {i}. {go['jugador']} — {go['goles']} {unidad}")

    if clasificacion_completa:
        detalles.append("")
        detalles.append("🏆 Clasificación completa:")
        for eq in clasificacion_completa:
            marca = "  <<<" if normalizar_nombre(eq["equipo"]) == normalizar_nombre(MI_EQUIPO_NOMBRE) else ""
            detalles.append(
                f"  {eq['posicion']:>2}. {eq['equipo']:<36} "
                f"{eq['pj']:>2}PJ {eq['gf']:>3}:{eq['gc']:<3} {eq['puntos']:>2} pts{marca}"
            )

    rival = visitante if es_efro_local else local
    titulo = f"⚽ Efro B: {marcador_real} vs {rival} [{est_txt}]"
    cuerpo_texto = "\n".join(detalles)

    # 2. Versión HTML Visual
    badge_bg = "#ECFDF5" if partido.get("estado") == "cerrada" else "#FFFBEB"
    badge_color = "#065F46" if partido.get("estado") == "cerrada" else "#92400E"
    badge_border = "#A7F3D0" if partido.get("estado") == "cerrada" else "#FDE68A"
    badge_icon = "✓" if partido.get("estado") == "cerrada" else "⏳"

    escudo_l_html = f'<img src="{escudo_local}" width="64" height="64" style="object-fit:contain;" alt="{local}">' if escudo_local else '<div style="font-size:36px;">🛡️</div>'
    escudo_v_html = f'<img src="{escudo_visitante}" width="64" height="64" style="object-fit:contain;" alt="{visitante}">' if escudo_visitante else '<div style="font-size:36px;">🛡️</div>'

    clasif_html = ""
    if clasificacion:
        pos = clasificacion.get("posicion")
        pts = clasificacion.get("puntos")
        pj = clasificacion.get("pj", 0)
        pg = clasificacion.get("pg", 0)
        pe = clasificacion.get("pe", 0)
        pp = clasificacion.get("pp", 0)
        gf = clasificacion.get("gf", 0)
        gc = clasificacion.get("gc", 0)
        dif = gf - gc

        clasif_html = f"""
        <div style="background-color: #F8FAFC; border-radius: 10px; padding: 16px; margin-top: 20px; border: 1px solid #E2E8F0;">
            <h4 style="margin: 0 0 12px 0; color: #002B49; font-size: 15px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                🏆 Clasificación Benjamín Grupo 10
            </h4>
            <table width="100%" cellpadding="0" cellspacing="0" style="text-align: center;">
                <tr>
                    <td style="padding: 6px; background: #ffffff; border-radius: 8px; border: 1px solid #E2E8F0; width: 22%;">
                        <span style="font-size: 11px; color: #64748B; display: block;">Posición</span>
                        <strong style="font-size: 18px; color: #002B49;">{pos}º</strong>
                    </td>
                    <td style="width: 4%;"></td>
                    <td style="padding: 6px; background: #ffffff; border-radius: 8px; border: 1px solid #E2E8F0; width: 22%;">
                        <span style="font-size: 11px; color: #64748B; display: block;">Puntos</span>
                        <strong style="font-size: 18px; color: #0284C7;">{pts} pts</strong>
                    </td>
                    <td style="width: 4%;"></td>
                    <td style="padding: 6px; background: #ffffff; border-radius: 8px; border: 1px solid #E2E8F0; width: 22%;">
                        <span style="font-size: 11px; color: #64748B; display: block;">Partidos</span>
                        <strong style="font-size: 14px; color: #334155;">{pj} PJ <span style="font-size:11px; color:#10B981;">({pg}V</span>-<span style="font-size:11px; color:#64748B;">{pe}E</span>-<span style="font-size:11px; color:#EF4444;">{pp}D)</span></strong>
                    </td>
                    <td style="width: 4%;"></td>
                    <td style="padding: 6px; background: #ffffff; border-radius: 8px; border: 1px solid #E2E8F0; width: 22%;">
                        <span style="font-size: 11px; color: #64748B; display: block;">Goles</span>
                        <strong style="font-size: 14px; color: #334155;">{gf}:{gc} ({dif:+d})</strong>
                    </td>
                </tr>
            </table>
        </div>
        """

    url_acta = f"https://www.asturfutbol.es/pnfg/NPcd/NFG_CmpPartido?cod_primaria=1000120&CodActa={acta}" if acta else "https://www.asturfutbol.es/"

    # 3. Sección de goles del partido
    goles_html = ""
    if goles:
        filas_goles = ""
        for gol in goles:
            marca_pp = " <span style='color:#B91C1C;font-weight:bold;'>(p.p.)</span>" if gol.get("tipo") == "pp" else ""
            filas_goles += f"""
                <tr>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; text-align: center; color: #0284C7; font-weight: bold; white-space: nowrap;">{gol.get('minuto', '')}'</td>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; color: #1E293B;">{gol.get('jugador', '')}{marca_pp}</td>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; text-align: right; color: #64748B; font-size: 12px;">{_lado_a_nombre(partido, gol.get('equipo'))}</td>
                </tr>"""
        goles_html = f"""
        <div style="background-color: #F8FAFC; border-radius: 10px; padding: 16px; margin-top: 20px; border: 1px solid #E2E8F0;">
            <h4 style="margin: 0 0 12px 0; color: #002B49; font-size: 15px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                ⚽ Goles del partido <span style="color:#64748B; font-weight:normal; text-transform:none;">({len(goles)})</span>
            </h4>
            <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 13px; border-collapse: collapse;">{filas_goles}
            </table>
        </div>"""

    # 4. Sección de goleadores del equipo
    goleadores_html = ""
    if goleadores_equipo:
        filas_gol = ""
        for i, go in enumerate(goleadores_equipo, 1):
            filas_gol += f"""
                <tr>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; text-align: center; color: #64748B; font-weight: bold;">{i}</td>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; color: #1E293B;">{go['jugador']}</td>
                    <td style="padding: 6px 8px; border-bottom: 1px solid #F1F5F9; text-align: right; color: #0284C7; font-weight: bold;">{go['goles']}</td>
                </tr>"""
        goleadores_html = f"""
        <div style="background-color: #F8FAFC; border-radius: 10px; padding: 16px; margin-top: 20px; border: 1px solid #E2E8F0;">
            <h4 style="margin: 0 0 12px 0; color: #002B49; font-size: 15px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                🎯 Goleadores {MI_EQUIPO_NOMBRE}
            </h4>
            <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 13px; border-collapse: collapse;">{filas_gol}
            </table>
        </div>"""

    # 5. Sección de clasificación completa
    clasif_completa_html = ""
    if clasificacion_completa:
        filas_clasif = ""
        for eq in clasificacion_completa:
            es_efro = normalizar_nombre(eq["equipo"]) == normalizar_nombre(MI_EQUIPO_NOMBRE)
            fondo = "#EFF6FF" if es_efro else "#FFFFFF"
            peso = "bold" if es_efro else "normal"
            color_eq = "#1D4ED8" if es_efro else "#1E293B"
            filas_clasif += f"""
                <tr style="background-color: {fondo};">
                    <td style="padding: 5px 6px; text-align: center; color: #64748B; border-bottom: 1px solid #F1F5F9;">{eq['posicion']}</td>
                    <td style="padding: 5px 6px; text-align: left; font-weight: {peso}; color: {color_eq}; border-bottom: 1px solid #F1F5F9;">{eq['equipo']}</td>
                    <td style="padding: 5px 6px; text-align: center; color: #475569; border-bottom: 1px solid #F1F5F9;">{eq['pj']}</td>
                    <td style="padding: 5px 6px; text-align: center; color: #475569; border-bottom: 1px solid #F1F5F9;">{eq['gf']}:{eq['gc']}</td>
                    <td style="padding: 5px 6px; text-align: center; color: #475569; border-bottom: 1px solid #F1F5F9;">{eq['dif']:+d}</td>
                    <td style="padding: 5px 6px; text-align: center; font-weight: bold; color: #002B49; border-bottom: 1px solid #F1F5F9;">{eq['puntos']}</td>
                </tr>"""
        clasif_completa_html = f"""
        <div style="background-color: #F8FAFC; border-radius: 10px; padding: 16px; margin-top: 20px; border: 1px solid #E2E8F0;">
            <h4 style="margin: 0 0 12px 0; color: #002B49; font-size: 15px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                🏆 Clasificación · 3ª Benjamín Grupo 10
            </h4>
            <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 12px; border-collapse: collapse;">
                <tr style="color:#64748B; font-size: 11px; text-transform: uppercase;">
                    <td style="padding: 4px; text-align: center; width: 8%;">#</td>
                    <td style="padding: 4px; text-align: left;">Equipo</td>
                    <td style="padding: 4px; text-align: center; width: 10%;">PJ</td>
                    <td style="padding: 4px; text-align: center; width: 14%;">GF:GC</td>
                    <td style="padding: 4px; text-align: center; width: 10%;">Dif</td>
                    <td style="padding: 4px; text-align: center; width: 10%;">Pts</td>
                </tr>{filas_clasif}
            </table>
        </div>"""

    nota_marcador_html = ""
    if marcador_real != marcador:
        nota_marcador_html = f"""
        <div style="background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 8px; padding: 10px 14px; margin-top: 14px; font-size: 12px; color: #92400E;">
            ℹ️ El acta oficial limita el marcador a 5 goles de diferencia. <strong>Resultado real: {marcador_real}</strong> (oficial: {marcador}).
        </div>"""

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 0; background-color: #F1F5F9; font-family: 'Segoe UI', Helvetica, Arial, sans-serif; color: #1E293B;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F1F5F9; padding: 25px 10px;">
            <tr>
                <td align="center">
                    <table width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.07); border: 1px solid #E2E8F0;" cellpadding="0" cellspacing="0">
                        
                        <!-- Cabecera -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #002B49 0%, #084370 100%); padding: 18px 24px; text-align: center; color: #ffffff;">
                                <div style="font-size: 12px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #93C5FD; margin-bottom: 4px;">
                                    REAL FEDERACIÓN DE FÚTBOL DEL PRINCIPADO DE ASTURIAS
                                </div>
                                <h1 style="margin: 0; font-size: 20px; font-weight: 800; color: #ffffff;">
                                    EFRO "B" {f'· JORNADA {jornada}' if jornada else ''}
                                </h1>
                                <div style="font-size: 12px; color: #E2E8F0; margin-top: 3px;">
                                    3ª Benjamín · Grupo 10
                                </div>
                            </td>
                        </tr>

                        <!-- Tarjeta Scoreboard Central -->
                        <tr>
                            <td style="padding: 24px;">
                                <div style="text-align: center; margin-bottom: 16px;">
                                    <span style="display: inline-block; background-color: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}; font-size: 12px; font-weight: bold; padding: 4px 12px; border-radius: 20px;">
                                        {badge_icon} Resultado {est_txt}
                                    </span>
                                </div>

                                <table width="100%" cellpadding="0" cellspacing="0" style="text-align: center;">
                                    <tr>
                                        <!-- Local -->
                                        <td style="width: 38%; vertical-align: middle;">
                                            <div style="margin-bottom: 8px;">{escudo_l_html}</div>
                                            <strong style="font-size: 15px; color: #0F172A; line-height: 1.2; display: block;">
                                                {local}
                                            </strong>
                                            <span style="font-size: 11px; color: #64748B; font-weight: 600;">(LOCAL)</span>
                                        </td>

                                        <!-- Marcador -->
                                        <td style="width: 24%; vertical-align: middle;">
                                            <div style="background-color: #002B49; color: #ffffff; font-size: 32px; font-weight: 900; padding: 10px 4px; border-radius: 12px; letter-spacing: 2px; box-shadow: 0 4px 10px rgba(0,43,73,0.25);">
                                                {marcador_real}
                                            </div>
                                        </td>

                                        <!-- Visitante -->
                                        <td style="width: 38%; vertical-align: middle;">
                                            <div style="margin-bottom: 8px;">{escudo_v_html}</div>
                                            <strong style="font-size: 15px; color: #0F172A; line-height: 1.2; display: block;">
                                                {visitante}
                                            </strong>
                                            <span style="font-size: 11px; color: #64748B; font-weight: 600;">(VISITANTE)</span>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Datos del Encuentro -->
                                <div style="background-color: #F8FAFC; border-radius: 10px; padding: 14px 18px; margin-top: 22px; font-size: 13px; color: #475569; border: 1px solid #E2E8F0;">
                                    {f'<div style="margin-bottom: 6px;">📅 <strong>Fecha:</strong> {fecha}</div>' if fecha else ''}
                                    {f'<div style="margin-bottom: 6px;">📍 <strong>Campo:</strong> {campo}</div>' if campo else ''}
                                    {f'<div>🧑‍⚖️ <strong>Árbitro:</strong> {arbitro}</div>' if arbitro else ''}
                                </div>

                                {nota_marcador_html}

                                <!-- Goles del partido -->
                                {goles_html}

                                <!-- Clasificación (resumen del equipo) -->
                                {clasif_html}

                                <!-- Goleadores del equipo -->
                                {goleadores_html}

                                <!-- Clasificación completa -->
                                {clasif_completa_html}

                                <!-- Botón Ver Acta -->
                                <div style="text-align: center; margin-top: 24px;">
                                    <a href="{url_acta}" target="_blank" style="background-color: #0284C7; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: bold; padding: 11px 22px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 6px rgba(2,132,199,0.3);">
                                        📄 Ver Acta Oficial en Asturfutbol
                                    </a>
                                </div>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #F8FAFC; padding: 14px 20px; text-align: center; font-size: 11px; color: #94A3B8; border-top: 1px solid #E2E8F0;">
                                Notificación automática para seguimiento de Efro "B" · asturfutbol.es
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return titulo, cuerpo_texto, cuerpo_html


def format_mensaje_previo(partido: dict, jornada: int = None) -> tuple[str, str, str]:
    """Construye el mensaje y HTML de aviso previo del partido para el fin de semana."""
    j_str = f" (Jornada {jornada})" if jornada else ""
    local = partido["local"]
    visitante = partido["visitante"]
    fecha = partido.get("fecha", "Por determinar")
    campo = partido.get("campo", "Por determinar")
    arbitro = partido.get("arbitro", "Por determinar")
    escudo_local = partido.get("escudo_local") or ""
    escudo_visitante = partido.get("escudo_visitante") or ""

    titulo = f"📅 Próximo partido Efro B: {local} vs {visitante}{j_str}"
    
    lineas = [
        f"{local} vs {visitante}",
        f"Horario: {fecha}",
        f"Campo: {campo}",
    ]
    if arbitro and arbitro != "Por determinar":
        lineas.append(f"Árbitro: {arbitro}")
    cuerpo_texto = "\n".join(lineas)

    escudo_l_html = f'<img src="{escudo_local}" width="60" height="60" style="object-fit:contain;" alt="{local}">' if escudo_local else '<div style="font-size:32px;">🛡️</div>'
    escudo_v_html = f'<img src="{escudo_visitante}" width="60" height="60" style="object-fit:contain;" alt="{visitante}">' if escudo_visitante else '<div style="font-size:32px;">🛡️</div>'

    cuerpo_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 0; background-color: #F1F5F9; font-family: 'Segoe UI', Helvetica, Arial, sans-serif; color: #1E293B;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #F1F5F9; padding: 25px 10px;">
            <tr>
                <td align="center">
                    <table width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.07); border: 1px solid #E2E8F0;" cellpadding="0" cellspacing="0">
                        
                        <!-- Cabecera -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #002B49 0%, #084370 100%); padding: 18px 24px; text-align: center; color: #ffffff;">
                                <div style="font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #F59E0B; margin-bottom: 4px;">
                                    ⚡ RECORDATORIO DE PARTIDO
                                </div>
                                <h1 style="margin: 0; font-size: 20px; font-weight: 800; color: #ffffff;">
                                    {f'JORNADA {jornada}' if jornada else 'PRÓXIMO ENCUENTRO'} · EFRO "B"
                                </h1>
                            </td>
                        </tr>

                        <!-- Tarjeta Encuentro -->
                        <tr>
                            <td style="padding: 24px;">
                                <table width="100%" cellpadding="0" cellspacing="0" style="text-align: center; margin-bottom: 20px;">
                                    <tr>
                                        <td style="width: 42%;">
                                            <div style="margin-bottom: 8px;">{escudo_l_html}</div>
                                            <strong style="font-size: 15px; color: #0F172A; display: block;">{local}</strong>
                                            <span style="font-size: 11px; color: #64748B;">Local</span>
                                        </td>
                                        <td style="width: 16%;">
                                            <div style="background-color: #E2E8F0; color: #475569; font-size: 14px; font-weight: 900; padding: 6px; border-radius: 50%; width: 32px; height: 32px; line-height: 32px; margin: 0 auto;">
                                                VS
                                            </div>
                                        </td>
                                        <td style="width: 42%;">
                                            <div style="margin-bottom: 8px;">{escudo_v_html}</div>
                                            <strong style="font-size: 15px; color: #0F172A; display: block;">{visitante}</strong>
                                            <span style="font-size: 11px; color: #64748B;">Visitante</span>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Tarjeta Horario y Lugar Destacada -->
                                <div style="background: linear-gradient(135deg, #EFF6FF 0%, #F0FDF4 100%); border-radius: 12px; padding: 18px; border: 1px solid #BFDBFE;">
                                    <div style="margin-bottom: 10px;">
                                        <span style="font-size: 12px; color: #1E40AF; font-weight: bold; text-transform: uppercase; display: block;">⏰ Fecha y Hora</span>
                                        <strong style="font-size: 17px; color: #1E3A8A;">{fecha}</strong>
                                    </div>
                                    <div style="margin-bottom: 10px;">
                                        <span style="font-size: 12px; color: #166534; font-weight: bold; text-transform: uppercase; display: block;">📍 Terreno de Juego</span>
                                        <strong style="font-size: 16px; color: #14532D;">{campo}</strong>
                                    </div>
                                    {f'<div><span style="font-size: 12px; color: #64748B; font-weight: bold; text-transform: uppercase; display: block;">🧑‍⚖️ Árbitro</span><span style="font-size: 14px; color: #334155;">{arbitro}</span></div>' if (arbitro and arbitro != "Por determinar") else ''}
                                </div>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #F8FAFC; padding: 12px 20px; text-align: center; font-size: 11px; color: #94A3B8; border-top: 1px solid #E2E8F0;">
                                ¡Mucho Efro! · Recordatorio automático
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return titulo, cuerpo_texto, cuerpo_html


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
    cuerpo_texto: str,
    cuerpo_html: str = None,
    destinatario: str = NOTIFICATION_EMAIL,
) -> bool:
    """
    Envía correo electrónico multipart (HTML visual con fallback a texto plano) vía SMTP.
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not (smtp_user and smtp_pass):
        logger.warning(
            "Para recibir el correo electrónico directo, configura SMTP_USER y SMTP_PASS "
            "en tu archivo .env o en los secretos de GitHub."
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Avisos Efro B <{smtp_user}>"
        msg["To"] = destinatario
        msg["Subject"] = titulo

        # Adjuntar versión texto plano
        msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))

        # Adjuntar versión HTML enriquecida si existe
        if cuerpo_html:
            msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

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
    cuerpo_texto: str,
    cuerpo_html: str = None,
    topic: str = NTFY_TOPIC,
    email: str = NOTIFICATION_EMAIL,
    prioridad: str = "default",
) -> tuple[bool, bool]:
    """
    Punto de entrada de notificación global.
    Emite notificación push móvil (si ENABLE_NTFY está activo) y correo electrónico HTML.
    Retorna (exito_push, exito_email).
    """
    exito_push = False
    if ENABLE_NTFY:
        exito_push = notificar_ntfy(titulo, cuerpo_texto, topic=topic, prioridad=prioridad)
    exito_email = notificar_email(titulo, cuerpo_texto, cuerpo_html=cuerpo_html, destinatario=email)
    return exito_push, exito_email
