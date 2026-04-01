#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词构建器

整合数据字典和风险指南，生成完整的系统提示词和用户提示词。
"""

from typing import Dict, Optional, Any, List
from datetime import datetime

from core.ai_strategy_engine.schema.futures_schema import futures_schema
from core.ai_strategy_engine.modes import TradingMode
from config.ai_prompt_components import (
    PROMPT_COMPONENTS,
    FUNCTION_CALLING_SCHEMA,
    INDICATOR_THRESHOLDS,
    DATA_PROCESSING,
    INTERVAL_NAMES,
    INTERVAL_ORDER,
    POSITION_SIZING,
    TREND_ANALYSIS,
    get_trading_mode_guidance,
    get_interval_name,
    format_position_sizing_guidance,
)


class PromptBuilder:
    """提示词构建器

    整合：
    1. 数据字典（Schema）
    2. 风险控制指南
    3. 交易模式指导
    4. 完整的上下文格式化
    """

    def __init__(self, template_name: str = "default", trading_mode: TradingMode = TradingMode.AGGRESSIVE):
        """初始化提示词构建器

        Args:
            template_name: 模板名称（保留用于兼容性）
            trading_mode: 交易模式
        """
        self.template_name = template_name
        self.trading_mode = trading_mode
        self.schema = futures_schema

    def build_system_prompt(self, risk_manager: Optional[Any] = None) -> str:
        """构建系统提示词

        系统提示词包含：
        1. 角色定义
        2. 交易模式指导
        3. 数据字典（Schema）
        4. 风险控制要求
        5. 输出格式说明

        Args:
            risk_manager: 风险管理器（可选）

        Returns:
            str: 系统提示词
        """
        sections = [
            self._get_role_definition(),
            self._get_trading_mode_guidance(),
            self.schema.get_full_schema(),
            self._get_smc_analysis_guide(),
            self._get_risk_guidelines(risk_manager),
            self._get_output_format_spec(),
        ]

        return "\n\n".join(sections)

    def build_user_prompt(
        self,
        context: Dict[str, Any],
        decision_history: Optional[list] = None
    ) -> str:
        """构建用户提示词

        用户提示词包含：
        1. 当前时间和品种
        2. 账户状态
        3. 持仓明细
        4. 市场数据（价格、指标）
        5. 历史决策
        6. 决策请求

        Args:
            context: 决策上下文
            decision_history: 决策历史（可选）

        Returns:
            str: 用户提示词
        """
        sections = [
            self._format_header(context),
            self._format_account(context),
            self._format_position_sizing_guidance(context),
        ]

        # 持仓明细（可选）
        if context.get("positions"):
            sections.append(self._format_positions(context))

        sections.extend([
            self._format_market(context),
            self._format_indicators(context),
        ])

        # 原始K线数据（如果有）
        if context.get("recent_bars"):
            sections.append(self._format_recent_bars(context))

        # 交易指导（如果有）
        if context.get("trading_guidance"):
            sections.append(f"## 技术指标交易指导\n\n{context['trading_guidance']}")

        # SMC分析（如果有）
        if context.get("smc"):
            sections.append(self._format_smc(context))

        # 多周期趋势分析（如果有多周期数据）
        if context.get("market_data"):
            multi_timeframe_section = self._format_multi_timeframe(context)
            if multi_timeframe_section:
                sections.append(multi_timeframe_section)

        # 历史决策（可选）
        if decision_history:
            sections.append(self._format_decision_history(decision_history))

        sections.append(self._format_request())

        return "\n\n".join(sections)

    def _get_role_definition(self) -> str:
        """获取角色定义"""
        return PROMPT_COMPONENTS["role_definition"]

    def _get_trading_mode_guidance(self) -> str:
        """获取交易模式指导"""
        return get_trading_mode_guidance(self.trading_mode.value)

    def _get_risk_guidelines(self, risk_manager: Optional[Any] = None) -> str:
        """获取风险指南（动态填充所有交易模式相关参数）"""
        if risk_manager:
            return risk_manager.get_risk_guidelines("cn")

        # 获取当前交易模式配置
        mode_config = self.trading_mode.get_config()
        min_size, max_size = mode_config["position_size_range"]
        min_confidence = mode_config.get("min_confidence", 0.5)

        # 获取全局风险限制
        from config.ai_strategy_config import RISK_LIMITS

        template = PROMPT_COMPONENTS["risk_guidelines_template"]
        return template.format(
            max_positions=RISK_LIMITS["hard_limits"]["max_positions"],
            max_position_value=RISK_LIMITS["hard_limits"]["max_position_value"],
            min_confidence=min_confidence,
            max_daily_loss=RISK_LIMITS["hard_limits"]["max_daily_loss"],
            target_reward_ratio=RISK_LIMITS["soft_limits"]["target_reward_ratio"],
            min_conf_pct=int(min_confidence * 100),
            position_size_min=min_size,
            position_size_max=max_size,
        )

    def _get_smc_analysis_guide(self) -> str:
        """获取SMC指标分析指南"""
        return PROMPT_COMPONENTS["smc_analysis_guide"]

    def _get_output_format_spec(self) -> str:
        """获取输出格式说明"""
        return PROMPT_COMPONENTS["output_format_spec"]

    def _format_header(self, context: Dict) -> str:
        """格式化头部信息"""
        dt = context.get("datetime")
        symbol = context.get("symbol", "UNKNOWN")

        return f"""## 当前交易信息

