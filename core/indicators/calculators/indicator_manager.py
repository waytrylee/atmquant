#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标管理器

在 CTA 策略中统一管理多个无头指标计算器。
每个时间周期可创建独立的 IndicatorManager 实例，天然支持多周期。

使用示例::

    from core.indicators.calculators import (
        IndicatorManager, MACDCalculator, RSICalculator,
        SupertrendCalculator, BollCalculator
    )

    class MyStrategy(CtaTemplate):
        def on_init(self):
            self.am = ArrayManager(size=100)
            self.indicators = IndicatorManager()
            self.indicators.add("macd", MACDCalculator(12, 26, 9))
            self.indicators.add("rsi", RSICalculator(14))
            self.indicators.add("supertrend", SupertrendCalculator(10, 3.0))
            self.indicators.add("boll", BollCalculator(20, 2.0))

            # 高周期
            self.ham = ArrayManager(size=100)
            self.htf_indicators = IndicatorManager()
            self.htf_indicators.add("supertrend", SupertrendCalculator(10, 3.0))

            self.load_bar(30)

        def on_bar(self, bar: BarData):
            self.am.update_bar(bar)
            if not self.am.inited:
                return

            self.indicators.update(self.am)

            macd = self.indicators.get("macd").get_values()
            rsi = self.indicators.get("rsi").get_values()
            st = self.indicators.get("supertrend").get_values()

            if st["direction"] == "up" and macd["cross_signal"] == "golden_cross":
                self.buy(bar.close_price, 1)

        def on_htf_bar(self, bar: BarData):
            self.ham.update_bar(bar)
            self.htf_indicators.update(self.ham)
"""

from typing import Dict, Any, Optional
from .base import HeadlessCalculator


class IndicatorManager:
    """
    指标管理器 - 在 CTA 策略中统一管理所有无头指标计算器

    特点：
    - 零 Qt 依赖
    - 一次 update() 更新所有指标
    - 支持按名称获取指标
    - get_all_values() 一次获取所有指标当前值
    """

    def __init__(self):
        self._calculators: Dict[str, HeadlessCalculator] = {}

    def add(self, name: str, calculator: HeadlessCalculator) -> "IndicatorManager":
        """
        添加指标计算器。

        Args:
            name: 指标名称（如 "macd"、"rsi"）
            calculator: HeadlessCalculator 实例

        Returns:
            self，支持链式调用
        """
        self._calculators[name] = calculator
        return self

    def remove(self, name: str) -> None:
        """移除指标计算器"""
        self._calculators.pop(name, None)

    def update(self, am) -> None:
        """
        一次性更新所有指标计算器。

        Args:
            am: vnpy.trader.utility.ArrayManager 实例
        """
        for calc in self._calculators.values():
            calc.update(am)

    def get(self, name: str) -> Optional[HeadlessCalculator]:
        """
        按名称获取指标计算器。

        Args:
            name: 指标名称

        Returns:
            对应的 HeadlessCalculator 实例，不存在则返回 None
        """
        return self._calculators.get(name)

    def get_values(self, name: str) -> Dict[str, Any]:
        """
        获取指定指标的当前值。

        Args:
            name: 指标名称

        Returns:
            指标值字典，指标不存在或未初始化返回空字典
        """
        calc = self._calculators.get(name)
        if calc and calc.inited:
            return calc.get_values()
        return {}

    def get_all_values(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有已初始化指标的当前值。

        Returns:
            {指标名: 指标值字典} 的嵌套字典
        """
        result = {}
        for name, calc in self._calculators.items():
            if calc.inited:
                result[name] = calc.get_values()
        return result

    @property
    def all_inited(self) -> bool:
        """所有指标是否都已初始化"""
        if not self._calculators:
            return False
        return all(calc.inited for calc in self._calculators.values())

    @property
    def names(self) -> list:
        """已注册的指标名称列表"""
        return list(self._calculators.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._calculators

    def __len__(self) -> int:
        return len(self._calculators)

    def __repr__(self) -> str:
        items = [f"{name}({'ok' if calc.inited else 'pending'})"
                 for name, calc in self._calculators.items()]
        return f"IndicatorManager([{', '.join(items)}])"
