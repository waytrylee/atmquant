#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场数据采集工具
从 EnhancedChartWidget 中提取市场数据和技术指标信息，用于AI分析
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np

from vnpy.trader.object import BarData
from vnpy.trader.utility import ArrayManager


# 基础指标列表（优先从图表获取，图表没有才计算）
BASIC_INDICATORS = ["boll", "macd", "rsi", "dmi", "sma", "ema", "atr", "volume"]


class MarketDataCollector:
    """市场数据采集器 - 从图表组件提取数据"""

    @staticmethod
    def collect_from_chart(
        chart,  # EnhancedChartWidget
        vt_symbol: str,
        position_manager=None,
        include_multi_timeframe: bool = False,
        include_position: bool = False,
        include_auxiliary: bool = False,
        target_intervals: List[str] = None
    ) -> Dict[str, Any]:
        """
        从图表组件采集市场数据（简化版）

        Args:
            chart: EnhancedChartWidget 实例
            vt_symbol: 合约代码
            position_manager: PositionManager实例（可选）
            include_multi_timeframe: 是否包含多周期数据
            include_position: 是否包含持仓数据
            include_auxiliary: 是否包含辅助分析
            target_intervals: 目标周期列表

        Returns:
            完整的市场数据字典
        """
        market_data = {
            "symbol": vt_symbol,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_interval": chart._actual_interval if hasattr(chart, "_actual_interval") else "unknown",
            "indicators": {}
        }

        # 采集当前周期的K线数据
        current_bars = MarketDataCollector._get_bars_from_chart(chart)
        if current_bars:
            market_data["current_price"] = current_bars[-1].close_price
            market_data["recent_bars_info"] = {
                "current_timeframe": {
                    "timeframe": chart._actual_interval if hasattr(chart, "_actual_interval") else "unknown",
                    "count": len(current_bars),
                    "bars": MarketDataCollector._format_bars(current_bars[-20:])
                }
            }

        # 采集指标
        market_data["indicators"] = MarketDataCollector._collect_indicators(chart, current_bars)

        # 多周期数据
        if include_multi_timeframe and current_bars:
            timeframes = MarketDataCollector.collect_multi_timeframe_bars(
                chart,
                market_data["current_interval"],
                target_intervals
            )
            market_data["timeframes"] = timeframes

        # 持仓数据
        if include_position and position_manager and current_bars:
            position_data = MarketDataCollector.collect_position_data(
                position_manager,
                vt_symbol,
                current_bars[-1].close_price
            )
            market_data["position"] = position_data

        # 辅助分析
        if include_auxiliary and current_bars:
            market_data["gap_analysis"] = MarketDataCollector.analyze_gaps(current_bars)
            market_data["volatility_analysis"] = MarketDataCollector.calculate_atr(current_bars)
            market_data["volume_analysis"] = MarketDataCollector.analyze_volume(current_bars)

        # 转换所有numpy类型为Python原生类型
        market_data = MarketDataCollector._convert_numpy_types(market_data)

        return market_data

    @staticmethod
    def _get_bars_from_chart(chart) -> List[BarData]:
        """从图表获取K线数据"""
        try:
            # 优先从 manager 获取（更可靠）
            if hasattr(chart, "_manager") and hasattr(chart._manager, "_bars"):
                return list(chart._manager._bars.values())

            # 备用方案：从 CandleItem 获取
            if hasattr(chart, "_items") and "candle" in chart._items:
                candle_item = chart._items["candle"]
                if hasattr(candle_item, "_bar_picutures"):
                    bars = []
                    for ix, bar in candle_item._bar_picutures.items():
                        if isinstance(bar, BarData):
                            bars.append(bar)
                    if len(bars) > 0:
                        return sorted(bars, key=lambda x: x.datetime)

            return []
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return []

    @staticmethod
    def _format_bars(bars: List[BarData]) -> List[Dict[str, Any]]:
        """格式化K线数据"""
        formatted_bars = []
        for bar in bars:
            formatted_bars.append({
                "datetime": bar.datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume
            })
        return formatted_bars

    @staticmethod
    def _collect_indicators(chart, bars: List[BarData]) -> Dict[str, Any]:
        """
        简化的指标采集流程
        优先从图表获取，图表没有才通过talib/numpy计算

        Args:
            chart: EnhancedChartWidget实例
            bars: K线数据

        Returns:
            指标数据字典
        """
        indicators = {}

        if not bars:
            return indicators

        # 采集基础指标
        for indicator_key in BASIC_INDICATORS:
            try:
                # 优先从图表获取
                if hasattr(chart, "_items") and indicator_key in chart._items:
                    item = chart._items[indicator_key]
                    if hasattr(item, "get_current_values"):
                        values = item.get_current_values()
                        if values:
                            indicators[indicator_key] = values
                            continue  # 成功获取，跳过计算

                # 图表没有，尝试计算（仅ATR）
                if indicator_key == "atr":
                    atr_data = MarketDataCollector.calculate_atr(bars)
                    if atr_data:
                        indicators["atr"] = atr_data
                # 其他指标如果图表没有，就不采集

            except Exception as e:
                print(f"[WARNING] 采集{indicator_key}失败: {e}")

        return indicators

    @staticmethod
    def _convert_numpy_types(data: Any) -> Any:
        """
        递归转换numpy类型为Python原生类型
        """
        import numpy as np

        if isinstance(data, dict):
            return {k: MarketDataCollector._convert_numpy_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [MarketDataCollector._convert_numpy_types(item) for item in data]
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.bool_):
            return bool(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        else:
            return data

    @staticmethod
    def _calculate_indicators_for_bars(bars: List[BarData]) -> Dict[str, Any]:
        """
        直接从K线数据计算指标（用于多周期分析）
        不依赖chart对象，直接使用talib和ArrayManager计算

        Args:
            bars: K线数据列表

        Returns:
            指标数据字典
        """
        import talib
        import numpy as np
        from vnpy.trader.utility import ArrayManager

        indicators = {}

        if not bars or len(bars) < 50:  # 至少需要50根K线才能计算有效指标
            return indicators

        try:
            # 使用ArrayManager
            am = ArrayManager(len(bars))
            for bar in bars:
                am.update_bar(bar)

            # 提取价格和成交量数据
            close_prices = np.array([bar.close_price for bar in bars])
            high_prices = np.array([bar.high_price for bar in bars])
            low_prices = np.array([bar.low_price for bar in bars])
            open_prices = np.array([bar.open_price for bar in bars])

            # 计算BOLL
            try:
                upper, middle, lower = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2)
                if not np.isnan(upper[-1]):
                    indicators["boll"] = {
                        "upper": round(float(upper[-1]), 2),
                        "middle": round(float(middle[-1]), 2),
                        "lower": round(float(lower[-1]), 2),
                        "current_price": round(float(close_prices[-1]), 2)
                    }
            except:
                pass

            # 计算SMA
            try:
                sma5 = talib.SMA(close_prices, timeperiod=5)
                sma10 = talib.SMA(close_prices, timeperiod=10)
                sma20 = talib.SMA(close_prices, timeperiod=20)
                sma60 = talib.SMA(close_prices, timeperiod=60)

                if not np.isnan(sma60[-1]):
                    indicators["sma"] = {
                        "sma5": round(float(sma5[-1]), 2) if not np.isnan(sma5[-1]) else None,
                        "sma10": round(float(sma10[-1]), 2) if not np.isnan(sma10[-1]) else None,
                        "sma20": round(float(sma20[-1]), 2) if not np.isnan(sma20[-1]) else None,
                        "sma60": round(float(sma60[-1]), 2) if not np.isnan(sma60[-1]) else None,
                    }
            except:
                pass

            # 计算EMA
            try:
                ema9 = talib.EMA(close_prices, timeperiod=9)
                ema21 = talib.EMA(close_prices, timeperiod=21)
                ema50 = talib.EMA(close_prices, timeperiod=50)
                ema200 = talib.EMA(close_prices, timeperiod=200)

                if not np.isnan(ema200[-1]):
                    # 判断趋势
                    trend = "up" if ema9[-1] > ema21[-1] else "down"

                    indicators["ema"] = {
                        "ema9": round(float(ema9[-1]), 2) if not np.isnan(ema9[-1]) else None,
                        "ema21": round(float(ema21[-1]), 2) if not np.isnan(ema21[-1]) else None,
                        "ema50": round(float(ema50[-1]), 2) if not np.isnan(ema50[-1]) else None,
                        "ema200": round(float(ema200[-1]), 2) if not np.isnan(ema200[-1]) else None,
                        "trend": trend
                    }
            except:
                pass

            # 计算MACD
            try:
                macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
                if not np.isnan(hist[-1]):
                    indicators["macd"] = {
                        "macd": round(float(macd[-1]), 2),
                        "signal": round(float(signal[-1]), 2),
                        "histogram": round(float(hist[-1]), 2)
                    }
            except:
                pass

            # 计算RSI
            try:
                rsi = talib.RSI(close_prices, timeperiod=14)
                if not np.isnan(rsi[-1]):
                    indicators["rsi"] = {
                        "value": round(float(rsi[-1]), 2)
                    }
            except:
                pass

            # 计算DMI
            try:
                pdi = talib.PLUS_DI(high_prices, low_prices, close_prices, timeperiod=14)
                mdi = talib.MINUS_DI(high_prices, low_prices, close_prices, timeperiod=14)
                adx = talib.ADX(high_prices, low_prices, close_prices, timeperiod=14)

                if not np.isnan(adx[-1]):
                    indicators["dmi"] = {
                        "pdi": round(float(pdi[-1]), 2),
                        "mdi": round(float(mdi[-1]), 2),
                        "adx": round(float(adx[-1]), 2)
                    }
            except:
                pass

            # 计算ATR
            try:
                atr_values = talib.ATR(high_prices, low_prices, close_prices, timeperiod=14)
                if not np.isnan(atr_values[-1]):
                    atr_value = float(atr_values[-1])
                    current_price = float(close_prices[-1])
                    atr_ratio = atr_value / current_price if current_price > 0 else 0

                    # 判断波动状态
                    if atr_ratio < 0.01:
                        volatility = "low"
                    elif atr_ratio < 0.02:
                        volatility = "medium"
                    else:
                        volatility = "high"

                    indicators["atr"] = {
                        "value": round(atr_value, 2),
                        "ratio": round(atr_ratio, 4),
                        "volatility": volatility
                    }
            except:
                pass

            # 计算SuperTrend
            try:
                atr = talib.ATR(high_prices, low_prices, close_prices, timeperiod=14)
                basic_band = (high_prices + low_prices) / 2
                multiplier = 3.0

                # 计算上下轨
                up_values = np.zeros(len(bars))
                dn_values = np.zeros(len(bars))
                trend_values = np.ones(len(bars))

                for i in range(len(bars)):
                    if np.isnan(atr[i]):
                        continue

                    up_basic = basic_band[i] - (atr[i] * multiplier)
                    dn_basic = basic_band[i] + (atr[i] * multiplier)

                    if i == 0:
                        up_values[i] = up_basic
                        dn_values[i] = dn_basic
                        trend_values[i] = 1
                    else:
                        if close_prices[i-1] > up_values[i-1]:
                            up_values[i] = max(up_basic, up_values[i-1])
                        else:
                            up_values[i] = up_basic

                        if close_prices[i-1] < dn_values[i-1]:
                            dn_values[i] = min(dn_basic, dn_values[i-1])
                        else:
                            dn_values[i] = dn_basic

                        prev_trend = trend_values[i-1]
                        if prev_trend == -1 and close_prices[i] > dn_values[i-1]:
                            trend_values[i] = 1
                        elif prev_trend == 1 and close_prices[i] < up_values[i-1]:
                            trend_values[i] = -1
                        else:
                            trend_values[i] = prev_trend

                supertrend_value = up_values[-1] if trend_values[-1] == 1 else dn_values[-1]
                direction = "up" if trend_values[-1] == 1 else "down"

                indicators["supertrend"] = {
                    "direction": direction,
                    "value": round(float(supertrend_value), 2),
                    "atr_value": round(float(atr[-1]), 2),
                    "upper_band": round(float(dn_values[-1]), 2),
                    "lower_band": round(float(up_values[-1]), 2),
                    "current_price": round(float(close_prices[-1]), 2)
                }
            except Exception as e:
                print(f"计算SuperTrend失败: {e}")

            # 计算ZLEMA
            try:
                period = 70
                lag = int((period - 1) / 2)

                # 创建延迟调整后的价格序列
                adjusted_prices = np.zeros(len(close_prices))
                for i in range(len(close_prices)):
                    if i >= lag:
                        adjusted_prices[i] = close_prices[i] + (close_prices[i] - close_prices[i - lag])
                    else:
                        adjusted_prices[i] = close_prices[i]

                # 计算ZLEMA值
                zlema_values = talib.EMA(adjusted_prices, timeperiod=period)

                # 计算波动率带
                atr_values = talib.ATR(high_prices, low_prices, close_prices, timeperiod=period)
                band_multiplier = 1.2

                # 取最近period*3个周期内ATR的最高值
                volatility_window = period * 3
                if len(atr_values) >= volatility_window:
                    window_atr = atr_values[-volatility_window:]
                    volatility = np.nanmax(window_atr) * band_multiplier
                else:
                    volatility = np.nanmax(atr_values) * band_multiplier

                zlema = zlema_values[-1]
                zlema_upper = zlema + volatility
                zlema_lower = zlema - volatility

                # 判断趋势
                trend = "neutral"
                if close_prices[-1] > zlema_upper and close_prices[-2] <= (zlema_values[-2] + volatility):
                    trend = "up"
                elif close_prices[-1] < zlema_lower and close_prices[-2] >= (zlema_values[-2] - volatility):
                    trend = "down"

                indicators["zlema"] = {
                    "value": round(float(zlema), 2),
                    "trend": trend,
                    "upper_band": round(float(zlema_upper), 2),
                    "lower_band": round(float(zlema_lower), 2),
                    "current_price": round(float(close_prices[-1]), 2)
                }
            except Exception as e:
                print(f"计算ZLEMA失败: {e}")

            # 计算Volume指标
            try:
                volumes = np.array([bar.volume for bar in bars])

                # 计算成交量MA
                vol_ma = talib.SMA(volumes, timeperiod=20)

                # 计算成交量变化百分比
                vol_change_pct = 0
                if len(volumes) > 1:
                    prev_volume = volumes[-2]
                    if prev_volume > 0:
                        vol_change_pct = ((volumes[-1] - prev_volume) / prev_volume) * 100

                # 判断成交量状态
                current_volume = int(volumes[-1])
                avg_volume = int(vol_ma[-1]) if not np.isnan(vol_ma[-1]) else None
                volume_ratio = current_volume / avg_volume if avg_volume and avg_volume > 0 else 0

                volume_status = "Normal"
                is_spike = False
                if avg_volume and avg_volume > 0:
                    if volume_ratio >= 2.0:
                        volume_status = "Spike"
                        is_spike = True
                    elif volume_ratio >= 1.2:
                        volume_status = "High"

                # 买卖量分解（基于收盘价在最高最低价之间的位置）
                current_bar = bars[-1]
                if current_bar.high_price == current_bar.low_price or current_volume == 0:
                    buy_volume = 0
                    sell_volume = 0
                    buy_ratio = 0
                    sell_ratio = 0
                else:
                    buy_volume = current_volume * (current_bar.close_price - current_bar.low_price) / (current_bar.high_price - current_bar.low_price)
                    sell_volume = current_volume * (current_bar.high_price - current_bar.close_price) / (current_bar.high_price - current_bar.low_price)
                    buy_ratio = buy_volume / current_volume
                    sell_ratio = sell_volume / current_volume

                # 计算买卖比率
                buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')

                # 判断买卖力量
                volume_force = "买卖均衡"
                if buy_sell_ratio > 2.0:
                    volume_force = "买盘强势"
                elif buy_sell_ratio > 1.3:
                    volume_force = "买盘占优"
                elif buy_sell_ratio > 0.7:
                    volume_force = "买卖均衡"
                elif buy_sell_ratio > 0.5:
                    volume_force = "卖盘占优"
                else:
                    volume_force = "卖盘强势"

                indicators["volume"] = {
                    # 基础数据
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                    "volume_ratio": round(volume_ratio, 2),
                    "volume_status": volume_status,
                    "volume_change_pct": round(vol_change_pct, 2),

                    # 买卖分解
                    "buy_volume": round(buy_volume, 2),
                    "sell_volume": round(sell_volume, 2),
                    "buy_ratio": round(buy_ratio * 100, 2),
                    "sell_ratio": round(sell_ratio * 100, 2),
                    "buy_sell_ratio": round(buy_sell_ratio, 2) if buy_sell_ratio != float('inf') else 999,
                    "volume_force": volume_force,

                    # 标记
                    "is_spike": is_spike,

                    # 前期数据对比
                    "previous_volume": int(volumes[-2]) if len(volumes) > 1 else None,

                    # 参数
                    "parameters": {
                        "ma_period": 20,
                        "spike_threshold": 2.0
                    }
                }
            except Exception as e:
                print(f"计算Volume失败: {e}")

        except Exception as e:
            print(f"计算指标数据失败: {e}")

        return indicators

    @staticmethod
    def calculate_atr(bars: List[BarData], period: int = 14) -> Dict[str, Any]:
        """
        计算ATR并分析波动率

        Args:
            bars: K线数据
            period: ATR周期

        Returns:
            ATR值和波动率分析
        """
        if len(bars) < period + 1:
            return {}

        try:
            am = ArrayManager(len(bars))
            for bar in bars:
                am.update_bar(bar)

            atr_value = am.atr(period, array=False)
            current_price = bars[-1].close_price
            atr_ratio = atr_value / current_price if current_price > 0 else 0

            # 判断波动状态
            if atr_ratio < 0.01:
                volatility = "low"
            elif atr_ratio < 0.02:
                volatility = "medium"
            else:
                volatility = "high"

            return {
                "value": round(atr_value, 2),
                "ratio": round(atr_ratio, 4),
                "volatility": volatility
            }
        except Exception as e:
            print(f"计算ATR失败: {e}")
            return {}

    @staticmethod
    def collect_multi_timeframe_bars(
        chart,
        current_interval: str,
        target_intervals: List[str] = None
    ) -> Dict[str, Any]:
        """
        采集多周期K线数据

        Args:
            chart: EnhancedChartWidget实例
            current_interval: 当前周期
            target_intervals: 目标周期列表

        Returns:
            包含4个周期K线数据的字典
        """
        if target_intervals is None:
            # 默认周期映射
            interval_map = {
                "1m": {"current": "1m", "higher": "5m", "lower": None, "daily": "daily"},
                "5m": {"current": "5m", "higher": "15m", "lower": "1m", "daily": "daily"},
                "15m": {"current": "15m", "higher": "1h", "lower": "5m", "daily": "daily"},
                "1h": {"current": "1h", "higher": "4h", "lower": "15m", "daily": "daily"}
            }
            target_intervals = interval_map.get(current_interval, {})

        timeframes = {}

        # 采集每个周期的数据
        for tf_name, tf_interval in target_intervals.items():
            if tf_interval is None:
                continue
            if tf_interval == current_interval:
                # 当前周期：从chart直接获取
                bars = MarketDataCollector._get_bars_from_chart(chart)
                count = 20
            else:
                # 其他周期：尝试聚合
                if hasattr(chart, "_aggregate_bars"):
                    try:
                        bars = chart._aggregate_bars(tf_interval)
                    except:
                        bars = []
                else:
                    bars = []
                count = 10 if tf_name == "daily" else 8

            if bars:
                timeframes[f"{tf_name}_timeframe"] = {
                    "timeframe": tf_interval,
                    "count": len(bars),
                    "bars": MarketDataCollector._format_bars(bars[-count:])
                }

        return timeframes

    @staticmethod
    def collect_position_data(
        position_manager,
        vt_symbol: str,
        current_price: float
    ) -> Dict[str, Any]:
        """
        采集持仓数据

        Args:
            position_manager: PositionManager实例
            vt_symbol: 合约代码
            current_price: 当前价格

        Returns:
            持仓数据字典
        """
        if not position_manager:
            return {}

        try:
            # 获取净持仓
            net_position = position_manager.get_position(vt_symbol)

            # 获取多空持仓详情
            long_position = position_manager.get_long_position(vt_symbol) if hasattr(position_manager, 'get_long_position') else 0
            short_position = position_manager.get_short_position(vt_symbol) if hasattr(position_manager, 'get_short_position') else 0

            # 获取持仓数据
            position_data = {}
            if hasattr(position_manager, 'position_data'):
                position_data = position_manager.position_data.get(vt_symbol, {})

            # 计算入场价格和浮动盈亏
            entry_price = 0.0
            unrealized_pnl = 0.0

            if net_position > 0 and position_data.get("long"):
                entry_price = position_data["long"].price
                unrealized_pnl = (current_price - entry_price) * net_position
            elif net_position < 0 and position_data.get("short"):
                entry_price = position_data["short"].price
                unrealized_pnl = (entry_price - current_price) * abs(net_position)

            pnl_ratio = (unrealized_pnl / entry_price) if entry_price > 0 else 0

            return {
                "net_position": net_position,
                "long_position": long_position,
                "short_position": short_position,
                "entry_price": round(entry_price, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "pnl_ratio": round(pnl_ratio, 4)
            }
        except Exception as e:
            print(f"采集持仓数据失败: {e}")
            return {}

    @staticmethod
    def analyze_gaps(bars: List[BarData], lookback: int = 20) -> Dict[str, Any]:
        """
        分析开盘缺口

        Args:
            bars: K线数据
            lookback: 回看K线数量

        Returns:
            缺口分析结果
        """
        if len(bars) < 2:
            return {}

        try:
            recent_bars = bars[-lookback:]
            unfilled_gaps = []

            for i in range(1, len(recent_bars)):
                prev_bar = recent_bars[i - 1]
                curr_bar = recent_bars[i]

                # 检查向上跳空缺口
                if curr_bar.low_price > prev_bar.high_price:
                    gap = {
                        "type": "gap_up",
                        "high": round(curr_bar.low_price, 2),
                        "low": round(prev_bar.high_price, 2),
                        "datetime": curr_bar.datetime.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    # 检查是否被填补
                    is_filled = any(bar.low_price <= gap["low"] for bar in recent_bars[i+1:])
                    if not is_filled:
                        unfilled_gaps.append(gap)

                # 检查向下跳空缺口
                elif curr_bar.high_price < prev_bar.low_price:
                    gap = {
                        "type": "gap_down",
                        "high": round(prev_bar.low_price, 2),
                        "low": round(curr_bar.high_price, 2),
                        "datetime": curr_bar.datetime.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    # 检查是否被填补
                    is_filled = any(bar.high_price >= gap["high"] for bar in recent_bars[i+1:])
                    if not is_filled:
                        unfilled_gaps.append(gap)

            # 找到最重要的缺口（最大的）
            key_gap_level = None
            if unfilled_gaps:
                largest_gap = max(unfilled_gaps, key=lambda g: g["high"] - g["low"])
                key_gap_level = round((largest_gap["high"] + largest_gap["low"]) / 2, 2)

            return {
                "unfilled_gaps": unfilled_gaps[-5:],  # 最近5个缺口
                "recent_gaps_count": len(unfilled_gaps),
                "key_gap_level": key_gap_level
            }
        except Exception as e:
            print(f"分析缺口失败: {e}")
            return {}

    @staticmethod
    def analyze_volume(bars: List[BarData], period: int = 20) -> Dict[str, Any]:
        """
        分析成交量尖峰

        Args:
            bars: K线数据
            period: 平均成交量周期

        Returns:
            成交量分析结果
        """
        if len(bars) < period:
            return {}

        try:
            volumes = [bar.volume for bar in bars]
            current_volume = volumes[-1]
            avg_volume = sum(volumes[-period:]) / period
            ratio = current_volume / avg_volume if avg_volume > 0 else 0

            # 判断成交量状态
            if ratio > 2.0:
                state = "spike"
            elif ratio > 1.3:
                state = "high"
            elif ratio < 0.7:
                state = "low"
            else:
                state = "normal"

            return {
                "current_volume": current_volume,
                "avg_volume": round(avg_volume, 0),
                "ratio": round(ratio, 2),
                "state": state
            }
        except Exception as e:
            print(f"分析成交量失败: {e}")
            return {}

    @staticmethod
    def collect_multi_timeframe(
        charts: Dict[str, Any],  # {period: EnhancedChartWidget}
        vt_symbol: str
    ) -> Dict[str, Any]:
        """
        采集多周期数据（向后兼容方法）

        Args:
            charts: 周期到图表的映射
            vt_symbol: 合约代码

        Returns:
            包含多周期数据的字典
        """
        multi_data = {
            "symbol": vt_symbol,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timeframes": {}
        }

        for period, chart in charts.items():
            if chart is None:
                continue

            bars = MarketDataCollector._get_bars_from_chart(chart)
            if bars:
                multi_data["timeframes"][period] = {
                    "count": len(bars),
                    "bars": MarketDataCollector._format_bars(bars[-20:]),
                    "indicators": MarketDataCollector._collect_indicators(chart, bars)
                }

        return multi_data
