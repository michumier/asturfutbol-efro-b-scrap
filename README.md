# ⚽ Avisos de Resultados Efro "B" (Asturfutbol)

Script en Python para consultar la web de la Real Federación de Fútbol del Principado de Asturias ([asturfutbol.es](https://www.asturfutbol.es/)) y recibir notificaciones push en el móvil y/o por correo electrónico cuando haya un resultado nuevo o cambie de estado (provisional a definitivo), incluyendo marcador, posición en la clasificación y datos del partido.

Diseñado para uso personal, respetuoso con el servidor y **a coste 0€ en GitHub Actions**.

---

## 🚀 Características

- **Desofuscación de marcadores de Novanet**: Decodifica de forma nativa la ofuscación en JavaScript (`ntype` con array de sustitución `d`) y pseudo-elementos CSS con Unicode, descartando honeypots ocultos.
- **Validación de datos**: Comprueba la coherencia numérica del marcador y la clasificación antes de emitir cualquier aviso para no enviar datos corruptos.
- **Doble canal de notificación**:
  - **Móvil (Push instantáneo vía ntfy.sh)**: Llega al teléfono en tiempo real con sonido, tags y prioridad.
  - **Correo electrónico (`miguelmierc@gmail.com`)**: Notificación formateada con todos los detalles del partido y balance de la liga.
- **Aviso previo de jornada**: Notifica el horario, polideportivo/campo y árbitro asignado.
- **Detección inteligente de jornada**: Lee automáticamente el selector de jornadas de asturfutbol y elige la más cercana a la fecha de hoy.
- **Persistencia de estado**: Guarda en `estado.json` el último marcador notificado por `CodActa` para evitar alertas duplicadas.
- **Modos de prueba y simulación**: Permite validar offline con fixtures reales (`--fixture`), simular en vivo sin enviar (`--dry-run`) y enviar alertas de prueba (`--test-email`).

---

## 📱 Cómo recibir las notificaciones en el móvil (ntfy)

1. Instala la app gratuita **ntfy** en tu móvil:
   - [ntfy en Google Play (Android)](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - [ntfy en App Store (iOS)](https://apps.apple.com/app/ntfy/id1625396347)
   - O úsalo directamente en tu navegador web: [ntfy.sh/efro-b-notificaciones-miguel](https://ntfy.sh/efro-b-notificaciones-miguel)
2. Abre la app, pulsa en **Añadir tema** (`+`) y suscríbete a:
   `efro-b-notificaciones-miguel`
3. ¡Listo! Recibirás alertas push con vibración y sonido en tu móvil en cuanto termine o cambie el partido.

---

## 📧 Cómo activar el correo directo a Gmail (`miguelmierc@gmail.com`)

Para que el script pueda enviarte correos a través de tu cuenta de Google de forma segura:

1. Ve a tu cuenta de Google: [myaccount.google.com/security](https://myaccount.google.com/security).
2. Asegúrate de tener activada la **Verificación en 2 pasos**.
3. En el buscador de la cuenta escribe **Contraseñas de aplicaciones** (o accede a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Escribe un nombre como `EfroBot` y pulsa **Crear**.
5. Te generará una clave de 16 letras (ejemplo: `abcd efgh ijkl mnop`).
6. En tu archivo `.env` o en los **Secretos de GitHub** añade:
   ```env
   SMTP_USER=miguelmierc@gmail.com
   SMTP_PASS=tu_clave_de_16_caracteres
   ```

---

## 🛡️ Garantía de Coste Cero (0 €) en GitHub Actions

- Si tu repositorio en GitHub es **público**, GitHub Actions es **100% gratuito e ilimitado**.
- Si tu repositorio es **privado**, tu cuenta gratuita dispone de **2.000 minutos gratis al mes**.
- Este script tarda apenas **20 segundos** por ejecución.
- Al programarse solo sábados y domingos cada 30 minutos en horario de partidos (de 08:00 a 17:00 hora de España), se ejecuta unas 136 veces al mes, lo que supone un consumo mensual de unos **45 a 50 minutos** (menos del **2.5%** de tu cupo gratuito).
- En GitHub Settings -> Billing, el *Spending Limit* viene fijado en **$0** por defecto, garantizando que nunca se produzca ningún cobro.

---

## ⚙️ Instalación y Uso Local

### 1. Clonar e instalar dependencias
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configuración
Copia el archivo de ejemplo y ajusta tus preferencias:
```powershell
copy .env.example .env
```

### 3. Modos de ejecución

- **Enviar notificación de prueba a móvil y correo**:
  ```powershell
  python main.py --test-email
  ```

- **Simular en vivo contra asturfutbol sin enviar avisos (`--dry-run`)**:
  ```powershell
  python main.py --dry-run
  ```

- **Probar en modo offline usando los fixtures HTML locales**:
  ```powershell
  python main.py --fixture --dry-run
  ```

- **Ejecutar la suite completa de pruebas unitarias (`pytest`)**:
  ```powershell
  pytest -v
  ```

---

## ⏰ Automatización Alternativa (Raspberry Pi / Linux / PC)

Si prefieres no usar GitHub Actions y correrlo en tu propio servidor o Raspberry Pi, puedes añadir una tarea cron con `crontab -e`:

```bash
# Sábados y domingos cada 30 minutos de 08:00 a 16:30
*/30 8-16 * * 0,6 cd /ruta/a/mucho-efro && ./venv/bin/python main.py >> cron.log 2>&1
```

---

## 📜 Política Ética y Robots.txt

El archivo `robots.txt` de asturfutbol.es restringe el acceso automatizado general. Al tratarse de un script de **uso estrictamente personal** para seguir a nuestro equipo de fútbol base, se han aplicado las siguientes medidas de máxima cortesía y respeto:
- **Peticiones mínimas**: No se sondea durante la semana; únicamente fines de semana en horario de partidos, 1 sola ejecución cada 30 minutos.
- **Volumen mínimo**: Solo se descarga la jornada activa y la tabla de clasificación.
- **Identificación**: La cabecera `User-Agent` incluye identificación clara y correo de contacto para que el administrador pueda contactar en caso de cualquier inconveniente.
- **Sin redistribución**: Los datos no se almacenan en bases de datos públicas ni se republican en otras webs.
