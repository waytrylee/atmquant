#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带无头计算器

计算逻辑提取自 core/indicators/boll_item.py (BollItem)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any

from .base import HeadlessCalculator


class BollCalculator(HeadlessCalculator):
    """
    布林带指标计算器

    计算上轨、中轨、下轨，判断挤压状态和价格位置。

    Args:
        period: 布林带周期，默认 20
        std_dev: 标准差倍数，默认 2.0

    示例::

        calc = BollCalculator(20, 2.0)
        calc.update(am)
        values = calc.get_values()
        # {"upper": ..., "middle": ..., "lower": ..., "width": ..., ...}
    """

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        self.period = period
        self.std_dev = std_dev

        self._values: Dict[str, Any] = {}
        self._inited: bool = False
        self._prev_width: float = np.nan

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_arrays(close_array: np.ndarray,
                       period: int = 20,
                       std_dev: float = 2.0):
        """
        全量计算布林带，返回三条 numpy 数组 (upper, middle, lower)。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        upper, middle, lower = talib.BBANDS(
            close_array,
            timeperiod=period,
            nbdevup=std_dev,
            nbdevdn=std_dev,
            matype=0,
        )
        return upper, middle, lower

    def update(self, am) -> None:
        """基于 ArrayManager 更新布林带计算"""
        if not am.inited:
            return

        try:
            upper_array, middle_array, lower_array = self.compute_arrays(
                am.close_array, self.period, self.std_dev
            )

            upper = upper_array[-1]
            middle = middle_array[-1]
            lower = lower_array[-1]

            if np.isnan(upper) or np.isnan(middle) or np.isnan(lower):
                return

            width = upper - lower
            current_price = am.close_array[-1]

            # 获取前一期数据
            prev_upper = upper_array[-2] if len(upper_array) > 1 else np.nan
            prev_middle = middle_array[-2] if len(middle_array) > 1 else np.nan
            prev_lower = lower_array[-2] if len(lower_array) > 1 else np.nan

            # 挤压判断
            squeeze = False
            prev_width = self._prev_width
            if not np.isnan(prev_width) and prev_width > 0:
                if width < prev_width * 0.8:
                    squeeze = True

            self._values = {
                "upper": round(float(upper), 2),
                "middle": round(float(middle), 2),
                "lower": round(float(lower), 2),
                "previous_upper": round(float(prev_upper), 2) if not np.isnan(prev_upper) else None,
                "previous_middle": round(float(prev_middle), 2) if not np.isnan(prev_middle) else None,
                "previous_lower": round(float(prev_lower), 2) if not np.isnan(prev_lower) else None,
                "width": round(float(width), 2),
                "squeeze": squeeze,
                "current_price": round(float(current_price), 2),
                "parameters": {
                    "window": self.period,
                    "std_dev": self.std_dev
                }
            }

            self._prev_width = width
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
