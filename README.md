# ⚽ Avisos Efro "B" (Asturfutbol)

Script en Python que consulta [asturfutbol.es](https://www.asturfutbol.es/) y envía
notificaciones (email y/o push con [ntfy](https://ntfy.sh/)) con los resultados,
goles, goleadores y clasificación de un equipo de fútbol base.

Uso estrictamente personal.

## Características

- **Resultado real desde el acta**: marcador reconstruido de los goles, con autor y minuto.
- **Goleadores del equipo** y **clasificación completa** en cada correo.
- **Recordatorio previo** del partido (viernes): horario, campo, árbitro, clasificación y goleadores.
- **Sin spam**: como máximo 1 aviso provisional + 1 aviso definitivo por partido.
- **Persistencia de estado** (`estado.json`) para no repetir notificaciones.
- **Modos de prueba**: fixtures locales, simulación sin envío y envío de prueba.

## Requisitos

- Python 3.10+
- Una cuenta de correo con SMTP (por ejemplo, Gmail con contraseña de aplicación)
- Opcional: app de ntfy para notificaciones push

## Instalación

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` con tus datos. **No subas nunca `.env` al repositorio.**

## Configuración

| Variable | Descripción |
| --- | --- |
| `MI_EQUIPO_ID` / `MI_EQUIPO_NOMBRE` | Equipo a seguir |
| `NOTIFICATION_EMAIL` | Correo destino |
| `SMTP_HOST` / `SMTP_PORT` | Servidor SMTP |
| `SMTP_USER` / `SMTP_PASS` | Credenciales SMTP (contraseña de aplicación) |
| `NTFY_TOPIC` | Canal privado de ntfy |
| `ENABLE_NTFY` | `true` / `false` para activar push |
| `USER_AGENT_EMAIL` | Contacto incluido en el User-Agent |
| `LOG_LEVEL` | Nivel de logs (`INFO` por defecto) |

En GitHub Actions, define estos valores como **Repository secrets**.

## Uso

```powershell
python main.py                # ejecución normal
python main.py --dry-run      # simula sin enviar ni guardar estado
python main.py --fixture      # prueba offline con HTML local
python main.py --test-email   # envía una notificación de prueba
python main.py --jornada 4    # fuerza una jornada concreta
python main.py --force        # ignora el estado y fuerza el envío
```

Tests:

```powershell
pytest -q
```

## Automatización

El repositorio incluye `.github/workflows/scraper.yml`, que se ejecuta con GitHub Actions:

- **Viernes por la tarde**: recordatorio del próximo partido.
- **Sábados y domingos**: consulta de resultados cada 30 minutos.
- Guarda `estado.json` automáticamente y publica `run.log` como artefacto para depurar.

También se puede ejecutar con cron en un servidor propio:

```bash
*/30 8-16 * * 0,6 cd /ruta/al/proyecto && ./venv/bin/python main.py >> cron.log 2>&1
```

## Aviso

Proyecto personal y sin ánimo de lucro. Las peticiones se limitan al horario de
partidos y a la información necesaria, respetando el `robots.txt` del sitio.
