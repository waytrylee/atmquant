#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期 SMA 无头计算器

计算逻辑提取自 core/indicators/multi_sma_item.py (MultiSmaItem)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any, Tuple

from .base import HeadlessCalculator


class SMACalculator(HeadlessCalculator):
    """
    多周期简单移动平均线(SMA)计算器

    同时计算多个周期的 SMA 值，检测均线排列和交叉。

    Args:
        periods: SMA 周期元组，默认 (25, 60, 100)

    示例::

        calc = SMACalculator((25, 60, 100))
        calc.update(am)
        values = calc.get_values()
        # {"sma_25": ..., "sma_60": ..., "sma_100": ..., "arrangement": "bullish", ...}
    """

    def __init__(self, periods: Tuple[int, ...] = (25, 60, 100)):
        self.periods = periods
        self._values: Dict[str, Any] = {}
        self._inited: bool = False

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_array(close_array: np.ndarray, period: int) -> np.ndarray:
        """
        计算单个周期的 SMA 全量数组。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        return talib.SMA(close_array, timeperiod=period)

    def update(self, am) -> None:
        """基于 ArrayManager 更新 SMA 计算"""
        if not am.inited:
            return

        close_array = am.close_array

        try:
            sma_values = {}
            prev_sma_values = {}

            for period in self.periods:
                sma_array = self.compute_array(close_array, period)
                val = sma_array[-1]
                prev_val = sma_array[-2] if len(sma_array) > 1 else np.nan

                if np.isnan(val):
                    return  # 任何一个周期数据不足就不输出

                sma_values[period] = float(val)
                prev_sma_values[period] = float(prev_val) if not np.isnan(prev_val) else None

            current_price = float(close_array[-1])

            # 判断均线排列
            sorted_periods = sorted(self.periods)
            current_sma_vals = [sma_values[p] for p in sorted_periods]

            arrangement = "neutral"
            if len(current_sma_vals) >= 2:
                # 多头排列：短期 > 长期
                if all(current_sma_vals[i] >= current_sma_vals[i+1]
                       for i in range(len(current_sma_vals) - 1)):
                    arrangement = "bullish"
                # 空头排列：短期 < 长期
                elif all(current_sma_vals[i] <= current_sma_vals[i+1]
                         for i in range(len(current_sma_vals) - 1)):
                    arrangement = "bearish"

            # 构建结果
            result = {
                "current_price": round(current_price, 2),
                "arrangement": arrangement,
            }

            for period in self.periods:
                result[f"sma_{period}"] = round(sma_values[period], 2)
                if prev_sma_values[period] is not None:
                    result[f"prev_sma_{period}"] = round(prev_sma_values[period], 2)

            self._values = result
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
