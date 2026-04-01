#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD指标
基于vnpy ChartItem实现的MACD技术指标
"""

from typing import Dict, Any, Tuple, List
import numpy as np
import pyqtgraph as pg

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData
from vnpy.chart.item import ChartItem
from vnpy.chart.manager import BarManager

from .indicator_base import ConfigurableIndicator
from .calculators.macd_calculator import MACDCalculator


class Macd3Item(ChartItem, ConfigurableIndicator):
    """
    三根线的MACD
    参考原始代码风格，支持参数配置
    """
    
    def __init__(self, manager: BarManager, short_window: int = 12, long_window: int = 26, M: int = 9):
        """初始化MACD指标"""
        super().__init__(manager)
        
        # 参数设置
        self.short_window = short_window
        self.long_window = long_window
        self.M = M
        
        # 现代化配色方案 - 更加专业和美观
        # DIFF线 - 使用现代蓝色，线条稍粗
        self.diff_pen: QtGui.QPen = pg.mkPen(color=(64, 158, 255), width=2)  # 现代蓝色
        # DEA线 - 使用橙色，形成良好对比
        self.dea_pen: QtGui.QPen = pg.mkPen(color=(255, 152, 0), width=2)    # 现代橙色
        
        # MACD柱状图 - 中国习惯：红涨绿跌
        self.macd_bull_pen: QtGui.QPen = pg.mkPen(color=(239, 68, 68), width=1)      # 多头用红色（上涨）
        self.macd_bear_pen: QtGui.QPen = pg.mkPen(color=(34, 197, 94), width=1)      # 空头用绿色（下跌）
        
        # 背离线 - 中国习惯：红涨绿跌
        self.bull_divergence_pen: QtGui.QPen = pg.mkPen(color=(245, 101, 101), width=3, style=QtCore.Qt.DashLine) # 多头背离用红色虚线
        self.bear_divergence_pen: QtGui.QPen = pg.mkPen(color=(16, 185, 129), width=3, style=QtCore.Qt.DashLine)  # 空头背离用绿色虚线
        
        # 零轴参考线 - 使用半透明灰色
        self.zero_line_pen: QtGui.QPen = pg.mkPen(color=(156, 163, 175, 128), width=1, style=QtCore.Qt.DashLine)
        
        # 保留旧的画笔用于兼容性（更新为中国习惯）
        self.white_pen: QtGui.QPen = self.diff_pen  # 向后兼容
        self.yellow_pen: QtGui.QPen = self.dea_pen  # 向后兼容
        self.red_pen: QtGui.QPen = self.macd_bull_pen   # 红色用于多头（上涨）
        self.green_pen: QtGui.QPen = self.macd_bear_pen # 绿色用于空头（下跌）
        self.gold_pen: QtGui.QPen = self.bear_divergence_pen  # 向后兼容
        self.purple_pen: QtGui.QPen = self.bull_divergence_pen  # 向后兼容
        
        # 缓存设置
        self._values_ranges: Dict[Tuple[int, int], Tuple[float, float]] = {}
        
        # 添加放大因子，适应短周期数据
        self.scale_factor = 100.0  # 默认放大100倍
        
        # 数据缓存
        self.macd_data: Dict[int, List[float]] = {}
        self._needs_recalc = True
        
        # 背离数据
        self.start_bull_indices = []
        self.end_bull_indices = []
        self.start_bear_indices = []
        self.end_bear_indices = []

    def add_divergence_pairs(self, short_window, long_window, period, bull_divergence_pairs, bear_divergence_pairs):
        """添加背离对"""
        self.short_window = short_window
        self.long_window = long_window
        self.M = period
        self.start_bull_indices = [pair[1] for pair in bull_divergence_pairs]
        self.end_bull_indices = [pair[0] for pair in bull_divergence_pairs]
        self.start_bear_indices = [pair[1] for pair in bear_divergence_pairs]
        self.end_bear_indices = [pair[0] for pair in bear_divergence_pairs]
        
    def set_scale_factor(self, scale_factor: float = 100.0):
        """设置MACD值的放大因子"""
        self.scale_factor = scale_factor
        # 清空缓存数据，重新计算
        self.macd_data.clear()
        self._values_ranges.clear()
        # 触发重绘
        self.update()
    
    def update_history(self, history: List[BarData]) -> None:
        """重写update_history方法，确保数据更新时清理缓存"""
        self.macd_data.clear()
        self._values_ranges.clear()
        self._needs_recalc = True
        super().update_history(history)
    
    def update_bar(self, bar: BarData) -> None:
        """重写update_bar方法，确保新数据更新时清理相关缓存"""
        self.macd_data.clear()
        self._values_ranges.clear()
        self._needs_recalc = True
        super().update_bar(bar)

    def _ensure_calculated(self) -> None:
        """全量计算 MACD 数据，委托给 MACDCalculator"""
        if not self._needs_recalc and self.macd_data:
            return

        bars = self._manager.get_all_bars()
        min_required = max(self.short_window, self.long_window) + self.M * 2
        if not bars or len(bars) < min_required:
            return

        try:
            close_array = np.array([bar.close_price for bar in bars])
            diffs, deas, macds = MACDCalculator.compute_arrays(
                close_array, self.short_window, self.long_window, self.M
            )

            # 计算慢线
            valid_data = not np.isnan(deas).all()
            if valid_data:
                try:
                    slow_deas = MACDCalculator.compute_ema(deas, self.M)
                except Exception:
                    slow_deas = np.full_like(deas, np.nan)
            else:
                slow_deas = np.full_like(deas, np.nan)

            # 检测是否为短周期小数值数据，应用放大因子
            valid_macds = macds[~np.isnan(macds)]
            if len(valid_macds) > 0 and np.max(np.abs(valid_macds)) < 1.0:
                diffs = diffs * self.scale_factor
                deas = deas * self.scale_factor
                macds = macds * self.scale_factor
                slow_deas = slow_deas * self.scale_factor

            self.macd_data.clear()
            for n in range(len(diffs)):
                self.macd_data[n] = [diffs[n], deas[n], macds[n], slow_deas[n]]
            self._needs_recalc = False
        except Exception:
            pass

    def _get_macd_value(self, ix: int) -> List[float]:
        """获取指定索引的 MACD 值"""
        invalid_value = [np.nan, np.nan, np.nan, np.nan]
        if ix < 0:
            return invalid_value
        self._ensure_calculated()
        return self.macd_data.get(ix, invalid_value)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """绘制MACD"""
        # 创建绘图对象
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)
        
        # 启用抗锯齿，提升绘图质量
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # 获取当前值
        macd_value = self._get_macd_value(ix)
        
        # 检查数据有效性
        if all(np.isnan(val) for val in macd_value):
            painter.end()
            return picture

        # 1. 绘制零轴参考线（仅在第一个K线时绘制）
        if ix == 0:
            painter.setPen(self.zero_line_pen)
            painter.drawLine(QtCore.QPointF(-0.5, 0), QtCore.QPointF(0.5, 0))

        # 2. 绘制MACD柱状图 - 使用现代化颜色和渐变效果
        if not np.isnan(macd_value[2]):
            bar_width = 0.6
            bar_height = macd_value[2]
            
            if macd_value[2] > 0:
                # 多头柱状图 - 中国习惯：红色（上涨）
                painter.setPen(self.macd_bull_pen)
                # 创建渐变填充 - 红色半透明
                brush = pg.mkBrush(239, 68, 68, 180)  # 红色半透明效果
                painter.setBrush(brush)
            else:
                # 空头柱状图 - 中国习惯：绿色（下跌）
                painter.setPen(self.macd_bear_pen)
                # 创建渐变填充 - 绿色半透明
                brush = pg.mkBrush(34, 197, 94, 180)  # 绿色半透明效果
                painter.setBrush(brush)
            
            # 绘制圆角矩形，更现代化
            rect = QtCore.QRectF(ix - bar_width/2, 0, bar_width, bar_height)
            painter.drawRect(rect)

        # 3. 绘制MACD线条（只有当前点和前一点都有效时才绘制）
        if ix > 0:
            last_macd_value = self._get_macd_value(ix - 1)
            
            # 绘制DIFF线（现代蓝色，更粗）
            if not (np.isnan(macd_value[0]) or np.isnan(last_macd_value[0])):
                end_point0 = QtCore.QPointF(ix, macd_value[0])
                start_point0 = QtCore.QPointF(ix - 1, last_macd_value[0])
                painter.setPen(self.diff_pen)
                painter.drawLine(start_point0, end_point0)

            # 绘制DEA线（现代橙色，更粗）
            if not (np.isnan(macd_value[1]) or np.isnan(last_macd_value[1])):
                end_point1 = QtCore.QPointF(ix, macd_value[1])
                start_point1 = QtCore.QPointF(ix - 1, last_macd_value[1])
                painter.setPen(self.dea_pen)
                painter.drawLine(start_point1, end_point1)

        # 4. 绘制背离线 - 使用现代化样式
        try:
            # 顶背离线（翠绿色虚线）
            if ix in self.start_bull_indices:
                start_index = self.start_bull_indices.index(ix)
                if start_index < len(self.end_bull_indices):
                    end_index = self.end_bull_indices[start_index]
                    end_macd_value = self._get_macd_value(end_index)
                    if not (np.isnan(macd_value[2]) or np.isnan(end_macd_value[2])):
                        start_point = QtCore.QPointF(ix, macd_value[2])
                        end_point = QtCore.QPointF(end_index, end_macd_value[2])
                        painter.setPen(self.bull_divergence_pen)
                        painter.drawLine(start_point, end_point)

            # 底背离线（珊瑚红虚线）
            if ix in self.start_bear_indices:
                start_index = self.start_bear_indices.index(ix)
                if start_index < len(self.end_bear_indices):
                    end_index = self.end_bear_indices[start_index]
                    end_macd_value = self._get_macd_value(end_index)
                    if not (np.isnan(macd_value[2]) or np.isnan(end_macd_value[2])):
                        start_point = QtCore.QPointF(ix, macd_value[2])
                        end_point = QtCore.QPointF(end_index, end_macd_value[2])
                        painter.setPen(self.bear_divergence_pen)
                        painter.drawLine(start_point, end_point)
        except (IndexError, ValueError) as e:
            # 忽略背离线绘制错误，不影响主要图形
            pass

        painter.end()
        return picture

    def boundingRect(self) -> QtCore.QRectF:
        """返回边界矩形"""
        min_y, max_y = self.get_y_range()
        bar_count = self._manager.get_count()
        
        # 确保有足够的边距
        margin = abs(max_y - min_y) * 0.1 if max_y != min_y else 10
        
        rect = QtCore.QRectF(
            0,
            min_y - margin,
            max(bar_count, 1),  # 确保宽度至少为1
            max_y - min_y + 2 * margin
        )
        return rect

    def get_y_range(self, min_ix: int = None, max_ix: int = None) -> Tuple[float, float]:
        """获取MACD指标的Y轴范围值"""
        bar_count = self._manager.get_count()
        
        # 如果没有数据，返回默认范围
        if bar_count == 0 or not self.macd_data:
            return -100.0, 100.0

        # 如果显示范围为全局或未指定
        if min_ix is None or max_ix is None:
            min_ix = 0
            max_ix = bar_count - 1

        # 限制索引范围在合法数据范围内
        min_ix = max(min_ix, 0)
        max_ix = min(max_ix, bar_count - 1)
        
        # 确保范围有效
        if min_ix > max_ix:
            return -100.0, 100.0

        # 提取范围内的所有MACD值（包括diff, dea, macd）
        valid_values = []
        
        for ix in range(min_ix, max_ix + 1):
            if ix in self.macd_data:
                macd_values = self.macd_data[ix]
                # 收集diff, dea, macd三个值（跳过slow_dea）
                for i in [0, 1, 2]:  # diff, dea, macd
                    if i < len(macd_values) and not np.isnan(macd_values[i]):
                        valid_values.append(macd_values[i])

        # 如果没有有效值，返回默认范围
        if not valid_values:
            return -100.0, 100.0

        # 计算范围内的最大和最小值
        min_price = min(valid_values)
        max_price = max(valid_values)
        
        # 如果最大值和最小值相等，添加一些边距
        if abs(max_price - min_price) < 1e-6:
            center = (max_price + min_price) / 2
            range_margin = max(abs(center) * 0.1, 10.0)
            min_price = center - range_margin
            max_price = center + range_margin
        else:
            # 添加10%的边距以便更好显示
            range_span = max_price - min_price
            margin = range_span * 0.1
            min_price -= margin
            max_price += margin

        return min_price, max_price

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前MACD数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1

        # 使用_get_macd_value确保数据被计算（即使指标被隐藏）
        macd_values = self._get_macd_value(ix)
        if all(np.isnan(val) for val in macd_values):
            return {}
        diff = macd_values[0]  # DIFF
        dea = macd_values[1]   # DEA
        macd_hist = macd_values[2]  # MACD柱状图

        # 获取前一个数据
        prev_macd_values = self._get_macd_value(ix - 1)
        prev_macd_hist = prev_macd_values[2] if not all(np.isnan(val) for val in prev_macd_values) else None

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        # 确定趋势
        histogram = macd_hist
        trend = "up" if histogram > 0 else "down" if histogram < 0 else "neutral"

        # 检查金叉死叉
        cross_signal = None
        if prev_macd_values:
            prev_diff = prev_macd_values[0]
            prev_dea = prev_macd_values[1]
            # 金叉：DIFF上穿DEA
            if prev_diff <= prev_dea and diff > dea:
                cross_signal = "golden_cross"
            # 死叉：DIFF下穿DEA
            elif prev_diff >= prev_dea and diff < dea:
                cross_signal = "death_cross"

        return {
            "macd": round(macd_hist, 4),
            "diff": round(diff, 4),
            "signal": round(dea, 4),
            "histogram": round(macd_hist, 4),
            "previous_histogram": round(prev_macd_hist, 4) if prev_macd_hist is not None else None,
            "trend": trend,
            "cross_signal": cross_signal,
            "current_price": round(current_price, 2),
            "parameters": {
                "short_window": self.short_window,
                "long_window": self.long_window,
                "signal_window": self.M
            }
        }

    def get_info_text(self, ix: int) -> str:
        """获取MACD信息文本，包含数值和信号解读"""
        if ix in self.macd_data:
            macd_values = self.macd_data[ix]
            diff = macd_values[0]
            dea = macd_values[1]
            macd = macd_values[2]

            # 检查是否应用了放大因子
            scale_text = f" ×{self.scale_factor:.0f}" if self.scale_factor != 1.0 else ""

            # 基础信息
            info_lines = [
                f"MACD ({self.short_window},{self.long_window},{self.M}){scale_text}",
                f"DIFF: {diff:.4f}",
                f"DEA: {dea:.4f}",
                f"MACD: {macd:.4f}",
            ]

            # 获取前一个数据用于趋势判断
            prev_ix = ix - 1
            if prev_ix in self.macd_data:
                prev_values = self.macd_data[prev_ix]
                prev_diff = prev_values[0]
                prev_dea = prev_values[1]
                prev_macd = prev_values[2]

                # 提前计算变化量，避免作用域问题
                macd_change = macd - prev_macd
                diff_change = diff - prev_diff

                # MACD柱状图分析 - 核心指标
                if macd > 0:
                    if prev_macd <= 0:
                        info_lines.append("MACD转正 - 多头启动信号")
                        info_lines.append("策略: 重要买入信号，可建仓做多")
                    else:
                        if macd_change > abs(prev_macd) * 0.3:
                            info_lines.append("MACD快速放大 - 多头动能增强")
                            info_lines.append("趋势: 上涨加速，持有多单")
                        elif macd_change < 0:
                            info_lines.append("MACD红柱缩短 - 多头动能减弱")
                            info_lines.append("警惕: 上涨放缓，注意止盈")
                        else:
                            info_lines.append("MACD红柱 - 多头主导")
                else:
                    if prev_macd >= 0:
                        info_lines.append("MACD转负 - 空头启动信号")
                        info_lines.append("策略: 重要卖出信号，可建仓做空")
                    else:
                        if macd_change < abs(prev_macd) * 0.3:
                            info_lines.append("MACD快速放大 - 空头动能增强")
                            info_lines.append("趋势: 下跌加速，持有空单")
                        elif macd_change > 0:
                            info_lines.append("MACD绿柱缩短 - 空头动能减弱")
                            info_lines.append("警惕: 下跌放缓，注意止盈")
                        else:
                            info_lines.append("MACD绿柱 - 空头主导")

                # 零轴位置分析 - 趋势判断
                if diff > 0 and dea > 0:
                    info_lines.append("零轴上方 - 多头市场")
                    if macd > 0:
                        info_lines.append("市场状态: 强势多头，做多为主")
                    else:
                        info_lines.append("市场状态: 多头调整，回调做多")
                elif diff < 0 and dea < 0:
                    info_lines.append("零轴下方 - 空头市场")
                    if macd < 0:
                        info_lines.append("市场状态: 强势空头，做空为主")
                    else:
                        info_lines.append("市场状态: 空头调整，反弹做空")
                else:
                    info_lines.append("零轴附近 - 多空转换中")
                    info_lines.append("市场状态: 观望为主，等待方向明确")

                # 金叉死叉分析 - 经典信号
                if prev_diff <= prev_dea and diff > dea:
                    if diff > 0:
                        info_lines.append("黄金交叉(零轴上方) - 强烈买入信号")
                        info_lines.append("操作: 积极做多，这是强势金叉")
                    else:
                        info_lines.append("黄金交叉(零轴下方) - 初步买入信号")
                        info_lines.append("操作: 谨慎做多，等待零轴确认")

                elif prev_diff >= prev_dea and diff < dea:
                    if diff < 0:
                        info_lines.append("死亡交叉(零轴下方) - 强烈卖出信号")
                        info_lines.append("操作: 积极做空，这是强势死叉")
                    else:
                        info_lines.append("死亡交叉(零轴上方) - 初步卖出信号")
                        info_lines.append("操作: 谨慎做空，等待零轴确认")

                # DIFF线趋势分析
                diff_slope_ratio = abs(diff_change / prev_diff) * 100 if prev_diff != 0 else 0

                if diff_slope_ratio > 10:
                    if diff_change > 0:
                        info_lines.append("DIFF急速上升 - 买入动能强劲")
                    else:
                        info_lines.append("DIFF急速下降 - 卖出动能强劲")
                elif diff_slope_ratio > 5:
                    if diff_change > 0:
                        info_lines.append("DIFF稳步上升 - 买入力量持续")
                    else:
                        info_lines.append("DIFF稳步下降 - 卖出力量持续")

                # MACD背离检测提示
                if ix in self.start_bull_indices:
                    info_lines.append("检测到底背离 - 反转看涨信号")
                    info_lines.append("重要机会: 价格新低而MACD不创新低")
                    info_lines.append("策略: 等待价格企稳后积极做多")

                if ix in self.start_bear_indices:
                    info_lines.append("检测到顶背离 - 反转看跌信号")
                    info_lines.append("重要警告: 价格新高而MACD不创新高")
                    info_lines.append("策略: 等待价格回落后积极做空")

                # DIFF和DEA之间的距离分析
                diff_dea_distance = abs(diff - dea)
                if diff_dea_distance < abs(diff) * 0.1:
                    info_lines.append("DIFF与DEA粘合 - 变盘临近")
                    info_lines.append("关注: 即将产生金叉或死叉信号")

                # 零轴突破分析 - 重要趋势信号
                if prev_diff <= 0 and diff > 0:
                    info_lines.append("DIFF突破零轴 - 由弱转强")
                    info_lines.append("策略: 重要多头信号，可加仓做多")
                elif prev_diff >= 0 and diff < 0:
                    info_lines.append("DIFF跌破零轴 - 由强转弱")
                    info_lines.append("策略: 重要空头信号，可加仓做空")

                if prev_dea <= 0 and dea > 0:
                    info_lines.append("DEA突破零轴 - 趋势确认转多")
                    info_lines.append("确认: 多头趋势已确立")
                elif prev_dea >= 0 and dea < 0:
                    info_lines.append("DEA跌破零轴 - 趋势确认转空")
                    info_lines.append("确认: 空头趋势已确立")

                # MACD柱状图能量分析
                if abs(macd) > abs(prev_macd) * 2:
                    info_lines.append("MACD能量爆发 - 趋势加速")
                    info_lines.append("警惕: 短期可能过度，注意回调风险")

                # 结合价格位置的综合判断（如果可以获取价格）
                bar = self._manager.get_bar(ix)
                if bar:
                    prev_bar = self._manager.get_bar(prev_ix)
                    if prev_bar:
                        price_change = (bar.close_price - prev_bar.close_price) / prev_bar.close_price * 100

                        # 价格MACD背离初步判断
                        if price_change > 2 and macd_change < 0 and macd > 0:
                            info_lines.append("价格大涨但MACD缩短 - 背离迹象")
                            info_lines.append("警告: 可能形成顶背离，注意风险")
                        elif price_change < -2 and macd_change > 0 and macd < 0:
                            info_lines.append("价格大跌但MACD缩短 - 背离迹象")
                            info_lines.append("机会: 可能形成底背离，关注反转")

            else:
                # 没有前一个数据时的基本判断
                if macd > 0:
                    info_lines.append("MACD红柱 - 多头主导")
                elif macd < 0:
                    info_lines.append("MACD绿柱 - 空头主导")
                else:
                    info_lines.append("MACD零值 - 多空均衡")

                if diff > 0:
                    info_lines.append("零轴上方 - 多头市场")
                elif diff < 0:
                    info_lines.append("零轴下方 - 空头市场")

            return "\n".join(info_lines)

        return f"MACD({self.short_window},{self.long_window},{self.M}) - 数据不足"

    def clear_all(self) -> None:
        """清空所有数据和缓存"""
        self.macd_data.clear()
        self._values_ranges.clear()
        self._needs_recalc = True
        self.start_bull_indices.clear()
        self.end_bull_indices.clear()
        self.start_bear_indices.clear()
        self.end_bear_indices.clear()
        super().clear_all()

    # 配置相关方法
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        config_items = [
            ("short_window", "快速周期", "spinbox", {"min": 5, "max": 50, "value": self.short_window}),
            ("long_window", "慢速周期", "spinbox", {"min": 10, "max": 100, "value": self.long_window}),
            ("M", "信号周期", "spinbox", {"min": 5, "max": 30, "value": self.M}),
            ("scale_factor", "放大因子", "doublespinbox", {"min": 1.0, "max": 1000.0, "step": 10.0, "value": self.scale_factor})
        ]
        return self.create_config_dialog(parent, "MACD配置", config_items)

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置"""
        self.short_window = config.get('short_window', self.short_window)
        self.long_window = config.get('long_window', self.long_window)
        self.M = config.get('M', self.M)
        self.scale_factor = config.get('scale_factor', self.scale_factor)
        
        # 重新初始化
        self.macd_data.clear()
        self._values_ranges.clear()
        self._needs_recalc = True
        self.update()

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'short_window': self.short_window,
            'long_window': self.long_window,
            'M': self.M,
            'scale_factor': self.scale_factor
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'short_window': 12,
            'long_window': 26,
            'M': 9,
            'scale_factor': 100.0
        }

    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return """
参数说明：
• 快速周期: 快速EMA的计算周期(建议12)
• 慢速周期: 慢速EMA的计算周期(建议26)
• 信号周期: MACD信号线的计算周期(建议9)
• 放大因子: 用于放大小数值MACD，便于观察

颜色说明：
• 蓝色线: DIFF线(快慢EMA差值)
• 橙色线: DEA线(DIFF的信号线)
• 红色柱: MACD为正值(多头)
• 绿色柱: MACD为负值(空头)
        """
