#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 无头计算器

计算逻辑提取自 core/indicators/macd_item.py (Macd3Item)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any, Optional

from .base import HeadlessCalculator


class MACDCalculator(HeadlessCalculator):
    """
    MACD 指标计算器

    计算 DIFF、DEA（Signal）、MACD 柱状图值，
    检测金叉/死叉信号，判断趋势方向。

    Args:
        fast_period: 快速 EMA 周期，默认 12
        slow_period: 慢速 EMA 周期，默认 26
        signal_period: 信号线周期，默认 9

    示例::

        calc = MACDCalculator(12, 26, 9)
        calc.update(am)
        values = calc.get_values()
        # {
        #     "macd": float, "diff": float, "signal": float,
        #     "histogram": float, "trend": str,
        #     "cross_signal": str or None, ...
        # }
    """

    def __init__(self, fast_period: int = 12, slow_period: int = 26,
                 signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        self._values: Dict[str, Any] = {}
        self._inited: bool = False

        # 用于交叉检测的前一期数据
        self._prev_diff: float = np.nan
        self._prev_dea: float = np.nan
        self._prev_histogram: float = np.nan

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_arrays(close_array: np.ndarray,
                       fast_period: int = 12,
                       slow_period: int = 26,
                       signal_period: int = 9):
        """
        全量计算 MACD，返回三条 numpy 数组 (diff, dea, macd_hist)。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        diffs, deas, macds = talib.MACD(
            close_array,
            fastperiod=fast_period,
            slowperiod=slow_period,
            signalperiod=signal_period
        )
        return diffs, deas, macds

    @staticmethod
    def compute_ema(values: np.ndarray, period: int) -> np.ndarray:
        """计算 EMA，供 chart item 中对 DEA 做二次平滑时使用。"""
        return talib.EMA(values, timeperiod=period)

    def update(self, am) -> None:
        """基于 ArrayManager 更新 MACD 计算"""
        if not am.inited:
            return

        close_array = am.close_array

        # 计算所需最少数据量
        min_required = self.slow_period + self.signal_period * 2
        valid_count = np.sum(~np.isnan(close_array) & (close_array != 0))
        if valid_count < min_required:
            return

        try:
            # 使用 talib 计算 MACD
            diffs, deas, macds = self.compute_arrays(
                close_array, self.fast_period, self.slow_period, self.signal_period
            )

            # 获取当前值
            diff = diffs[-1]
            dea = deas[-1]
            macd_hist = macds[-1]

            if np.isnan(diff) or np.isnan(dea) or np.isnan(macd_hist):
                return

            # 获取前一期值
            prev_diff = diffs[-2] if len(diffs) > 1 and not np.isnan(diffs[-2]) else self._prev_diff
            prev_dea = deas[-2] if len(deas) > 1 and not np.isnan(deas[-2]) else self._prev_dea
            prev_histogram = macds[-2] if len(macds) > 1 and not np.isnan(macds[-2]) else self._prev_histogram

            # 趋势判断
            trend = "up" if macd_hist > 0 else "down" if macd_hist < 0 else "neutral"

            # 金叉/死叉检测
            cross_signal = None
            if not np.isnan(prev_diff) and not np.isnan(prev_dea):
                if prev_diff <= prev_dea and diff > dea:
                    cross_signal = "golden_cross"
                elif prev_diff >= prev_dea and diff < dea:
                    cross_signal = "death_cross"

            # 当前收盘价
            current_price = close_array[-1]

            self._values = {
                "macd": round(float(macd_hist), 4),
                "diff": round(float(diff), 4),
                "signal": round(float(dea), 4),
                "histogram": round(float(macd_hist), 4),
                "previous_histogram": round(float(prev_histogram), 4) if not np.isnan(prev_histogram) else None,
                "trend": trend,
                "cross_signal": cross_signal,
                "current_price": round(float(current_price), 2),
                "parameters": {
                    "fast_period": self.fast_period,
                    "slow_period": self.slow_period,
                    "signal_period": self.signal_period
                }
            }

            # 保存前一期数据
            self._prev_diff = diff
            self._prev_dea = dea
            self._prev_histogram = macd_hist

            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
