"""
ATMTrader数据模型模块

包含交易记录、AI分析结果、回测存储等数据模型定义
"""

from .trade_models import (
    TradeData,
    TradeStatus,
    get_last_trade,
    get_unclosed_trades,
    save_trade_data,
    update_db_trade_data
)

from .ai_analysis_data import (
    DbAIAnalysis,
    save_ai_analysis,
    get_latest_analysis,
    get_today_scheduled_analysis,
    get_latest_after_time,
    save_news_analysis
)

from .backtest_storage_models import (
    DbBacktestTrade,
    DbBacktestDecision,
    save_backtest_trade,
    save_backtest_decision,
    get_backtest_trades,
    get_backtest_decisions,
    create_backtest_tables
)

# 创建别名以兼容旧代码
DbTradeData = TradeData

__all__ = [
    # 交易数据模型
    'TradeData',
    'DbTradeData',  # 别名，用于兼容性
    'TradeStatus',
    'get_last_trade',
    'get_unclosed_trades',
    'save_trade_data',
    'update_db_trade_data',
    # AI分析数据模型
    'DbAIAnalysis',
    'save_ai_analysis',
    'get_latest_analysis',
    'get_today_scheduled_analysis',
    'get_latest_after_time',
    'save_news_analysis',
    # 回测存储数据模型
    'DbBacktestTrade',
    'DbBacktestDecision',
    'save_backtest_trade',
    'save_backtest_decision',
    'get_backtest_trades',
    'get_backtest_decisions',
    'create_backtest_tables'
]