- **时间**: {dt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(dt, 'strftime') else dt}
- **品种**: {symbol}
"""

    def _format_account(self, context: Dict) -> str:
        """格式化账户信息"""
        account = context.get("account", {})
        balance = account.get("balance", 0)
        available = account.get("available", 0)
        total_pnl = account.get("total_pnl", 0)

        return f"""## 账户状态

- **总资金**: {balance:.2f}元
- **可用资金**: {available:.2f}元
- **总盈亏**: {total_pnl:.2f}元
"""

    def _format_position_sizing_guidance(self, context: Dict) -> str:
        """格式化仓位规模计算指导"""
        account = context.get("account", {})
        balance = account.get("balance", 100000)

        # 获取交易模式配置
        mode_config = self.trading_mode.get_config()
        min_size, max_size = mode_config["position_size_range"]
        min_confidence = mode_config["min_confidence"]

        return format_position_sizing_guidance(
            balance=balance,
            trading_mode=self.trading_mode.value,
            min_size=min_size,
            max_size=max_size,
            min_confidence=min_confidence
        )

    def _format_positions(self, context: Dict) -> str:
        """格式化持仓信息"""
        positions = context.get("positions", [])
        lines = ["## 当前持仓\n"]

        for pos in positions:
            lines.append(
                f"- {pos.get('symbol', 'N/A')}: {pos.get('side', 'N/A')} "
                f"{pos.get('quantity', 0)}手 @{pos.get('entry_price', 0):.2f}"
            )

        return "\n".join(lines)

    def _format_market(self, context: Dict) -> str:
        """格式化市场数据"""
        market = context.get("market", {})
        price = market.get("current_price", 0)
        open_price = market.get("open", price)
        high_price = market.get("high", price)
        low_price = market.get("low", price)
        volume = market.get("volume", 0)
        summary = market.get("summary", {})

        change_pct = summary.get("change_pct", 0)
        high_20 = summary.get("high_20", price)
        low_20 = summary.get("low_20", price)

        # 获取当前分析的时间周期
        primary_interval = self._get_primary_interval(context)
        interval_name = get_interval_name(primary_interval) if primary_interval else "未知周期"

        # 基础市场数据
        lines = [
            "## 市场数据\n",
            f"**分析周期**: {interval_name}（以下数据基于此周期）\n",
            f"- **当前价格**: {price:.2f}",
            f"- **OHLC**: 开{open_price:.2f} / 高{high_price:.2f} / 低{low_price:.2f} / 收{price:.2f}",
            f"- **成交量**: {volume:.0f}手",
            f"- **涨跌幅**: {change_pct:+.2f}%",
            f"- **20日高点**: {high_20:.2f}",
            f"- **20日低点**: {low_20:.2f}",
        ]

        # 历史价格序列（如果有）
        price_history = market.get("price_history", {})
        if price_history and price_history.get("close"):
            close_prices = price_history["close"]
            high_prices = price_history["high"]
            low_prices = price_history["low"]

            # 只显示最近N根K线的价格（避免过长）
            recent_count = min(DATA_PROCESSING["recent_bars_display"], len(close_prices))
            recent_closes = close_prices[-recent_count:]

            lines.append(f"\n### 近期价格走势（最近{recent_count}根K线）")
            lines.append(f"- **收盘价序列**: {', '.join([f'{p:.2f}' for p in recent_closes])}")

            # 计算价格变化趋势
            lookback = DATA_PROCESSING["price_change_lookback"]
            if len(close_prices) >= lookback:
                price_ago = close_prices[-lookback]
                price_change = (price - price_ago) / price_ago * 100 if price_ago > 0 else 0
                lines.append(f"- **{lookback}根K线涨跌**: {price_change:+.2f}%")

            # 价格位置（相对于近期高低点）
            position_lookback = DATA_PROCESSING["price_position_lookback"]
            if len(high_prices) >= position_lookback and len(low_prices) >= position_lookback:
                recent_high = max(high_prices[-position_lookback:])
                recent_low = min(low_prices[-position_lookback:])
                if recent_high > recent_low:
                    price_position = (price - recent_low) / (recent_high - recent_low) * 100
                    lines.append(f"- **价格位置**: {price_position:.1f}% (0%=近期低点, 100%=近期高点)")

        # 趋势方向（如果有）
        trend_direction = market.get("trend_direction")
        if trend_direction:
            trend_text = TREND_ANALYSIS["trend_direction_map"].get(trend_direction, trend_direction)
            lines.append(f"- **趋势方向**: {trend_text}")

        return "\n".join(lines)

    def _format_indicators(self, context: Dict) -> str:
        """格式化技术指标（唯一格式：嵌套字典，与 BacktestAdapter 一致）

        - ema: EMA(9,20,60) → ema_9, ema_20, ema_60, arrangement
        - sma: SMA(25,60,100) → sma_25, sma_60, sma_100, arrangement
        - macd/rsi/dmi/boll/atr: 各为子字典
        """
        indicators = context.get("indicators", {})
        lines = ["## 技术指标（主周期）\n"]

        if not indicators:
            lines.append("无指标数据")
            return "\n".join(lines)

        # EMA(9,20,60)
        ema_data = indicators.get("ema")
        if isinstance(ema_data, dict):
            arrangement = ema_data.get("arrangement", "neutral")
            arr_text = {"bullish": "多头排列", "bearish": "空头排列"}.get(arrangement, "震荡排列")
            ema_vals = [f"EMA{k.split('_')[1]}: {v:.2f}" for k, v in ema_data.items()
                        if k.startswith("ema_") and not k.startswith("prev_")]
            if ema_vals:
                lines.append("### EMA均线 (9,20,60)")
                lines.append(f"- {', '.join(ema_vals)}")
                lines.append(f"- **排列状态**: {arr_text}")

        # SMA
        sma_data = indicators.get("sma")
        if isinstance(sma_data, dict):
            arrangement = sma_data.get("arrangement", "neutral")
            arr_text = {"bullish": "多头排列", "bearish": "空头排列"}.get(arrangement, "震荡排列")
            sma_vals = [f"SMA{k.split('_')[1]}: {v:.2f}" for k, v in sma_data.items()
                        if k.startswith("sma_") and not k.startswith("prev_")]
            if sma_vals:
                lines.append("\n### SMA均线 (25,60,100)")
                lines.append(f"- {', '.join(sma_vals)}")
                lines.append(f"- **排列状态**: {arr_text}")

        # MACD(12,26,9)
        macd_data = indicators.get("macd")
        if isinstance(macd_data, dict):
            dif = macd_data.get("dif", 0)
            dea = macd_data.get("dea", 0)
            macd_val = macd_data.get("macd", 0)
            lines.append("\n### MACD (12,26,9)")
            lines.append(f"- DIF: {dif:.4f}, DEA: {dea:.4f}, MACD: {macd_val:.4f}")

            macd_signals = TREND_ANALYSIS["macd_signals"]
            if dif > dea and dif > 0:
                lines.append(f"- **信号**: {macd_signals['strong_bullish']}")
            elif dif > dea and dif < 0:
                lines.append(f"- **信号**: {macd_signals['weak_rebound']}")
            elif dif < dea and dif > 0:
                lines.append(f"- **信号**: {macd_signals['strong_pullback']}")
            else:
                lines.append(f"- **信号**: {macd_signals['weak_bearish']}")

            cross = macd_data.get("cross_signal")
            if cross:
                cross_text = "金叉" if cross == "golden_cross" else "死叉"
                lines.append(f"- **交叉信号**: {cross_text}")

            dif_hist = macd_data.get("dif_history")
            if dif_hist:
                lines.append(f"- **DIF近10期**: {', '.join(str(x) for x in dif_hist)}")

        # RSI(14)
        rsi_data = indicators.get("rsi")
        if isinstance(rsi_data, dict):
            rsi = rsi_data.get("value", 50)
            lines.append("\n### RSI")
            lines.append(f"- **RSI(14)**: {rsi:.2f}")

            rsi_states = TREND_ANALYSIS["rsi_states"]
            rsi_overbought = INDICATOR_THRESHOLDS["rsi_overbought"]
            rsi_oversold = INDICATOR_THRESHOLDS["rsi_oversold"]
            rsi_bullish = INDICATOR_THRESHOLDS["rsi_bullish"]

            if rsi >= rsi_overbought:
                lines.append(f"- **状态**: {rsi_states['overbought']}")
            elif rsi <= rsi_oversold:
                lines.append(f"- **状态**: {rsi_states['oversold']}")
            elif rsi >= rsi_bullish:
                lines.append(f"- **状态**: {rsi_states['bullish']}")
            else:
                lines.append(f"- **状态**: {rsi_states['bearish']}")

            rsi_hist = rsi_data.get("history")
            if rsi_hist:
                lines.append(f"- **近10期**: {', '.join(str(x) for x in rsi_hist)}")

        # 布林带(20,2)
        boll_data = indicators.get("boll")
        if isinstance(boll_data, dict):
            lines.append("\n### 布林带 (20,2)")
            lines.append(
                f"- 上轨: {boll_data.get('upper', 0):.2f}, "
                f"中轨: {boll_data.get('middle', 0):.2f}, "
                f"下轨: {boll_data.get('lower', 0):.2f}"
            )
            pp = boll_data.get("price_position")
            if pp is not None:
                lines.append(f"- **价格位置**: {pp:.1f}% (0%=下轨, 100%=上轨)")
            if boll_data.get("squeeze"):
                lines.append("- **状态**: 布林带收窄 (挤压中)")

        # DMI / ADX
        dmi_data = indicators.get("dmi")
        if isinstance(dmi_data, dict):
            adx = dmi_data.get("adx", 25)
            plus_di = dmi_data.get("plus_di", 20)
            minus_di = dmi_data.get("minus_di", 20)

            adx_strong = INDICATOR_THRESHOLDS["adx_strong_trend"]
            adx_medium = INDICATOR_THRESHOLDS["adx_medium_trend"]

            # 确定趋势强度和方向
            if adx >= adx_strong:
                strength = "强"
                direction = "↑" if plus_di > minus_di else "↓"
            elif adx >= adx_medium:
                strength = "中"
                direction = "↑" if plus_di > minus_di else "↓"
            else:
                strength = "弱"
                direction = "→"

            # 一行输出
            lines.append(f"\n### ADX趋势: {adx:.1f} ({strength}{direction})")

        # ATR(14)
        atr_data = indicators.get("atr")
        if isinstance(atr_data, dict):
            atr_val = atr_data.get("value", 0)
            atr_pct = atr_data.get("pct", 0)
            lines.append("\n### ATR波动率")
            lines.append(f"- **ATR(14)**: {atr_val:.2f} ({atr_pct:.2f}%)")

            atr_volatility = TREND_ANALYSIS["atr_volatility"]
            atr_high = INDICATOR_THRESHOLDS["atr_high_volatility"]
            atr_medium = INDICATOR_THRESHOLDS["atr_medium_volatility"]

            if atr_pct > atr_high:
                lines.append(f"- **波动率**: {atr_volatility['high']}")
            elif atr_pct > atr_medium:
                lines.append(f"- **波动率**: {atr_volatility['medium']}")
            else:
                lines.append(f"- **波动率**: {atr_volatility['low']}")

        return "\n".join(lines)

    def _format_recent_bars(self, context: Dict) -> str:
        """格式化原始K线数据

        参考旧版 collect_market_data 的 recent_bars_info，
        将原始 OHLCV 展示给 AI 做形态识别和价格行为分析。
        """
        recent_bars = context.get("recent_bars", {})
        if not recent_bars:
            return ""

        lines = ["## 近期K线数据\n"]

        for section_key, label in [("primary", "主周期"), ("secondary", "次周期")]:
            section = recent_bars.get(section_key)
            if not section:
                continue

            tf = section.get("timeframe", "")
            bars = section.get("bars", [])
            tf_name = get_interval_name(tf) if tf else tf

            lines.append(f"### {label}（{tf_name}，最近{len(bars)}根）")
            lines.append("| 时间 | 开 | 高 | 低 | 收 | 量 |")
            lines.append("|------|------|------|------|------|------|")

            for b in bars:
                lines.append(
                    f"| {b['datetime']} | {b['open']:.2f} | {b['high']:.2f} | "
                    f"{b['low']:.2f} | {b['close']:.2f} | {b['volume']} |"
                )
            lines.append("")

        return "\n".join(lines)

    def _format_smc(self, context: Dict) -> str:
        """格式化SMC市场结构背景（精简版，辅助参考）"""
        smc = context.get("smc", {})
        if not smc:
            return ""

        lines = ["## SMC 市场结构背景（辅助参考）\n"]
        lines.append("⚠️ 以下为市场结构背景信息，非决策依据。请优先依据技术指标信号。\n")

        # 1. 市场结构
        structure = smc.get("market_structure", {})
        if structure:
            major_high = structure.get("major_high")
            major_low = structure.get("major_low")
            if major_high or major_low:
                lines.append("### 市场结构")
                if major_high:
                    lines.append(f"- **Major高点**: {major_high['price']:.2f} ({major_high['type']})")
                if major_low:
                    lines.append(f"- **Major低点**: {major_low['price']:.2f} ({major_low['type']})")

        # 2. 关键支撑/阻力位（精简为各3个）
        support = smc.get("support_levels", [])
        resistance = smc.get("resistance_levels", [])

        if support or resistance:
            lines.append("\n### 关键价位")
            if resistance:
                lines.append(f"- **阻力位**: {', '.join(f'{r:.2f}' for r in resistance)}")
            if support:
                lines.append(f"- **支撑位**: {', '.join(f'{s:.2f}' for s in support)}")

        return "\n".join(lines)

    def _format_multi_timeframe(self, context: Dict) -> str:
        """格式化多周期趋势分析（market_data 内 indicators 均为嵌套字典）"""
        market_data = context.get("market_data", {})
        if not market_data:
            return ""

        symbol = context.get("symbol")
        symbol_data = market_data.get(symbol, {})

        if not symbol_data or len(symbol_data) <= 1:
            return ""

        lines = ["## 多周期趋势分析\n"]

        available_intervals = [i for i in INTERVAL_ORDER if i in symbol_data]
        if not available_intervals:
            return ""

        timeframe_trends = {}
        for interval in available_intervals:
            interval_data = symbol_data[interval]
            indicators = interval_data.get("indicators", {})
            parts = []

            # EMA(9,20,60)
            ema_data = indicators.get("ema")
            if isinstance(ema_data, dict):
                arr = ema_data.get("arrangement", "neutral")
                if arr == "bullish":
                    parts.append("EMA多头排列")
                elif arr == "bearish":
                    parts.append("EMA空头排列")
                else:
                    parts.append("EMA震荡")

            # SMA(25,60,100)
            sma_data = indicators.get("sma")
            if isinstance(sma_data, dict):
                arr = sma_data.get("arrangement", "neutral")
                if arr == "bullish":
                    parts.append("SMA多头")
                elif arr == "bearish":
                    parts.append("SMA空头")

            # MACD(12,26,9)
            macd_data = indicators.get("macd")
            if isinstance(macd_data, dict):
                dif = macd_data.get("dif", 0)
                dea = macd_data.get("dea", 0)
                cross = macd_data.get("cross_signal")
                if cross == "golden_cross":
                    parts.append("MACD金叉")
                elif cross == "death_cross":
                    parts.append("MACD死叉")
                elif dif > dea and dif > 0:
                    parts.append("MACD强多")
                elif dif > dea:
                    parts.append("MACD弱多")
                elif dif < dea and dif < 0:
                    parts.append("MACD强空")
                else:
                    parts.append("MACD弱空")

            # RSI(14)
            rsi_data = indicators.get("rsi")
            rsi = rsi_data.get("value", 50) if isinstance(rsi_data, dict) else None

            if rsi is not None:
                if rsi >= INDICATOR_THRESHOLDS["rsi_overbought"]:
                    parts.append(f"RSI超买({rsi:.0f})")
                elif rsi <= INDICATOR_THRESHOLDS["rsi_oversold"]:
                    parts.append(f"RSI超卖({rsi:.0f})")
                else:
                    parts.append(f"RSI({rsi:.0f})")

            # DMI/ADX(14,7)
            dmi_data = indicators.get("dmi")
            adx = dmi_data.get("adx", 0) if isinstance(dmi_data, dict) else None

            if adx is not None:
                if adx >= INDICATOR_THRESHOLDS["adx_strong_trend"]:
                    parts.append(f"趋势强({adx:.0f})")
                elif adx >= INDICATOR_THRESHOLDS["adx_medium_trend"]:
                    parts.append(f"趋势中({adx:.0f})")
                # 弱趋势不显示，避免过度提示

            # 布林带
            boll_data = indicators.get("boll")
            if isinstance(boll_data, dict):
                pp = boll_data.get("price_position")
                if pp is not None:
                    if pp >= 90:
                        parts.append("BOLL上轨压力")
                    elif pp <= 10:
                        parts.append("BOLL下轨支撑")
                if boll_data.get("squeeze"):
                    parts.append("BOLL挤压")

            timeframe_trends[interval] = " | ".join(parts) if parts else "数据不足"

        for interval in available_intervals:
            interval_name = get_interval_name(interval)
            lines.append(f"- **{interval_name}**: {timeframe_trends[interval]}")

        # 趋势一致性分析
        total_count = len(timeframe_trends)

        lines.append("\n### 多周期共振分析")

        bullish_tfs = sum(1 for t in timeframe_trends.values()
                          if any(kw in t for kw in ["多头排列", "强多", "上涨", "金叉"]))
        bearish_tfs = sum(1 for t in timeframe_trends.values()
                          if any(kw in t for kw in ["空头排列", "强空", "下跌", "死叉"]))

        consensus_threshold = INDICATOR_THRESHOLDS["multi_timeframe_consensus"]
        if bullish_tfs >= total_count * consensus_threshold:
            lines.append(f"- **趋势一致性**: 强烈看涨 ({bullish_tfs}/{total_count}个周期偏多)")
        elif bearish_tfs >= total_count * consensus_threshold:
            lines.append(f"- **趋势一致性**: 强烈看跌 ({bearish_tfs}/{total_count}个周期偏空)")
        elif bullish_tfs > bearish_tfs:
            lines.append(f"- **趋势一致性**: 偏多 ({bullish_tfs}多 vs {bearish_tfs}空)")
        elif bearish_tfs > bullish_tfs:
            lines.append(f"- **趋势一致性**: 偏空 ({bearish_tfs}空 vs {bullish_tfs}多)")
        else:
            lines.append(f"- **趋势一致性**: 分歧 (多空力量均衡)")

        return "\n".join(lines)

    def _get_interval_name(self, interval: str) -> str:
        """获取周期的中文名称（已弃用，使用配置中的函数）

        Args:
            interval: 周期代码（如 "1m", "1h"）

        Returns:
            str: 中文名称
        """
        return get_interval_name(interval)

    def _get_primary_interval(self, context: Dict) -> str:
        """获取主要分析周期

        Args:
            context: 决策上下文

        Returns:
            str: 主要周期代码（如 "1m", "5m"）
        """
        # 优先使用 context 中明确指定的主决策周期
        if "primary_interval" in context:
            return context["primary_interval"]

        # 尝试从market_data中推断主要周期
        market_data = context.get("market_data", {})
        if market_data:
            symbol = context.get("symbol")
            symbol_data = market_data.get(symbol, {})
            if symbol_data:
                # 按照从小到大的顺序返回第一个可用周期
                for interval in INTERVAL_ORDER:
                    if interval in symbol_data:
                        return interval
                # 如果都不在，返回第一个
                return list(symbol_data.keys())[0]

        # 如果无法推断，返回空字符串
        return ""

    def _format_decision_history(self, history: list) -> str:
        """格式化决策历史"""
        lines = ["## 近期决策历史\n"]

        display_count = DATA_PROCESSING["decision_history_display"]
        for i, dec in enumerate(history[-display_count:], 1):
            # 使用 datetime 字段
            dt = dec.get("datetime", "")
            action = dec.get("action", "")
            reason = dec.get("reason", "")
            lines.append(f"{i}. {dt} - {action} - {reason}")

        return "\n".join(lines)

    def _format_request(self) -> str:
        """格式化决策请求"""
        return PROMPT_COMPONENTS["decision_request"]

    def get_trading_functions(self) -> List[Dict]:
        """获取交易函数定义（用于Function Calling）

        Returns:
            List[Dict]: 函数定义列表
        """
        return FUNCTION_CALLING_SCHEMA
