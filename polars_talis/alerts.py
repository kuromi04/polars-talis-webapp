"""
alerts.py — Sistema de alertas para estrategias de cruce de medias móviles.

Envía notificaciones a Telegram cuando se detecta un cruce de MA 100 → MA 200.
Soporta adjuntar una imagen del gráfico generado.
"""

import os
import json
import urllib.request
import urllib.parse
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuración desde variables de entorno
# ─────────────────────────────────────────────────────────────────────────────

def _get_env_or_raise(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Variable de entorno '{key}' no está configurada. "
            f"Cópiala desde examples/.env.example y ajusta el valor."
        )
    return val


# ─────────────────────────────────────────────────────────────────────────────
# Envío de mensajes de texto
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram_message(
    text: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "Markdown",
) -> bool:
    """
    Envía un mensaje de texto plano a Telegram.

    Args:
        text:       Contenido del mensaje (admite Markdown).
        bot_token:  Token del bot. Si None, usa la variable de entorno TELEGRAM_BOT_TOKEN.
        chat_id:    ID del chat. Si None, usa la variable de entorno TELEGRAM_CHAT_ID.
        parse_mode: Modo de parseo del texto ("Markdown" o "HTML").

    Returns:
        True si el mensaje se envió correctamente, False en caso de error.
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = chat_id   or os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no están configurados.")
        return False

    url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"❌ Error al enviar mensaje: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Envío de imágenes (gráficos)
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram_photo(
    photo_path: str,
    caption: str = "",
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """
    Envía una imagen (PNG/JPG) a Telegram con leyenda opcional.

    Args:
        photo_path: Ruta local de la imagen.
        caption:    Leyenda del gráfico (admite Markdown).
        bot_token:  Token del bot (o lee TELEGRAM_BOT_TOKEN).
        chat_id:    ID del chat (o lee TELEGRAM_CHAT_ID).

    Returns:
        True si se envió correctamente.
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = chat_id   or os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no están configurados.")
        return False

    path = Path(photo_path)
    if not path.exists():
        print(f"❌ Error: La imagen '{photo_path}' no existe.")
        return False

    url      = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    boundary = "----TelegramFormBoundary" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    parts: list[bytes] = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode(),
    ]
    if caption:
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode()
        )
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"parse_mode\"\r\n\r\nMarkdown\r\n".encode()
        )

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "image/png"
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode()
    )

    with open(path, "rb") as f:
        parts.append(f.read())
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req  = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))

    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"❌ Error al enviar imagen: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Alerta de cruce de medias móviles
# ─────────────────────────────────────────────────────────────────────────────

def format_crossover_alert(
    signal_info: dict,
    symbol: str = "ASSET",
    timeframe: str = "1D",
    price: Optional[float] = None,
) -> str:
    """
    Genera el texto formateado (Markdown) para una alerta de cruce de medias.

    Args:
        signal_info: dict devuelto por ``MACrossover.get_latest_signal()``.
        symbol:      Nombre del activo (ej. "BTC/USDT", "AAPL").
        timeframe:   Marco temporal (ej. "1H", "4H", "1D").
        price:       Precio de cierre actual (opcional).

    Returns:
        Cadena de texto en formato Markdown lista para enviar a Telegram.
    """
    sig        = signal_info.get("signal", "")
    crossover  = signal_info.get("crossover", 0)
    ma_fast    = signal_info.get("ma_fast")
    ma_slow    = signal_info.get("ma_slow")
    fast_p     = signal_info.get("fast_period", 100)
    slow_p     = signal_info.get("slow_period", 200)
    ma_type    = signal_info.get("ma_type", "SMA")
    timestamp  = signal_info.get("timestamp")

    if crossover == 0:
        return ""  # sin cruce → sin alerta

    # Iconos según dirección
    if crossover == 1:
        direction_icon = "🟢 *LONG — GOLDEN CROSS*"
        description    = (
            f"La {ma_type} {fast_p} cruzó *hacia arriba* la {ma_type} {slow_p}.\n"
            f"Señal *alcista* confirmada."
        )
    else:
        direction_icon = "🔴 *SHORT — DEATH CROSS*"
        description    = (
            f"La {ma_type} {fast_p} cruzó *hacia abajo* la {ma_type} {slow_p}.\n"
            f"Señal *bajista* confirmada."
        )

    # Formatear timestamp
    ts_str = ""
    if timestamp:
        try:
            if hasattr(timestamp, "strftime"):
                ts_str = f"\n• *Hora:* {timestamp.strftime('%Y-%m-%d %H:%M')} UTC"
            else:
                ts_str = f"\n• *Hora:* {timestamp}"
        except Exception:
            ts_str = f"\n• *Hora:* {timestamp}"

    price_str = f"\n• *Precio actual:* `{price:.4f}`" if price is not None else ""

    message = (
        f"📡 *Alerta — Cruce de Medias Móviles*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• *Activo:* `{symbol}`\n"
        f"• *Timeframe:* `{timeframe}`"
        f"{ts_str}"
        f"{price_str}\n\n"
        f"{direction_icon}\n\n"
        f"{description}\n\n"
        f"• *{ma_type} {fast_p}:* `{ma_fast:.4f}`\n"
        f"• *{ma_type} {slow_p}:* `{ma_slow:.4f}`\n\n"
        f"🤖 _Generado por Polars-Talis_"
    )
    return message


def send_crossover_alert(
    signal_info: dict,
    symbol: str = "ASSET",
    timeframe: str = "1D",
    price: Optional[float] = None,
    chart_path: Optional[str] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """
    Envía una alerta de cruce de medias a Telegram cuando hay señal activa.

    Si no hay cruce en la última vela (signal_info["crossover"] == 0),
    la función retorna False sin enviar nada.

    Args:
        signal_info:  dict de ``MACrossover.get_latest_signal()``.
        symbol:       Nombre del activo.
        timeframe:    Marco temporal.
        price:        Precio de cierre actual.
        chart_path:   Ruta a imagen del gráfico (opcional).
        bot_token:    Token del bot (o lee TELEGRAM_BOT_TOKEN).
        chat_id:      ID del chat (o lee TELEGRAM_CHAT_ID).

    Returns:
        True si la alerta fue enviada, False si no había señal o hubo error.
    """
    if signal_info.get("crossover", 0) == 0:
        return False  # No hay cruce: no enviar nada

    message = format_crossover_alert(signal_info, symbol, timeframe, price)
    if not message:
        return False

    print(f"📤 Enviando alerta de cruce ({signal_info['signal']}) a Telegram…")

    # Si hay gráfico, enviar foto con la alerta como caption
    if chart_path and Path(chart_path).exists():
        ok = send_telegram_photo(chart_path, caption=message,
                                  bot_token=bot_token, chat_id=chat_id)
    else:
        ok = send_telegram_message(message, bot_token=bot_token, chat_id=chat_id)

    if ok:
        print(f"✅ Alerta enviada: {signal_info['signal']} — {symbol} [{timeframe}]")
    else:
        print("❌ Error al enviar la alerta.")

    return ok
