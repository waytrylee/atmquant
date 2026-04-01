#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仓位计算器

基于风险管理和账户状态计算合适的开仓数量。
"""

from typing import Dict, Optional


class PositionSizer:
    """仓位计算器

    根据多个因素计算合适的开仓数量：
    1. AI建议的仓位比例
    2. 可用资金
    3. 风险管理限制
    4. 合约规格
    """

    def __init__(self, risk_manager: Optional[object] = None):
        """初始化仓位计算器

        Args:
            risk_manager: 风险管理器实例
        """
        self.risk_manager = risk_manager

    def calculate(
        self,
        decision: Dict,
        account_balance: float,
        available_margin: float,
        current_price: float,
        symbol: str = "",
        direction: str = "long"
    ) -> int:
        """计算开仓数量

        Args:
            decision: AI决策字典
            account_balance: 账户总资金
            available_margin: 可用保证金
            current_price: 当前价格
            symbol: 品种代码
            direction: 方向 ("long" 或 "short")

        Returns:
            int: 开仓手数
        """
        # 1. 获取合约规格（包括保证金率）
        contract_size, margin_rate = self._get_contract_spec(symbol)

        # 2. 获取AI建议的仓位比例
        suggested_size = decision.get("position_size", 0.3)

        # 3. 应用风险管理限制
        if self.risk_manager:
            adjusted_size = self.risk_manager.adjust_position_size(
                suggested_size,
                account_balance,
                available_margin,
                symbol
            )
        else:
            # 默认限制
            adjusted_size = min(suggested_size, 0.3)

        # 4. 计算可用资金
        capital_to_use = account_balance * adjusted_size

        # 5. 计算手数（考虑保证金）
        # 每手保证金 = 价格 × 合约乘数 × 保证金率
        margin_per_lot = current_price * contract_size * margin_rate
        if margin_per_lot <= 0:
            return 1

        lots = int(capital_to_use / margin_per_lot)

        # 6. 确保至少1手
        return max(1, lots)

    def calculate_with_risk(
        self,
        decision: Dict,
        account_balance: float,
        available_margin: float,
        current_price: float,
        stop_loss_price: Optional[float] = None,
        symbol: str = "",
        direction: str = "long"
    ) -> int:
        """基于风险计算开仓数量（考虑止损）

        Args:
            decision: AI决策字典
            account_balance: 账户总资金
            available_margin: 可用保证金
            current_price: 当前价格
            stop_loss_price: 止损价格
            symbol: 品种代码
            direction: 方向

        Returns:
            int: 开仓手数
        """
        # 1. 基础计算
        base_lots = self.calculate(
            decision, account_balance, available_margin,
            current_price, symbol, direction
        )

        # 2. 如果没有止损，直接返回
        if stop_loss_price is None:
            return base_lots

        # 3. 基于风险调整
        contract_size, _ = self._get_contract_spec(symbol)

        # 计算每手的风险金额
        if direction == "long":
            risk_per_lot = (current_price - stop_loss_price) * contract_size
        else:
            risk_per_lot = (stop_loss_price - current_price) * contract_size

        if risk_per_lot <= 0:
            return base_lots

        # 限制每笔交易风险不超过总资金的2%
        max_risk = account_balance * 0.02
        risk_adjusted_lots = int(max_risk / risk_per_lot)

        # 取较小值
        return min(base_lots, risk_adjusted_lots)

    def _get_contract_spec(self, symbol: str) -> tuple:
        """获取合约规格（乘数和保证金率）

        Args:
            symbol: 品种代码（如 "hc2504.SHFE" 或 "hc"）

        Returns:
            tuple: (合约乘数, 保证金率)
        """
        try:
            from config.futures_config import get_futures_info
            import re

            # 提取品种代码：从 "hc2504.SHFE" 或 "rb2605" 中提取 "hc" 或 "rb"
            if symbol:
                # 去除交易所后缀
                code = symbol.split('.')[0]
                # 提取字母部分（品种代码）
                match = re.match(r'^([a-zA-Z]+)', code)
                if match:
                    symbol_code = match.group(1).lower()
                else:
                    symbol_code = code.lower()
            else:
                symbol_code = ""

            info = get_futures_info(symbol_code)
            contract_size = info.get("size", 10)
            margin_rate = info.get("deposit_rate", 0.1)  # 默认10%保证金
            return contract_size, margin_rate
        except Exception:
            return 10, 0.1  # 默认值：10手乘数，10%保证金

    def calculate_add_position(
        self,
        current_position: int,
        decision: Dict,
        account_balance: float,
        available_margin: float,
        current_price: float,
        symbol: str = ""
    ) -> int:
        """计算加仓数量

        Args:
            current_position: 当前持仓
            decision: AI决策字典
            account_balance: 账户总资金
            available_margin: 可用保证金
            current_price: 当前价格
            symbol: 品种代码

        Returns:
            int: 加仓手数
        """
        # 加仓数量通常是原仓位的一半
        current_size = abs(current_position)

        # 计算基础数量
        base_lots = self.calculate(
            decision, account_balance, available_margin,
            current_price, symbol
        )

        # 限制加仓数量不超过现有持仓
        add_lots = min(base_lots, current_size // 2)

        return max(1, add_lots)

    def calculate_reduce_position(
        self,
        current_position: int,
        reduce_ratio: float = 0.5
    ) -> int:
        """计算减仓数量

        Args:
            current_position: 当前持仓
            reduce_ratio: 减仓比例

        Returns:
            int: 减仓手数
        """
        current_size = abs(current_position)
        reduce_size = int(current_size * reduce_ratio)

        # 确保至少减1手
        return max(1, reduce_size)
