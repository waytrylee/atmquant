#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险管理器

提供硬限制（代码强制执行）和软限制（AI引导）的双重风险控制。
实现风险管理设计。
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field

from core.ai_strategy_engine.risk.limits import HARD_LIMITS, SOFT_LIMITS
from core.ai_strategy_engine.decision.validator import ValidationResult


@dataclass
class RiskCheckResult:
    """风险检查结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    adjusted_position_size: Optional[float] = None


class RiskManager:
    """风险管理器

    风险控制层次：
    1. 硬限制（代码强制执行）- 决策必须满足
    2. 软限制（AI引导）- 通过提示词引导
    """

    def __init__(
        self,
        hard_limits: Optional[Dict] = None,
        soft_limits: Optional[Dict] = None
    ):
        """初始化风险管理器

        Args:
            hard_limits: 硬限制配置
            soft_limits: 软限制配置
        """
        self.hard_limits = hard_limits or HARD_LIMITS.copy()
        self.soft_limits = soft_limits or SOFT_LIMITS.copy()

    def validate(
        self,
        decision: Dict,
        account_balance: float,
        available_margin: float,
        current_positions: int,
        position_value: float = 0,
        trading_mode = None  # 新增参数：交易模式
    ) -> ValidationResult:
        """验证决策是否符合风险限制

        Args:
            decision: 决策字典
            account_balance: 账户总资金
            available_margin: 可用保证金
            current_positions: 当前持仓品种数
            position_value: 当前持仓价值
            trading_mode: 交易模式（用于获取模式特定的min_confidence）

        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []

        action = decision.get("action", "")
        confidence = decision.get("confidence", 0)
        position_size = decision.get("position_size", 0)

        # ===== 硬限制检查 =====

        # 1. 置信度检查（从交易模式获取）
        if trading_mode:
            mode_config = trading_mode.get_config()
            min_confidence = mode_config.get("min_confidence", 0.5)
        else:
            min_confidence = 0.5  # 后备默认值

        if confidence < min_confidence:
            errors.append(f"置信度过低: {confidence} < {min_confidence}")

        # 2. 持仓数量检查
        max_positions = self.hard_limits.get("max_positions", 3)
        if action in ("LONG", "SHORT") and current_positions >= max_positions:
            errors.append(
                f"持仓数量已达上限: {current_positions} >= {max_positions}"
            )

        # 3. 仓位价值检查
        max_position_value = self.hard_limits.get("max_position_value", 0.3)
        new_position_value = account_balance * position_size
        total_position_value = position_value + new_position_value

        if total_position_value > account_balance * max_position_value:
            errors.append(
                f"仓位价值超限: {total_position_value:.2f} > {account_balance * max_position_value:.2f}"
            )

        # 4. 可用资金检查
        required_margin = account_balance * position_size
        if required_margin > available_margin:
            errors.append(
                f"资金不足: 需要{required_margin:.2f}, 可用{available_margin:.2f}"
            )

        # ===== 软限制检查（警告）=====

        # 1. 置信度警告（动态：在min_confidence基础上加15%）
        if confidence >= min_confidence and confidence < min_confidence + 0.15:
            warnings.append(f"置信度偏低: {confidence}")

        # 2. 仓位比例警告
        if position_size > 0.2:
            warnings.append(f"仓位比例较大: {position_size:.1%}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def check_liquidation_risk(
        self,
        position: int,
        entry_price: float,
        current_price: float,
        liquidation_price: float
    ) -> Dict:
        """检查清算风险

        Args:
            position: 持仓数量
            entry_price: 开仓价
            current_price: 当前价
            liquidation_price: 强平价

        Returns:
            dict: 清算风险信息
        """
        if position == 0:
            return {
                "has_risk": False,
                "distance_to_liquidation": 0,
                "risk_level": "none"
            }

        # 计算到强平价距离
        if position > 0:
            # 多头
            distance = (current_price - liquidation_price) / current_price
        else:
            # 空头
            distance = (liquidation_price - current_price) / current_price

        # 评估风险等级
        if distance < 0.01:
            risk_level = "critical"
        elif distance < 0.05:
            risk_level = "high"
        elif distance < 0.10:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "has_risk": True,
            "distance_to_liquidation": distance,
            "risk_level": risk_level
        }

    def adjust_position_size(
        self,
        requested_size: float,
        account_balance: float,
        available_margin: float,
        symbol: str = ""
    ) -> float:
        """调整仓位大小以符合风险限制

        Args:
            requested_size: AI建议的仓位大小
            account_balance: 账户总资金
            available_margin: 可用保证金
            symbol: 品种代码（用于获取特定限制）

        Returns:
            float: 调整后的仓位大小
        """
        # 1. 应用硬限制
        max_position_value = self.hard_limits.get("max_position_value", 0.3)
        max_size = max_position_value

        # 2. 考虑可用资金
        max_size_by_margin = available_margin / account_balance

        # 3. 取较小值
        adjusted_size = min(requested_size, max_size, max_size_by_margin)

        # 4. 确保最小值
        if adjusted_size < 0.01:
            adjusted_size = 0.01

        return adjusted_size

    def get_max_position_size(self, symbol: str = "") -> float:
        """获取指定品种的最大仓位比例

        Args:
            symbol: 品种代码（可根据品种特性动态调整）

        Returns:
            float: 最大仓位比例
        """
        base_limit = self.hard_limits.get("max_position_value", 0.3)

        # 可以根据品种特性动态调整
        if symbol:
            try:
                from config.futures_config import get_futures_info
                symbol_code = symbol.split('.')[0]
                info = get_futures_info(symbol_code)

                # 根据保证金率调整
                deposit_rate = info.get("deposit_rate", 0.1)
                # 保证金率越高，允许的仓位越小
                adjusted_limit = base_limit * (0.1 / deposit_rate)
                return min(adjusted_limit, base_limit)
            except Exception:
                pass

        return base_limit

    def get_risk_guidelines(self, language: str = "cn") -> str:
        """生成风险控制指南（用于插入系统提示词）

        Args:
            language: 语言 ("cn" 或 "en")

        Returns:
            str: 风险指南文本
        """
        if language == "cn":
            max_positions = self.hard_limits.get("max_positions", 3)
            max_position_value = self.hard_limits.get("max_position_value", 0.3)
            min_confidence = self.hard_limits.get("min_confidence", 0.5)
            target_reward_ratio = self.soft_limits.get("target_reward_ratio", 2.0)

            return f"""# 风险控制要求

## 硬性限制（必须遵守）
1. **最大持仓品种数**: {max_positions}个
2. **单品种最大仓位**: {max_position_value:.0%}资金
3. **最小置信度**: {min_confidence}（低于此值系统将拒绝执行）

## 建议标准（应当遵守）
1. **目标盈亏比**: {target_reward_ratio}:1（风险收益比）
2. **止损设置**: 每笔交易必须设置止损位
3. **相关性控制**: 避免同时持有高相关性品种

## 清算风险
- 系统会实时检测清算风险
- 接近清算线时系统会强制平仓
"""
        else:
            max_positions = self.hard_limits.get("max_positions", 3)
            max_position_value = self.hard_limits.get("max_position_value", 0.3)
            min_confidence = self.hard_limits.get("min_confidence", 0.5)
            target_reward_ratio = self.soft_limits.get("target_reward_ratio", 2.0)

            return f"""# Risk Control Requirements

## Hard Limits (Must Follow)
1. **Max Positions**: {max_positions} symbols
2. **Max Position Size**: {max_position_value:.0%} of capital
3. **Min Confidence**: {min_confidence} (below this system will reject)

## Recommended Standards (Should Follow)
1. **Target Risk-Reward Ratio**: {target_reward_ratio}:1
2. **Stop Loss**: Must set stop loss for every trade
3. **Correlation Control**: Avoid holding highly correlated symbols

## Liquidation Risk
- System monitors liquidation risk in real-time
- Forced liquidation near liquidation price
"""

    def check_daily_loss_limit(
        self,
        daily_pnl: float,
        initial_balance: float
    ) -> bool:
        """检查日亏损限制

        Args:
            daily_pnl: 当日盈亏
            initial_balance: 初始资金

        Returns:
            bool: True表示可以继续交易，False表示达到限制
        """
        max_daily_loss = self.hard_limits.get("max_daily_loss", 0.05)
        loss_ratio = abs(daily_pnl) / initial_balance if daily_pnl < 0 else 0

        return loss_ratio < max_daily_loss
