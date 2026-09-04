"""
signals.py — Estrategias de cruce de medias móviles.

Detecta el cruce de la SMA/EMA de 100 períodos sobre la SMA/EMA de 200 períodos
en cualquier timeframe, generando señales LONG y SHORT.
"""

import polars as pl
from typing import Optional, List, Literal
from ..core.base import BaseIndicator, IndicatorConfig, IndicatorType


class MACrossover(BaseIndicator):
    """
    Estrategia de cruce de Media Móvil 100 → Media Móvil 200.

    Detecta el momento exacto en que la MA rápida (100) cruza a la MA lenta (200):
      - LONG  (+1): MA_100 cruza hacia ARRIBA de MA_200  (cruce alcista / Golden Cross)
      - SHORT (-1): MA_100 cruza hacia ABAJO  de MA_200  (cruce bajista / Death Cross)
      - SIN SEÑAL (0): sin cruce en esa vela

    Funciona con cualquier timeframe. Por defecto usa SMA; se puede elegir EMA.

    Columnas de salida:
      - ``MA_100``        : Media móvil de 100 períodos
      - ``MA_200``        : Media móvil de 200 períodos
      - ``MA_crossover``  : Señal de cruce  (+1 LONG, -1 SHORT, 0 sin cruce)
      - ``MA_signal``     : Etiqueta textual  ("LONG", "SHORT", "")
    """

    def __init__(
        self,
        fast_period: int = 100,
        slow_period: int = 200,
        ma_type: Literal["SMA", "EMA"] = "SMA",
        column: str = "close",
        name: Optional[str] = None,
    ):
        """
        Args:
            fast_period: Período de la MA rápida (por defecto 100).
            slow_period: Período de la MA lenta  (por defecto 200).
            ma_type:     Tipo de media móvil, "SMA" o "EMA".
            column:      Columna de precio a usar (por defecto "close").
            name:        Prefijo personalizado para las columnas de salida.
        """
        prefix = name or f"MA"
        config = IndicatorConfig(
            name=name or f"MACrossover_{fast_period}_{slow_period}",
            type=IndicatorType.TREND,
            params={
                "fast_period": fast_period,
                "slow_period": slow_period,
                "ma_type": ma_type,
                "column": column,
                "prefix": prefix,
            },
            output_columns=[
                f"{prefix}_{fast_period}",
                f"{prefix}_{slow_period}",
                f"{prefix}_crossover",
                f"{prefix}_signal",
            ],
        )
        super().__init__(config)

    def _validate_config(self) -> None:
        p = self.config.params
        if p["fast_period"] <= 0 or p["slow_period"] <= 0:
            raise ValueError("Los períodos deben ser enteros positivos.")
        if p["fast_period"] >= p["slow_period"]:
            raise ValueError(
                f"fast_period ({p['fast_period']}) debe ser menor que "
                f"slow_period ({p['slow_period']})."
            )
        if p["ma_type"] not in ("SMA", "EMA"):
            raise ValueError("ma_type debe ser 'SMA' o 'EMA'.")

    def _calculate(self, df: pl.DataFrame) -> pl.DataFrame:
        p = self.config.params
        column = p["column"]
        fast = p["fast_period"]
        slow = p["slow_period"]
        ma_type = p["ma_type"]
        out_fast, out_slow, out_cross, out_signal = self.config.output_columns

        # ── Calcular las dos medias móviles ──────────────────────────────────
        if ma_type == "SMA":
            result = df.with_columns([
                pl.col(column).rolling_mean(window_size=fast).alias(out_fast),
                pl.col(column).rolling_mean(window_size=slow).alias(out_slow),
            ])
        else:  # EMA
            alpha_fast = 2 / (fast + 1)
            alpha_slow = 2 / (slow + 1)
            result = df.with_columns([
                pl.col(column).ewm_mean(alpha=alpha_fast).alias(out_fast),
                pl.col(column).ewm_mean(alpha=alpha_slow).alias(out_slow),
            ])

        # ── Detectar cruce (diferencia entre MA_fast y MA_slow) ──────────────
        # diff_prev > 0 → MA_fast estaba por encima la vela anterior
        # diff_curr < 0 → MA_fast está por debajo ahora → CRUCE BAJISTA (SHORT)
        result = result.with_columns([
            (pl.col(out_fast) - pl.col(out_slow)).alias("_diff")
        ]).with_columns([
            pl.col("_diff").shift(1).alias("_diff_prev")
        ]).with_columns([
            pl.when(
                # Cruce ALCISTA: vela anterior diff < 0,  ahora diff >= 0
                (pl.col("_diff_prev") < 0) & (pl.col("_diff") >= 0)
            ).then(pl.lit(1))
            .when(
                # Cruce BAJISTA: vela anterior diff > 0,  ahora diff <= 0
                (pl.col("_diff_prev") > 0) & (pl.col("_diff") <= 0)
            ).then(pl.lit(-1))
            .otherwise(pl.lit(0))
            .alias(out_cross)
        ]).with_columns([
            pl.when(pl.col(out_cross) == 1).then(pl.lit("LONG"))
            .when(pl.col(out_cross) == -1).then(pl.lit("SHORT"))
            .otherwise(pl.lit(""))
            .alias(out_signal)
        ]).drop(["_diff", "_diff_prev"])

        return result

    def get_required_columns(self) -> List[str]:
        return [self.config.params["column"]]

    def get_latest_signal(self, df: pl.DataFrame) -> dict:
        """
        Calcula los indicadores y devuelve la señal de la última vela.

        Returns:
            dict con claves: crossover (int), signal (str), ma_fast (float),
            ma_slow (float), timestamp (si existe columna 'date' o 'time').
        """
        result = self._calculate(df)
        last = result.tail(1).to_dicts()[0]
        out_fast, out_slow, out_cross, out_signal = self.config.output_columns
        info = {
            "crossover": last[out_cross],
            "signal": last[out_signal],
            "ma_fast": last[out_fast],
            "ma_slow": last[out_slow],
            "fast_period": self.config.params["fast_period"],
            "slow_period": self.config.params["slow_period"],
            "ma_type": self.config.params["ma_type"],
        }
        # Añadir timestamp si existe
        for ts_col in ("date", "time", "timestamp", "datetime"):
            if ts_col in last:
                info["timestamp"] = last[ts_col]
                break
        return info
