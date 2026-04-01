#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMI 无头计算器

计算逻辑提取自 core/indicators/dmi_item.py (DmiItem)
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any

from .base import HeadlessCalculator


class DMICalculator(HeadlessCalculator):
    """
    DMI 方向性运动指标计算器

    计算 PDI、MDI、ADX、ADXR，判断趋势方向和强度。

    Args:
        di_period: PDI/MDI 计算周期，默认 14
        adx_period: ADXR 计算周期，默认 7

    示例::

        calc = DMICalculator(14, 7)
        calc.update(am)
        values = calc.get_values()
        # {"pdi": ..., "mdi": ..., "adx": ..., "trend": "up", ...}
    """

    def __init__(self, di_period: int = 14, adx_period: int = 7):
        self.di_period = di_period
        self.adx_period = adx_period

        self._values: Dict[str, Any] = {}
        self._inited: bool = False
        self._prev_pdi: float = np.nan
        self._prev_mdi: float = np.nan

    # ------------------------------------------------------------------
    # 核心计算 —— 唯一的 talib 调用点，chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_arrays(high_array: np.ndarray,
                       low_array: np.ndarray,
                       close_array: np.ndarray,
                       di_period: int = 14,
                       adx_period: int = 7):
        """
        全量计算 DMI，返回四条 numpy 数组 (pdi, mdi, adx, adxr)。

        可被 chart item 直接调用以获取逐根 K 线的值。
        """
        pdi = talib.PLUS_DI(high_array, low_array, close_array, timeperiod=di_period)
        mdi = talib.MINUS_DI(high_array, low_array, close_array, timeperiod=di_period)
        adx = talib.ADX(high_array, low_array, close_array, timeperiod=di_period)
        adxr = talib.ADXR(high_array, low_array, close_array, timeperiod=adx_period)
        return pdi, mdi, adx, adxr

    def update(self, am) -> None:
        """基于 ArrayManager 更新 DMI 计算"""
        if not am.inited:
            return

        high_array = am.high_array
        low_array = am.low_array
        close_array = am.close_array

        try:
            pdi_array, mdi_array, adx_array, adxr_array = self.compute_arrays(
                high_array, low_array, close_array, self.di_period, self.adx_period
            )

            pdi = pdi_array[-1]
            mdi = mdi_array[-1]
            adx = adx_array[-1]
            adxr = adxr_array[-1]

            if any(np.isnan(v) for v in [pdi, mdi, adx, adxr]):
                return

            # 前一期数据
            prev_pdi = pdi_array[-2] if len(pdi_array) > 1 and not np.isnan(pdi_array[-2]) else self._prev_pdi
            prev_mdi = mdi_array[-2] if len(mdi_array) > 1 and not np.isnan(mdi_array[-2]) else self._prev_mdi

            # 趋势方向
            trend = "neutral"
            if pdi > mdi:
                trend = "up"
            elif mdi > pdi:
                trend = "down"

            # 趋势强度
            strength = "weak"
            if adx > 40:
                strength = "strong"
            elif adx > 25:
                strength = "moderate"

            current_price = close_array[-1]

            self._values = {
                "pdi": round(float(pdi), 2),
                "mdi": round(float(mdi), 2),
                "adx": round(float(adx), 2),
                "adxr": round(float(adxr), 2),
                "previous_pdi": round(float(prev_pdi), 2) if not np.isnan(prev_pdi) else None,
                "previous_mdi": round(float(prev_mdi), 2) if not np.isnan(prev_mdi) else None,
                "trend": trend,
                "trend_strength": strength,
                "current_price": round(float(current_price), 2),
            }

            self._prev_pdi = pdi
            self._prev_mdi = mdi
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
