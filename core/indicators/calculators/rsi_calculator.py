#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI 无头计算器

计算逻辑提取自 core/indicators/rsi_item.py (RsiItem)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any

from .base import HeadlessCalculator


class RSICalculator(HeadlessCalculator):
    """
    RSI 相对强弱指标计算器

    计算 RSI 值，判断超买超卖状态和趋势方向。

    Args:
        period: RSI 计算周期，默认 14
        overbought: 超买阈值，默认 70
        oversold: 超卖阈值，默认 30

    示例::

        calc = RSICalculator(14, 70, 30)
        calc.update(am)
        values = calc.get_values()
        # {"value": 65.3, "overbought": False, "oversold": False, ...}
    """

    def __init__(self, period: int = 14, overbought: float = 70.0,
                 oversold: float = 30.0):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

        self._values: Dict[str, Any] = {}
        self._inited: bool = False
        self._prev_rsi: float = np.nan

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_array(close_array: np.ndarray, period: int = 14) -> np.ndarray:
        """
        计算 RSI 全量数组。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        return talib.RSI(close_array, timeperiod=period)

    def update(self, am) -> None:
        """基于 ArrayManager 更新 RSI 计算"""
        if not am.inited:
            return

        close_array = am.close_array

        try:
            rsi_array = self.compute_array(close_array, self.period)

            rsi_value = rsi_array[-1]
            if np.isnan(rsi_value):
                return

            prev_rsi = rsi_array[-2] if len(rsi_array) > 1 and not np.isnan(rsi_array[-2]) else self._prev_rsi

            # 趋势判断
            trend = "neutral"
            if not np.isnan(prev_rsi):
                if rsi_value > prev_rsi:
                    trend = "up"
                elif rsi_value < prev_rsi:
                    trend = "down"

            # 超买超卖
            is_overbought = rsi_value >= self.overbought
            is_oversold = rsi_value <= self.oversold

            current_price = close_array[-1]

            self._values = {
                "value": round(float(rsi_value), 1),
                "previous": round(float(prev_rsi), 1) if not np.isnan(prev_rsi) else None,
                "trend": trend,
                "overbought": is_overbought,
                "oversold": is_oversold,
                "current_price": round(float(current_price), 2),
                "thresholds": {
                    "long": self.overbought,
                    "short": self.oversold
                }
            }

            self._prev_rsi = rsi_value
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
