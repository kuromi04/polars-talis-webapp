"""
ma_crossover_alert.py — Ejemplo completo de la estrategia de cruce MA 100/200.

Ejecuta el análisis de cruce de medias móviles y envía la alerta a Telegram
si se detecta un cruce en la última vela del dataset.

Uso:
    1. Copia examples/.env.example → examples/.env y rellena tus credenciales.
    2. Ejecuta: python examples/ma_crossover_alert.py

Variables de entorno requeridas:
    TELEGRAM_BOT_TOKEN — Token del bot provisto por @BotFather
    TELEGRAM_CHAT_ID   — ID de tu chat (obtenlo escribiendo a @userinfobot)
"""

import os
import sys
import polars as pl
import numpy as np
import matplotlib
matplotlib.use("Agg")          # Sin pantalla (Termux / headless)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path

# ── Añadir raíz del proyecto al path ─────────────────────────────────────────
sys.path.append(str(Path(__file__).parent.parent))

from polars_talis import (
    TechnicalAnalyzer,
    MACrossover,
    send_crossover_alert,
    send_telegram_message,
)


# ─────────────────────────────────────────────────────────────────────────────
# Configuración del ejemplo
# ─────────────────────────────────────────────────────────────────────────────

SYMBOL    = "BTC/USDT"   # ← Cambia por el activo real que monitoreas
TIMEFRAME = "1D"         # ← Cambia por el timeframe real (ej. "4H", "1H", "15m")

# Ruta de la imagen del gráfico que se adjuntará a la alerta
CHART_PATH = Path(__file__).parent.parent / "images" / "ma_crossover.png"


# ─────────────────────────────────────────────────────────────────────────────
# Generación de datos simulados (reemplaza esto por tu fuente real de datos)
# ─────────────────────────────────────────────────────────────────────────────

def generate_sample_data(bars: int = 300, start_price: float = 30_000) -> pl.DataFrame:
    """
    Genera velas OHLCV sintéticas con un cruce MA100/MA200 forzado cerca del final,
    para poder ver la alerta en acción.

    En producción reemplaza esta función por datos reales de tu broker/exchange.
    """
    np.random.seed(0)
    start = datetime(2023, 1, 1)
    dates = [start + timedelta(days=i) for i in range(bars)]

    prices = [start_price]
    for i in range(1, bars):
        # Tendencia alcista inicial → bajista en la segunda mitad → alcista al final
        if i < bars // 2:
            drift = 0.002
        elif i < bars * 3 // 4:
            drift = -0.003
        else:
            drift = 0.004           # cruce alcista forzado al final

        change = np.random.normal(drift, 0.018)
        prices.append(max(prices[-1] * (1 + change), 100.0))

    volumes = np.random.randint(1_000, 50_000, bars).astype(int)

    return pl.DataFrame({
        "date":   dates,
        "close":  prices,
        "volume": volumes,
    }, strict=False)


# ─────────────────────────────────────────────────────────────────────────────
# Gráfico del cruce de medias
# ─────────────────────────────────────────────────────────────────────────────

