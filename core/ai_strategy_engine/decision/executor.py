#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
决策执行器

将AI决策转换为vnpy订单并执行。
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from core.ai_strategy_engine.risk.position_sizer import PositionSizer


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    message: str
    order_ids: list = field(default_factory=list)
    executed_price: Optional[float] = None
    executed_size: Optional[int] = None
    execution_time: Optional[datetime] = None


@dataclass
class TradingContext:
    """交易上下文"""
    datetime: datetime
    symbol: str
    current_bar: Any
    account_balance: float
    available_margin: float
    current_position: int
    entry_price: float = 0.0


class DecisionExecutor:
    """决策执行器

    职责：
    1. 将决策转换为vnpy订单
    2. 处理开仓、平仓、加仓、减仓
    3. 更新策略状态
    4. 决策排序（平仓优先）
    """

    SUPPORTED_ACTIONS = {
        "LONG",      # 开多
        "SHORT",     # 开空
        "CLOSE",     # 平仓
        "HOLD",      # 持仓
        "ADD_LONG",  # 加多
        "ADD_SHORT", # 加空
        "REDUCE",    # 减仓
    }

    # 决策优先级（数值越小优先级越高）
    ACTION_PRIORITY = {
        "CLOSE": 1,       # 平仓优先
        "REDUCE": 1,      # 减仓优先
        "LONG": 2,        # 开多
        "SHORT": 2,       # 开空
        "ADD_LONG": 3,    # 加多（已有盈利时）
        "ADD_SHORT": 3,   # 加空（已有盈利时）
        "HOLD": 99,       # 持有最低优先级
    }

    def __init__(self, strategy: Any, position_sizer: 'PositionSizer'):
        """初始化执行器

        Args:
            strategy: vnpy策略实例
            position_sizer: 仓位计算器
        """
        self.strategy = strategy
        self.position_sizer = position_sizer

    @staticmethod
    def sort_decisions(decisions: list) -> list:
        """对多个决策进行排序（平仓优先）

        Args:
            decisions: 决策列表，每个元素包含 'action' 字段

        Returns:
            list: 排序后的决策列表
        """
        def get_priority(decision: dict) -> int:
            action = decision.get("action", "HOLD")
            return DecisionExecutor.ACTION_PRIORITY.get(action, 99)

        return sorted(decisions, key=get_priority)

    def execute(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行决策

        Args:
            decision: 解析后的决策字典
            context: 交易上下文

        Returns:
            ExecutionResult: 执行结果
        """
        action = decision.get("action", "HOLD")

        if action == "LONG":
            return self._execute_long(decision, context)
        elif action == "SHORT":
            return self._execute_short(decision, context)
        elif action == "CLOSE":
            return self._execute_close(decision, context)
        elif action == "HOLD":
            return ExecutionResult(
                success=True,
                message="持仓不变",
                execution_time=datetime.now()
            )
        elif action == "ADD_LONG":
            return self._execute_add_long(decision, context)
        elif action == "ADD_SHORT":
            return self._execute_add_short(decision, context)
        elif action == "REDUCE":
            return self._execute_reduce(decision, context)
        else:
            return ExecutionResult(
                success=False,
                message=f"不支持的操作类型: {action}",
                execution_time=datetime.now()
            )

    def _execute_long(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行开多

        Args:
            decision: 决策字典
            context: 交易上下文

        Returns:
            ExecutionResult: 执行结果
        """
        # 1. 检查是否有空单需要平仓
        if context.current_position < 0:
            self.strategy.logger.info("先平掉空单，再开多")
            price = context.current_bar.close_price
            self.strategy.cover(price, abs(context.current_position))

        # 2. 如果已经有多单，不再开仓
        if context.current_position > 0:
            return ExecutionResult(
                success=False,
                message="已有多单，跳过开多",
                execution_time=datetime.now()
            )

        # 3. 计算开仓数量
        quantity = self.position_sizer.calculate(
            decision=decision,
            account_balance=context.account_balance,
            available_margin=context.available_margin,
            current_price=context.current_bar.close_price,
            symbol=context.symbol,
            direction="long"
        )

        if quantity <= 0:
            return ExecutionResult(
                success=False,
                message=f"计算出的开仓数量为0: balance={context.account_balance}, "
                       f"position_size={decision.get('position_size', 0)}",
                execution_time=datetime.now()
            )

        # 4. 执行开仓
        price = context.current_bar.close_price
        order_ids = self.strategy.buy(price, quantity)

        # 5. 更新策略状态
        if hasattr(self.strategy, 'entry_price'):
            self.strategy.entry_price = price

        stop_loss = decision.get("stop_loss")
        take_profit = decision.get("take_profit")

        if stop_loss and hasattr(self.strategy, 'stop_loss_price'):
            self.strategy.stop_loss_price = stop_loss
        if take_profit and hasattr(self.strategy, 'take_profit_price'):
            self.strategy.take_profit_price = take_profit

        reason = decision.get("reason", "")
        self.strategy.write_log(
            f"AI开多: 价格={price:.2f}, 数量={quantity}, "
            f"止损={stop_loss}, 止盈={take_profit}, 理由={reason}"
        )

        return ExecutionResult(
            success=True,
            message=f"开多 {quantity}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=quantity,
            execution_time=datetime.now()
        )

    def _execute_short(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行开空

        Args:
            decision: 决策字典
            context: 交易上下文

        Returns:
            ExecutionResult: 执行结果
        """
        # 1. 检查是否有多单需要平仓
        if context.current_position > 0:
            self.strategy.logger.info("先平掉多单，再开空")
            price = context.current_bar.close_price
            self.strategy.sell(price, abs(context.current_position))

        # 2. 如果已经有空单，不再开仓
        if context.current_position < 0:
            return ExecutionResult(
                success=False,
                message="已有空单，跳过开空",
                execution_time=datetime.now()
            )

        # 3. 计算开仓数量
        quantity = self.position_sizer.calculate(
            decision=decision,
            account_balance=context.account_balance,
            available_margin=context.available_margin,
            current_price=context.current_bar.close_price,
            symbol=context.symbol,
            direction="short"
        )

        if quantity <= 0:
            return ExecutionResult(
                success=False,
                message=f"计算出的开仓数量为0",
                execution_time=datetime.now()
            )

        # 4. 执行开仓
        price = context.current_bar.close_price
        order_ids = self.strategy.short(price, quantity)

        # 5. 更新策略状态
        if hasattr(self.strategy, 'entry_price'):
            self.strategy.entry_price = price

        stop_loss = decision.get("stop_loss")
        take_profit = decision.get("take_profit")

        if stop_loss and hasattr(self.strategy, 'stop_loss_price'):
            self.strategy.stop_loss_price = stop_loss
        if take_profit and hasattr(self.strategy, 'take_profit_price'):
            self.strategy.take_profit_price = take_profit

        reason = decision.get("reason", "")
        self.strategy.write_log(
            f"AI开空: 价格={price:.2f}, 数量={quantity}, "
            f"止损={stop_loss}, 止盈={take_profit}, 理由={reason}"
        )

        return ExecutionResult(
            success=True,
            message=f"开空 {quantity}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=quantity,
            execution_time=datetime.now()
        )

    def _execute_close(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行平仓

        Args:
            decision: 决策字典
            context: 交易上下文

        Returns:
            ExecutionResult: 执行结果
        """
        if context.current_position == 0:
            return ExecutionResult(
                success=False,
                message="无持仓，跳过平仓",
                execution_time=datetime.now()
            )

        price = context.current_bar.close_price
        order_ids = []

        if context.current_position > 0:
            # 平多
            order_ids = self.strategy.sell(price, abs(context.current_position))
            self.strategy.write_log(f"AI平多: 价格={price:.2f}, 数量={abs(context.current_position)}")
        else:
            # 平空
            order_ids = self.strategy.cover(price, abs(context.current_position))
            self.strategy.write_log(f"AI平空: 价格={price:.2f}, 数量={abs(context.current_position)}")

        # 重置持仓相关变量
        if hasattr(self.strategy, 'entry_price'):
            self.strategy.entry_price = 0.0
        if hasattr(self.strategy, 'stop_loss_price'):
            self.strategy.stop_loss_price = 0.0
        if hasattr(self.strategy, 'take_profit_price'):
            self.strategy.take_profit_price = 0.0

        return ExecutionResult(
            success=True,
            message=f"平仓 {abs(context.current_position)}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=abs(context.current_position),
            execution_time=datetime.now()
        )

    def _execute_add_long(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行加多"""
        if context.current_position <= 0:
            return ExecutionResult(
                success=False,
                message="无多单可加仓",
                execution_time=datetime.now()
            )

        # 计算加仓数量（通常是原仓位的一半）
        original_decision = decision.copy()
        original_decision["position_size"] = decision.get("position_size", 0.5) / 2

        quantity = self.position_sizer.calculate(
            decision=original_decision,
            account_balance=context.account_balance,
            available_margin=context.available_margin,
            current_price=context.current_bar.close_price,
            symbol=context.symbol,
            direction="long"
        )
        if quantity <= 0:
            return ExecutionResult(
                success=False,
                message="计算出的加仓数量为0",
                execution_time=datetime.now()
            )

        price = context.current_bar.close_price
        order_ids = self.strategy.buy(price, quantity)

        self.strategy.write_log(f"AI加多: 价格={price:.2f}, 数量={quantity}")

        return ExecutionResult(
            success=True,
            message=f"加多 {quantity}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=quantity,
            execution_time=datetime.now()
        )

    def _execute_add_short(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行加空"""
        if context.current_position >= 0:
            return ExecutionResult(
                success=False,
                message="无空单可加仓",
                execution_time=datetime.now()
            )

        # 计算加仓数量
        original_decision = decision.copy()
        original_decision["position_size"] = decision.get("position_size", 0.5) / 2

        quantity = self.position_sizer.calculate(
            decision=original_decision,
            account_balance=context.account_balance,
            available_margin=context.available_margin,
            current_price=context.current_bar.close_price,
            symbol=context.symbol,
            direction="short"
        )
        if quantity <= 0:
            return ExecutionResult(
                success=False,
                message="计算出的加仓数量为0",
                execution_time=datetime.now()
            )

        price = context.current_bar.close_price
        order_ids = self.strategy.short(price, quantity)

        self.strategy.write_log(f"AI加空: 价格={price:.2f}, 数量={quantity}")

        return ExecutionResult(
            success=True,
            message=f"加空 {quantity}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=quantity,
            execution_time=datetime.now()
        )

    def _execute_reduce(self, decision: Dict, context: TradingContext) -> ExecutionResult:
        """执行减仓"""
        if context.current_position == 0:
            return ExecutionResult(
                success=False,
                message="无持仓可减仓",
                execution_time=datetime.now()
            )

        # 减仓一半
        reduce_size = abs(context.current_position) // 2
        if reduce_size == 0:
            reduce_size = 1

        price = context.current_bar.close_price

        if context.current_position > 0:
            # 减多
            order_ids = self.strategy.sell(price, reduce_size)
            self.strategy.write_log(f"AI减多: 价格={price:.2f}, 数量={reduce_size}")
        else:
            # 减空
            order_ids = self.strategy.cover(price, reduce_size)
            self.strategy.write_log(f"AI减空: 价格={price:.2f}, 数量={reduce_size}")

        return ExecutionResult(
            success=True,
            message=f"减仓 {reduce_size}手 @{price:.2f}",
            order_ids=order_ids,
            executed_price=price,
            executed_size=reduce_size,
            execution_time=datetime.now()
        )
