#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Volume 无头计算器

计算逻辑提取自 core/indicators/enhanced_volume_item.py
零 Qt 依赖，基于 ArrayManager 计算。
"""

import numpy as np
import talib
from typing import Dict, Any

from .base import HeadlessCalculator


class VolumeCalculator(HeadlessCalculator):
    """
    增强版成交量指标计算器

    计算成交量均线、尖峰识别、买卖量分解等。

    Args:
        ma_period: 成交量MA周期，默认 20
        spike_threshold: 尖峰识别倍数，默认 2.0
    """

    def __init__(self, ma_period: int = 20, spike_threshold: float = 2.0):
        self.ma_period = ma_period
        self.spike_threshold = spike_threshold
        self._values: Dict[str, Any] = {}
        self._inited: bool = False

    # ------------------------------------------------------------------
    # 核心计算 —— chart item 也复用此方法
    # ------------------------------------------------------------------
    @staticmethod
    def compute_array(volume_array: np.ndarray, ma_period: int = 20):
        """
        计算成交量 SMA 均线。

        Returns:
            vol_ma — 成交量移动平均数组
        """
        vol_ma = talib.SMA(volume_array, timeperiod=ma_period)
        return vol_ma

    def update(self, am) -> None:
        """基于 ArrayManager 更新成交量指标计算"""
        if not am.inited:
            return

        close_array = am.close_array
        volume_array = am.volume_array
        high_array = am.high_array
        low_array = am.low_array

        if len(volume_array) < self.ma_period:
            return

        try:
            vol_ma = self.compute_array(volume_array, self.ma_period)

            current_vol = volume_array[-1]
            current_ma = vol_ma[-1]

            if np.isnan(current_ma) or current_ma <= 0:
                return

            vol_ratio = current_vol / current_ma

            # 成交量状态
            if vol_ratio >= self.spike_threshold:
                volume_status = "Spike"
            elif vol_ratio >= 1.2:
                volume_status = "High"
            else:
                volume_status = "Normal"

            # 买卖量分解
            h = high_array[-1]
            l = low_array[-1]
            c = close_array[-1]
            if h != l and current_vol > 0:
                buy_ratio = (c - l) / (h - l)
                sell_ratio = (h - c) / (h - l)
            else:
                buy_ratio = 0.0
                sell_ratio = 0.0

            buy_vol = current_vol * buy_ratio
            sell_vol = current_vol * sell_ratio
            bs_ratio = buy_vol / sell_vol if sell_vol > 0 else float('inf')

            # 成交量变化
            prev_vol = volume_array[-2] if len(volume_array) > 1 else 0
            vol_change = ((current_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0

            self._values = {
                "current_volume": int(current_vol),
                "avg_volume": int(current_ma),
                "volume_ratio": round(float(vol_ratio), 2),
                "volume_status": volume_status,
                "volume_change_pct": round(float(vol_change), 2),
                "buy_volume": round(float(buy_vol), 2),
                "sell_volume": round(float(sell_vol), 2),
                "buy_ratio": round(float(buy_ratio * 100), 2),
                "sell_ratio": round(float(sell_ratio * 100), 2),
                "buy_sell_ratio": round(float(bs_ratio), 2),
                "is_spike": vol_ratio >= self.spike_threshold,
            }
            self._inited = True

        except Exception:
            pass

    def get_values(self) -> Dict[str, Any]:
        return self._values

    @property
    def inited(self) -> bool:
        return self._inited