def create_ma_crossover_chart(df: pl.DataFrame, signal_info: dict, save_path: Path) -> None:
    """Genera un gráfico PNG con las dos MAs y marca el cruce si existe."""
    fast_p  = signal_info["fast_period"]
    slow_p  = signal_info["slow_period"]
    ma_type = signal_info["ma_type"]

    out_fast   = f"MA_{fast_p}"
    out_slow   = f"MA_{slow_p}"
    out_cross  = f"MA_crossover"

    dates  = [d.date() for d in df["date"].to_list()]
    close  = df["close"].to_list()
    ma100  = df[out_fast].to_list()
    ma200  = df[out_slow].to_list()
    cross  = df[out_cross].to_list()

    fig, ax = plt.subplots(figsize=(14, 7))
    plt.style.use("seaborn-v0_8-darkgrid")

    ax.plot(dates, close, label="Precio cierre", linewidth=1.5, color="#4FC3F7", alpha=0.85)
    ax.plot(dates, ma100, label=f"{ma_type} {fast_p}", linewidth=2, color="#FFD54F")
    ax.plot(dates, ma200, label=f"{ma_type} {slow_p}", linewidth=2, color="#EF9A9A")

    # Marcar cruces
    for i, (d, c) in enumerate(zip(dates, cross)):
        if c == 1:
            ax.axvline(x=d, color="lime", linewidth=2, linestyle="--", alpha=0.9)
            ax.annotate("LONG ▲", xy=(d, close[i]), xytext=(0, 20),
                        textcoords="offset points", ha="center",
                        color="lime", fontweight="bold", fontsize=9)
        elif c == -1:
            ax.axvline(x=d, color="tomato", linewidth=2, linestyle="--", alpha=0.9)
            ax.annotate("SHORT ▼", xy=(d, close[i]), xytext=(0, -25),
                        textcoords="offset points", ha="center",
                        color="tomato", fontweight="bold", fontsize=9)

    ax.set_title(
        f"Estrategia de Cruce — {ma_type} {fast_p} / {ma_type} {slow_p}  |  {SYMBOL}  [{TIMEFRAME}]",
        fontsize=14, fontweight="bold", pad=15
    )
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Precio", fontsize=11)
    ax.legend(loc="upper left", frameon=True, fancybox=True, shadow=True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    plt.tight_layout()

    save_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(save_path), dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"📊 Gráfico guardado en: {save_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def run():
    """Pipeline completo: calcula, detecta cruce y envía alerta si corresponde."""

    print(f"\n{'='*55}")
    print(f"  📈  Estrategia MA Crossover — {SYMBOL}  [{TIMEFRAME}]")
    print(f"{'='*55}\n")

    # 1. Cargar datos (reemplaza generate_sample_data por tu fuente real)
    print("📥 Cargando datos…")
    df = generate_sample_data(bars=350)
    print(f"   {len(df)} velas cargadas.\n")

    # 2. Configurar la estrategia MA 100 / MA 200
    strategy = MACrossover(
        fast_period=100,
        slow_period=200,
        ma_type="SMA",      # Cambia a "EMA" si prefieres EMA
        column="close",
    )

    # 3. Calcular indicadores
    print("🔧 Calculando SMA 100 y SMA 200…")
    result_df = strategy._calculate(df)

    # 4. Obtener señal de la última vela
    signal_info = strategy.get_latest_signal(df)

    last_close = df["close"].tail(1).to_list()[0]
    last_date  = df["date"].tail(1).to_list()[0]

    print(f"\n📋 Última vela: {last_date.strftime('%Y-%m-%d') if hasattr(last_date, 'strftime') else last_date}")
    print(f"   Precio:   {last_close:.4f}")
    print(f"   SMA 100:  {signal_info['ma_fast']:.4f}")
    print(f"   SMA 200:  {signal_info['ma_slow']:.4f}")
    print(f"   Señal:    {signal_info['signal'] or 'Sin cruce'}")

    # 5. Generar gráfico
    print("\n🎨 Generando gráfico…")
    create_ma_crossover_chart(result_df, signal_info, CHART_PATH)

    # 6. Enviar alerta si hay cruce
    if signal_info["crossover"] != 0:
        print(f"\n🚨 ¡CRUCE DETECTADO! → {signal_info['signal']}")
        sent = send_crossover_alert(
            signal_info=signal_info,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            price=last_close,
            chart_path=str(CHART_PATH),
        )
        if not sent:
            print("⚠️  La alerta no pudo enviarse (revisa tus credenciales en .env).")
    else:
        print("\n💤 Sin cruce en la última vela. No se envía alerta.")
        # Opcional: enviar un resumen de estado aunque no haya cruce
        status_msg = (
            f"📊 *Estado MA Crossover — {SYMBOL} [{TIMEFRAME}]*\n\n"
            f"• SMA 100: `{signal_info['ma_fast']:.4f}`\n"
            f"• SMA 200: `{signal_info['ma_slow']:.4f}`\n"
            f"• Precio:  `{last_close:.4f}`\n\n"
            f"_Sin cruce activo en esta vela._\n"
            f"🤖 _Polars-Talis_"
        )
        # Descomenta para enviar el resumen aunque no haya cruce:
        # send_telegram_message(status_msg)

    print(f"\n{'='*55}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Cargar .env si existe
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    run()
