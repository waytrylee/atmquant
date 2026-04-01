#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无头指标计算器基类

零 Qt/pyqtgraph 依赖，纯 numpy/talib 计算。
设计用于 CTA 策略中直接复用 core/indicators/ 的指标计算逻辑，
无需渲染图表，支持回测和实盘（包括无 UI 运行）场景。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class HeadlessCalculator(ABC):
    """
    无头指标计算器基类

    所有计算器必须实现以下接口：
    - update(am): 基于 ArrayManager 更新计算
    - get_values(): 获取当前指标值（与图表指标的 get_current_values() 格式一致）
    - inited: 数据是否充足

    使用示例::

        from vnpy.trader.utility import ArrayManager
        from core.indicators.calculators import MACDCalculator

        am = ArrayManager(size=100)
        calc = MACDCalculator(12, 26, 9)

        # 在 on_bar 中
        am.update_bar(bar)
        if am.inited:
            calc.update(am)
            values = calc.get_values()
            # values = {"macd": ..., "diff": ..., "signal": ..., ...}
    """

    @abstractmethod
    def update(self, am) -> None:
        """
        基于 ArrayManager 更新指标计算。

        Args:
            am: vnpy.trader.utility.ArrayManager 实例
        """
        pass

    @abstractmethod
    def get_values(self) -> Dict[str, Any]:
        """
        获取当前指标值。

        返回格式与对应图表指标的 get_current_values() 保持一致，
        便于 AI 分析和策略逻辑复用。

        Returns:
            包含指标计算结果的字典
        """
        pass

    @property
    @abstractmethod
    def inited(self) -> bool:
        """数据是否充足，可以开始输出有效指标值"""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(inited={self.inited})"
