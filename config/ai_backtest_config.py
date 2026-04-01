#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI回测引擎配置

包含回测参数、存储配置、检查点配置等。
"""

from typing import Dict


# ===== 回测默认参数 =====
BACKTEST_DEFAULTS = {
    "initial_balance": 100000,               # 初始资金（元）
    "decision_interval": 5,                  # 决策间隔（K线数）
    "max_context_bars": 100,                 # 最大上下文K线数
    "max_position_size": 0.3,                # 最大仓位比例（30%）
    "stop_loss_pct": 0.02,                   # 止损百分比（2%）
    "take_profit_pct": 0.05,                 # 止盈百分比（5%）
    "default_deposit_rate": 0.10,            # 默认保证金率（10%）
    "min_deposit_rate": 0.07,                # 最小保证金率（7%，对应最大20倍杠杆）
    "fee_rate": 0.0001,                      # 手续费率（0.01%）
    "fixed_fee": 0.0,                        # 固定手续费（元/单位）
}


# ===== 存储配置 =====
STORAGE_CONFIG = {
    "storage_dir": "backtests",              # 存储目录
    "storage_backend": "jsonl",              # 存储后端（jsonl/sqlite/mysql）
    "checkpoint_file": "checkpoint.json",    # 检查点文件名
    "lock_file": "lock",                     # 进程锁文件名
    "equity_file": "equity.jsonl",           # 权益曲线文件名
    "trades_file": "trades.jsonl",           # 交易记录文件名
    "metrics_file": "metrics.json",          # 性能指标文件名
    "decisions_file": "decisions.jsonl",     # 决策记录文件名
    "cache_file": "ai_cache.json",           # AI缓存文件名
}


# ===== 检查点配置 =====
CHECKPOINT_CONFIG = {
    "checkpoint_interval_bars": 20,          # 检查点间隔（K线数）
    "checkpoint_interval_seconds": 2,        # 检查点间隔（秒）
    "heartbeat_interval": 2,                 # 心跳间隔（秒）
    "stale_after": 10,                       # 锁超时时间（秒）
}


# ===== 账户配置 =====
ACCOUNT_CONFIG = {
    "initial_balance": 100000,               # 初始资金（元）
    "fee_rate": 0.0001,                      # 手续费率（0.01%）
    "fixed_fee": 0.0,                        # 固定手续费（元/单位）
    "fill_policy": "next_open",              # 成交策略（next_open/bar_vwap/mid/market/close）
    "pricetick": 0.01,                       # 最小价格变动
    "size": 1.0,                             # 合约乘数
    "deposit_rate": 0.10,                    # 保证金率（10%）
    "min_deposit_rate": 0.07,                # 最小保证金率（7%）
}


# ===== 多周期配置 =====
MULTI_TIMEFRAME_CONFIG = {
    "use_multi_timeframe": False,            # 是否使用多周期分析
    "timeframes": ["1m", "5m", "15m"],       # 多周期列表
}


# ===== 缓存配置 =====
CACHE_CONFIG = {
    "cache_ai_decisions": True,              # 是否缓存AI决策
    "shared_cache_path": None,               # 共享缓存路径
    "replay_only": False,                    # 仅回放模式（只使用缓存）
}


# ===== API成本估算参数 =====
API_COST_ESTIMATION = {
    "input_tokens_per_decision": 1000,       # 每次决策输入token数
    "output_tokens_per_decision": 500,       # 每次决策输出token数
}


# ===== 辅助函数 =====

def get_backtest_defaults() -> Dict:
    """获取回测默认参数"""
    return BACKTEST_DEFAULTS.copy()


def get_storage_config() -> Dict:
    """获取存储配置"""
    return STORAGE_CONFIG.copy()


def get_checkpoint_config() -> Dict:
    """获取检查点配置"""
    return CHECKPOINT_CONFIG.copy()


def get_account_config() -> Dict:
    """获取账户配置"""
    return ACCOUNT_CONFIG.copy()
