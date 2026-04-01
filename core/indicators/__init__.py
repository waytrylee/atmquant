#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标模块
包含所有技术指标的实现

设计说明：
- 基础指标（开源）：直接导入，所有用户可用
- 扩展指标：条件导入，需要额外安装（通过知识星球获取）
"""

# ==================== 基础指标（开源，所有用户可用） ====================
from .dyna_array_manager import DynaArrayManager
from .indicator_base import ConfigurableIndicator
from .boll_item import BollItem
from .multi_sma_item import MultiSmaItem
from .multi_ema_item import MultiEmaItem
from .rsi_item import RsiItem
from .macd_item import Macd3Item
from .dmi_item import DmiItem

# 构建基础导出列表
__all__ = [
    # 工具类
    "DynaArrayManager",

    # 基础配置接口
    "ConfigurableIndicator",

    # 基础技术指标
    "BollItem",
    "MultiSmaItem",
    "MultiEmaItem",
    "RsiItem",
    "Macd3Item",
    "DmiItem",
]

# Kalman指标（付费版）
try:
    from .kalman_item import KalmanItem
    __all__.append("KalmanItem")
except ImportError:
    pass

# ==================== 扩展指标（条件导入，需额外安装） ====================

# 自适应MACD豪华版
try:
    from .adaptive_macd_deluxe_item import AdaptiveMacdDeluxeItem
    __all__.append("AdaptiveMacdDeluxeItem")
except ImportError:
    pass

# 增强版成交量指标
try:
    from .enhanced_volume_item import EnhancedVolumeItem
    __all__.append("EnhancedVolumeItem")
except ImportError:
    pass

# 斐波那契入场带指标
try:
    from .fibonacci_entry_bands_item import FibonacciEntryBandsItem
    __all__.append("FibonacciEntryBandsItem")
except ImportError:
    pass

# 聪明钱通道指标
try:
    from .smart_money_channels import SmartMoneyChannelsItem
    __all__.append("SmartMoneyChannelsItem")
except ImportError:
    pass

# 挤压动量指标
try:
    from .squeeze_momentum_item import SqueezeMomentumItem
    __all__.append("SqueezeMomentumItem")
except ImportError:
    pass

# 超趋势RSI指标
try:
    from .supertrended_rsi_item import SupertrendedRsiItem
    __all__.append("SupertrendedRsiItem")
except ImportError:
    pass

# WaveTrend指标
try:
    from .wavetrend_item import WaveTrendItem
    __all__.append("WaveTrendItem")
except ImportError:
    pass

# Smart Money Concept指标
try:
    from .smc import SmartMoneyConceptItem
    __all__.append("SmartMoneyConceptItem")
except ImportError:
    pass

# K线形态识别指标
try:
    from .candlestick_patterns_item import CandlestickPatternsItem
    __all__.append("CandlestickPatternsItem")
except ImportError:
    pass

# 谐波形态指标
try:
    from .harmonic_pattern_item import HarmonicPatternItem
    __all__.append("HarmonicPatternItem")
except ImportError:
    pass
