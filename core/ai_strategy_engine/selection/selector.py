#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
品种选择器

从候选品种池中选择合适的交易品种，适配中国期货市场。
"""

from typing import List, Optional
from datetime import datetime

from config.futures_config import get_symbol_category


class SymbolSelector:
    """品种选择器

    职责：
    1. 从候选品种池中选择合适的交易品种
    2. 考虑流动性、波动率、相关性等因素
    3. 适配中国期货合约切换机制
    """

    def __init__(self, config: Optional[dict] = None):
        """初始化品种选择器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.min_volume = self.config.get("min_volume", 5000)
        self.min_open_interest = self.config.get("min_open_interest", 20000)
        self.enable_categories = self.config.get(
            "enable_categories",
            ["黑色系", "化工系", "有色金属", "农产品", "能源化工"]
        )

    def get_candidate_symbols(
        self,
        current_time: datetime,
        max_candidates: int = 5
    ) -> List[str]:
        """获取候选品种列表

        Args:
            current_time: 当前时间
            max_candidates: 最大候选品种数

        Returns:
            List[str]: 品种代码列表（格式如"rb2605.SHFE"）
        """
        # 1. 获取活跃合约池
        active_contracts = self._get_active_contracts(current_time)

        # 2. 过滤条件
        filtered = self._apply_filters(active_contracts, current_time)

        # 3. 按类别排序
        categorized = self._categorize_symbols(filtered)

        # 4. 从每个类别选择代表性品种
        candidates = []
        for category in self.enable_categories:
            if category in categorized:
                candidates.extend(categorized[category][:2])
                if len(candidates) >= max_candidates:
                    break

        return candidates[:max_candidates]

    def get_static_symbols(self, symbols: List[str]) -> List[str]:
        """获取静态品种列表

        Args:
            symbols: 用户指定的品种列表

        Returns:
            List[str]: 品种代码列表
        """
        result = []
        for symbol in symbols:
            # 格式化品种代码
            formatted = self._format_symbol(symbol)
            if formatted:
                result.append(formatted)
        return result

    def _get_active_contracts(self, current_time: datetime) -> List[str]:
        """获取活跃合约列表

        Args:
            current_time: 当前时间

        Returns:
            List[str]: 活跃合约列表
        """
        try:
            from config.futures_config import FUTURES_INFO, get_priority_contracts

            candidates = []
            current_month = current_time.month
            current_year = current_time.year

            for symbol_code in FUTURES_INFO.keys():
                # 获取该品种的优先合约
                contracts = get_priority_contracts(symbol_code, current_time)

                # 优先选择主力合约
                if contracts:
                    # 选择第一个（主力合约）
                    candidates.append(contracts[0])

            return candidates

        except Exception as e:
            # 如果配置加载失败，返回默认品种
            return self._get_default_symbols()

    def _get_default_symbols(self) -> List[str]:
        """获取默认品种列表"""
        return [
            "rb2505.SHFE",  # 螺纹钢
            "hc2505.SHFE",  # 热卷
            "cu2505.SHFE",  # 铜
            "al2505.SHFE",  # 铝
            "au2506.SHFE",  # 黄金
            "ag2506.SHFE",  # 白银
            "sc2506.INE",   # 原油
            "fu2506.SHFE",  # 燃料油
            "p2505.DCE",    # 棕榈油
            "m2505.DCE",    # 豆粕
            "y2505.DCE",    # 豆油
            "a2505.DCE",    # 豆一
            "c2505.DCE",    # 玉米
            "cs2505.DCE",   # 玉米淀粉
            "cf2505.CZCE",  # 棉花
            "sr2505.CZCE",  # 白糖
            "ta2505.CZCE",  # PTA
            "ma2505.CZCE",  # 甲醇
            "fg2505.CZCE",  # 玻璃
            "rm2505.CZCE",  # 菜粕
            "oi2505.CZCE",  # 菜油
            "sa2506.CZCE",  # 纯碱
            "ru2505.SHFE",  # 橡胶
            "ni2505.SHFE",  # 镍
            "sn2505.SHFE",  # 锡
            "zn2505.SHFE",  # 锌
            "pb2505.SHFE",  # 铅
            "jd2505.DCE",   # 鸡蛋
            "lh2505.DCE",   # 生猪
            "pg2505.DCE",   # 液化气
            "eb2505.DCE",   # 苯乙烯
            "eg2505.DCE",   # 乙二醇
            "pp2505.DCE",   # PP
            "l2505.DCE",    # LLDPE
            "v2505.DCE",    # PVC
            "i2505.DCE",    # 铁矿石
            "j2505.DCE",    # 焦炭
            "jm2505.DCE",   # 焦煤
        ]

    def _apply_filters(self, contracts: List[str], current_time: datetime) -> List[str]:
        """应用过滤条件

        Args:
            contracts: 合约列表
            current_time: 当前时间

        Returns:
            List[str]: 过滤后的合约列表
        """
        filtered = []

        for contract in contracts:
            # 1. 检查交易时段
            if not self._check_trading_session(contract, current_time):
                continue

            # 2. 检查合约到期时间（太近的合约跳过）
            if not self._check_expiry(contract, current_time):
                continue

            filtered.append(contract)

        return filtered

    def _check_trading_session(self, contract: str, current_time: datetime) -> bool:
        """检查交易时段

        Args:
            contract: 合约代码
            current_time: 当前时间

        Returns:
            bool: 是否在交易时段
        """
        try:
            from config.trading_sessions_config import get_trading_session_by_symbol

            symbol = contract.split('.')[0]
            session = get_trading_session_by_symbol(symbol)

            if not session:
                return True  # 如果获取失败，默认通过

            # 简单检查：只要有定义的时段就认为可以交易
            return len(session.day_sessions) > 0 or len(session.night_sessions) > 0

        except Exception:
            return True

    def _check_expiry(self, contract: str, current_time: datetime) -> bool:
        """检查合约到期时间

        Args:
            contract: 合约代码
            current_time: 当前时间

        Returns:
            bool: 是否未过期
        """
        # 从合约代码中提取月份
        parts = contract.split('.')
        if len(parts) < 2:
            return True

        symbol_part = parts[0]
        if len(symbol_part) < 4:
            return True

        try:
            # 提取年份和月份（如"2605"表示2026年5月）
            year_str = "20" + symbol_part[-4:-2]
            month_str = symbol_part[-2:]

            contract_year = int(year_str)
            contract_month = int(month_str)

            # 检查合约是否在当前月份之后
            current_year = current_time.year
            current_month = current_time.month

            # 计算合约到期月份（合约月份通常是交割月，提前1-2个月停止交易）
            expiry_month = contract_month - 2
            expiry_year = contract_year

            if expiry_month <= 0:
                expiry_month += 12
                expiry_year -= 1

            # 比较时间
            if expiry_year < current_year:
                return False
            if expiry_year == current_year and expiry_month < current_month:
                return False

            return True

        except Exception:
            return True

    def _categorize_symbols(self, symbols: List[str]) -> dict:
        """按类别对品种进行分组

        Args:
            symbols: 品种列表

        Returns:
            dict: 按类别分组的品种字典
        """
        from config.futures_config import get_all_categories

        categories = {cat: [] for cat in get_all_categories()}

        for symbol in symbols:
            category = get_symbol_category(symbol)
            if category in categories:
                categories[category].append(symbol)

        return categories

    def _format_symbol(self, symbol: str) -> Optional[str]:
        """格式化品种代码

        Args:
            symbol: 品种代码

        Returns:
            Optional[str]: 格式化后的完整品种代码
        """
        try:
            from config.futures_config import get_priority_contracts

            # 如果已经包含交易所，直接返回
            if '.' in symbol:
                return symbol

            # 获取优先合约
            contracts = get_priority_contracts(symbol, datetime.now())
            return contracts[0] if contracts else None

        except Exception:
            return None
