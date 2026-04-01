#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
无头指标计算器模块

零 Qt/pyqtgraph 依赖的技术指标计算器，
设计用于 CTA 策略中直接复用 core/indicators/ 的指标计算逻辑。

特点：
- 零 Qt 依赖：纯 numpy/talib 计算，可在无 UI 环境运行
- 基于 ArrayManager：复用策略已有的 ArrayManager，无需额外数据管理
- 统一接口：所有计算器实现 update() / get_values() / inited 接口
- 多周期支持：每个时间周期创建独立的 IndicatorManager 实例
- 低内存开销：不存储绘图对象，仅保留计算结果
- 回测/实盘通用：不区分运行环境，相同代码在所有场景工作

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
"""

# 基类
from .base import HeadlessCalculator

# 管理器
from .indicator_manager import IndicatorManager

# ==================== 基础指标计算器 ====================
from .macd_calculator import MACDCalculator
from .rsi_calculator import RSICalculator
from .boll_calculator import BollCalculator
from .dmi_calculator import DMICalculator
from .sma_calculator import SMACalculator
from .ema_calculator import EMACalculator

# ==================== 高级指标计算器（可选，缺失时不影响系统运行）====================
_ADVANCED_CALCULATORS = {
    "SupertrendCalculator": (".supertrend_calculator", "SupertrendCalculator"),
    "WaveTrendCalculator": (".wavetrend_calculator", "WaveTrendCalculator"),
    "SqueezeMomentumCalculator": (".squeeze_calculator", "SqueezeMomentumCalculator"),
    "FibonacciCalculator": (".fibonacci_calculator", "FibonacciCalculator"),
    "KalmanCalculator": (".kalman_calculator", "KalmanCalculator"),
    "KALMAN_PRESETS": (".kalman_calculator", "KALMAN_PRESETS"),
}

for _name, (_module, _attr) in _ADVANCED_CALCULATORS.items():
    try:
        _mod = __import__(f"core.indicators.calculators{_module}", fromlist=[_attr])
        globals()[_name] = getattr(_mod, _attr)
    except (ImportError, AttributeError):
        pass


__all__ = [
    # 基类和管理器
    "HeadlessCalculator",
    "IndicatorManager",

    # 基础指标
    "MACDCalculator",
    "RSICalculator",
    "BollCalculator",
    "DMICalculator",
    "SMACalculator",
    "EMACalculator",

    # 高级指标（仅在源文件存在时可用）
    "SupertrendCalculator",
    "WaveTrendCalculator",
    "SqueezeMomentumCalculator",
    "FibonacciCalculator",
    "KalmanCalculator",
    "KALMAN_PRESETS",
]
