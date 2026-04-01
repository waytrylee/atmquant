#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI决策上下文构建器

统一上下文构建器，支持回测和实盘两种模式。
合并自原 ai_core/context_builder.py
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

from vnpy.trader.object import BarData


class ContextBuilder:
    """统一上下文构建器
    
    核心特性：
    1. 统一的数据格式（回测和实盘共享）
    2. 支持单品种和多品种
    3. 自动适配数据来源
    4. 完整的技术指标集成
    """

    def build(
        self,
        strategy_or_context: Any,
        current_bar: Any,
        config: Any = None,
        mode: str = "auto",
        **extra_fields
    ) -> Dict:
        """构建完整决策上下文

        Args:
            strategy_or_context: vnpy策略实例 或 回测上下文
            current_bar: 当前K线数据
            config: AI回测配置（可选）
            mode: 运行模式 ("auto" | "backtest" | "live")
            **extra_fields: 额外字段（如market_data, decision_cycle等）

        Returns:
            Dict: 包含所有决策上下文的字典
        """
        # 自动检测模式
        if mode == "auto":
            mode = self._detect_mode(strategy_or_context)

        # 构建基础上下文
        context = {
            "datetime": self._get_datetime(strategy_or_context, current_bar),
            "symbol": self._get_symbol(strategy_or_context, current_bar),
            "account": self._build_account(strategy_or_context, extra_fields),
            "positions": self._build_positions(strategy_or_context),
            "market": self._build_market(strategy_or_context, current_bar, config, extra_fields),
            "indicators": self._build_indicators(strategy_or_context),
            "history": self._build_decision_history(strategy_or_context),
            "risk": self._build_risk_context(strategy_or_context),
        }

        # 模式特定字段
        if mode == "backtest":
            context.update(self._build_backtest_fields(extra_fields))
        elif mode == "live":
            context.update(self._build_live_fields(strategy_or_context))

        return context

    def _detect_mode(self, strategy_or_context: Any) -> str:
        """检测运行模式"""
        if hasattr(strategy_or_context, 'bar_index'):
            return "backtest"
        if hasattr(strategy_or_context, 'decision_cycle'):
            return "backtest"
        if hasattr(strategy_or_context, 'market_data'):
            return "backtest"
        return "live"

    def _get_datetime(self, source: Any, current_bar: Any) -> datetime:
        """获取时间（优先使用K线时间）"""
        if current_bar and hasattr(current_bar, 'datetime'):
            return current_bar.datetime
        return datetime.now()

    def _get_symbol(self, source: Any, current_bar: Any) -> str:
        """获取品种代码"""
        if hasattr(source, 'vt_symbol'):
            return source.vt_symbol
        if current_bar and hasattr(current_bar, 'vt_symbol'):
            return current_bar.vt_symbol
        if current_bar and hasattr(current_bar, 'symbol'):
            return current_bar.symbol
        return ""

    def _build_account(self, source: Any, extra_fields: Dict) -> Dict:
        """构建账户信息"""
        # 回测模式：从extra_fields获取
        if "account_state" in extra_fields:
            account_state = extra_fields["account_state"]
            return {
                "balance": account_state.get("equity", 100000),
                "available": account_state.get("cash", 100000),
                "margin_used": account_state.get("margin_used", 0),
                "unrealized_pnl": account_state.get("unrealized_pnl", 0),
                "realized_pnl": account_state.get("realized_pnl", 0),
                "total_pnl": (
                    account_state.get("unrealized_pnl", 0) +
                    account_state.get("realized_pnl", 0)
                ),
            }

        # 实盘模式：从策略实例获取
        capital = 100000
        available = capital

        if hasattr(source, 'cta_engine'):
            engine = source.cta_engine
            capital = getattr(engine, 'capital', capital)
            available = capital

        # 如果有持仓，扣除占用的保证金
        if hasattr(source, 'pos') and source.pos != 0:
            entry_price = getattr(source, 'entry_price', 0)
            if entry_price > 0:
                margin = abs(source.pos) * entry_price
                available = capital - margin

        return {
            "balance": float(capital),
            "available": float(available),
            "position": int(getattr(source, 'pos', 0)),
            "total_pnl": float(getattr(source, 'total_pnl', 0))
        }

    def _build_positions(self, source: Any) -> List[Dict]:
        """构建持仓信息"""
        positions = []

        # 回测模式：从extra_fields获取
        if hasattr(source, 'positions'):
            return source.positions

        # 实盘模式：从策略获取
        if hasattr(source, 'pos') and source.pos != 0:
            positions.append({
                "symbol": getattr(source, 'vt_symbol', ''),
                "side": "long" if source.pos > 0 else "short",
                "quantity": abs(source.pos),
                "entry_price": getattr(source, 'entry_price', 0),
                "unrealized_pnl": getattr(source, 'unrealized_pnl', 0)
            })

        return positions

    def _build_market(
        self,
        source: Any,
        current_bar: Any,
        config: Any,
        extra_fields: Dict
    ) -> Dict:
        """构建市场数据"""
        market = {}

        # 基础价格数据
        if current_bar:
            market["current_price"] = float(getattr(current_bar, 'close_price', 0))
            market["open"] = float(getattr(current_bar, 'open_price', 0))
            market["high"] = float(getattr(current_bar, 'high_price', 0))
            market["low"] = float(getattr(current_bar, 'low_price', 0))
            market["volume"] = float(getattr(current_bar, 'volume', 0))

        # 历史K线数据
        max_context_bars = getattr(config, 'max_context_bars', 100) if config else 100
        bars = self._get_historical_bars(source, current_bar, max_context_bars)
        
        if bars:
            market["price_action"] = bars[-20:]  # 最近20根K线
            market["summary"] = self._calculate_market_summary(bars)

        # 多周期数据（回测）
        if "market_data" in extra_fields:
            market["market_data"] = extra_fields["market_data"]

        return market

    def _get_historical_bars(
        self,
        source: Any,
        current_bar: Any,
        max_bars: int
    ) -> List[Dict]:
        """获取历史K线数据"""
        bars = []

        if hasattr(source, 'am'):
            am = source.am
            if hasattr(am, 'inited') and am.inited:
                for i in range(min(max_bars, len(am.close_array))):
                    idx = len(am.close_array) - 1 - i
                    if idx < 0:
                        break
                    bars.append({
                        "time": current_bar.datetime,
                        "open": float(am.open_array[idx]),
                        "high": float(am.high_array[idx]),
                        "low": float(am.low_array[idx]),
                        "close": float(am.close_array[idx]),
                        "volume": float(am.volume_array[idx]) if hasattr(am, 'volume_array') else 0
                    })
        elif hasattr(source, 'bars_array'):
            bars_array = source.bars_array[-max_bars:]
            for b in bars_array:
                bars.append({
                    "time": b.datetime,
                    "open": float(b.open_price),
                    "high": float(b.high_price),
                    "low": float(b.low_price),
                    "close": float(b.close_price),
                    "volume": float(b.volume)
                })

        # 如果没有历史数据，至少包含当前K线
        if not bars and current_bar:
            bars = [{
                "time": current_bar.datetime,
                "open": float(current_bar.open_price),
                "high": float(current_bar.high_price),
                "low": float(current_bar.low_price),
                "close": float(current_bar.close_price),
                "volume": float(current_bar.volume)
            }]

        return bars

    def _calculate_market_summary(self, bars: List[Dict]) -> Dict:
        """计算市场摘要信息"""
        if len(bars) < 2:
            return {
                "change_pct": 0,
                "high_20": float(bars[0]["high"]),
                "low_20": float(bars[0]["low"]),
            }

        first_close = float(bars[0]["close"])
        last_close = float(bars[-1]["close"])
        change_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0

        recent_bars = bars[-20:] if len(bars) >= 20 else bars
        high_20 = max(float(b["high"]) for b in recent_bars)
        low_20 = min(float(b["low"]) for b in recent_bars)

        return {
            "change_pct": round(change_pct, 2),
            "high_20": round(high_20, 2),
            "low_20": round(low_20, 2),
        }

    def _build_indicators(self, source: Any) -> Dict:
        """构建技术指标"""
        indicators = {}

        if hasattr(source, 'am') and hasattr(source.am, 'inited') and source.am.inited:
            am = source.am
            indicator_attrs = [
                'sma_short', 'sma_long', 'sma_array',
                'ema_short', 'ema_long', 'ema_array',
                'macd_value', 'macd_signal', 'macd_hist',
                'rsi_value', 'rsi_array',
                'atr_value', 'atr_array'
            ]

            for attr in indicator_attrs:
                if hasattr(am, attr):
                    value = getattr(am, attr)
                    if hasattr(value, '__getitem__') and len(value) > 0:
                        indicators[attr] = float(value[-1])
                    elif isinstance(value, (int, float)):
                        indicators[attr] = float(value)

        # 策略直接定义的指标变量
        strategy_indicators = [
            ('sma_short', 'sma_short'),
            ('sma_long', 'sma_long'),
            ('macd', 'macd_value'),
            ('macd_signal', 'macd_signal'),
            ('rsi', 'rsi_value'),
            ('atr', 'atr_value'),
        ]

        for api_attr, indicator_name in strategy_indicators:
            if indicator_name not in indicators and hasattr(source, api_attr):
                value = getattr(source, api_attr)
                if hasattr(value, '__getitem__') and len(value) > 0:
                    indicators[indicator_name] = float(value[-1])
                elif isinstance(value, (int, float)):
                    indicators[indicator_name] = float(value)

        return indicators

    def _build_decision_history(self, source: Any) -> List[Dict]:
        """构建决策历史"""
        if not hasattr(source, 'decision_history'):
            return []
        history = source.decision_history
        return history[-3:] if len(history) > 3 else history

    def _build_risk_context(self, source: Any) -> Dict:
        """构建风险上下文"""
        return {
            "max_position_size": float(getattr(source, 'max_position_size', 0.3)),
            "stop_loss_pct": float(getattr(source, 'stop_loss_pct', 0.02)),
            "take_profit_pct": float(getattr(source, 'take_profit_pct', 0.05))
        }

    def _build_backtest_fields(self, extra_fields: Dict) -> Dict:
        """构建回测特有字段"""
        return {
            "decision_cycle": extra_fields.get("decision_cycle", 0),
            "bar_index": extra_fields.get("bar_index", 0),
        }

    def _build_live_fields(self, source: Any) -> Dict:
        """构建实盘特有字段"""
        fields = {}
        if hasattr(source, 'decision_history'):
            fields["history"] = source.decision_history[-5:]
        return fields




class MultiSymbolContextBuilder(ContextBuilder):
    """多品种上下文构建器

    在统一上下文基础上添加多品种管理功能
    """

    def build_multi_symbol(
        self,
        strategy: Any,
        focus_symbol: str,
        current_bar: Any,
        candidate_symbols: List[str],
        **extra_fields
    ) -> Dict:
        """构建多品种上下文

        Args:
            strategy: 策略实例
            focus_symbol: 当前关注的品种
            current_bar: 当前K线
            candidate_symbols: 候选品种列表
            **extra_fields: 额外字段

        Returns:
            Dict: 多品种上下文
        """
        context = self.build(
            strategy,
            current_bar,
            mode="live",
            focus_symbol=focus_symbol,
            **extra_fields
        )

        context.update({
            "focus_symbol": focus_symbol,
            "all_symbols": candidate_symbols,
            "risk": {
                "max_positions": extra_fields.get("max_positions", 3),
                "current_positions": extra_fields.get("current_positions", 0),
            },
        })

        return context
