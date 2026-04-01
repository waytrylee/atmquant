#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险限制定义

定义风险控制的硬限制和软限制。
"""

from typing import Dict
from config.ai_strategy_config import RISK_LIMITS


# 从配置文件读取风险限制
HARD_LIMITS = RISK_LIMITS["hard_limits"]
SOFT_LIMITS = RISK_LIMITS["soft_limits"]


def get_hard_limits() -> Dict:
    """获取硬限制"""
    return HARD_LIMITS.copy()


def get_soft_limits() -> Dict:
    """获取软限制"""
    return SOFT_LIMITS.copy()
