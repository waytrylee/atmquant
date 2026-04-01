#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期简单移动平均线指标 - 完全按照参考代码样式
"""

from typing import Dict, Tuple, Any
import numpy as np
from vnpy.trader.object import BarData
from vnpy.chart.item import CandleItem
from vnpy.trader.ui import QtGui, QtCore, QtWidgets
import pyqtgraph as pg

from .indicator_base import ConfigurableIndicator
from .calculators.sma_calculator import SMACalculator


class MultiSmaItem(CandleItem, ConfigurableIndicator):
    """
    绘制多条简单移动平均线(SMA)的类 - 参考原始代码样式
    """

    def __init__(self, manager, periods: Tuple[int, ...] = (25, 60, 100)):
        """
        初始化
        """
        super().__init__(manager)

        self.periods = periods
        self.lines: Dict[int, QtGui.QPen] = {}  # 存储窗口大小和对应的画笔
        self.sma_data: Dict[int, Dict[int, float]] = {}  # 存储多个窗口的均线数据
        
        # 设置颜色 - 按照短线、中线、慢线惯例
        colors = [
            (255, 255, 255),    # 白色 - 短线(25)，最活跃
            (255, 0, 255),      # 紫色 - 中线(60)，中性过渡
            (100, 100, 255),    # 蓝色 - 慢线(100)，稳重
            (0, 255, 255),      # 青色 - 额外线
            (255, 128, 0),      # 橙色 - 额外线
            (128, 255, 128),    # 浅绿色 - 额外线
            (255, 128, 128),    # 浅红色 - 额外线
            (128, 128, 255),    # 浅蓝色 - 额外线
        ]
        
        # 为每个周期设置画笔 - 参考原始代码样式
        for i, period in enumerate(self.periods):
            color = colors[i % len(colors)]
            self.add_sma_line(period, color, 2)

    def add_sma_line(self, sma_window: int, color: Tuple[int, int, int] = (100, 100, 255), width: int = 2):
        """
        添加一条均线 - 参考原始代码样式
        """
        self.lines[sma_window] = pg.mkPen(color=color, width=width)
        self.sma_data[sma_window] = {}

    def _ensure_calculated(self, sma_window: int) -> None:
        """全量计算指定周期的 SMA 数据，委托给 SMACalculator"""
        if self.sma_data.get(sma_window):
            return
        bars = self._manager.get_all_bars()
        if not bars or len(bars) < sma_window:
            return
        close_array = np.array([bar.close_price for bar in bars])
        sma_array = SMACalculator.compute_array(close_array, sma_window)
        self.sma_data[sma_window] = {}
        for n, value in enumerate(sma_array):
            self.sma_data[sma_window][n] = value

    def get_sma_value(self, ix: int, sma_window: int) -> float:
        """获取指定窗口大小的 SMA 值"""
        if ix < 0:
            return np.nan
        self._ensure_calculated(sma_window)
        if sma_window in self.sma_data and ix in self.sma_data[sma_window]:
            return self.sma_data[sma_window][ix]
        return np.nan

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        绘制K线与均线 - 完全按照参考代码样式
        """
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)

        for sma_window, pen in self.lines.items():
            sma_value = self.get_sma_value(ix, sma_window)
            last_sma_value = self.get_sma_value(ix - 1, sma_window)

            # 只有当前值和前一个值都有效且非NaN时才绘制线条
            if (not np.isnan(sma_value) and not np.isnan(last_sma_value) and 
                ix >= sma_window):
                
                # 设置画笔颜色
                painter.setPen(pen)

                # 绘制均线
                start_point = QtCore.QPointF(ix - 1, last_sma_value)
                end_point = QtCore.QPointF(ix, sma_value)
                painter.drawLine(start_point, end_point)

        painter.end()
        return picture

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前SMA数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1
        sma_values = {}
        prev_sma_values = {}

        # 使用get_sma_value确保数据被计算（即使指标被隐藏）
        for sma_window in self.sma_data.keys():
            value = self.get_sma_value(ix, sma_window)
            if not np.isnan(value):
                sma_values[sma_window] = value

            prev_value = self.get_sma_value(ix - 1, sma_window)
            if not np.isnan(prev_value):
                prev_sma_values[sma_window] = prev_value

        if not sma_values:
            return {}

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        # 判断趋势（基于短期和长期SMA）
        windows = sorted(sma_values.keys())
        if len(windows) >= 2:
            short_window = windows[0]
            long_window = windows[-1]
            short_sma = sma_values[short_window]
            long_sma = sma_values[long_window]
            trend = "up" if short_sma > long_sma else "down" if short_sma < long_sma else "neutral"
        else:
            trend = "unknown"

        return {
            "values": {k: round(v, 2) for k, v in sma_values.items()},
            "previous_values": {k: round(v, 2) for k, v in prev_sma_values.items()} if prev_sma_values else {},
            "trend": trend,
            "current_price": round(current_price, 2),
            "windows": windows
        }

    def get_info_text(self, ix: int) -> str:
        """
        返回信息文本，显示所有 SMA 值和交易指导
        """
        info_lines = []
        sma_values = {}

        # 收集所有SMA值
        for sma_window, data in self.sma_data.items():
            if ix in data and not np.isnan(data[ix]):
                sma_values[sma_window] = data[ix]
                info_lines.append(f"SMA({sma_window}): {data[ix]:.2f}")

        if not sma_values:
            return "SMA数据不足"

        # 获取当前价格用于分析
        bar = self._manager.get_bar(ix)
        current_price = bar.close_price if bar else None

        # 获取前一个数据用于趋势判断
        prev_ix = ix - 1
        prev_sma_values = {}
        prev_price = None

        if prev_ix >= 0:
            prev_bar = self._manager.get_bar(prev_ix)
            prev_price = prev_bar.close_price if prev_bar else None

            for sma_window, data in self.sma_data.items():
                if prev_ix in data and not np.isnan(data[prev_ix]):
                    prev_sma_values[sma_window] = data[prev_ix]

        # 按周期排序（快中慢三条线）
        periods = sorted(sma_values.keys())

        if len(periods) >= 2 and current_price is not None:

            # SMA排列状态分析（SMA稳定性更好，适合中长期趋势判断）
            if len(periods) >= 3:
                fast_sma = sma_values[periods[0]]   # 快线
                mid_sma = sma_values[periods[1]]    # 中线
                slow_sma = sma_values[periods[2]]   # 慢线

                # 判断SMA排列类型
                if fast_sma > mid_sma > slow_sma:
                    info_lines.append("SMA状态: 多头排列")
                    info_lines.append("趋势强度: 稳定上升（SMA确认性更强）")
                elif fast_sma < mid_sma < slow_sma:
                    info_lines.append("SMA状态: 空头排列")
                    info_lines.append("趋势强度: 稳定下降（SMA确认性更强）")
                else:
                    info_lines.append("SMA状态: 震荡排列")
                    info_lines.append("趋势强度: 方向不明（等待趋势确立）")

                # 分析SMA间距离（SMA需要更大散度确认趋势，商品期货优化）
                ma_spread_fast_mid = abs(fast_sma - mid_sma) / mid_sma * 100
                ma_spread_mid_slow = abs(mid_sma - slow_sma) / slow_sma * 100

                if ma_spread_fast_mid > 3.5 or ma_spread_mid_slow > 2.5:
                    info_lines.append("SMA散度: 大 - 趋势强劲且稳定")
                elif ma_spread_fast_mid > 2.0 or ma_spread_mid_slow > 1.5:
                    info_lines.append("SMA散度: 中等 - 趋势明确")
                else:
                    info_lines.append("SMA散度: 小 - 趋势较弱或整理中")

            # 价格与SMA关系分析
            price_above_count = sum(1 for sma_val in sma_values.values() if current_price > sma_val)
            total_lines = len(sma_values)

            if price_above_count == total_lines:
                info_lines.append("价格位置: 全部SMA之上")
                info_lines.append("市场状态: 强势多头（SMA全面支撑）")
            elif price_above_count == 0:
                info_lines.append("价格位置: 全部SMA之下")
                info_lines.append("市场状态: 强势空头（SMA全面压制）")
            else:
                info_lines.append(f"价格位置: {price_above_count}/{total_lines}SMA之上")
                info_lines.append("市场状态: 震荡转换期（关注SMA方向）")

            # 检测SMA交叉信号（SMA交叉更稳定、假信号更少）
            if prev_sma_values and prev_price is not None:

                # 检测黄金交叉和死亡交叉
                crossovers_detected = []

                if len(periods) >= 2:
                    fast_period = periods[0]
                    slow_period = periods[1]

                    if (fast_period in prev_sma_values and slow_period in prev_sma_values):
                        prev_fast = prev_sma_values[fast_period]
                        prev_slow = prev_sma_values[slow_period]
                        curr_fast = sma_values[fast_period]
                        curr_slow = sma_values[slow_period]

                        # SMA黄金交叉（更可靠的确认信号）
                        if prev_fast <= prev_slow and curr_fast > curr_slow:
                            crossovers_detected.append("SMA黄金交叉 - 稳定看涨信号")
                        # SMA死亡交叉
                        elif prev_fast >= prev_slow and curr_fast < curr_slow:
                            crossovers_detected.append("SMA死亡交叉 - 稳定看跌信号")

                # 检测价格与SMA的交叉（稳定的支撑阻力确认）
                for period in periods:
                    if period in prev_sma_values:
                        prev_sma = prev_sma_values[period]
                        curr_sma = sma_values[period]

                        # 价格上穿SMA（稳定的突破信号）
                        if prev_price <= prev_sma and current_price > curr_sma:
                            crossovers_detected.append(f"价格上穿SMA({period}) - 稳定做多信号")
                        # 价格下穿SMA
                        elif prev_price >= prev_sma and current_price < curr_sma:
                            crossovers_detected.append(f"价格下穿SMA({period}) - 稳定做空信号")

                if crossovers_detected:
                    info_lines.extend(crossovers_detected)
                else:
                    info_lines.append("交叉信号: 无明显交叉")

            # SMA支撑阻力分析（SMA作为稳定的支撑阻力参考）
            nearest_support = None
            nearest_resistance = None
            min_support_dist = float('inf')
            min_resistance_dist = float('inf')

            for period, sma_val in sma_values.items():
                distance = abs(current_price - sma_val) / current_price * 100

                if sma_val < current_price and distance < min_support_dist:
                    nearest_support = (period, sma_val, distance)
                    min_support_dist = distance
                elif sma_val > current_price and distance < min_resistance_dist:
                    nearest_resistance = (period, sma_val, distance)
                    min_resistance_dist = distance

            # 差异化阈值设置（根据SMA周期特性）
            def get_sma_thresholds_and_advice(period, distance, is_support=True):
                """根据SMA周期返回阈值和交易建议"""
                if period <= 30:  # 快线（如SMA10, SMA20, SMA30）
                    close_threshold = 0.8
                    near_threshold = 2.0
                    line_type = "快线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA支撑极近 - 短线反弹概率高"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA支撑 - 短线回踩买入机会"
                        else:
                            advice = f"远离{line_type}SMA支撑 - 等待回踩确认"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA阻力极近 - 短线回调风险高"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA阻力 - 短线减仓时机"
                        else:
                            advice = f"远离{line_type}SMA阻力 - 突破后可追涨"
                elif period <= 100:  # 中线（如SMA50, SMA60, SMA100）
                    close_threshold = 1.2
                    near_threshold = 3.0
                    line_type = "中线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA支撑很近 - 中期稳定支撑力强"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA支撑 - 重要中期买入位"
                        else:
                            advice = f"远离{line_type}SMA支撑 - 中期趋势良好"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA阻力很近 - 中期压力位测试"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA阻力 - 中期获利了结位"
                        else:
                            advice = f"远离{line_type}SMA阻力 - 突破确认中期转势"
                else:  # 慢线（如SMA200, SMA250）
                    close_threshold = 2.0
                    near_threshold = 4.0
                    line_type = "慢线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA支撑很近 - 长期趋势核心支撑"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA支撑 - 长期投资黄金买点"
                        else:
                            advice = f"远离{line_type}SMA支撑 - 长期趋势强劲"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}SMA阻力很近 - 长期趋势转换关键"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}SMA阻力 - 长期顶部区域谨慎"
                        else:
                            advice = f"远离{line_type}SMA阻力 - 突破确认长期牛市"

                return close_threshold, near_threshold, advice

            if nearest_support:
                period, price, dist = nearest_support
                close_thresh, near_thresh, advice = get_sma_thresholds_and_advice(period, dist, True)
                info_lines.append(f"最近支撑: SMA({period}) {price:.2f} ({dist:.1f}%)")
                info_lines.append(advice)

            if nearest_resistance:
                period, price, dist = nearest_resistance
                close_thresh, near_thresh, advice = get_sma_thresholds_and_advice(period, dist, False)
                info_lines.append(f"最近阻力: SMA({period}) {price:.2f} ({dist:.1f}%)")
                info_lines.append(advice)

            # SMA趋势强度分析（SMA斜率变化更平滑可靠）
            if prev_sma_values:
                trend_strength_scores = []

                for period in periods:
                    if period in prev_sma_values:
                        curr_sma = sma_values[period]
                        prev_sma = prev_sma_values[period]

                        # 计算SMA斜率（趋势强度）
                        slope = (curr_sma - prev_sma) / prev_sma * 100
                        trend_strength_scores.append(slope)

                if trend_strength_scores:
                    avg_slope = sum(trend_strength_scores) / len(trend_strength_scores)

                    if avg_slope > 0.4:
                        info_lines.append("SMA趋势: 稳定上升")
                        info_lines.append("操作建议: 顺势做多，SMA回踩是良机")
                    elif avg_slope < -0.4:
                        info_lines.append("SMA趋势: 稳定下降")
                        info_lines.append("操作建议: 顺势做空，SMA反弹减仓")
                    elif avg_slope > 0.12:
                        info_lines.append("SMA趋势: 温和上升")
                        info_lines.append("操作建议: 谨慎做多，关注SMA支撑")
                    elif avg_slope < -0.12:
                        info_lines.append("SMA趋势: 温和下降")
                        info_lines.append("操作建议: 谨慎做空，关注SMA阻力")
                    else:
                        info_lines.append("SMA趋势: 横盘整理")
                        info_lines.append("操作建议: 区间操作，等待SMA方向明确")

            # SMA经典策略分析（基于实际设置的快中慢周期）
            if len(periods) >= 3:
                fast_sma = sma_values[periods[0]]   # 最快线
                mid_sma = sma_values[periods[1]]    # 中线
                slow_sma = sma_values[periods[2]]   # 最慢线

                # 经典SMA策略分析
                if current_price > fast_sma > mid_sma > slow_sma:
                    info_lines.append(f"稳定多头格局: 价格>SMA{periods[0]}>SMA{periods[1]}>SMA{periods[2]}")
                    info_lines.append(f"策略: 强势做多，SMA{periods[0]}回踩加仓，SMA{periods[1]}为核心支撑")
                elif current_price < fast_sma < mid_sma < slow_sma:
                    info_lines.append(f"稳定空头格局: 价格<SMA{periods[0]}<SMA{periods[1]}<SMA{periods[2]}")
                    info_lines.append(f"策略: 强势做空，SMA{periods[0]}反弹减仓，SMA{periods[1]}为核心阻力")
                elif fast_sma > mid_sma and current_price > mid_sma:
                    info_lines.append(f"偏多格局: SMA{periods[0]}上穿SMA{periods[1]}，价格在SMA{periods[1]}上方")
                    info_lines.append(f"策略: 谨慎做多，等待SMA{periods[1]}支撑确认")
                elif fast_sma < mid_sma and current_price < mid_sma:
                    info_lines.append(f"偏空格局: SMA{periods[0]}下穿SMA{periods[1]}，价格在SMA{periods[1]}下方")
                    info_lines.append(f"策略: 谨慎做空，等待SMA{periods[1]}阻力确认")
                else:
                    info_lines.append("震荡格局: SMA排列混乱，方向不明")
                    info_lines.append("策略: 观望为主，等待SMA重新排列")

            # SMA特有的稳定性分析
            if len(periods) >= 3:
                fast_sma = sma_values[periods[0]]
                slow_sma = sma_values[periods[2]]

                # 检查SMA收敛（SMA收敛比EMA更显著，变盘信号更强）
                ma_compression = abs(fast_sma - slow_sma) / slow_sma * 100
                if ma_compression < 0.8:
                    info_lines.append("SMA极度收敛 - 重大趋势变盘在即")
                elif ma_compression < 1.5:
                    info_lines.append("SMA收敛中 - 准备捕捉方向突破")

                # SMA与价格的乖离分析（SMA乖离修复更有规律）
                if current_price and fast_sma:
                    price_sma_deviation = abs(current_price - fast_sma) / fast_sma * 100
                    if price_sma_deviation > 4.0:
                        info_lines.append("价格与快线SMA乖离过大 - 回归概率很高")
                    elif price_sma_deviation > 2.0:
                        info_lines.append("价格与快线SMA适度乖离 - 关注回归")

        return "\n".join(info_lines)

    def update_history(self, history) -> None:
        """重写update_history，清除缓存触发重算"""
        for w in self.sma_data:
            self.sma_data[w].clear()
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """重写update_bar，清除缓存让下次访问触发重算"""
        for w in self.sma_data:
            self.sma_data[w].clear()
        super().update_bar(bar)

    def update_history(self, history) -> None:
        """重写update_history，清除缓存触发重算"""
        for k in self.sma_data:
            self.sma_data[k].clear()
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """重写update_bar，清除缓存让下次访问触发重算"""
        for k in self.sma_data:
            self.sma_data[k].clear()
        super().update_bar(bar)

    def clear_all(self) -> None:
        """清除所有数据"""
        super().clear_all()
        for sma_window in self.sma_data:
            self.sma_data[sma_window].clear()
        self._bar_picutures.clear()
        self.update()

    # ConfigurableIndicator接口实现
    def get_config_params(self) -> Dict:
        """返回可配置参数"""
        return {
            'periods': {
                'name': 'SMA周期组合',
                'type': 'str',
                'value': ','.join(map(str, self.periods)),
                'description': '用逗号分隔的周期，如: 5,10,20,60'
            }
        }

    def update_config(self, config: Dict) -> None:
        """更新配置"""
        if 'periods' in config:
            try:
                periods_str = config['periods']
                new_periods = tuple(int(p.strip()) for p in periods_str.split(',') if p.strip())
                if new_periods:
                    self.periods = new_periods
                    
                    # 重新设置画笔和数据
                    self.lines.clear()
                    self.sma_data.clear()

                    colors = [
                        (255, 255, 255),    # 白色 - 短线
                        (255, 0, 255),      # 紫色 - 中线
                        (100, 100, 255),    # 蓝色 - 慢线
                        (0, 255, 255),      # 青色
                        (255, 128, 0),      # 橙色
                        (128, 255, 128),    # 浅绿色
                        (255, 128, 128),    # 浅红色
                        (128, 128, 255),    # 浅蓝色
                    ]
                    
                    for i, period in enumerate(self.periods):
                        color = colors[i % len(colors)]
                        self.add_sma_line(period, color, 2)
                    
                    self.clear_all()
            except (ValueError, TypeError):
                pass  # 忽略无效输入
    
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        periods_str = ",".join(str(p) for p in self.periods)
        config_items = [
            ("periods", "SMA周期", "lineedit", periods_str)
        ]
        
        return self.create_config_dialog(parent, "多周期SMA配置", config_items)
    
    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return "SMA周期配置说明：\n• 用逗号分隔多个周期值\n• 例如：5,10,20,60\n• 支持最多8条SMA线"
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置"""
        if 'periods' in config:
            periods_value = config['periods']
            if isinstance(periods_value, str):
                # 解析逗号分隔的字符串
                try:
                    new_periods = tuple(int(p.strip()) for p in periods_value.split(',') if p.strip())
                    if new_periods:
                        self.periods = new_periods
                        
                        # 重新设置画笔和数据
                        self.lines.clear()
                        self.sma_data.clear()

                        colors = [
                            (255, 255, 255),    # 白色 - 短线
                            (255, 0, 255),      # 紫色 - 中线
                            (100, 100, 255),    # 蓝色 - 慢线
                            (0, 255, 255),      # 青色
                            (255, 128, 0),      # 橙色
                            (128, 255, 128),    # 浅绿色
                            (255, 128, 128),    # 浅红色
                            (128, 128, 255),    # 浅蓝色
                        ]
                        
                        for i, period in enumerate(self.periods):
                            color = colors[i % len(colors)]
                            self.add_sma_line(period, color, 2)
                        
                        self.clear_all()
                except (ValueError, TypeError):
                    pass  # 忽略无效输入
            elif isinstance(periods_value, (list, tuple)):
                # 直接设置周期列表
                self.periods = tuple(periods_value)
                # 重新初始化
                self.lines.clear()
                self.sma_data.clear()
                colors = [(255, 255, 255), (255, 0, 255), (100, 100, 255), (0, 255, 255)]
                for i, period in enumerate(self.periods):
                    color = colors[i % len(colors)]
                    self.add_sma_line(period, color, 2)
                self.clear_all()
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'periods': ",".join(str(p) for p in self.periods)
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'periods': "25,60,100"
        }