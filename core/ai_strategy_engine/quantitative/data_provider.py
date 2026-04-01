#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化数据提供者

为中国期货市场提供量化数据获取功能。
中国期货市场的特性：
- 无机构/散户资金流区分
- 有持仓量公开数据
- 有品种分类（黑色系、化工系等）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from core.logging.logger_manager import get_logger

logger = get_logger(__name__)


@dataclass
class OIChangeData:
    """持仓量变化数据

    追踪不同时间周期的持仓量变化。
    """
    symbol: str                      # 品种代码（如 "rb2605.SHFE"）
    current_oi: float = 0            # 当前持仓量（手）
    oi_delta_1h: float = 0           # 1小时变化（手）
    oi_delta_1h_pct: float = 0       # 1小时变化百分比
    oi_delta_4h: float = 0           # 4小时变化（手）
    oi_delta_4h_pct: float = 0       # 4小时变化百分比
    oi_delta_24h: float = 0          # 24小时变化（手）
    oi_delta_24h_pct: float = 0      # 24小时变化百分比
    oi_avg_20: float = 0             # 20日平均持仓量
    datetime: Optional[datetime] = None

    def get_oi_trend(self) -> str:
        """获取持仓量趋势描述

        Returns:
            str: 趋势描述 ("rapidly_increasing", "increasing", "stable", "decreasing", "rapidly_decreasing")
        """
        if self.oi_delta_24h_pct > 0.10:
            return "rapidly_increasing"
        elif self.oi_delta_24h_pct > 0.02:
            return "increasing"
        elif self.oi_delta_24h_pct < -0.10:
            return "rapidly_decreasing"
        elif self.oi_delta_24h_pct < -0.02:
            return "decreasing"
        else:
            return "stable"


@dataclass
class PriceChangeData:
    """价格变化数据

    追踪不同时间周期的价格变化。
    """
    symbol: str                      # 品种代码
    current_price: float = 0         # 当前价格
    price_delta_1h: float = 0        # 1小时变化
    price_delta_1h_pct: float = 0    # 1小时变化百分比
    price_delta_4h: float = 0        # 4小时变化
    price_delta_4h_pct: float = 0    # 4小时变化百分比
    price_delta_24h: float = 0       # 24小时变化
    price_delta_24h_pct: float = 0   # 24小时变化百分比
    volatility_20d: float = 0        # 20日波动率
    datetime: Optional[datetime] = None


@dataclass
class MarketRankingItem:
    """市场排名项"""
    symbol: str                      # 品种代码
    value: float                     # 排名值
    change_pct: float = 0            # 变化百分比
    category: str = ""               # 品种类别（黑色系、化工系等）


@dataclass
class MarketRankingData:
    """市场排名数据

    包含多种维度的市场排名。
    """
    oi_growth_top: List[MarketRankingItem] = field(default_factory=list)     # OI增长榜
    oi_growth_low: List[MarketRankingItem] = field(default_factory=list)     # OI减少榜
    price_gainer_top: List[MarketRankingItem] = field(default_factory=list)  # 涨幅榜
    price_loser_top: List[MarketRankingItem] = field(default_factory=list)   # 跌幅榜
    volume_active_top: List[MarketRankingItem] = field(default_factory=list) # 成交活跃榜

    def get_top_symbols(self, n: int = 5) -> List[str]:
        """获取综合排名前N的品种

        Args:
            n: 返回数量

        Returns:
            List[str]: 品种代码列表
        """
        score_map = {}

        # OI增长加分
        for i, item in enumerate(self.oi_growth_top[:10]):
            score_map[item.symbol] = score_map.get(item.symbol, 0) + (10 - i)

        # 价格上涨加分
        for i, item in enumerate(self.price_gainer_top[:10]):
            score_map[item.symbol] = score_map.get(item.symbol, 0) + (10 - i)

        # 成交活跃加分
        for i, item in enumerate(self.volume_active_top[:10]):
            score_map[item.symbol] = score_map.get(item.symbol, 0) + (10 - i)

        # 按分数排序
        sorted_symbols = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in sorted_symbols[:n]]


