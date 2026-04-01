#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI策略引擎模块

实现完整的AI决策能力架构，为ATMTrader提供完整的AI决策能力。
支持回测和实盘两种使用方式。

增强版（整合原ai_backtester特性）：
- AI缓存（SHA256哈希）
- 富上下文构建（Schema + 统计）
- 回测适配器
"""

from .engine import AIStrategyEngine, AIStrategyConfig, DecisionResult
from .schema.futures_schema import FuturesSchema, FieldDefinition
from .context.context_builder import ContextBuilder, MultiSymbolContextBuilder
from .cache import AICache, CachedDecision, compute_cache_key, create_ai_cache
from .backtest_adapter import BacktestAdapter, detect_backtest_mode

__all__ = [
    # 核心引擎
    "AIStrategyEngine",
    "AIStrategyConfig",
    "DecisionResult",

    # Schema
    "FuturesSchema",
    "FieldDefinition",

    # 上下文构建
    "ContextBuilder",
    "MultiSymbolContextBuilder",

    # 缓存
    "AICache",
    "CachedDecision",
    "compute_cache_key",
    "create_ai_cache",

    # 回测适配器
    "BacktestAdapter",
    "detect_backtest_mode",
]
