#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术指标配置

包含技术指标参数、时间周期映射、默认合约规格等。
"""

from typing import Dict


# ===== 技术指标参数 =====
INDICATOR_PARAMS = {
    "ema": {
        "fast": 12,                          # 快速EMA周期
        "slow": 26,                          # 慢速EMA周期
    },
    "macd": {
        "signal": 9,                         # MACD信号线周期
    },
    "rsi": {
        "window": 14,                        # RSI周期
    },
    "atr": {
        "window": 14,                        # ATR周期
    },
    "adx": {
        "window": 14,                        # ADX周期
    },
}


# ===== 数据源配置 =====
DATAFEED_CONFIG = {
    "buffer_bars": 200,                      # 缓冲区K线数
    "min_bars_for_indicators": 20,           # 指标计算最小K线数
}


# ===== 时间周期映射（毫秒） =====
TIMEFRAME_DURATION_MS = {
    "1m": 60 * 1000,                         # 1分钟
    "3m": 3 * 60 * 1000,                     # 3分钟
    "5m": 5 * 60 * 1000,                     # 5分钟
    "15m": 15 * 60 * 1000,                   # 15分钟
    "30m": 30 * 60 * 1000,                   # 30分钟
    "1h": 60 * 60 * 1000,                    # 1小时
    "2h": 2 * 60 * 60 * 1000,                # 2小时
    "4h": 4 * 60 * 60 * 1000,                # 4小时
    "d": 24 * 60 * 60 * 1000,                # 日线
    "w": 7 * 24 * 60 * 60 * 1000,            # 周线
}


# ===== 默认合约规格 =====
DEFAULT_CONTRACT_SPECS = {
    "size": 10,                              # 合约乘数
    "pricetick": 0.1,                        # 最小价格变动
    "deposit_rate": 0.07,                    # 保证金率（7%）
    "rate": 0.0001,                          # 手续费率（0.01%）
}


# ===== K线聚合窗口 =====
BAR_AGGREGATION_WINDOWS = {
    "5m": 5,                                 # 5分钟K线聚合窗口
    "15m": 15,                               # 15分钟K线聚合窗口
    "1h": 1,                                 # 1小时K线聚合窗口
}


# ===== 趋势判断阈值 =====
TREND_THRESHOLDS = {
    "trend_up_threshold": 1.002,             # 上涨趋势阈值（0.2%）
    "trend_down_threshold": 0.998,           # 下跌趋势阈值（-0.2%）
}


# ===== 辅助函数 =====

def get_indicator_params(indicator: str) -> Dict:
    """获取指标参数

    Args:
        indicator: 指标名称（ema/macd/rsi/atr/adx）

    Returns:
        Dict: 指标参数
    """
    return INDICATOR_PARAMS.get(indicator, {}).copy()


def get_timeframe_duration_ms(interval: str) -> int:
    """获取时间周期的毫秒数

    Args:
        interval: 时间周期（1m/5m/15m/1h/4h/d/w）

    Returns:
        int: 毫秒数
    """
    return TIMEFRAME_DURATION_MS.get(interval, 60 * 60 * 1000)


def get_default_contract_specs() -> Dict:
    """获取默认合约规格"""
    return DEFAULT_CONTRACT_SPECS.copy()