class QuantitativeDataProvider:
    """量化数据提供者

    从vnpy数据源获取量化数据，计算持仓量变化、价格变化等指标。
    """

    def __init__(self, data_gateway=None):
        """初始化量化数据提供者

        Args:
            data_gateway: vnpy数据网关（可选，用于实时数据）
        """
        self.data_gateway = data_gateway
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=5)  # 缓存5分钟

    def get_oi_change(self, symbol: str, bars_data: List[Any]) -> OIChangeData:
        """获取持仓量变化数据

        Args:
            symbol: 品种代码
            bars_data: K线数据列表（从新到旧）

        Returns:
            OIChangeData: 持仓量变化数据
        """
        # 检查缓存
        cache_key = f"oi_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        if len(bars_data) < 24:
            logger.warning(f"K线数据不足，无法计算OI变化: {symbol}")
            return OIChangeData(symbol=symbol)

        # 提取持仓量数据
        oi_values = []
        for bar in bars_data[:100]:  # 最多取100根K线
            oi = getattr(bar, 'open_interest', 0)
            if oi > 0:
                oi_values.append(oi)

        if len(oi_values) < 2:
            return OIChangeData(symbol=symbol)

        current_oi = oi_values[0]

        # 计算不同周期的变化
        oi_delta_1h = self._calculate_delta(oi_values, 1) if len(oi_values) > 1 else 0
        oi_delta_4h = self._calculate_delta(oi_values, 4) if len(oi_values) > 4 else 0
        oi_delta_24h = self._calculate_delta(oi_values, 24) if len(oi_values) > 24 else 0

        # 计算变化百分比
        oi_delta_1h_pct = (oi_delta_1h / current_oi * 100) if current_oi > 0 else 0
        oi_delta_4h_pct = (oi_delta_4h / current_oi * 100) if current_oi > 0 else 0
        oi_delta_24h_pct = (oi_delta_24h / current_oi * 100) if current_oi > 0 else 0

        # 计算20日平均
        oi_avg_20 = sum(oi_values[:20]) / 20 if len(oi_values) >= 20 else current_oi

        result = OIChangeData(
            symbol=symbol,
            current_oi=current_oi,
            oi_delta_1h=oi_delta_1h,
            oi_delta_1h_pct=oi_delta_1h_pct,
            oi_delta_4h=oi_delta_4h,
            oi_delta_4h_pct=oi_delta_4h_pct,
            oi_delta_24h=oi_delta_24h,
            oi_delta_24h_pct=oi_delta_24h_pct,
            oi_avg_20=oi_avg_20,
            datetime=datetime.now()
        )

        # 更新缓存
        self._update_cache(cache_key, result)

        return result

    def get_price_change(self, symbol: str, bars_data: List[Any]) -> PriceChangeData:
        """获取价格变化数据

        Args:
            symbol: 品种代码
            bars_data: K线数据列表（从新到旧）

        Returns:
            PriceChangeData: 价格变化数据
        """
        # 检查缓存
        cache_key = f"price_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        if len(bars_data) < 24:
            logger.warning(f"K线数据不足，无法计算价格变化: {symbol}")
            return PriceChangeData(symbol=symbol)

        close_prices = []
        for bar in bars_data[:100]:
            close = getattr(bar, 'close_price', 0)
            if close > 0:
                close_prices.append(close)

        if len(close_prices) < 2:
            return PriceChangeData(symbol=symbol)

        current_price = close_prices[0]

        # 计算不同周期的变化
        price_delta_1h = self._calculate_delta(close_prices, 1) if len(close_prices) > 1 else 0
        price_delta_4h = self._calculate_delta(close_prices, 4) if len(close_prices) > 4 else 0
        price_delta_24h = self._calculate_delta(close_prices, 24) if len(close_prices) > 24 else 0

        # 计算变化百分比
        price_delta_1h_pct = (price_delta_1h / current_price * 100) if current_price > 0 else 0
        price_delta_4h_pct = (price_delta_4h / current_price * 100) if current_price > 0 else 0
        price_delta_24h_pct = (price_delta_24h / current_price * 100) if current_price > 0 else 0

        # 计算20日波动率
        volatility_20d = self._calculate_volatility(close_prices[:20]) if len(close_prices) >= 20 else 0

        result = PriceChangeData(
            symbol=symbol,
            current_price=current_price,
            price_delta_1h=price_delta_1h,
            price_delta_1h_pct=price_delta_1h_pct,
            price_delta_4h=price_delta_4h,
            price_delta_4h_pct=price_delta_4h_pct,
            price_delta_24h=price_delta_24h,
            price_delta_24h_pct=price_delta_24h_pct,
            volatility_20d=volatility_20d,
            datetime=datetime.now()
        )

        # 更新缓存
        self._update_cache(cache_key, result)

        return result

    def get_market_ranking(
        self,
        symbols: List[str],
        bars_data_map: Dict[str, List[Any]]
    ) -> MarketRankingData:
        """获取市场排名数据

        Args:
            symbols: 品种代码列表
            bars_data_map: 品种到K线数据的映射

        Returns:
            MarketRankingData: 市场排名数据
        """
        # 检查缓存
        cache_key = "ranking"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        oi_growth_items = []
        price_gainer_items = []
        price_loser_items = []
        volume_items = []

        for symbol in symbols:
            bars = bars_data_map.get(symbol, [])
            if len(bars) < 2:
                continue

            # 获取OI变化
            oi_data = self.get_oi_change(symbol, bars)
            if oi_data.current_oi > 0:
                oi_growth_items.append(MarketRankingItem(
                    symbol=symbol,
                    value=oi_data.oi_delta_24h,
                    change_pct=oi_data.oi_delta_24h_pct,
                    category=self._get_symbol_category(symbol)
                ))

            # 获取价格变化
            price_data = self.get_price_change(symbol, bars)
            if price_data.current_price > 0:
                price_gainer_items.append(MarketRankingItem(
                    symbol=symbol,
                    value=price_data.price_delta_24h,
                    change_pct=price_data.price_delta_24h_pct,
                    category=self._get_symbol_category(symbol)
                ))
                price_loser_items.append(MarketRankingItem(
                    symbol=symbol,
                    value=price_data.price_delta_24h,
                    change_pct=price_data.price_delta_24h_pct,
                    category=self._get_symbol_category(symbol)
                ))

            # 获取成交量
            if len(bars) > 0:
                volume = getattr(bars[0], 'volume', 0)
                if volume > 0:
                    volume_items.append(MarketRankingItem(
                        symbol=symbol,
                        value=volume,
                        change_pct=0,
                        category=self._get_symbol_category(symbol)
                    ))

        # 排序
        oi_growth_items.sort(key=lambda x: x.change_pct, reverse=True)
        price_gainer_items.sort(key=lambda x: x.change_pct, reverse=True)
        price_loser_items.sort(key=lambda x: x.change_pct)
        volume_items.sort(key=lambda x: x.value, reverse=True)

        result = MarketRankingData(
            oi_growth_top=oi_growth_items[:10],
            oi_growth_low=oi_growth_items[-10:] if len(oi_growth_items) >= 10 else [],
            price_gainer_top=price_gainer_items[:10],
            price_loser_top=price_loser_items[:10],
            volume_active_top=volume_items[:10]
        )

        # 更新缓存
        self._update_cache(cache_key, result)

        return result

    def _calculate_delta(self, values: List[float], periods: int) -> float:
        """计算变化量

        Args:
            values: 值列表（从新到旧）
            periods: 周期数

        Returns:
            float: 变化量
        """
        if len(values) < periods + 1:
            return 0
        return values[0] - values[periods]

    def _calculate_volatility(self, prices: List[float]) -> float:
        """计算波动率

        Args:
            prices: 价格列表

        Returns:
            float: 波动率（标准差）
        """
        if len(prices) < 2:
            return 0

        import statistics
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        if not returns:
            return 0

        return statistics.stdev(returns) * 100 if len(returns) > 1 else 0

    def _get_symbol_category(self, symbol: str) -> str:
        """获取品种类别

        Args:
            symbol: 品种代码（如 "rb2605.SHFE"）

        Returns:
            str: 类别名称
        """
        from config.futures_config import get_symbol_category
        return get_symbol_category(symbol)

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效

        Args:
            key: 缓存键

        Returns:
            bool: 是否有效
        """
        if key not in self._cache:
            return False
        if key not in self._cache_time:
            return False

        cache_age = datetime.now() - self._cache_time[key]
        return cache_age < self._cache_ttl

    def _update_cache(self, key: str, value: Any):
        """更新缓存

        Args:
            key: 缓存键
            value: 缓存值
        """
        self._cache[key] = value
        self._cache_time[key] = datetime.now()

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_time.clear()
