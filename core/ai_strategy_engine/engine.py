#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI策略引擎核心

整合所有模块，提供完整的AI决策能力。
支持回测(run_cycle)和实盘(decide)两种使用方式。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from loguru import logger

from core.ai_clients.factory import AIClientFactory
from core.ai_strategy_engine.context.context_builder import ContextBuilder
from core.ai_strategy_engine.decision.parser import EnhancedDecisionParser, ParsedDecision
from core.ai_strategy_engine.decision.executor import DecisionExecutor, TradingContext
from core.ai_strategy_engine.decision.validator import DecisionValidator
from core.ai_strategy_engine.risk.manager import RiskManager
from core.ai_strategy_engine.risk.position_sizer import PositionSizer
from core.ai_strategy_engine.prompts.builder import PromptBuilder
from core.ai_strategy_engine.modes import TradingMode
from core.ai_strategy_engine.cache import AICache, compute_cache_key


@dataclass
class AIStrategyConfig:
    """AI策略配置（增强版）

    整合了原BacktestDecisionEngine的配置项
    """
    # AI配置
    ai_model: str = "gpt-3.5-turbo"
    api_key: str = ""
    api_base: Optional[str] = None

    # 决策配置
    decision_interval: int = 5
    max_context_bars: int = 100

    # 风险配置
    max_positions: int = 3
    max_position_size: float = 0.3
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05

    # 提示词配置
    prompt_template: str = "default"
    trading_mode: str = "conservative"

    # === 新增: 缓存配置（从BacktestDecisionEngine迁移） ===
    enable_cache: bool = False
    cache_path: Optional[str] = None

    # === 新增: 调试配置 ===
    verbose_logging: bool = False


@dataclass
class DecisionResult:
    """决策结果（统一格式）
    
    支持回测和实盘两种场景
    """
    # 基础字段
    success: bool
    action: str = "HOLD"              # LONG/SHORT/CLOSE/HOLD/ADD_LONG/ADD_SHORT/REDUCE
    confidence: float = 0.0
    reason: str = ""
    reasoning: str = ""               # CoT思维链

    # 交易参数
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    quantity: Optional[int] = None

    # 验证信息
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)

    # 回测兼容字段
    decision: Optional[ParsedDecision] = None
    execution_result: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # 元数据
    datetime: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "success": self.success,
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "reasoning": self.reasoning,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "quantity": self.quantity,
            "validation_errors": self.validation_errors,
            "validation_warnings": self.validation_warnings,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DecisionResult":
        """从字典恢复（用于缓存恢复）"""
        return cls(
            success=data.get("success", False),
            action=data.get("action", "HOLD"),
            confidence=data.get("confidence", 0.0),
            reason=data.get("reason", ""),
            reasoning=data.get("reasoning", ""),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            position_size=data.get("position_size"),
            quantity=data.get("quantity"),
            validation_errors=data.get("validation_errors", []),
            validation_warnings=data.get("validation_warnings", []),
        )


