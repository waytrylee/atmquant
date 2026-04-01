#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期 EMA 无头计算器

计算逻辑提取自 core/indicators/multi_ema_item.py (MultiEmaItem)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any, Tuple

from .base import HeadlessCalculator


class EMACalculator(HeadlessCalculator):
    """
    多周期指数移动平均线(EMA)计算器

    同时计算多个周期的 EMA 值，检测均线排列。

    Args:
        periods: EMA 周期元组，默认 (9, 20, 60)

    示例::

        calc = EMACalculator((9, 20, 60))
        calc.update(am)
        values = calc.get_values()
        # {"ema_9": ..., "ema_20": ..., "ema_60": ..., "arrangement": "bullish", ...}
    """

    def __init__(self, periods: Tuple[int, ...] = (9, 20, 60)):
        self.periods = periods
        self._values: Dict[str, Any] = {}
        self._inited: bool = False

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_array(close_array: np.ndarray, period: int) -> np.ndarray:
        """
        计算单个周期的 EMA 全量数组。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        return talib.EMA(close_array, timeperiod=period)

    def update(self, am) -> None:
        """基于 ArrayManager 更新 EMA 计算"""
        if not am.inited:
            return

        close_array = am.close_array

        try:
            ema_values = {}
            prev_ema_values = {}

            for period in self.periods:
                ema_array = self.compute_array(close_array, period)
                val = ema_array[-1]
                prev_val = ema_array[-2] if len(ema_array) > 1 else np.nan

                if np.isnan(val):
                    return  # 任何一个周期数据不足就不输出

                ema_values[period] = float(val)
                prev_ema_values[period] = float(prev_val) if not np.isnan(prev_val) else None

            current_price = float(close_array[-1])

            # 判断均线排列
            sorted_periods = sorted(self.periods)
            current_ema_vals = [ema_values[p] for p in sorted_periods]

            arrangement = "neutral"
            if len(current_ema_vals) >= 2:
                # 多头排列：短期 > 长期
                if all(current_ema_vals[i] >= current_ema_vals[i+1]
                       for i in range(len(current_ema_vals) - 1)):
                    arrangement = "bullish"
                # 空头排列：短期 < 长期
                elif all(current_ema_vals[i] <= current_ema_vals[i+1]
                         for i in range(len(current_ema_vals) - 1)):
                    arrangement = "bearish"

            # 构建结果
            result = {
                "current_price": round(current_price, 2),
                "arrangement": arrangement,
            }

            for period in self.periods:
                result[f"ema_{period}"] = round(ema_values[period], 2)
                if prev_ema_values[period] is not None:
                    result[f"prev_ema_{period}"] = round(prev_ema_values[period], 2)

            self._values = result
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
