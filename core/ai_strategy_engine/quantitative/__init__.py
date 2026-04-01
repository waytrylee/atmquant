#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI策略引擎量化数据模块

为中国期货市场提供量化数据支持，包括：
1. 持仓量变化追踪
2. 价格变化追踪
3. 市场排名数据
4. 资金流向分析

适配中国期货市场特性。
"""

from core.ai_strategy_engine.quantitative.data_provider import (
    QuantitativeDataProvider,
    OIChangeData,
    PriceChangeData,
    MarketRankingData,
)
from core.ai_strategy_engine.quantitative.formatter import (
    QuantitativeDataFormatter,
    format_oi_for_prompt,
    format_ranking_for_prompt,
)


__all__ = [
    "QuantitativeDataProvider",
    "OIChangeData",
    "PriceChangeData",
    "MarketRankingData",
    "QuantitativeDataFormatter",
    "format_oi_for_prompt",
    "format_ranking_for_prompt",
]
