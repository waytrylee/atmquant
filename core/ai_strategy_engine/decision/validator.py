#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
决策验证器

验证AI决策是否符合风险控制要求。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0

    def get_error_message(self) -> str:
        """获取错误消息"""
        return "; ".join(self.errors)

    def get_warning_message(self) -> str:
        """获取警告消息"""
        return "; ".join(self.warnings)


class DecisionValidator:
    """决策验证器

    验证AI决策的基本要求。
    """

    # 支持的操作类型
    VALID_ACTIONS = {
        "LONG",      # 开多
        "SHORT",     # 开空
        "CLOSE",     # 平仓
        "HOLD",      # 持仓
        "ADD_LONG",  # 加多
        "ADD_SHORT", # 加空
        "REDUCE",    # 减仓
    }

    def __init__(
        self,
        trading_mode = None,  # 新增：交易模式
        max_position_size: float = 0.3,  # 修改默认值为0.3（与hard_limits一致）
        min_position_size: float = 0.01,
        max_stop_loss_pct: float = 0.05,
        max_take_profit_pct: float = 0.10
    ):
        """初始化验证器

        Args:
            trading_mode: 交易模式对象（用于获取模式特定的min_confidence, stop_loss_pct, take_profit_pct）
            max_position_size: 最大仓位比例
            min_position_size: 最小仓位比例
            max_stop_loss_pct: 最大止损百分比（如0.05表示5%），可被交易模式配置覆盖
            max_take_profit_pct: 最大止盈百分比（如0.10表示10%），可被交易模式配置覆盖
        """
        # 从交易模式获取配置
        if trading_mode:
            mode_config = trading_mode.get_config()
            self.min_confidence = mode_config.get("min_confidence", 0.5)
            # 使用交易模式的止盈止损作为最大限制
            self.max_stop_loss_pct = mode_config.get("stop_loss_pct", max_stop_loss_pct)
            self.max_take_profit_pct = mode_config.get("take_profit_pct", max_take_profit_pct)
        else:
            self.min_confidence = 0.5  # 后备默认值
            self.max_stop_loss_pct = max_stop_loss_pct
            self.max_take_profit_pct = max_take_profit_pct

        self.max_position_size = max_position_size
        self.min_position_size = min_position_size

    def validate(self, decision: dict, context: Optional[dict] = None) -> ValidationResult:
        """验证决策

        Args:
            decision: 决策字典
            context: 交易上下文（可选，包含current_price等信息）

        Returns:
            ValidationResult: 验证结果
        """
        errors = []
        warnings = []

        # 1. 验证action类型
        action = decision.get("action", "")
        if action not in self.VALID_ACTIONS:
            errors.append(f"无效的操作类型: {action}")

        # 2. 验证置信度（HOLD 和 CLOSE 动作豁免）
        confidence = decision.get("confidence", 0)
        if action not in ("HOLD", "CLOSE"):
            if confidence < self.min_confidence:
                errors.append(f"置信度过低: {confidence} < {self.min_confidence}")
            elif confidence < self.min_confidence + 0.15:  # 动态：在min_confidence基础上加15%
                warnings.append(f"置信度偏低: {confidence}")

        # 3. 验证仓位大小（HOLD、CLOSE、REDUCE 动作豁免）
        position_size = decision.get("position_size", 0)
        if action not in ("HOLD", "CLOSE", "REDUCE"):
            if position_size < self.min_position_size:
                errors.append(f"仓位过小: {position_size} < {self.min_position_size}")
            elif position_size > self.max_position_size:
                errors.append(f"仓位过大: {position_size} > {self.max_position_size}")

        # 4. 验证止损止盈
        stop_loss = decision.get("stop_loss")
        take_profit = decision.get("take_profit")
        current_price = context.get("current_price") if context else None

        if action in ("LONG", "SHORT", "ADD_LONG", "ADD_SHORT"):
            # 开仓操作应该有止损止盈
            if stop_loss is None and take_profit is None:
                warnings.append("开仓操作未设置止损止盈")

            # 验证止损止盈的合理性
            if stop_loss is not None and take_profit is not None:
                if stop_loss <= 0 or take_profit <= 0:
                    errors.append("止损止盈价格必须大于0")

                # 对于多头，止损应该低于止盈
                if action in ("LONG", "ADD_LONG") and stop_loss >= take_profit:
                    errors.append("多头止损应该低于止盈")

                # 对于空头，止损应该高于止盈
                if action in ("SHORT", "ADD_SHORT") and stop_loss <= take_profit:
                    errors.append("空头止损应该高于止盈")

                # 验证止损止盈幅度（需要当前价格）
                if current_price and current_price > 0:
                    if action in ("LONG", "ADD_LONG"):
                        # 多头：计算止损和止盈的幅度
                        stop_loss_pct = abs(current_price - stop_loss) / current_price
                        take_profit_pct = abs(take_profit - current_price) / current_price

                        if stop_loss_pct > self.max_stop_loss_pct:
                            errors.append(f"止损幅度过大: {stop_loss_pct:.2%} > {self.max_stop_loss_pct:.2%}")
                        if take_profit_pct > self.max_take_profit_pct:
                            errors.append(f"止盈幅度过大: {take_profit_pct:.2%} > {self.max_take_profit_pct:.2%}")

                    elif action in ("SHORT", "ADD_SHORT"):
                        # 空头：计算止损和止盈的幅度
                        stop_loss_pct = abs(stop_loss - current_price) / current_price
                        take_profit_pct = abs(current_price - take_profit) / current_price

                        if stop_loss_pct > self.max_stop_loss_pct:
                            errors.append(f"止损幅度过大: {stop_loss_pct:.2%} > {self.max_stop_loss_pct:.2%}")
                        if take_profit_pct > self.max_take_profit_pct:
                            errors.append(f"止盈幅度过大: {take_profit_pct:.2%} > {self.max_take_profit_pct:.2%}")

        # 5. 验证理由
        reason = decision.get("reason", "")
        if not reason or len(reason.strip()) == 0:
            warnings.append("决策缺少理由说明")
        elif len(reason) < 5:
            warnings.append("决策理由过短")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_for_context(
        self,
        decision: dict,
        account_balance: float,
        available_margin: float,
        current_position: int,
        current_price: float = 0
    ) -> ValidationResult:
        """根据账户状态验证决策

        Args:
            decision: 决策字典
            account_balance: 账户总资金
            available_margin: 可用保证金
            current_position: 当前持仓
            current_price: 当前价格（用于验证止损止盈幅度）

        Returns:
            ValidationResult: 验证结果
        """
        # 先进行基础验证（传递当前价格用于止损止盈验证）
        context = {"current_price": current_price} if current_price > 0 else None
        result = self.validate(decision, context)

        action = decision.get("action", "")
        position_size = decision.get("position_size", 0)

        # 根据操作类型进行额外验证
        if action in ("LONG", "SHORT"):
            # 开仓操作：检查是否有足够资金
            required_margin = account_balance * position_size
            if required_margin > available_margin:
                result.errors.append(
                    f"资金不足: 需要{required_margin:.2f}, 可用{available_margin:.2f}"
                )

        elif action == "CLOSE":
            # 平仓操作：检查是否有持仓
            if current_position == 0:
                result.errors.append("无持仓可平")

        elif action in ("ADD_LONG", "ADD_SHORT"):
            # 加仓操作：检查是否有持仓
            if current_position == 0:
                result.errors.append("无持仓可加仓")

        return result