class AIStrategyEngine:
    """AI策略引擎

    整合所有模块，提供完整的AI决策能力。

    使用方式：
    1. 回测模式：engine.run_cycle(strategy, bar)
    2. 实盘模式：engine.decide(context)
    """

    def __init__(
        self,
        config: Optional[AIStrategyConfig] = None,
        # 支持简化初始化参数
        ai_model: str = "gpt-3.5-turbo",
        api_key: str = "",
        prompt_template: str = "default",
        trading_mode: str = "conservative",
        max_position_size: float = 0.3,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.05,
    ):
        """初始化AI策略引擎

        Args:
            config: AI策略配置对象（优先使用）
            ai_model: AI模型名称（简化参数）
            api_key: API密钥（简化参数）
            prompt_template: 提示词模板（简化参数）
            trading_mode: 交易模式（简化参数）
            max_position_size: 最大仓位比例（简化参数）
            stop_loss_pct: 止损百分比（简化参数）
            take_profit_pct: 止盈百分比（简化参数）
        """
        # 支持两种初始化方式
        if config is None:
            config = AIStrategyConfig(
                ai_model=ai_model,
                api_key=api_key,
                prompt_template=prompt_template,
                trading_mode=trading_mode,
                max_position_size=max_position_size,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )
        
        self.config = config
        self.max_position_size = config.max_position_size

        # 初始化AI客户端
        self.ai_client = None
        if config.api_key:
            try:
                self.ai_client = AIClientFactory.create(
                    model_name=config.ai_model,
                    api_key=config.api_key
                )
            except Exception as e:
                raise ValueError(f"AI客户端初始化失败: {e}")

        # 初始化组件
        self.context_builder = ContextBuilder()
        self.trading_mode = TradingMode.from_string(config.trading_mode)
        self.prompt_builder = PromptBuilder(
            template_name=config.prompt_template,
            trading_mode=self.trading_mode
        )
        self.parser = EnhancedDecisionParser()
        self.validator = DecisionValidator(
            trading_mode=self.trading_mode,
            max_position_size=config.max_position_size
        )
        self.risk_manager = RiskManager()
        self.position_sizer = PositionSizer(self.risk_manager)

        # === 新增: 初始化缓存（从BacktestDecisionEngine迁移） ===
        self.cache: Optional[AICache] = None
        if config.enable_cache:
            cache_path = config.cache_path or f".cache/ai_cache_{config.ai_model}.json"
            self.cache = AICache(cache_path=cache_path)
            logger.info(f"AI缓存已启用: {cache_path}")

    def decide(
        self,
        context: Dict,
        mode: str = "auto"
    ) -> DecisionResult:
        """执行AI决策（实盘推荐）

        简化的决策接口，直接接收上下文字典。

        整合了原BacktestDecisionEngine的特性：
        - AI缓存（可选）
        - 富上下文构建
        - 调试日志（可选）

        Args:
            context: 决策上下文（统一格式）
            mode: 运行模式 ("auto" | "backtest" | "live")

        Returns:
            DecisionResult: 决策结果
        """
        dt = context.get("datetime", datetime.now())

        if not self.ai_client:
            return DecisionResult(
                success=False,
                action="HOLD",
                datetime=dt,
                validation_errors=["AI客户端未初始化"]
            )

        try:
            # === 新增: 检查缓存 ===
            if self.cache:
                cache_key = compute_cache_key(
                    context,
                    self.config.prompt_template,
                    dt
                )
                cached = self.cache.get(cache_key)
                if cached:
                    logger.debug(f"缓存命中: {cache_key[:16]}...")
                    return DecisionResult.from_dict(cached)

            # === 新增: 构建富上下文 ===
            rich_context = self._build_rich_context(context)

            # 1. 构建提示词
            system_prompt = self.prompt_builder.build_system_prompt(self.risk_manager)
            user_prompt = self.prompt_builder.build_user_prompt(
                rich_context,
                rich_context.get("history")
            )

            # === 新增: 调试日志 ===
            if self.config.verbose_logging:
                self._log_prompts(system_prompt, user_prompt)

            # 2. 调用AI模型
            ai_response = self._call_ai_model(system_prompt, user_prompt)

            # === 新增: 调试日志（AI响应） ===
            if self.config.verbose_logging:
                logger.info("=" * 80)
                logger.info("AI 响应:")
                logger.info(ai_response)
                logger.info("=" * 80)

            # 3. 解析响应
            parsed_decision = self.parser.parse(ai_response)

            # 4. 验证决策
            account = rich_context.get("account", {})
            validation = self.validator.validate_for_context(
                {
                    "action": parsed_decision.action,
                    "position_size": parsed_decision.position_size,
                    "confidence": parsed_decision.confidence,
                    "stop_loss": parsed_decision.stop_loss,
                    "take_profit": parsed_decision.take_profit,
                    "reason": parsed_decision.reason,  # 修复：传递reason字段用于验证
                },
                account_balance=account.get("balance", 100000),
                available_margin=account.get("available", 100000),
                current_position=rich_context.get("positions", [])
            )

            if not validation.is_valid:
                result = DecisionResult(
                    success=False,
                    action=parsed_decision.action,
                    confidence=parsed_decision.confidence,
                    reason=parsed_decision.reason,
                    reasoning=parsed_decision.reasoning,
                    stop_loss=parsed_decision.stop_loss,
                    take_profit=parsed_decision.take_profit,
                    position_size=parsed_decision.position_size,
                    validation_errors=validation.errors,
                    validation_warnings=validation.warnings,
                    datetime=dt,
                )
                return result

            # 5. 构建成功结果
            result = DecisionResult(
                success=True,
                action=parsed_decision.action,
                confidence=parsed_decision.confidence,
                reason=parsed_decision.reason,
                reasoning=parsed_decision.reasoning,
                stop_loss=parsed_decision.stop_loss,
                take_profit=parsed_decision.take_profit,
                position_size=parsed_decision.position_size,
                validation_warnings=validation.warnings,
                datetime=dt,
            )

            # 6. 计算手数（回测模式）
            if mode in ("backtest", "auto"):
                result.quantity = self._calculate_quantity(
                    rich_context,
                    parsed_decision.position_size
                )

            # === 新增: 缓存结果 ===
            if self.cache and result.success:
                cache_key = compute_cache_key(
                    context,
                    self.config.prompt_template,
                    dt
                )
                self.cache.put(
                    cache_key=cache_key,
                    variant=self.config.prompt_template,
                    datetime_obj=dt,
                    decision=result.to_dict()
                )

            # === 新增: 成功交易提醒 ===
            if result.action != "HOLD" and self.config.verbose_logging:
                logger.warning("=" * 80)
                logger.warning(f"[SUCCESS] 成功交易决策!")
                logger.warning(f"   操作: {result.action}")
                logger.warning(f"   置信度: {result.confidence:.2%}")
                logger.warning(f"   理由: {result.reason}")
                logger.warning("=" * 80)

            return result

        except Exception as e:
            logger.error(f"决策执行失败: {e}")
            return DecisionResult(
                success=False,
                action="HOLD",
                datetime=dt,
                validation_errors=[f"决策执行失败: {e}"]
            )

    def run_cycle(
        self,
        strategy: Any,
        current_bar: Any
    ) -> DecisionResult:
        """执行一个完整的决策周期（回测推荐）

        Args:
            strategy: vnpy策略实例
            current_bar: 当前K线数据

        Returns:
            DecisionResult: 决策结果
        """
        dt = current_bar.datetime

        try:
            # 1. 构建交易上下文
            context = self.context_builder.build(strategy, current_bar, self.config)

            # 2. 生成提示词
            system_prompt = self.prompt_builder.build_system_prompt(self.risk_manager)
            user_prompt = self.prompt_builder.build_user_prompt(
                context,
                getattr(strategy, 'decision_history', None)
            )

            # 3. 调用AI模型
            if not self.ai_client:
                return DecisionResult(
                    success=False,
                    errors=["AI客户端未初始化"],
                    datetime=dt
                )

            ai_response = self._call_ai_model(system_prompt, user_prompt)

            # 4. 解析响应
            parsed_decision = self.parser.parse(ai_response)

            # 5. 验证决策
            account = context.get("account", {})
            validation = self.validator.validate_for_context(
                {
                    "action": parsed_decision.action,
                    "position_size": parsed_decision.position_size,
                    "confidence": parsed_decision.confidence,
                    "stop_loss": parsed_decision.stop_loss,
                    "take_profit": parsed_decision.take_profit,
                    "reason": parsed_decision.reason,  # 修复：传递reason字段用于验证
                },
                account_balance=account.get("balance", 100000),
                available_margin=account.get("available", 100000),
                current_position=strategy.pos
            )

            if not validation.is_valid:
                return DecisionResult(
                    success=False,
                    action=parsed_decision.action,
                    confidence=parsed_decision.confidence,
                    reason=parsed_decision.reason,
                    reasoning=parsed_decision.reasoning,
                    decision=parsed_decision,
                    errors=validation.errors,
                    warnings=validation.warnings,
                    datetime=dt
                )

            # 6. 执行决策
            executor = DecisionExecutor(position_sizer=self.position_sizer)
            trading_context = TradingContext(
                datetime=dt,
                symbol=getattr(strategy, 'vt_symbol', ''),
                current_bar=current_bar,
                account_balance=account.get("balance", 100000),
                available_margin=account.get("available", 100000),
                current_position=strategy.pos
            )

            execution_result = executor.execute(
                {
                    "action": parsed_decision.action,
                    "position_size": parsed_decision.position_size,
                    "confidence": parsed_decision.confidence,
                    "reason": parsed_decision.reason,
                    "stop_loss": parsed_decision.stop_loss,
                    "take_profit": parsed_decision.take_profit,
                },
                trading_context
            )

            return DecisionResult(
                success=execution_result.success,
                action=parsed_decision.action,
                confidence=parsed_decision.confidence,
                reason=parsed_decision.reason,
                reasoning=parsed_decision.reasoning,
                stop_loss=parsed_decision.stop_loss,
                take_profit=parsed_decision.take_profit,
                position_size=parsed_decision.position_size,
                quantity=execution_result.quantity if hasattr(execution_result, 'quantity') else None,
                decision=parsed_decision,
                execution_result=execution_result,
                warnings=validation.warnings,
                datetime=dt
            )

        except Exception as e:
            return DecisionResult(
                success=False,
                action="HOLD",
                errors=[f"决策执行失败: {e}"],
                datetime=dt
            )

    def _build_rich_context(self, context: Dict) -> Dict:
        """构建富上下文（从BacktestDecisionEngine迁移）

        添加：
        - Schema字段定义（让AI理解数据含义）
        - 20日高低点统计
        - 趋势方向推断
        - 历史价格序列

        Args:
            context: 原始上下文

        Returns:
            Dict: 增强后的上下文
        """
        rich_context = context.copy()

        # 获取市场数据
        market = context.get("market", {})
        indicators = context.get("indicators", {})

        # 计算20日高低点（如果有历史数据）
        history = context.get("history", [])
        if history:
            recent_20 = history[-20:] if len(history) >= 20 else history
            closes = [h.get("close", 0) for h in recent_20]
            highs = [h.get("high", 0) for h in recent_20]
            lows = [h.get("low", 0) for h in recent_20]

            if closes:
                rich_context["market"] = {
                    **market,
                    "high_20": max(highs) if highs else market.get("current_price", 0),
                    "low_20": min(lows) if lows else market.get("current_price", 0),
                    "change_pct": ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0,
                }

        # 计算趋势方向（基于 EMA(9,20,60) 的 arrangement 或 快线9 vs 中线20）
        ema_blk = indicators.get("ema") or {}
        trend_direction = None
        if isinstance(ema_blk, dict):
            arrangement = ema_blk.get("arrangement")
            if arrangement == "bullish":
                trend_direction = "up"
            elif arrangement == "bearish":
                trend_direction = "down"
            else:
                ema_9 = float(ema_blk.get("ema_9") or 0)
                ema_20 = float(ema_blk.get("ema_20") or 0)
                if ema_9 and ema_20:
                    if ema_9 > ema_20 * 1.002:
                        trend_direction = "up"
                    elif ema_9 < ema_20 * 0.998:
                        trend_direction = "down"
                    else:
                        trend_direction = "sideways"

        if trend_direction is not None:
            rich_context["market"] = {
                **rich_context.get("market", market),
                "trend_direction": trend_direction,
            }

        # 添加Schema字段定义（简化版，与 BacktestAdapter 嵌套指标一致）
        rich_context["schema_hints"] = {
            "price_fields": {
                "current_price": "当前价格（元）",
                "open": "开盘价",
                "high": "最高价",
                "low": "最低价",
                "volume": "成交量",
            },
            "indicator_fields": {
                "ema": "EMA(9,20,60)：ema_9/ema_20/ema_60、arrangement(bullish/bearish/neutral)",
                "sma": "SMA(25,60,100)：sma_25/sma_60/sma_100、arrangement",
                "macd": "MACD(12,26,9)：dif/dea/macd、trend、cross_signal、dif_history",
                "rsi": "RSI(14)：value、history",
                "dmi": "DMI/ADX(14,7)：adx、plus_di、minus_di",
                "boll": "布林带(20,2)：upper/middle/lower、price_position、squeeze",
                "atr": "ATR(14)：value、pct",
            }
        }

        return rich_context

    def _log_prompts(self, system_prompt: str, user_prompt: str) -> None:
        """输出完整的提示词调试日志"""
        # 输出完整的 System Prompt
        logger.info("=" * 100)
        logger.info("【AI System Prompt - 完整内容】")
        logger.info("=" * 100)
        logger.info(system_prompt)
        logger.info("=" * 100)

        # 输出完整的 User Prompt
        logger.info("=" * 100)
        logger.info("【AI User Prompt - 完整内容】")
        logger.info("=" * 100)
        logger.info(user_prompt)
        logger.info("=" * 100)

    def _call_ai_model(self, system_prompt: str, user_prompt: str) -> Any:
        """调用AI模型"""
        if self.ai_client.supports_function_calling():
            functions = self.prompt_builder.get_trading_functions()
            return self.ai_client.generate_decision_with_functions(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                functions=functions
            )
        else:
            return self.ai_client.generate_decision(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

    def _calculate_quantity(self, context: Dict, position_size: float) -> int:
        """计算手数"""
        account = context.get("account", {})
        market = context.get("market", {})

        balance = account.get("balance", 100000)
        available = account.get("available", 100000)
        current_price = market.get("current_price", 1)

        return self.position_sizer.calculate(
            {"position_size": position_size, "confidence": 0.7},
            account_balance=balance,
            available_margin=available,
            current_price=current_price,
            symbol=context.get("symbol", "")
        )

    def get_risk_manager(self) -> RiskManager:
        """获取风险管理器"""
        return self.risk_manager

    def get_position_sizer(self) -> PositionSizer:
        """获取仓位计算器"""
        return self.position_sizer


