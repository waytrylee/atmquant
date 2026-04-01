#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI策略引擎配置

包含风险限制、交易模式、AI配置等参数。
"""

from typing import Dict, Tuple


# ===== 风险限制配置 =====
RISK_LIMITS = {
    "hard_limits": {
        "max_positions": 3,              # 最大持仓品种数
        "max_position_value": 0.3,       # 单品种最大仓位比例（30%）
        "max_daily_loss": 0.05,          # 日最大亏损比例（5%）
    },
    "soft_limits": {
        "target_reward_ratio": 2.0,      # 目标盈亏比
        "max_correlation": 0.8,          # 最大相关性
    }
}


# ===== 交易模式配置 =====
# 注：已降低置信度阈值，避免过度过滤交易机会
# 每个模式包含：仓位范围、置信度阈值、止盈止损参数
TRADING_MODES = {
    "aggressive": {
        "position_size_range": (0.2, 0.3),    # 仓位范围
        "min_confidence": 0.55,               # 最小置信度
        "stop_loss_pct": 0.02,                # 止损：2%
        "take_profit_pct": 0.04,              # 止盈：4%（盈亏比2:1）
    },
    "conservative": {
        "position_size_range": (0.1, 0.2),    # 仓位范围
        "min_confidence": 0.60,               # 最小置信度
        "stop_loss_pct": 0.03,                # 止损：3%
        "take_profit_pct": 0.06,              # 止盈：6%（盈亏比2:1）
    },
    "scalping": {
        "position_size_range": (0.15, 0.25),  # 仓位范围
        "min_confidence": 0.45,               # 最小置信度
        "stop_loss_pct": 0.01,                # 止损：1%（快进快出）
        "take_profit_pct": 0.015,             # 止盈：1.5%（盈亏比1.5:1）
    },
}


# ===== AI配置 =====
AI_CONFIG = {
    "default_model": "deepseek-chat",    # 默认AI模型
    "decision_interval": 5,              # 决策间隔（K线数）
    "max_context_bars": 100,             # 最大上下文K线数
    "max_tokens": 2000,                  # 最大生成token数
    "temperature": 0.7,                  # 温度参数
}


# ===== 辅助函数 =====

def get_hard_limits() -> Dict:
    """获取硬限制"""
    return RISK_LIMITS["hard_limits"].copy()


def get_soft_limits() -> Dict:
    """获取软限制"""
    return RISK_LIMITS["soft_limits"].copy()


def get_trading_mode_config(mode: str) -> Dict:
    """获取交易模式配置

    Args:
        mode: 交易模式名称（aggressive/conservative/scalping）

    Returns:
        Dict: 交易模式配置
    """
    return TRADING_MODES.get(mode, TRADING_MODES["aggressive"]).copy()


def get_ai_config() -> Dict:
    """获取AI配置"""
    return AI_CONFIG.copy()
