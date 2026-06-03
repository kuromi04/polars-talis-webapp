import os
import urllib.request
import urllib.parse
import mimetypes
import json
import polars as pl
from pathlib import Path
from datetime import datetime

# Importar polars_talis
import sys
sys.path.append(str(Path(__file__).parent.parent))
from polars_talis import TechnicalAnalyzer, SMA, EMA, RSI, MACD, BollingerBands

# Configuración por defecto o cargada de variables de entorno
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str) -> bool:
    """Envía un mensaje de texto a Telegram usando urllib"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Error: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no están configurados.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"❌ Error al enviar mensaje: {e}")
        return False

def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """Envía una imagen a Telegram usando urllib multipart/form-data"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Error: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no están configurados.")
        return False
    
    path = Path(photo_path)
    if not path.exists():
        print(f"❌ Error: La imagen {photo_path} no existe.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    boundary = "----TelegramFormBoundary" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Construir cuerpo multipart/form-data
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TELEGRAM_CHAT_ID}\r\n".encode("utf-8"))
    if caption:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"parse_mode\"\r\n\r\nMarkdown\r\n".encode("utf-8"))
        
    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "image/png"
    
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode("utf-8")
    )
    
    with open(path, "rb") as f:
        img_data = f.read()
        
    parts.append(img_data)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    
    body = b"".join(parts)
    
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"❌ Error al enviar imagen: {e}")
        return False

def analyze_and_alert():
    """Calcula indicadores y envía alerta resumen con gráficos a Telegram"""
    print("📈 Iniciando análisis técnico de alerta...")
    
    # Generar datos simulados (para el ejemplo)
    from create_visualizations import generate_sample_data, create_price_and_trend_chart
    df = generate_sample_data(100) # 100 velas
    
    analyzer = TechnicalAnalyzer(max_workers=4)
    analyzer.add_indicators([
        SMA(20),
        SMA(50),
        EMA(12),
        RSI(14),
        BollingerBands(20)
    ])
    
    result = analyzer.calculate(df)
    
    # Obtener el último registro
    last_row = result.tail(1).to_dicts()[0]
    date_str = last_row["date"].strftime("%Y-%m-%d")
    price = last_row["close"]
    rsi = last_row["RSI_14"]
    sma_20 = last_row["SMA_20"]
    sma_50 = last_row["SMA_50"]
    
    # Condición de ejemplo para el trader
    trend = "Alcista 🟢" if price > sma_20 else "Bajista 🔴"
    rsi_status = "Neutral"
    if rsi < 30:
        rsi_status = "Sobreventa 🔥 (Oportunidad de Compra)"
    elif rsi > 70:
        rsi_status = "Sobrecompra ⚠️ (Oportunidad de Venta)"
        
    summary_message = (
        f"📊 *Alerta de Mercado - {date_str}*\n\n"
        f"• *Precio Actual:* ${price:.2f}\n"
        f"• *Tendencia (vs SMA 20):* {trend}\n"
        f"• *RSI (14):* {rsi:.2f} ({rsi_status})\n"
        f"• *SMA (50):* ${sma_50:.2f}\n\n"
        f"🚀 _Alerta automatizada generada por Polars-Talis y Termux._"
    )
    
    print("📤 Enviando mensaje de resumen a Telegram...")
    if send_telegram_message(summary_message):
        print("✅ Resumen enviado exitosamente.")
    else:
        print("❌ Falló el envío del resumen.")
        
    # Generar el gráfico y guardarlo
    image_path = Path(__file__).parent.parent / "images" / "price_trends.png"
    if image_path.exists():
        print(f"📤 Enviando gráfico {image_path.name} a Telegram...")
        if send_telegram_photo(str(image_path), caption="📈 Gráfico de Tendencia de Precios"):
            print("✅ Gráfico enviado exitosamente.")
        else:
            print("❌ Falló el envío del gráfico.")

if __name__ == "__main__":
    # Cargar archivo .env local si existe
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()
                    
    # Actualizar variables locales tras lectura de .env
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    analyze_and_alert()
