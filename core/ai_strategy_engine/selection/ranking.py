#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
品种评分器

对候选品种进行评分排序，考虑流动性、波动率、趋势强度等因素。
"""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np


class SymbolRanker:
    """品种评分器

    对候选品种进行评分排序，考虑：
    1. 流动性（成交量、持仓量）
    2. 波动率（ATR）
    3. 趋势强度（ADX）
    4. 市场相关性
    """

    def __init__(self, config: dict = None):
        """初始化评分器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.liquidity_weight = self.config.get("liquidity_weight", 0.4)
        self.volatility_weight = self.config.get("volatility_weight", 0.3)
        self.trend_weight = self.config.get("trend_weight", 0.3)

    def rank(
        self,
        symbols: List[str],
        current_time: datetime
    ) -> List[str]:
        """对品种列表进行评分排序

        Args:
            symbols: 品种列表
            current_time: 当前时间

        Returns:
            List[str]: 排序后的品种列表
        """
        scores = []

        for symbol in symbols:
            score = self._calculate_score(symbol, current_time)
            scores.append((symbol, score))

        # 按分数降序排序
        scores.sort(key=lambda x: x[1], reverse=True)

        return [s[0] for s in scores]

    def _calculate_score(self, symbol: str, current_time: datetime) -> float:
        """计算单个品种的评分

        Args:
            symbol: 品种代码
            current_time: 当前时间

        Returns:
            float: 综合评分
        """
        # 获取各项指标评分
        liquidity_score = self._score_liquidity(symbol)
        volatility_score = self._score_volatility(symbol, current_time)
        trend_score = self._score_trend(symbol, current_time)

        # 加权平均
        total_score = (
            liquidity_score * self.liquidity_weight +
            volatility_score * self.volatility_weight +
            trend_score * self.trend_weight
        )

        return total_score

    def _score_liquidity(self, symbol: str) -> float:
        """评分流动性

        Args:
            symbol: 品种代码

        Returns:
            float: 流动性评分 (0-1)
        """
        try:
            from vnpy.trader.database import get_database
            from vnpy.trader.object import BarData

            database = get_database()

            # 获取最近的K线数据
            symbol_code = symbol.split('.')[0]
            exchange = symbol.split('.')[1] if '.' in symbol else ""

            # 查询最近1天的数据
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)

            bars: List[BarData] = database.load_bar_data(
                symbol=symbol_code,
                exchange=exchange,
                interval="1m",
                start=start_time,
                end=end_time
            )

            if not bars or len(bars) < 100:
                return 0.3  # 默认分数

            # 计算平均成交量和持仓量
            volumes = [bar.volume for bar in bars[-100:]]
            avg_volume = np.mean(volumes)

            # 基于成交量评分
            if avg_volume > 50000:
                return 1.0
            elif avg_volume > 20000:
                return 0.8
            elif avg_volume > 10000:
                return 0.6
            elif avg_volume > 5000:
                return 0.4
            else:
                return 0.2

        except Exception:
            return 0.3

    def _score_volatility(self, symbol: str, current_time: datetime) -> float:
        """评分波动率

        Args:
            symbol: 品种代码
            current_time: 当前时间

        Returns:
            float: 波动率评分 (0-1)
        """
        try:
            from vnpy.trader.database import get_database
            from vnpy.trader.object import BarData

            database = get_database()

            symbol_code = symbol.split('.')[0]
            exchange = symbol.split('.')[1] if '.' in symbol else ""

            # 获取最近的数据计算ATR
            end_time = current_time
            start_time = end_time - timedelta(days=7)

            bars: List[BarData] = database.load_bar_data(
                symbol=symbol_code,
                exchange=exchange,
                interval="1h",
                start=start_time,
                end=end_time
            )

            if not bars or len(bars) < 50:
                return 0.5  # 默认分数

            # 计算ATR
            atr = self._calculate_atr(bars[-50:])
            current_price = bars[-1].close_price

            # 计算波动率百分比
            volatility_pct = (atr / current_price) if current_price > 0 else 0

            # 基于波动率评分（适中波动率得高分）
            if 0.01 <= volatility_pct <= 0.03:
                return 1.0
            elif 0.005 <= volatility_pct < 0.01:
                return 0.7
            elif 0.03 < volatility_pct <= 0.05:
                return 0.7
            elif volatility_pct < 0.005:
                return 0.3  # 波动率过低
            else:
                return 0.4  # 波动率过高

        except Exception:
            return 0.5

    def _score_trend(self, symbol: str, current_time: datetime) -> float:
        """评分趋势强度

        Args:
            symbol: 品种代码
            current_time: 当前时间

        Returns:
            float: 趋势评分 (0-1)
        """
        try:
            from vnpy.trader.database import get_database
            from vnpy.trader.object import BarData

            database = get_database()

            symbol_code = symbol.split('.')[0]
            exchange = symbol.split('.')[1] if '.' in symbol else ""

            # 获取最近的数据
            end_time = current_time
            start_time = end_time - timedelta(days=7)

            bars: List[BarData] = database.load_bar_data(
                symbol=symbol_code,
                exchange=exchange,
                interval="1h",
                start=start_time,
                end=end_time
            )

            if not bars or len(bars) < 50:
                return 0.5  # 默认分数

            # 计算趋势指标
            closes = [bar.close_price for bar in bars[-50:]]

            # 计算ADX（简化版）
            adx = self._calculate_adx(bars[-50:])

            # 计算价格趋势
            price_trend = self._calculate_price_trend(closes)

            # 综合评分
            if adx > 25 and abs(price_trend) > 0.01:
                # 强趋势
                return 1.0
            elif adx > 20 and abs(price_trend) > 0.005:
                # 中等趋势
                return 0.8
            elif adx > 15:
                # 弱趋势
                return 0.6
            else:
                # 震荡
                return 0.4

        except Exception:
            return 0.5

    def _calculate_atr(self, bars: List) -> float:
        """计算ATR

        Args:
            bars: K线数据列表

        Returns:
            float: ATR值
        """
        if len(bars) < 2:
            return 0.0

        tr_list = []
        for i in range(1, len(bars)):
            high = bars[i].high_price
            low = bars[i].low_price
            prev_close = bars[i-1].close_price

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)

        return np.mean(tr_list) if tr_list else 0.0

    def _calculate_adx(self, bars: List, period: int = 14) -> float:
        """计算ADX（简化版）

        Args:
            bars: K线数据列表
            period: 周期

        Returns:
            float: ADX值
        """
        if len(bars) < period * 2:
            return 0.0

        # 计算TR
        tr_list = []
        for i in range(1, len(bars)):
            high = bars[i].high_price
            low = bars[i].low_price
            prev_close = bars[i-1].close_price
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        # 计算+DM和-DM
        plus_dm = []
        minus_dm = []
        for i in range(1, len(bars)):
            up_move = bars[i].high_price - bars[i-1].high_price
            down_move = bars[i-1].low_price - bars[i].low_price

            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)

            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)

        # 平滑
        atr = self._calculate_atr(bars)
        plus_di = np.mean(plus_dm[-period:]) / atr * 100 if atr > 0 else 0
        minus_di = np.mean(minus_dm[-period:]) / atr * 100 if atr > 0 else 0

        # 计算DX和ADX
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di
        dx = (di_diff / di_sum * 100) if di_sum > 0 else 0

        return dx  # 简化版，直接返回DX

    def _calculate_price_trend(self, closes: List[float]) -> float:
        """计算价格趋势

        Args:
            closes: 收盘价列表

        Returns:
            float: 趋势强度（正数表示上涨，负数表示下跌）
        """
        if len(closes) < 20:
            return 0.0

        # 计算短期和长期均线
        short_ma = np.mean(closes[-10:])
        long_ma = np.mean(closes[-30:])

        # 计算趋势
        trend = (short_ma - long_ma) / long_ma if long_ma > 0 else 0

        return trend

    def filter_by_correlation(
        self,
        symbols: List[str],
        selected_symbols: List[str],
        max_correlation: float = 0.8
    ) -> List[str]:
        """基于相关性过滤品种

        Args:
            symbols: 候选品种列表
            selected_symbols: 已选择的品种列表
            max_correlation: 最大相关性阈值

        Returns:
            List[str]: 过滤后的品种列表
        """
        if not selected_symbols:
            return symbols

        filtered = []

        for symbol in symbols:
            # 检查与已选品种的相关性
            is_correlated = False

            for selected in selected_symbols:
                if self._are_correlated(symbol, selected, max_correlation):
                    is_correlated = True
                    break

            if not is_correlated:
                filtered.append(symbol)

        return filtered

    def _are_correlated(
        self,
        symbol1: str,
        symbol2: str,
        threshold: float
    ) -> bool:
        """检查两个品种是否相关

        Args:
            symbol1: 品种1
            symbol2: 品种2
            threshold: 相关性阈值

        Returns:
            bool: 是否相关
        """
        from config.futures_config import get_symbol_category

        # 简单实现：基于品种类别判断
        # 同类别的品种认为相关
        category1 = get_symbol_category(symbol1)
        category2 = get_symbol_category(symbol2)

        return category1 == category2 and category1 != "其他"
