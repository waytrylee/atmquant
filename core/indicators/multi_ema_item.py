#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期指数移动平均线指标 - 完全按照参考代码样式
"""

from typing import Dict, Tuple, Any
import numpy as np
from vnpy.trader.object import BarData
from vnpy.chart.item import CandleItem
from vnpy.trader.ui import QtGui, QtCore, QtWidgets
import pyqtgraph as pg

from .indicator_base import ConfigurableIndicator
from .calculators.ema_calculator import EMACalculator


class MultiEmaItem(CandleItem, ConfigurableIndicator):
    """
    绘制多条指数移动平均线(EMA)的类 - 参考原始代码样式
    """

    def __init__(self, manager, periods: Tuple[int, ...] = (9, 20, 60)):
        """
        初始化
        """
        super().__init__(manager)

        self.periods = periods
        self.lines: Dict[int, QtGui.QPen] = {}  # 存储窗口大小和对应的画笔
        self.ema_data: Dict[int, Dict[int, float]] = {}  # 存储多个窗口的EMA数据
        
        # 设置颜色 - 与SMA区分开来
        colors = [
            (255, 165, 0),      # 橙色
            (255, 20, 147),     # 深粉色
            (0, 255, 127),      # 春绿色
            (30, 144, 255),     # 道奇蓝
            (255, 69, 0),       # 红橙色
            (138, 43, 226),     # 蓝紫色
            (50, 205, 50),      # 酸橙绿
            (255, 215, 0),      # 金色
        ]
        
        # 为每个周期设置画笔 - 参考原始代码样式
        for i, period in enumerate(self.periods):
            color = colors[i % len(colors)]
            self.add_ema_line(period, color, 2)

    def add_ema_line(self, ema_window: int, color: Tuple[int, int, int] = (100, 100, 255), width: int = 2):
        """
        添加一条EMA线 - 参考原始代码样式
        """
        self.lines[ema_window] = pg.mkPen(color=color, width=width)
        self.ema_data[ema_window] = {}

    def _ensure_calculated(self, ema_window: int) -> None:
        """全量计算指定周期的 EMA 数据，委托给 EMACalculator"""
        if self.ema_data.get(ema_window):
            return
        bars = self._manager.get_all_bars()
        if not bars or len(bars) < ema_window:
            return
        close_array = np.array([bar.close_price for bar in bars])
        ema_array = EMACalculator.compute_array(close_array, ema_window)
        self.ema_data[ema_window] = {}
        for n, value in enumerate(ema_array):
            self.ema_data[ema_window][n] = value

    def get_ema_value(self, ix: int, ema_window: int) -> float:
        """获取指定窗口大小的 EMA 值"""
        if ix < 0:
            return np.nan
        self._ensure_calculated(ema_window)
        if ema_window in self.ema_data and ix in self.ema_data[ema_window]:
            return self.ema_data[ema_window][ix]
        return np.nan

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        绘制K线与EMA - 完全按照参考代码样式
        """
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)

        for ema_window, pen in self.lines.items():
            ema_value = self.get_ema_value(ix, ema_window)
            last_ema_value = self.get_ema_value(ix - 1, ema_window)

            # 只有当前值和前一个值都有效且非NaN时才绘制线条
            if (not np.isnan(ema_value) and not np.isnan(last_ema_value) and 
                ix >= ema_window):
                
                # 设置画笔颜色
                painter.setPen(pen)

                # 绘制EMA线
                start_point = QtCore.QPointF(ix - 1, last_ema_value)
                end_point = QtCore.QPointF(ix, ema_value)
                painter.drawLine(start_point, end_point)

        painter.end()
        return picture

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前EMA数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1
        ema_values = {}
        prev_ema_values = {}

        # 使用get_ema_value确保数据被计算（即使指标被隐藏）
        for ema_window in self.ema_data.keys():
            value = self.get_ema_value(ix, ema_window)
            if not np.isnan(value):
                ema_values[ema_window] = value

            prev_value = self.get_ema_value(ix - 1, ema_window)
            if not np.isnan(prev_value):
                prev_ema_values[ema_window] = prev_value

        if not ema_values:
            return {}

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        # 判断趋势（基于短期和长期EMA）
        windows = sorted(ema_values.keys())
        if len(windows) >= 2:
            short_window = windows[0]
            long_window = windows[-1]
            short_ema = ema_values[short_window]
            long_ema = ema_values[long_window]
            trend = "up" if short_ema > long_ema else "down" if short_ema < long_ema else "neutral"
        else:
            trend = "unknown"

        return {
            "values": {k: round(v, 2) for k, v in ema_values.items()},
            "previous_values": {k: round(v, 2) for k, v in prev_ema_values.items()} if prev_ema_values else {},
            "trend": trend,
            "current_price": round(current_price, 2),
            "windows": windows
        }

    def get_info_text(self, ix: int) -> str:
        """
        返回信息文本，显示所有 EMA 值和交易指导
        """
        info_lines = []
        ema_values = {}

        # 收集所有EMA值
        for ema_window, data in self.ema_data.items():
            if ix in data and not np.isnan(data[ix]):
                ema_values[ema_window] = data[ix]
                info_lines.append(f"EMA({ema_window}): {data[ix]:.2f}")

        if not ema_values:
            return "EMA数据不足"

        # 获取当前价格用于分析
        bar = self._manager.get_bar(ix)
        current_price = bar.close_price if bar else None

        # 获取前一个数据用于趋势判断
        prev_ix = ix - 1
        prev_ema_values = {}
        prev_price = None

        if prev_ix >= 0:
            prev_bar = self._manager.get_bar(prev_ix)
            prev_price = prev_bar.close_price if prev_bar else None

            for ema_window, data in self.ema_data.items():
                if prev_ix in data and not np.isnan(data[prev_ix]):
                    prev_ema_values[ema_window] = data[prev_ix]

        # 按周期排序（快、中、慢三条线）
        periods = sorted(ema_values.keys())

        if len(periods) >= 2 and current_price is not None:

            # EMA排列状态分析（相比SMA，EMA对价格变化更敏感）
            if len(periods) >= 3:
                fast_ema = ema_values[periods[0]]
                mid_ema = ema_values[periods[1]]
                slow_ema = ema_values[periods[2]]

                # 判断EMA排列类型
                if fast_ema > mid_ema > slow_ema:
                    info_lines.append("EMA状态: 多头排列")
                    info_lines.append("趋势强度: 强势上升（EMA敏感反应）")
                elif fast_ema < mid_ema < slow_ema:
                    info_lines.append("EMA状态: 空头排列")
                    info_lines.append("趋势强度: 强势下降（EMA敏感反应）")
                else:
                    info_lines.append("EMA状态: 震荡排列")
                    info_lines.append("趋势强度: 方向不明（等待突破）")

                # 分析EMA间距离（EMA收敛发散特性，针对商品期货优化）
                ema_spread_fast_mid = abs(fast_ema - mid_ema) / mid_ema * 100
                ema_spread_mid_slow = abs(mid_ema - slow_ema) / slow_ema * 100

                if ema_spread_fast_mid > 2.0 or ema_spread_mid_slow > 1.5:
                    info_lines.append("EMA散度: 大 - 趋势加速（EMA快速发散）")
                elif ema_spread_fast_mid > 1.0 or ema_spread_mid_slow > 0.8:
                    info_lines.append("EMA散度: 中等 - 趋势稳定")
                else:
                    info_lines.append("EMA散度: 小 - 趋势减弱（EMA收敛中）")

            # 价格与EMA关系分析
            price_above_count = sum(1 for ema_val in ema_values.values() if current_price > ema_val)
            total_lines = len(ema_values)

            if price_above_count == total_lines:
                info_lines.append("价格位置: 全部EMA之上")
                info_lines.append("市场状态: 强势多头（EMA全面支撑）")
            elif price_above_count == 0:
                info_lines.append("价格位置: 全部EMA之下")
                info_lines.append("市场状态: 强势空头（EMA全面压制）")
            else:
                info_lines.append(f"价格位置: {price_above_count}/{total_lines}EMA之上")
                info_lines.append("市场状态: 震荡或转换期（关注EMA突破）")

            # 检测EMA交叉信号（EMA交叉更敏感、更早期）
            if prev_ema_values and prev_price is not None:

                # 检测黄金交叉和死亡交叉
                crossovers_detected = []

                if len(periods) >= 2:
                    fast_period = periods[0]
                    slow_period = periods[1]

                    if (fast_period in prev_ema_values and slow_period in prev_ema_values):
                        prev_fast = prev_ema_values[fast_period]
                        prev_slow = prev_ema_values[slow_period]
                        curr_fast = ema_values[fast_period]
                        curr_slow = ema_values[slow_period]

                        # 黄金交叉（EMA更早发出信号）
                        if prev_fast <= prev_slow and curr_fast > curr_slow:
                            crossovers_detected.append("EMA黄金交叉 - 早期看涨信号")
                        # 死亡交叉
                        elif prev_fast >= prev_slow and curr_fast < curr_slow:
                            crossovers_detected.append("EMA死亡交叉 - 早期看跌信号")

                # 检测价格与EMA的交叉（更敏感的支撑阻力反应）
                for period in periods:
                    if period in prev_ema_values:
                        prev_ema = prev_ema_values[period]
                        curr_ema = ema_values[period]

                        # 价格上穿EMA（更敏感的突破信号）
                        if prev_price <= prev_ema and current_price > curr_ema:
                            crossovers_detected.append(f"价格上穿EMA({period}) - 敏感做多信号")
                        # 价格下穿EMA
                        elif prev_price >= prev_ema and current_price < curr_ema:
                            crossovers_detected.append(f"价格下穿EMA({period}) - 敏感做空信号")

                if crossovers_detected:
                    info_lines.extend(crossovers_detected)
                else:
                    info_lines.append("交叉信号: 无明显交叉")

            # EMA回踩机会分析（EMA作为动态支撑阻力）
            nearest_support = None
            nearest_resistance = None
            min_support_dist = float('inf')
            min_resistance_dist = float('inf')

            for period, ema_val in ema_values.items():
                distance = abs(current_price - ema_val) / current_price * 100

                if ema_val < current_price and distance < min_support_dist:
                    nearest_support = (period, ema_val, distance)
                    min_support_dist = distance
                elif ema_val > current_price and distance < min_resistance_dist:
                    nearest_resistance = (period, ema_val, distance)
                    min_resistance_dist = distance

            # 差异化阈值设置（根据EMA周期特性）
            def get_ema_thresholds_and_advice(period, distance, is_support=True):
                """根据EMA周期返回阈值和交易建议"""
                if period <= 20:  # 快线（如EMA9, EMA12, EMA20）
                    close_threshold = 0.6
                    near_threshold = 1.5
                    line_type = "快线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA支撑极近 - 短线反弹信号强烈"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA支撑 - 准备短线回踩买入"
                        else:
                            advice = f"远离{line_type}EMA支撑 - 等待回踩确认"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA阻力极近 - 短线回调压力大"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA阻力 - 准备短线减仓"
                        else:
                            advice = f"远离{line_type}EMA阻力 - 突破后追涨"
                elif period <= 60:  # 中线（如EMA30, EMA50, EMA60）
                    close_threshold = 1.0
                    near_threshold = 2.5
                    line_type = "中线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA支撑很近 - 中期趋势支撑强劲"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA支撑 - 重要回踩买入机会"
                        else:
                            advice = f"远离{line_type}EMA支撑 - 关注中期趋势"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA阻力很近 - 中期压力位考验"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA阻力 - 重要减仓获利位"
                        else:
                            advice = f"远离{line_type}EMA阻力 - 突破确认中期转势"
                else:  # 慢线（如EMA100, EMA200）
                    close_threshold = 1.5
                    near_threshold = 3.5
                    line_type = "慢线"
                    if is_support:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA支撑很近 - 长期趋势关键支撑"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA支撑 - 长期投资买入良机"
                        else:
                            advice = f"远离{line_type}EMA支撑 - 长期趋势健康"
                    else:
                        if distance < close_threshold:
                            advice = f"距离{line_type}EMA阻力很近 - 长期趋势转换关键位"
                        elif distance < near_threshold:
                            advice = f"接近{line_type}EMA阻力 - 长期头部区域警惕"
                        else:
                            advice = f"远离{line_type}EMA阻力 - 突破确认长期牛市"

                return close_threshold, near_threshold, advice

            if nearest_support:
                period, price, dist = nearest_support
                close_thresh, near_thresh, advice = get_ema_thresholds_and_advice(period, dist, True)
                info_lines.append(f"最近支撑: EMA({period}) {price:.2f} ({dist:.1f}%)")
                info_lines.append(advice)

            if nearest_resistance:
                period, price, dist = nearest_resistance
                close_thresh, near_thresh, advice = get_ema_thresholds_and_advice(period, dist, False)
                info_lines.append(f"最近阻力: EMA({period}) {price:.2f} ({dist:.1f}%)")
                info_lines.append(advice)

            # EMA趋势强度分析（EMA斜率变化更明显）
            if prev_ema_values:
                trend_strength_scores = []

                for period in periods:
                    if period in prev_ema_values:
                        curr_ema = ema_values[period]
                        prev_ema = prev_ema_values[period]

                        # 计算EMA斜率（趋势强度）
                        slope = (curr_ema - prev_ema) / prev_ema * 100
                        trend_strength_scores.append(slope)

                if trend_strength_scores:
                    avg_slope = sum(trend_strength_scores) / len(trend_strength_scores)

                    if avg_slope > 0.5:
                        info_lines.append("EMA趋势: 强势上升")
                        info_lines.append("操作建议: 积极做多，EMA回踩加仓")
                    elif avg_slope < -0.5:
                        info_lines.append("EMA趋势: 强势下降")
                        info_lines.append("操作建议: 积极做空，EMA反弹减仓")
                    elif avg_slope > 0.15:
                        info_lines.append("EMA趋势: 温和上升")
                        info_lines.append("操作建议: 谨慎做多，关注EMA支撑")
                    elif avg_slope < -0.15:
                        info_lines.append("EMA趋势: 温和下降")
                        info_lines.append("操作建议: 谨慎做空，关注EMA阻力")
                    else:
                        info_lines.append("EMA趋势: 横盘整理")
                        info_lines.append("操作建议: 区间操作，等待EMA方向明确")

            # EMA特有的敏感性分析
            if len(periods) >= 3:
                fast_ema = ema_values[periods[0]]
                slow_ema = ema_values[periods[2]]

                # 检查EMA收敛（比SMA更早预警变盘，商品期货优化）
                ema_compression = abs(fast_ema - slow_ema) / slow_ema * 100
                if ema_compression < 0.5:
                    info_lines.append("EMA极度收敛 - 重大变盘在即")
                elif ema_compression < 1.0:
                    info_lines.append("EMA收敛中 - 准备捕捉早期突破")

                # EMA与价格的乖离分析（商品期货波动特性）
                if current_price and fast_ema:
                    price_ema_deviation = abs(current_price - fast_ema) / fast_ema * 100
                    if price_ema_deviation > 4.0:
                        info_lines.append("价格与快线EMA乖离过大 - 回归概率高")
                    elif price_ema_deviation > 2.0:
                        info_lines.append("价格与快线EMA适度乖离 - 关注回踩")

            # EMA经典策略分析（基于实际设置的快慢长周期）
            if len(periods) >= 3:
                fast_ema = ema_values[periods[0]]   # 最快线
                mid_ema = ema_values[periods[1]]    # 中线
                slow_ema = ema_values[periods[2]]   # 最慢线

                # 经典EMA策略分析
                if current_price > fast_ema > mid_ema > slow_ema:
                    info_lines.append(f"经典多头格局: 价格>EMA{periods[0]}>EMA{periods[1]}>EMA{periods[2]}")
                    info_lines.append(f"策略: 强势做多，EMA{periods[0]}回踩加仓，EMA{periods[1]}为强支撑")
                elif current_price < fast_ema < mid_ema < slow_ema:
                    info_lines.append(f"经典空头格局: 价格<EMA{periods[0]}<EMA{periods[1]}<EMA{periods[2]}")
                    info_lines.append(f"策略: 强势做空，EMA{periods[0]}反弹减仓，EMA{periods[1]}为强阻力")
                elif fast_ema > mid_ema and current_price > mid_ema:
                    info_lines.append(f"偏多格局: EMA{periods[0]}上穿EMA{periods[1]}，价格在EMA{periods[1]}上方")
                    info_lines.append(f"策略: 谨慎做多，等待EMA{periods[1]}支撑确认")
                elif fast_ema < mid_ema and current_price < mid_ema:
                    info_lines.append(f"偏空格局: EMA{periods[0]}下穿EMA{periods[1]}，价格在EMA{periods[1]}下方")
                    info_lines.append(f"策略: 谨慎做空，等待EMA{periods[1]}阻力确认")
                else:
                    info_lines.append("震荡格局: EMA排列混乱，方向不明")
                    info_lines.append("策略: 观望为主，等待EMA重新排列")

        return "\n".join(info_lines)

    def update_history(self, history) -> None:
        """重写update_history，清除缓存触发重算"""
        for k in self.ema_data:
            self.ema_data[k].clear()
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """重写update_bar，清除缓存让下次访问触发重算"""
        for k in self.ema_data:
            self.ema_data[k].clear()
        super().update_bar(bar)

    def clear_all(self) -> None:
        """清除所有数据"""
        super().clear_all()
        for ema_window in self.ema_data:
            self.ema_data[ema_window].clear()
        self._bar_picutures.clear()
        self.update()

    # ConfigurableIndicator接口实现
    def get_config_params(self) -> Dict:
        """返回可配置参数"""
        return {
            'periods': {
                'name': 'EMA周期组合',
                'type': 'str',
                'value': ','.join(map(str, self.periods)),
                'description': '用逗号分隔的周期，如: 12,26,50'
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
                    self.ema_data.clear()
                    
                    colors = [
                        (255, 165, 0),      # 橙色
                        (255, 20, 147),     # 深粉色
                        (0, 255, 127),      # 春绿色
                        (30, 144, 255),     # 道奇蓝
                        (255, 69, 0),       # 红橙色
                        (138, 43, 226),     # 蓝紫色
                        (50, 205, 50),      # 酸橙绿
                        (255, 215, 0),      # 金色
                    ]
                    
                    for i, period in enumerate(self.periods):
                        color = colors[i % len(colors)]
                        self.add_ema_line(period, color, 2)
                    
                    self.clear_all()
            except (ValueError, TypeError):
                pass  # 忽略无效输入
    
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        periods_str = ",".join(str(p) for p in self.periods)
        config_items = [
            ("periods", "EMA周期", "lineedit", periods_str)
        ]
        
        return self.create_config_dialog(parent, "多周期EMA配置", config_items)
    
    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return "EMA周期配置说明：\n• 用逗号分隔多个周期值\n• 例如：12,26,50\n• 支持最多8条EMA线"
    
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
                        self.ema_data.clear()
                        
                        colors = [
                            (255, 165, 0),      # 橙色
                            (255, 20, 147),     # 深粉色
                            (0, 255, 127),      # 春绿色
                            (30, 144, 255),     # 道奇蓝
                            (255, 69, 0),       # 红橙色
                            (138, 43, 226),     # 蓝紫色
                            (50, 205, 50),      # 酸橙绿
                            (255, 215, 0),      # 金色
                        ]
                        
                        for i, period in enumerate(self.periods):
                            color = colors[i % len(colors)]
                            self.add_ema_line(period, color, 2)
                        
                        self.clear_all()
                except (ValueError, TypeError):
                    pass  # 忽略无效输入
            elif isinstance(periods_value, (list, tuple)):
                # 直接设置周期列表
                self.periods = tuple(periods_value)
                # 重新初始化
                self.lines.clear()
                self.ema_data.clear()
                colors = [(255, 165, 0), (255, 20, 147), (0, 255, 127), (30, 144, 255)]
                for i, period in enumerate(self.periods):
                    color = colors[i % len(colors)]
                    self.add_ema_line(period, color, 2)
                self.clear_all()
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'periods': ",".join(str(p) for p in self.periods)
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'periods': "9,20,60"
        }