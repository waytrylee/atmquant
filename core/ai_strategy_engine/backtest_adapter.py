#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTA回测适配器

让AI策略能在vnpy_ctastrategy回测框架中运行。

使用方式：
    from core.ai_strategy_engine import BacktestAdapter, detect_backtest_mode

    # 在策略中检测回测模式
    if detect_backtest_mode(self):
        adapter = BacktestAdapter(self, self.ai_engine)
        result = adapter.make_decision(bar)
        adapter.execute_decision(result, bar)
"""

from typing import Dict, Optional, Any, List

import numpy as np
from loguru import logger

from vnpy.trader.object import BarData

from core.ai_strategy_engine.engine import AIStrategyEngine, DecisionResult
from core.indicators.calculators import (
    IndicatorManager,
    MACDCalculator,
    RSICalculator,
    EMACalculator,
    DMICalculator,
    SMACalculator,
    BollCalculator,
)


class BacktestAdapter:
    """CTA回测适配器

    让AI策略能在vnpy_ctastrategy回测框架中运行。
    支持多周期指标计算。

    功能：
    - 自动检测回测模式
    - 多周期指标计算（主周期 + 次周期）
    - 构建决策上下文（含 market_data 多周期结构）
    - 执行交易决策

    使用示例：
    ```python
    if detect_backtest_mode(self):
        adapter = BacktestAdapter(self, self.ai_engine)
        result = adapter.make_decision(bar)
        if result.success:
            adapter.execute_decision(result, bar)
    ```
    """

    def __init__(
        self,
        strategy: Any,
        engine: AIStrategyEngine,
        config: Optional[Dict] = None
    ):
        """初始化适配器

        Args:
            strategy: vnpy策略实例（CtaTemplate子类）
            engine: AI策略引擎实例
            config: 可选配置
        """
        self.strategy = strategy
        self.engine = engine
        self.config = config or {}

        # 从策略获取常用属性
        self.vt_symbol = getattr(strategy, 'vt_symbol', '')
        self.pos = getattr(strategy, 'pos', 0)

        # 多周期标识
        self._primary_tf = getattr(strategy, 'primary_timeframe', '1h')
        self._secondary_tf = getattr(strategy, 'secondary_timeframe', '15m')

        # 初始化多周期指标管理器
        self._init_indicators()

        logger.debug(
            f"BacktestAdapter初始化: {self.vt_symbol} "
            f"| 主周期={self._primary_tf} 次周期={self._secondary_tf}"
        )

    def _init_indicators(self) -> None:
        """初始化多周期技术指标计算器"""
        self.primary_indicators = IndicatorManager()
        self.primary_indicators.add("ema", EMACalculator(periods=(9, 20, 60)))
        self.primary_indicators.add("sma", SMACalculator(periods=(25, 60, 100)))
        self.primary_indicators.add("macd", MACDCalculator(12, 26, 9))
        self.primary_indicators.add("rsi", RSICalculator(14))
        self.primary_indicators.add("dmi", DMICalculator(14, 7))
        self.primary_indicators.add("boll", BollCalculator(20, 2.0))

        self.secondary_indicators = IndicatorManager()
        self.secondary_indicators.add("ema", EMACalculator(periods=(9, 20, 60)))
        self.secondary_indicators.add("sma", SMACalculator(periods=(25, 60, 100)))
        self.secondary_indicators.add("macd", MACDCalculator(12, 26, 9))
        self.secondary_indicators.add("rsi", RSICalculator(14))
        self.secondary_indicators.add("dmi", DMICalculator(14, 7))
        self.secondary_indicators.add("boll", BollCalculator(20, 2.0))

    def make_decision(self, bar: BarData) -> DecisionResult:
        """执行AI决策

        bar 是主周期（htf）K线，由策略的 on_htf_bar 传入。
        次周期指标从策略的 ltf_am 读取。

        Args:
            bar: 主周期K线数据

        Returns:
            DecisionResult: 决策结果
        """
        context = self._build_context(bar)
        return self.engine.decide(context, mode="backtest")

    def execute_decision(self, result: DecisionResult, bar: BarData) -> None:
        """执行交易决策

        Args:
            result: AI决策结果
            bar: 当前K线数据
        """
        if not result.success:
            logger.debug(f"决策未成功，跳过执行: {result.validation_errors}")
            return

        action = result.action
        quantity = result.quantity or 1
        self.pos = getattr(self.strategy, 'pos', 0)

        # 使用字典映射简化分支逻辑
        action_handlers = {
            "LONG": lambda: self._handle_long(bar, quantity),
            "SHORT": lambda: self._handle_short(bar, quantity),
            "CLOSE": lambda: self._handle_close(bar),
            "ADD_LONG": lambda: self._handle_add_long(bar, quantity),
            "ADD_SHORT": lambda: self._handle_add_short(bar, quantity),
            "REDUCE": lambda: self._handle_reduce(bar),
            "HOLD": lambda: logger.debug(f"AI持仓: {result.reason}"),
        }

        handler = action_handlers.get(action)
        if handler:
            handler()

    # ==================== 上下文构建 ====================

    def _build_context(self, bar: BarData) -> Dict:
        """构建决策上下文（含多周期数据和原始K线）

        参考旧版 collect_market_data 的丰富度，提供原始K线 + 多周期指标 + SMC。
        """
        ctx = {
            "datetime": bar.datetime,
            "symbol": bar.vt_symbol,
            "primary_interval": self._primary_tf,
            "secondary_interval": self._secondary_tf,
            "account": self._get_account_info(),
            "positions": self._get_positions(),
            "market": self._get_market_data(bar),
            "indicators": self._get_primary_indicators(),
        }

        # 原始K线数据（参考旧版 recent_bars_info）
        recent_bars = self._get_recent_bars()
        if recent_bars:
            ctx["recent_bars"] = recent_bars

        # 自然语言交易指导（参考旧版 technical_guidance）
        guidance = self._generate_trading_guidance(ctx.get("indicators", {}))
        if guidance:
            ctx["trading_guidance"] = guidance

        market_data = self._build_market_data(bar)
        if market_data:
            ctx["market_data"] = market_data

        return ctx

    def _get_account_info(self) -> Dict:
        """获取账户信息"""
        cta_engine = getattr(self.strategy, 'cta_engine', None)

        if not cta_engine:
            return {"balance": 100000, "available": 100000, "margin_used": 0}

        capital = getattr(cta_engine, 'capital', 100000)
        margin_used = 0

        if self.pos != 0:
            entry_price = getattr(self.strategy, 'entry_price', 0)
            margin_used = entry_price * abs(self.pos) * 0.1

        return {
            "balance": capital,
            "available": max(0, capital - margin_used),
            "margin_used": margin_used,
        }

    def _get_positions(self) -> list:
        """获取持仓信息"""
        if self.pos == 0:
            return []

        entry_price = getattr(self.strategy, 'entry_price', 0)
        return [{
            "symbol": self.vt_symbol,
            "side": "long" if self.pos > 0 else "short",
            "quantity": abs(self.pos),
            "entry_price": entry_price,
        }]

    def _get_recent_bars(self) -> Dict:
        """获取多周期原始K线数据

        参考旧版 collect_market_data 的 recent_bars_info 结构，
        提供原始 OHLCV 数据让 AI 自行做形态识别和结构分析。
        """
        result: Dict[str, Any] = {}

        # 主周期 K线（最近20根）
        htf_bars = getattr(self.strategy, 'htf_bar_history', [])
        if htf_bars and len(htf_bars) >= 5:
            bars = htf_bars[-20:]
            result["primary"] = {
                "timeframe": self._primary_tf,
                "count": len(bars),
                "bars": [
                    {
                        "datetime": b.datetime.strftime("%Y-%m-%d %H:%M") if hasattr(b.datetime, 'strftime') else str(b.datetime),
                        "open": round(b.open_price, 2),
                        "high": round(b.high_price, 2),
                        "low": round(b.low_price, 2),
                        "close": round(b.close_price, 2),
                        "volume": int(b.volume),
                    }
                    for b in bars
                ],
            }

        # 次周期 K线（最近8根）
        ltf_bars = getattr(self.strategy, 'ltf_bar_history', [])
        if ltf_bars and len(ltf_bars) >= 5:
            bars = ltf_bars[-8:]
            result["secondary"] = {
                "timeframe": self._secondary_tf,
                "count": len(bars),
                "bars": [
                    {
                        "datetime": b.datetime.strftime("%Y-%m-%d %H:%M") if hasattr(b.datetime, 'strftime') else str(b.datetime),
                        "open": round(b.open_price, 2),
                        "high": round(b.high_price, 2),
                        "low": round(b.low_price, 2),
                        "close": round(b.close_price, 2),
                        "volume": int(b.volume),
                    }
                    for b in bars
                ],
            }

        return result

    def _get_market_data(self, bar: BarData) -> Dict:
        """获取市场数据（含20根主周期K线的统计摘要）"""
        data: Dict[str, Any] = {
            "current_price": bar.close_price,
            "open": bar.open_price,
            "high": bar.high_price,
            "low": bar.low_price,
            "volume": bar.volume,
            "datetime": bar.datetime,
        }

        am = getattr(self.strategy, 'htf_am', None)
        if am and am.inited and len(am.close_array) >= 2:
            lookback = min(20, len(am.high_array))
            high_20 = float(max(am.high_array[-lookback:]))
            low_20 = float(min(am.low_array[-lookback:]))
            prev_close = float(am.close_array[-2])
            change_pct = (bar.close_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
            data["summary"] = {
                "change_pct": round(change_pct, 2),
                "high_20": round(high_20, 2),
                "low_20": round(low_20, 2),
            }

        return data

    # ==================== 多周期指标 ====================

    def _compute_indicators(self, indicator_mgr: "IndicatorManager", am) -> Dict:
        """从ArrayManager计算一组技术指标

        返回包含趋势、动量、波动率等多类指标的完整字典，
        参考旧版 collect_market_data 的数据丰富度。
        """
        indicators: Dict[str, Any] = {}
        if not am or not am.inited:
            return indicators

        try:
            indicator_mgr.update(am)
            current_price = float(am.close_array[-1]) if len(am.close_array) > 0 else 1

            # EMA（多周期）
            ema_calc = indicator_mgr.get("ema")
            if ema_calc and ema_calc.inited:
                v = ema_calc.get_values()
                indicators["ema"] = {
                    k: v[k] for k in v
                    if k.startswith("ema_") or k == "arrangement"
                }

            # SMA（多周期）
            sma_calc = indicator_mgr.get("sma")
            if sma_calc and sma_calc.inited:
                v = sma_calc.get_values()
                indicators["sma"] = {
                    k: v[k] for k in v
                    if k.startswith("sma_") or k == "arrangement"
                }

            # MACD（含历史和交叉信号）
            macd_calc = indicator_mgr.get("macd")
            if macd_calc and macd_calc.inited:
                v = macd_calc.get_values()
                indicators["macd"] = {
                    "dif": v.get("diff", 0),
                    "dea": v.get("signal", 0),
                    "macd": v.get("macd", 0),
                    "trend": v.get("trend"),
                    "cross_signal": v.get("cross_signal"),
                }
                # 近10根MACD历史（让AI看到指标趋势）
                try:
                    dif_arr, dea_arr, hist_arr = am.macd(12, 26, 9, array=True)
                    if dif_arr is not None and len(dif_arr) >= 10:
                        indicators["macd"]["dif_history"] = [
                            round(float(x), 4) for x in dif_arr[-10:] if not np.isnan(x)
                        ]
                        indicators["macd"]["dea_history"] = [
                            round(float(x), 4) for x in dea_arr[-10:] if not np.isnan(x)
                        ]
                except Exception:
                    pass

            # RSI（含历史）
            rsi_calc = indicator_mgr.get("rsi")
            if rsi_calc and rsi_calc.inited:
                rsi_val = rsi_calc.get_values().get("value", 50)
                indicators["rsi"] = {"value": round(rsi_val, 2)}
                try:
                    rsi_arr = am.rsi(14, array=True)
                    if rsi_arr is not None and len(rsi_arr) >= 10:
                        indicators["rsi"]["history"] = [
                            round(float(x), 2) for x in rsi_arr[-10:] if not np.isnan(x)
                        ]
                except Exception:
                    pass

            # DMI / ADX
            dmi_calc = indicator_mgr.get("dmi")
            if dmi_calc and dmi_calc.inited:
                v = dmi_calc.get_values()
                indicators["dmi"] = {
                    "adx": v.get("adx", 25),
                    "plus_di": v.get("pdi", 20),
                    "minus_di": v.get("mdi", 20),
                }

            # 布林带
            boll_calc = indicator_mgr.get("boll")
            if boll_calc and boll_calc.inited:
                v = boll_calc.get_values()
                boll_data: Dict[str, Any] = {
                    "upper": v.get("upper"),
                    "middle": v.get("middle"),
                    "lower": v.get("lower"),
                    "width": v.get("width"),
                    "squeeze": v.get("squeeze"),
                }
                # 价格在布林带中的位置
                upper = v.get("upper", 0)
                lower = v.get("lower", 0)
                if upper > lower:
                    boll_data["price_position"] = round(
                        (current_price - lower) / (upper - lower) * 100, 1
                    )
                indicators["boll"] = boll_data

            # ATR
            atr_14 = am.atr(14, array=False)
            indicators["atr"] = {
                "value": round(float(atr_14), 2),
                "pct": round(atr_14 / current_price * 100, 2) if current_price > 0 else 0,
            }

        except Exception as e:
            logger.warning(f"计算技术指标失败: {e}")

        return indicators

    def _get_primary_indicators(self) -> Dict:
        """获取主周期技术指标"""
        am = getattr(self.strategy, 'htf_am', None)
        if not am:
            am = getattr(self.strategy, 'am', None)
        return self._compute_indicators(self.primary_indicators, am)

    def _get_secondary_indicators(self) -> Dict:
        """获取次周期技术指标"""
        am = getattr(self.strategy, 'ltf_am', None)
        return self._compute_indicators(self.secondary_indicators, am)

    def _generate_trading_guidance(self, indicators: Dict) -> str:
        """基于已计算的指标值生成自然语言交易指导

        参考旧版 TechnicalGuidanceMixin 的解读方式，
        将指标数据转化为可操作的交易建议文本。
        """
        if not indicators:
            return ""

        lines = []

        # EMA 指导
        ema = indicators.get("ema")
        if isinstance(ema, dict):
            arr = ema.get("arrangement", "neutral")
            if arr == "bullish":
                lines.append("EMA: 完美多头排列，趋势强劲，回踩均线可加仓")
            elif arr == "bearish":
                lines.append("EMA: 完美空头排列，趋势向下，反弹均线可减仓")
            else:
                lines.append("EMA: 排列混乱，方向不明，宜观望等待")

        # SMA 指导
        sma = indicators.get("sma")
        if isinstance(sma, dict):
            arr = sma.get("arrangement", "neutral")
            if arr == "bullish":
                lines.append("SMA: 多头排列确认，趋势稳定上升")
            elif arr == "bearish":
                lines.append("SMA: 空头排列确认，趋势稳定下降")

        # MACD 指导
        macd = indicators.get("macd")
        if isinstance(macd, dict):
            dif = macd.get("dif", 0)
            dea = macd.get("dea", 0)
            cross = macd.get("cross_signal")
            if cross == "golden_cross":
                if dif > 0:
                    lines.append("MACD: 零轴上方金叉，强势做多信号")
                else:
                    lines.append("MACD: 零轴下方金叉，可能反转，等待确认")
            elif cross == "death_cross":
                if dif < 0:
                    lines.append("MACD: 零轴下方死叉，强势做空信号")
                else:
                    lines.append("MACD: 零轴上方死叉，可能回调，注意减仓")
            elif dif > dea and dif > 0:
                lines.append("MACD: DIF>DEA且在零轴上方，动量充足")
            elif dif < dea and dif < 0:
                lines.append("MACD: DIF<DEA且在零轴下方，空头动量占优")

            dif_hist = macd.get("dif_history", [])
            if len(dif_hist) >= 3:
                if all(dif_hist[i] > dif_hist[i-1] for i in range(-2, 0)):
                    lines.append("MACD趋势: DIF连续走高，动量增强")
                elif all(dif_hist[i] < dif_hist[i-1] for i in range(-2, 0)):
                    lines.append("MACD趋势: DIF连续走低，动量减弱")

        # RSI 指导
        rsi = indicators.get("rsi")
        if isinstance(rsi, dict):
            val = rsi.get("value", 50)
            if val >= 80:
                lines.append(f"RSI: {val:.0f} 严重超买，回调风险极高")
            elif val >= 70:
                lines.append(f"RSI: {val:.0f} 超买区域，注意止盈保护")
            elif val <= 20:
                lines.append(f"RSI: {val:.0f} 严重超卖，反弹机会大")
            elif val <= 30:
                lines.append(f"RSI: {val:.0f} 超卖区域，关注企稳信号")

            rsi_hist = rsi.get("history", [])
            if len(rsi_hist) >= 3 and val >= 60:
                if all(rsi_hist[i] < rsi_hist[i-1] for i in range(-2, 0)):
                    lines.append("RSI背离: RSI走低而价格可能走高，顶背离警告")

        # 布林带 指导
        boll = indicators.get("boll")
        if isinstance(boll, dict):
            pp = boll.get("price_position")
            if pp is not None:
                if pp >= 95:
                    lines.append("布林带: 价格触及上轨，超买压力大")
                elif pp <= 5:
                    lines.append("布林带: 价格触及下轨，超卖支撑强")
                elif 40 <= pp <= 60:
                    lines.append("布林带: 价格在中轨附近，方向待定")
            if boll.get("squeeze"):
                lines.append("布林带: 带宽收窄中，即将选择方向突破")

        # DMI/ADX 指导
        dmi = indicators.get("dmi")
        if isinstance(dmi, dict):
            adx = dmi.get("adx", 0)
            plus_di = dmi.get("plus_di", 0)
            minus_di = dmi.get("minus_di", 0)
            # 调整阈值与指导（强趋势20，中等趋势15）
            if adx >= 20:
                direction = "多" if plus_di > minus_di else "空"
                lines.append(f"趋势强(ADX={adx:.0f}), {direction}头占优")
            elif adx >= 15:
                lines.append(f"趋势形成中(ADX={adx:.0f})")
            # 弱趋势不阻止交易，只是提示降低仓位或止损更紧
            # 不再输出"不宜追单"的保守建议

        return "\n".join(lines)

    def _build_market_data(self, bar: BarData) -> Dict:
        """构建多周期数据结构

        返回格式:
        {
            "rb2605.SHFE": {
                "1h":  {"indicators": {...}},
                "15m": {"indicators": {...}},
            }
        }

        供 PromptBuilder._format_multi_timeframe() 使用。
        """
        symbol = bar.vt_symbol
        symbol_data: Dict[str, Dict] = {}

        primary_ind = self._get_primary_indicators()
        if primary_ind:
            symbol_data[self._primary_tf] = {"indicators": primary_ind}

        secondary_ind = self._get_secondary_indicators()
        if secondary_ind:
            symbol_data[self._secondary_tf] = {"indicators": secondary_ind}

        if len(symbol_data) < 2:
            return {}

        return {symbol: symbol_data}

    # ==================== 交易执行 ====================

    def _handle_long(self, bar: BarData, quantity: int) -> None:
        """处理做多"""
        if self.pos >= 0:
            self.strategy.buy(bar.close_price, quantity)
            logger.info(f"AI开多: 价格={bar.close_price:.2f}, 数量={quantity}")
        else:
            self.strategy.cover(bar.close_price, abs(self.pos))
            self.strategy.buy(bar.close_price, quantity)
            logger.info(f"AI平空开多: 价格={bar.close_price:.2f}, 数量={quantity}")

    def _handle_short(self, bar: BarData, quantity: int) -> None:
        """处理做空"""
        if self.pos <= 0:
            self.strategy.short(bar.close_price, quantity)
            logger.info(f"AI开空: 价格={bar.close_price:.2f}, 数量={quantity}")
        else:
            self.strategy.sell(bar.close_price, abs(self.pos))
            self.strategy.short(bar.close_price, quantity)
            logger.info(f"AI平多开空: 价格={bar.close_price:.2f}, 数量={quantity}")

    def _handle_close(self, bar: BarData) -> None:
        """处理平仓"""
        if self.pos > 0:
            self.strategy.sell(bar.close_price, abs(self.pos))
            logger.info(f"AI平多: 价格={bar.close_price:.2f}")
        elif self.pos < 0:
            self.strategy.cover(bar.close_price, abs(self.pos))
            logger.info(f"AI平空: 价格={bar.close_price:.2f}")

    def _handle_add_long(self, bar: BarData, quantity: int) -> None:
        """处理加多"""
        if self.pos > 0:
            self.strategy.buy(bar.close_price, quantity)
            logger.info(f"AI加多: 价格={bar.close_price:.2f}, 数量={quantity}")

    def _handle_add_short(self, bar: BarData, quantity: int) -> None:
        """处理加空"""
        if self.pos < 0:
            self.strategy.short(bar.close_price, quantity)
            logger.info(f"AI加空: 价格={bar.close_price:.2f}, 数量={quantity}")

    def _handle_reduce(self, bar: BarData) -> None:
        """处理减仓"""
        if self.pos > 0:
            reduce_qty = min(abs(self.pos) // 2, 1)
            self.strategy.sell(bar.close_price, reduce_qty)
            logger.info(f"AI减多: 价格={bar.close_price:.2f}, 数量={reduce_qty}")
        elif self.pos < 0:
            reduce_qty = min(abs(self.pos) // 2, 1)
            self.strategy.cover(bar.close_price, reduce_qty)
            logger.info(f"AI减空: 价格={bar.close_price:.2f}, 数量={reduce_qty}")


def detect_backtest_mode(strategy: Any) -> bool:
    """检测策略是否运行在回测器中

    Args:
        strategy: vnpy策略实例

    Returns:
        bool: 是否在回测模式
    """
    cta_engine = getattr(strategy, 'cta_engine', None)
    if not cta_engine:
        return False

    engine_type = getattr(cta_engine, 'engine_type', None)
    if not engine_type:
        return False

    return getattr(engine_type, 'name', '') == 'BACKTESTING'
