#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单品种AI策略

使用统一AI引擎进行决策的标准策略。
支持vnpy实盘的on_tick → on_bar流程。
支持vnpy_ctastrategy回测框架。
"""

from typing import Optional, List, Dict
from datetime import datetime, time

from vnpy.trader.object import BarData, TickData, TradeData, OrderData
from vnpy.trader.utility import BarGenerator, ArrayManager
from vnpy.trader.constant import Interval

from core.strategies.base_strategy import BaseCtaStrategy
from core.ai_strategy_engine import (
    AIStrategyEngine,
    AIStrategyConfig,
    ContextBuilder,
    BacktestAdapter,
    detect_backtest_mode,
)
from config.trading_sessions_config import get_trading_session_by_symbol


class SingleSymbolAIStrategy(BaseCtaStrategy):
    """单品种AI策略

    特性：
    1. 使用统一AI引擎进行决策
    2. 支持on_tick → on_bar标准流程
    3. 可配置的提示词模板
    4. 完整的风险管理
    5. 回测和实盘共享相同逻辑
    6. 支持vnpy_ctastrategy回测框架
    7. 回测时自动启用AI缓存

    策略参数：
        ai_model: AI模型名称
        api_key: API密钥
        decision_interval: 决策间隔（每N根K线触发一次）
        prompt_template: 提示词模板名称
        trading_mode: 交易模式（conservative/aggressive/scalping）
        max_position_size: 最大仓位比例
        stop_loss_pct: 止损百分比
        take_profit_pct: 止盈百分比
        enable_cache: 是否启用AI缓存（回测时自动启用）
        verbose_logging: 是否启用详细日志
    """

    author = "AI Single"

    parameters = [
        "ai_model",
        "api_key",
        "primary_timeframe",
        "secondary_timeframe",
        "decision_interval",
        "prompt_template",
        "trading_mode",
        "max_position_size",
        "stop_loss_pct",
        "take_profit_pct",
        "enable_cache",
        "verbose_logging",
    ]

    variables = [
        "bar_count",
        "total_decisions",
        "successful_decisions",
        "is_backtest_mode",
    ]

    # 默认参数值
    ai_model: str = "deepseek-chat"
    api_key: str = ""
    primary_timeframe: str = "1h"
    secondary_timeframe: str = "15m"
    decision_interval: int = 1
    prompt_template: str = "default"
    trading_mode: str = "aggressive"  # 默认激进模式
    max_position_size: float = 0.3
    stop_loss_pct: float = 0.0  # 0表示使用交易模式配置
    take_profit_pct: float = 0.0  # 0表示使用交易模式配置
    enable_cache: bool = False  # 回测时自动启用
    verbose_logging: bool = False

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """初始化策略

        Args:
            cta_engine: CTA引擎
            strategy_name: 策略名称
            vt_symbol: 交易品种
            setting: 策略参数字典
        """
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 应用交易模式配置（如果stop_loss_pct/take_profit_pct为0或未显式设置）
        self._apply_trading_mode_config()

        # 检测回测模式（直接使用模块函数）
        self.is_backtest_mode = detect_backtest_mode(self)

        # 回测时自动启用缓存和详细日志
        if self.is_backtest_mode:
            if not self.enable_cache:
                self.enable_cache = True
                self.logger.info("回测模式，自动启用AI缓存")
            if not self.verbose_logging:
                self.verbose_logging = True
                self.logger.info("回测模式，自动启用详细日志（含完整提示词）")

        # 初始化统一AI引擎
        self.ai_engine: Optional[AIStrategyEngine] = None
        self.backtest_adapter: Optional[BacktestAdapter] = None

        if self.api_key:
            try:
                # 创建配置（支持缓存）
                config = AIStrategyConfig(
                    ai_model=self.ai_model,
                    api_key=self.api_key,
                    prompt_template=self.prompt_template,
                    trading_mode=self.trading_mode,
                    max_position_size=self.max_position_size,
                    stop_loss_pct=self.stop_loss_pct,
                    take_profit_pct=self.take_profit_pct,
                    enable_cache=self.enable_cache,
                    cache_path=f".cache/ai_cache_{vt_symbol.replace('.', '_')}.json" if self.enable_cache else None,
                    verbose_logging=self.verbose_logging,
                )

                self.ai_engine = AIStrategyEngine(config=config)
                self.logger.info(f"AI引擎初始化成功: {self.ai_model}")

                # 回测模式下创建适配器
                if self.is_backtest_mode:
                    self.backtest_adapter = BacktestAdapter(self, self.ai_engine)
                    self.logger.info("回测适配器已启用")

            except Exception as e:
                self.logger.error(f"AI引擎初始化失败: {e}")
        else:
            self.logger.warning("未设置API密钥，AI决策功能将被禁用")

        # Tick合成1分钟K线（实盘用）
        self.bg = BarGenerator(self.on_bar, window=1, interval=Interval.MINUTE)

        # 1分钟ArrayManager（止损止盈检查用）
        self.am = ArrayManager()

        # 多周期BarGenerator和ArrayManager
        self._setup_multi_timeframe()

        # 策略变量
        self.bar_count = 0
        self.htf_bar_count = 0
        self.total_decisions = 0
        self.successful_decisions = 0

        # 决策历史
        self.decision_history: List[Dict] = []

        # 多周期K线历史（供适配器SMC检测器使用）
        self.htf_bar_history: List[BarData] = []
        self.ltf_bar_history: List[BarData] = []

        # 持仓相关
        self.entry_price = 0.0
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0

        # 上下文构建器
        self.context_builder = ContextBuilder()

    def _apply_trading_mode_config(self) -> None:
        """应用交易模式配置

        如果stop_loss_pct或take_profit_pct为0（未显式设置），
        则从交易模式配置中读取默认值。
        """
        from config.ai_strategy_config import get_trading_mode_config

        mode_config = get_trading_mode_config(self.trading_mode)

        # 如果stop_loss_pct为0或接近0，使用交易模式配置
        if self.stop_loss_pct <= 0.001:
            self.stop_loss_pct = mode_config.get("stop_loss_pct", 0.02)
            self.logger.info(f"使用{self.trading_mode}模式止损配置: {self.stop_loss_pct:.1%}")

        # 如果take_profit_pct为0或接近0，使用交易模式配置
        if self.take_profit_pct <= 0.001:
            self.take_profit_pct = mode_config.get("take_profit_pct", 0.05)
            self.logger.info(f"使用{self.trading_mode}模式止盈配置: {self.take_profit_pct:.1%}")

    def on_init(self) -> None:
        """策略初始化回调"""
        self.logger.info("单品种AI策略初始化")
        self.write_log("单品种AI策略初始化")

        # 根据主周期计算需要加载的1分钟K线数量
        # 至少需要100根主周期K线来初始化指标（EMA26等需要足够历史数据）
        p_window, _ = self._parse_timeframe(self.primary_timeframe)
        bars_needed = max(100 * p_window, 2000)
        self.load_bar(bars_needed)

        # 回测模式下，在初始化时展示完整配置（只展示一次）
        # 移到 on_init 而不是 on_start，确保在回测时一定会展示
        self.logger.info(f"[DEBUG] is_backtest_mode={self.is_backtest_mode}, ai_engine={'存在' if self.ai_engine else '不存在'}")
        if self.is_backtest_mode and self.ai_engine:
            self.logger.info("回测模式确认，准备展示配置信息...")
            self._log_initial_config()
        else:
            self.logger.info(f"跳过配置展示: is_backtest_mode={self.is_backtest_mode}")

    def on_start(self) -> None:
        """策略启动回调"""
        self.logger.info("单品种AI策略启动")
        self.write_log("单品种AI策略启动")

        if not self.ai_engine:
            self.logger.error("AI引擎未初始化，策略无法正常运行")

    def on_stop(self) -> None:
        """策略停止回调"""
        self.logger.info(
            f"单品种AI策略停止，"
            f"总决策次数: {self.total_decisions}, "
            f"成功决策: {self.successful_decisions}"
        )
        self.write_log(
            f"单品种AI策略停止，"
            f"总决策次数: {self.total_decisions}, "
            f"成功决策: {self.successful_decisions}"
        )

    def on_tick(self, tick: TickData) -> None:
        """Tick数据回调

        合成分钟K线，然后触发on_bar

        Args:
            tick: Tick数据
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """1分钟K线回调

        将1分钟K线喂给所有周期的BarGenerator，由各Generator聚合后
        回调on_htf_bar/on_ltf_bar。AI决策在主周期K线完成时触发。

        注意：只处理回测正式开始后的数据，初始化阶段的数据仅用于
        ArrayManager初始化，不触发BarGenerator和AI决策。
        """
        # 更新ArrayManager（初始化和回测阶段都需要）
        self.bar_count += 1
        self.am.update_bar(bar)

        # 只在策略正式启动后才处理多周期数据和风控
        # 这样避免load_bar()加载的初始化数据触发决策
        if self.trading:
            # 喂给多周期Generator
            self.htf_bg.update_bar(bar)
            self.ltf_bg.update_bar(bar)

            # 风险管理每根1分钟K线都检查
            self._check_risk_management(bar)

    def on_htf_bar(self, bar: BarData) -> None:
        """主周期K线回调 — 触发AI决策"""
        self.htf_am.update_bar(bar)
        self.htf_bar_count += 1

        self.htf_bar_history.append(bar)
        if len(self.htf_bar_history) > 600:
            self.htf_bar_history = self.htf_bar_history[-500:]

        if self.htf_am.inited and self.htf_bar_count % self.decision_interval == 0:
            self._make_ai_decision(bar)

    def on_ltf_bar(self, bar: BarData) -> None:
        """次周期K线回调 — 仅更新ArrayManager和K线历史"""
        self.ltf_am.update_bar(bar)

        self.ltf_bar_history.append(bar)
        if len(self.ltf_bar_history) > 600:
            self.ltf_bar_history = self.ltf_bar_history[-500:]

    # ==================== 多周期设置 ====================

    @staticmethod
    def _parse_timeframe(tf: str):
        """将周期字符串解析为 (window, Interval)

        '15m' → (15, Interval.MINUTE)
        '1h'  → (1,  Interval.HOUR)
        '4h'  → (4,  Interval.HOUR)
        'd'   → (1,  Interval.DAILY)
        """
        tf = tf.strip().lower()
        if tf.endswith("h"):
            return int(tf[:-1]), Interval.HOUR
        elif tf == "d" or tf.endswith("d"):
            return (int(tf[:-1]) if len(tf) > 1 else 1), Interval.DAILY
        else:
            return int(tf.rstrip("m")), Interval.MINUTE

    def _setup_multi_timeframe(self) -> None:
        """初始化多周期BarGenerator和ArrayManager"""
        symbol = self.vt_symbol.split(".")[0]
        exchange = self.vt_symbol.split(".")[1] if "." in self.vt_symbol else ""
        trading_session = get_trading_session_by_symbol(symbol, exchange)

        # 合并日盘和夜盘时段（如果品种有夜盘）
        all_hour_sessions = list(trading_session.hour_sessions or [])
        if trading_session.has_night_session and trading_session.night_sessions:
            all_hour_sessions.extend(trading_session.night_sessions)

        p_window, p_interval = self._parse_timeframe(self.primary_timeframe)
        self.htf_bg = BarGenerator(
            on_bar=self.on_bar,
            window=p_window,
            on_window_bar=self.on_htf_bar,
            interval=p_interval,
            daily_end=trading_session.daily_end,
            hour_sessions=all_hour_sessions if all_hour_sessions else None,
        )
        self.htf_am = ArrayManager(size=100)

        s_window, s_interval = self._parse_timeframe(self.secondary_timeframe)
        self.ltf_bg = BarGenerator(
            on_bar=self.on_bar,
            window=s_window,
            on_window_bar=self.on_ltf_bar,
            interval=s_interval,
            daily_end=trading_session.daily_end,
            hour_sessions=all_hour_sessions if all_hour_sessions else None,
        )
        self.ltf_am = ArrayManager(size=100)

        self.logger.info(
            f"多周期初始化完成: 主周期={self.primary_timeframe}, "
            f"次周期={self.secondary_timeframe}, "
            f"交易时段={len(all_hour_sessions)}个 "
            f"(日盘={len(trading_session.hour_sessions or [])}, "
            f"夜盘={len(trading_session.night_sessions or [])})"
        )

    def on_trade(self, trade: TradeData) -> None:
        """成交回报回调

        Args:
            trade: 成交数据
        """
        super().on_trade(trade)
        self.logger.success(
            f"成交: {trade.direction.value} {trade.volume}手 "
            f"@{trade.price:.2f}"
        )

    def on_order(self, order: OrderData) -> None:
        """委托回报回调

        Args:
            order: 委托数据
        """
        super().on_order(order)

    def _make_ai_decision(self, bar: BarData) -> None:
        """执行AI决策

        在回测模式下使用BacktestAdapter，在实盘模式下使用标准流程。

        Args:
            bar: 当前K线数据
        """
        if not self.ai_engine:
            self.logger.warning("AI引擎未初始化，跳过决策")
            return

        try:
            # 回测模式：使用适配器
            if self.is_backtest_mode and self.backtest_adapter:
                result = self.backtest_adapter.make_decision(bar)

                self.total_decisions += 1

                if result.success:
                    self.successful_decisions += 1

                    # 记录决策
                    self._record_decision(result, bar)

                    # 执行决策（通过适配器）
                    self.backtest_adapter.execute_decision(result, bar)

                    # 记录警告
                    for warning in result.validation_warnings:
                        self.logger.warning(f"决策警告: {warning}")
                else:
                    # 记录错误
                    for error in result.validation_errors:
                        self.logger.error(f"决策失败: {error}")

            # 实盘模式：使用标准流程
            else:
                # 构建上下文
                context = self.context_builder.build(
                    strategy=self,
                    current_bar=bar,
                    mode="live"
                )

                # 执行AI决策
                result = self.ai_engine.decide(context, mode="live")

                self.total_decisions += 1

                if result.success:
                    self.successful_decisions += 1

                    # 记录决策
                    self._record_decision(result, bar)

                    # 执行决策
                    self._execute_decision(result, bar)

                    # 记录警告
                    for warning in result.validation_warnings:
                        self.logger.warning(f"决策警告: {warning}")
                else:
                    # 记录错误
                    for error in result.validation_errors:
                        self.logger.error(f"决策失败: {error}")

        except Exception as e:
            self.logger.error(f"AI决策失败: {e}")
            self.write_log(f"AI决策失败: {e}")

    def _execute_decision(
        self,
        result,
        bar: BarData
    ) -> None:
        """执行交易决策

        Args:
            result: AI决策结果
            bar: 当前K线数据
        """
        action = result.action
        current_pos = self.pos

        # 根据决策执行交易
        if action == "LONG":
            if current_pos >= 0:
                self._execute_long(result, bar)
            else:
                # 先平空，再开多
                self._close_short(bar)
                self._execute_long(result, bar)

        elif action == "SHORT":
            if current_pos <= 0:
                self._execute_short(result, bar)
            else:
                # 先平多，再开空
                self._close_long(bar)
                self._execute_short(result, bar)

        elif action == "CLOSE":
            if current_pos > 0:
                self._close_long(bar)
            elif current_pos < 0:
                self._close_short(bar)

        elif action == "HOLD":
            self.logger.info(f"AI决策: 持仓 - {result.reason}")

        # 更新止损止盈
        if action in ("LONG", "SHORT") and result.stop_loss and result.take_profit:
            self.stop_loss_price = result.stop_loss
            self.take_profit_price = result.take_profit

    def _execute_long(self, result, bar: BarData) -> None:
        """执行开多"""
        if self.pos >= 0:
            self.logger.info("已有多头持仓，跳过开多")
            return

        # 使用AI引擎的仓位计算器计算手数
        quantity = self.ai_engine.get_position_sizer().calculate(
            {"position_size": result.position_size or self.max_position_size,
             "confidence": result.confidence},
            account_balance=100000,  # 应该从账户获取
            available_margin=100000,
            current_price=bar.close_price,
            symbol=self.vt_symbol
        )

        if quantity > 0:
            order_ids = self.buy(bar.close_price, quantity)
            self.entry_price = bar.close_price
            if result.stop_loss:
                self.stop_loss_price = result.stop_loss
            else:
                self.stop_loss_price = bar.close_price * (1 - self.stop_loss_pct)
            if result.take_profit:
                self.take_profit_price = result.take_profit
            else:
                self.take_profit_price = bar.close_price * (1 + self.take_profit_pct)

            self.write_log(
                f"AI开多: 价格={bar.close_price:.2f}, "
                f"数量={quantity}, 理由={result.reason}"
            )
        else:
            self.logger.warning("开多数量为0，跳过")

    def _execute_short(self, result, bar: BarData) -> None:
        """执行开空"""
        if self.pos <= 0:
            self.logger.info("已有空头持仓，跳过开空")
            return

        quantity = self.ai_engine.get_position_sizer().calculate(
            {"position_size": result.position_size or self.max_position_size,
             "confidence": result.confidence},
            account_balance=100000,
            available_margin=100000,
            current_price=bar.close_price,
            symbol=self.vt_symbol
        )

        if quantity > 0:
            order_ids = self.short(bar.close_price, quantity)
            self.entry_price = bar.close_price
            if result.stop_loss:
                self.stop_loss_price = result.stop_loss
            else:
                self.stop_loss_price = bar.close_price * (1 + self.stop_loss_pct)
            if result.take_profit:
                self.take_profit_price = result.take_profit
            else:
                self.take_profit_price = bar.close_price * (1 - self.take_profit_pct)

            self.write_log(
                f"AI开空: 价格={bar.close_price:.2f}, "
                f"数量={quantity}, 理由={result.reason}"
            )
        else:
            self.logger.warning("开空数量为0，跳过")

    def _close_long(self, bar: BarData) -> None:
        """平多"""
        if self.pos <= 0:
            return

        order_ids = self.sell(bar.close_price, abs(self.pos))
        self.write_log(f"AI平多: 价格={bar.close_price:.2f}")

        self.entry_price = 0.0
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0

    def _close_short(self, bar: BarData) -> None:
        """平空"""
        if self.pos >= 0:
            return

        order_ids = self.cover(bar.close_price, abs(self.pos))
        self.write_log(f"AI平空: 价格={bar.close_price:.2f}")

        self.entry_price = 0.0
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0

    def _log_initial_config(self) -> None:
        """在回测开始时展示真实System Prompt和User Prompt（只展示一次）"""
        if not self.ai_engine:
            return

        try:
            # 获取风险管理器
            risk_manager = self.ai_engine.get_risk_manager()

            # 1. 策略基本配置（单行）
            config_line = (
                f"AI策略配置 | 模型:{self.ai_model} | 模式:{self.trading_mode} | "
                f"间隔:{self.decision_interval}K线 | 仓位:{self.max_position_size:.0%} | "
                f"止损:{self.stop_loss_pct:.0%} | 止盈:{self.take_profit_pct:.0%} | "
                f"缓存:{'开' if self.enable_cache else '关'}"
            )
            self.logger.info(config_line)

            # 2. System Prompt
            self.logger.info("\n[System Prompt]")
            system_prompt = self.ai_engine.prompt_builder.build_system_prompt(risk_manager)
            self.logger.info(system_prompt)

            # 3. User Prompt（示例数据）
            self.logger.info("\n[User Prompt - 示例格式]")
            sample_context = {
                "datetime": datetime.now(),
                "symbol": self.vt_symbol,
                "account": {
                    "balance": 100000.0,
                    "available": 95000.0,
                    "total_pnl": 0.0,
                },
                "market": {
                    "current_price": 3500.0,
                    "open": 3495.0,
                    "high": 3510.0,
                    "low": 3490.0,
                    "volume": 10000,
                    "summary": {
                        "change_pct": 0.15,
                        "high_20": 3550.0,
                        "low_20": 3400.0,
                    },
                },
                "indicators": {
                    "ema": {
                        "ema_9": 3498.0,
                        "ema_20": 3495.0,
                        "ema_60": 3488.0,
                        "arrangement": "bullish",
                    },
                    "sma": {
                        "sma_25": 3496.0,
                        "sma_60": 3490.0,
                        "sma_100": 3475.0,
                        "arrangement": "bullish",
                    },
                    "macd": {
                        "dif": 2.5,
                        "dea": 2.0,
                        "macd": 0.5,
                        "trend": "bullish",
                        "cross_signal": None,
                    },
                    "rsi": {"value": 55.0},
                    "dmi": {"adx": 25.0, "plus_di": 20.0, "minus_di": 15.0},
                    "boll": {
                        "upper": 3520.0,
                        "middle": 3495.0,
                        "lower": 3470.0,
                        "width": 50.0,
                        "squeeze": False,
                        "price_position": 50.0,
                    },
                    "atr": {"value": 25.0, "pct": 0.71},
                },
                "positions": [],
            }
            user_prompt = self.ai_engine.prompt_builder.build_user_prompt(sample_context)
            self.logger.info(user_prompt)

            self.logger.info("开始回测...")
        except Exception as e:
            self.logger.error(f"配置信息输出失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _check_risk_management(self, bar: BarData) -> None:
        """风险管理检查

        Args:
            bar: 当前K线数据
        """
        if self.pos == 0:
            return

        # 检查止损
        if self.stop_loss_price > 0:
            if self.pos > 0 and bar.close_price <= self.stop_loss_price:
                self.write_log(
                    f"触发止损: 价格={bar.close_price:.2f}, "
                    f"止损价={self.stop_loss_price:.2f}"
                )
                self.sell(bar.close_price, abs(self.pos), stop=True)
            elif self.pos < 0 and bar.close_price >= self.stop_loss_price:
                self.write_log(
                    f"触发止损: 价格={bar.close_price:.2f}, "
                    f"止损价={self.stop_loss_price:.2f}"
                )
                self.cover(bar.close_price, abs(self.pos), stop=True)

        # 检查止盈
        if self.take_profit_price > 0:
            if self.pos > 0 and bar.close_price >= self.take_profit_price:
                self.write_log(
                    f"触发止盈: 价格={bar.close_price:.2f}, "
                    f"止盈价={self.take_profit_price:.2f}"
                )
                self.sell(bar.close_price, abs(self.pos), stop=True)
            elif self.pos < 0 and bar.close_price <= self.take_profit_price:
                self.write_log(
                    f"触发止盈: 价格={bar.close_price:.2f}, "
                    f"止盈价={self.take_profit_price:.2f}"
                )
                self.cover(bar.close_price, abs(self.pos), stop=True)

    def _record_decision(self, result, bar: BarData) -> None:
        """记录决策

        Args:
            result: AI决策结果
            bar: 当前K线数据
        """
        decision_record = {
            "timestamp": bar.datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": self.vt_symbol,
            "action": result.action,
            "position_size": result.position_size,
            "confidence": result.confidence,
            "reason": result.reason,
            "reasoning": result.reasoning[:200] if result.reasoning else "",
            "price": bar.close_price,
        }

        self.decision_history.append(decision_record)

        # 限制历史记录数量
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]

        self.logger.info(f"决策记录: {decision_record}")
