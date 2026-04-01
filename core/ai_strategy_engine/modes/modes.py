#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易模式定义

定义不同的交易模式枚举和相关配置。
"""

from enum import Enum

from config.ai_strategy_config import TRADING_MODES


class TradingMode(Enum):
    """交易模式枚举

    定义不同的交易模式，适应不同市场环境和用户偏好。
    """
    AGGRESSIVE = "aggressive"      # 激进模式：趋势突破，较高仓位
    CONSERVATIVE = "conservative"  # 保守模式：多信号确认
    SCALPING = "scalping"          # 剥头皮模式：短线动量，紧止盈

    @classmethod
    def from_string(cls, value: str) -> 'TradingMode':
        """从字符串创建交易模式

        Args:
            value: 模式字符串

        Returns:
            TradingMode: 交易模式枚举
        """
        value_map = {
            "aggressive": cls.AGGRESSIVE,
            "conservative": cls.CONSERVATIVE,
            "scalping": cls.SCALPING,
            "default": cls.AGGRESSIVE,
        }
        return value_map.get(value.lower(), cls.AGGRESSIVE)

    def get_config(self) -> dict:
        """获取交易模式配置

        Returns:
            dict: 交易模式配置
        """
        configs = {
            TradingMode.AGGRESSIVE: TRADING_MODES["aggressive"],
            TradingMode.CONSERVATIVE: TRADING_MODES["conservative"],
            TradingMode.SCALPING: TRADING_MODES["scalping"],
        }
        return configs.get(self, configs[TradingMode.AGGRESSIVE])
