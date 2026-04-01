#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI相对强弱指标
基于vnpy ChartItem实现的RSI技术指标
"""

from typing import Dict, Any, Tuple
import numpy as np
import pyqtgraph as pg

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData
from vnpy.chart.item import ChartItem
from vnpy.chart.manager import BarManager

from .indicator_base import ConfigurableIndicator
from .calculators.rsi_calculator import RSICalculator


class RsiItem(ChartItem, ConfigurableIndicator):
    """
    RSI相对强弱指标
    参考原始代码风格，支持参数配置
    """

    def __init__(self, manager: BarManager, rsi_window: int = 14, 
                 rsi_long_threshold: float = 70, rsi_short_threshold: float = 30):
        """初始化RSI指标"""
        super().__init__(manager)
        
        # 参数设置
        self.rsi_window = rsi_window
        self.rsi_long_threshold = rsi_long_threshold
        self.rsi_short_threshold = rsi_short_threshold
        
        # 颜色配置
        self.white_pen: QtGui.QPen = pg.mkPen(color=(255, 255, 255, 90), width=1)
        self.yellow_pen: QtGui.QPen = pg.mkPen(color=(255, 255, 0), width=2)
        self.gold_pen: QtGui.QPen = pg.mkPen(color=(252, 173, 4), width=5)  # 金色
        self.purple_pen: QtGui.QPen = pg.mkPen(color=(128, 0, 128), width=5)
        
        # 添加新的笔用于超买超卖区域
        self.overbought_pen: QtGui.QPen = pg.mkPen(color=(255, 50, 50), width=3)  # 红色粗线
        self.oversold_pen: QtGui.QPen = pg.mkPen(color=(50, 255, 50), width=3)    # 绿色粗线
        
        # 数据缓存
        self.rsi_data: Dict[int, float] = {}
        
        # 背离数据
        self.start_bull_indices = []
        self.end_bull_indices = []
        self.start_bear_indices = []
        self.end_bear_indices = []

    def add_divergence_pairs(self, rsi_window, bull_divergence_pairs, bear_divergence_pairs):
        """添加背离对"""
        self.rsi_window = rsi_window
        self.start_bull_indices = [pair[1] for pair in bull_divergence_pairs]
        self.end_bull_indices = [pair[0] for pair in bull_divergence_pairs]
        self.start_bear_indices = [pair[1] for pair in bear_divergence_pairs]
        self.end_bear_indices = [pair[0] for pair in bear_divergence_pairs]
        
    def set_thresholds(self, long_threshold: float = 70, short_threshold: float = 30):
        """设置RSI的超买超卖阈值"""
        self.rsi_long_threshold = long_threshold
        self.rsi_short_threshold = short_threshold

    def _ensure_calculated(self) -> None:
        """全量计算 RSI 数据，委托给 RSICalculator"""
        if self.rsi_data:
            return
        bars = self._manager.get_all_bars()
        if not bars or len(bars) < self.rsi_window:
            return
        close_array = np.array([bar.close_price for bar in bars])
        rsi_array = RSICalculator.compute_array(close_array, self.rsi_window)
        for n, value in enumerate(rsi_array):
            if not np.isnan(value):
                self.rsi_data[n] = value

    def get_rsi_value(self, ix: int) -> float:
        """获取RSI值"""
        if ix < 0:
            return 50
        self._ensure_calculated()
        return self.rsi_data.get(ix, 50.0)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """绘制RSI"""
        rsi_value = self.get_rsi_value(ix)
        last_rsi_value = self.get_rsi_value(ix - 1)

        # 创建绘图对象
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)

        # 绘制RSI线
        if not (np.isnan(last_rsi_value) or np.isnan(rsi_value)):
            end_point = QtCore.QPointF(ix, rsi_value)
            start_point = QtCore.QPointF(ix - 1, last_rsi_value)
            
            # 根据RSI值选择合适的笔
            if rsi_value >= self.rsi_long_threshold or last_rsi_value >= self.rsi_long_threshold:
                # 超买区域使用红色粗线
                painter.setPen(self.overbought_pen)
            elif rsi_value <= self.rsi_short_threshold or last_rsi_value <= self.rsi_short_threshold:
                # 超卖区域使用绿色粗线
                painter.setPen(self.oversold_pen)
            else:
                # 正常区域使用标准黄线
                painter.setPen(self.yellow_pen)
                
            painter.drawLine(start_point, end_point)

        # 绘制超买/超卖线
        painter.setPen(self.white_pen)
        ob_end_point = QtCore.QPointF(ix, self.rsi_long_threshold)
        ob_start_point = QtCore.QPointF(ix - 1, self.rsi_long_threshold)
        painter.drawLine(ob_start_point, ob_end_point)
        
        os_end_point = QtCore.QPointF(ix, self.rsi_short_threshold)
        os_start_point = QtCore.QPointF(ix - 1, self.rsi_short_threshold)
        painter.drawLine(os_start_point, os_end_point)

        # 绘制背离线
        if ix in self.start_bull_indices:
            start_index = self.start_bull_indices.index(ix)
            if start_index < len(self.end_bull_indices):
                end_index = self.end_bull_indices[start_index]
                last_rsi_value = self.get_rsi_value(end_index)
                start_point = QtCore.QPointF(ix, rsi_value)
                end_point = QtCore.QPointF(end_index, last_rsi_value)
                painter.setPen(self.purple_pen)
                painter.drawLine(start_point, end_point)

        if ix in self.start_bear_indices:
            start_index = self.start_bear_indices.index(ix)
            if start_index < len(self.end_bear_indices):
                end_index = self.end_bear_indices[start_index]
                last_rsi_value = self.get_rsi_value(end_index)
                start_point = QtCore.QPointF(ix, rsi_value)
                end_point = QtCore.QPointF(end_index, last_rsi_value)
                painter.setPen(self.gold_pen)
                painter.drawLine(start_point, end_point)

        painter.end()
        return picture

    def boundingRect(self) -> QtCore.QRectF:
        """返回边界矩形"""
        rect = QtCore.QRectF(
            0,
            15,
            len(self._bar_picutures),
            85
        )
        return rect

    def get_y_range(self, min_ix: int = None, max_ix: int = None) -> Tuple[float, float]:
        """获取Y轴范围"""
        return (15.0, 85.0)

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前RSI数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1

        # 使用get_rsi_value确保数据被计算（即使指标被隐藏）
        rsi_value = self.get_rsi_value(ix)
        if rsi_value == 50 and ix < self.rsi_window:  # 数据不足
            return {}

        prev_rsi_value = self.get_rsi_value(ix - 1)

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        # 判断超买超卖
        overbought = rsi_value >= self.rsi_long_threshold
        oversold = rsi_value <= self.rsi_short_threshold

        # 判断背离（如果有背离数据）
        divergence = "none"
        if hasattr(self, 'start_bull_indices') and hasattr(self, 'end_bull_indices'):
            if ix in self.start_bull_indices or ix in self.end_bull_indices:
                divergence = "bullish"
        if hasattr(self, 'start_bear_indices') and hasattr(self, 'end_bear_indices'):
            if ix in self.start_bear_indices or ix in self.end_bear_indices:
                if divergence != "bullish":
                    divergence = "bearish"

        return {
            "value": round(rsi_value, 1),
            "previous": round(prev_rsi_value, 1) if prev_rsi_value != 50 else None,
            "trend": "up" if prev_rsi_value != 50 and rsi_value > prev_rsi_value else "down" if prev_rsi_value != 50 and rsi_value < prev_rsi_value else "neutral",
            "overbought": overbought,
            "oversold": oversold,
            "divergence": divergence,
            "current_price": round(current_price, 2),
            "thresholds": {
                "long": self.rsi_long_threshold,
                "short": self.rsi_short_threshold
            }
        }

    def get_info_text(self, ix: int) -> str:
        """获取RSI信息文本，包含数值和交易指导"""
        if ix in self.rsi_data:
            rsi_value = self.rsi_data[ix]

            # 基础信息
            words = [f"RSI ({self.rsi_window}): {rsi_value:.1f}"]

            # 获取前一个数据用于趋势判断
            prev_ix = ix - 1
            if prev_ix in self.rsi_data:
                prev_rsi = self.rsi_data[prev_ix]

                # RSI区间分析 - 针对商品期货优化阈值
                if rsi_value >= 80:
                    words.append("极度超买 - 强烈卖出信号")
                    words.append("风险提示: 短期回调概率极大")
                elif rsi_value >= self.rsi_long_threshold:
                    words.append(f"超买区域 - 谨慎做多")
                    words.append("操作建议: 考虑分批减仓")
                elif rsi_value <= 20:
                    words.append("极度超卖 - 强烈买入信号")
                    words.append("机会提示: 短期反弹概率极大")
                elif rsi_value <= self.rsi_short_threshold:
                    words.append(f"超卖区域 - 关注做多")
                    words.append("操作建议: 可分批建仓")
                elif 45 <= rsi_value <= 55:
                    words.append("中性区域 - 观望为主")
                    words.append("策略: 等待明确突破信号")
                elif rsi_value > 55:
                    words.append("偏强区域 - 多头占优")
                    words.append("策略: 回调做多，注意止盈")
                else:
                    words.append("偏弱区域 - 空头占优")
                    words.append("策略: 反弹做空，注意止损")

                # RSI趋势分析 - 动量变化
                rsi_change = rsi_value - prev_rsi
                if abs(rsi_change) > 5:
                    if rsi_change > 0:
                        words.append("RSI快速上升 - 买盘动能强劲")
                        words.append("趋势: 短期动量加速向上")
                    else:
                        words.append("RSI快速下降 - 卖盘抛压加重")
                        words.append("趋势: 短期动量加速向下")
                elif abs(rsi_change) > 2:
                    if rsi_change > 0:
                        words.append("RSI温和上升 - 买盘稳步增加")
                    else:
                        words.append("RSI温和下降 - 卖盘稳步增加")
                elif abs(rsi_change) < 0.5:
                    words.append("RSI平稳 - 多空力量均衡")
                    words.append("市场状态: 短期震荡整理")

                # 持续性警告 - 背离风险提示
                if rsi_value > 70 and prev_rsi > 70:
                    words.append("持续超买 - 警惕顶背离风险")
                    words.append("风险管理: 严格设置止盈位")
                elif rsi_value < 30 and prev_rsi < 30:
                    words.append("持续超卖 - 关注底背离机会")
                    words.append("机会把握: 等待反转确认信号")

                # 关键位突破分析 - 重要技术位
                if prev_rsi <= 50 and rsi_value > 50:
                    words.append("突破中线(50) - 多头转强信号")
                    words.append("操作: 可尝试做多，止损设在50下方")
                elif prev_rsi >= 50 and rsi_value < 50:
                    words.append("跌破中线(50) - 空头转强信号")
                    words.append("操作: 可尝试做空，止损设在50上方")

                # 超买超卖线突破
                if prev_rsi <= self.rsi_long_threshold and rsi_value > self.rsi_long_threshold:
                    words.append(f"进入超买({self.rsi_long_threshold}) - 开始减仓信号")
                    words.append("时机: 首次进入超买区可持有，深度超买需减仓")
                elif prev_rsi >= self.rsi_short_threshold and rsi_value < self.rsi_short_threshold:
                    words.append(f"进入超卖({self.rsi_short_threshold}) - 开始加仓信号")
                    words.append("时机: 首次进入超卖区可观望，深度超卖可加仓")

                # RSI钝化分析 - 商品期货特有
                if rsi_value > 80:
                    consecutive_count = 1
                    check_ix = prev_ix
                    while check_ix >= 0 and check_ix in self.rsi_data and self.rsi_data[check_ix] > 80:
                        consecutive_count += 1
                        check_ix -= 1
                    if consecutive_count >= 3:
                        words.append(f"RSI高位钝化({consecutive_count}周期) - 强势行情持续")
                        words.append("特殊行情: 强趋势行情，可持有但严控风险")

                elif rsi_value < 20:
                    consecutive_count = 1
                    check_ix = prev_ix
                    while check_ix >= 0 and check_ix in self.rsi_data and self.rsi_data[check_ix] < 20:
                        consecutive_count += 1
                        check_ix -= 1
                    if consecutive_count >= 3:
                        words.append(f"RSI低位钝化({consecutive_count}周期) - 弱势行情持续")
                        words.append("特殊行情: 弱趋势行情，暂不抄底")

                # 背离检测提示
                if ix in self.start_bull_indices:
                    words.append("检测到底背离 - 看涨反转信号")
                    words.append("策略: 等待价格确认后做多")
                if ix in self.start_bear_indices:
                    words.append("检测到顶背离 - 看跌反转信号")
                    words.append("策略: 等待价格确认后做空")

            else:
                # 没有前一个数据时的基本判断
                if rsi_value >= 80:
                    words.append("极度超买 - 高度风险区域")
                elif rsi_value >= 70:
                    words.append("超买区域 - 谨慎做多")
                elif rsi_value <= 20:
                    words.append("极度超卖 - 反弹机会区域")
                elif rsi_value <= 30:
                    words.append("超卖区域 - 关注做多")
                else:
                    words.append("正常区域 - 结合其他指标")

            return "\n".join(words)
        else:
            return f"RSI({self.rsi_window}) - 数据不足"

    def clear_all(self) -> None:
        """清除所有数据"""
        super().clear_all()
        self.rsi_data.clear()
        self._bar_picutures.clear()
        self.update()

    def update_history(self, history) -> None:
        """更新历史数据时清空缓存"""
        self.rsi_data.clear()
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """更新单个K线时清空缓存，触发全量重算"""
        self.rsi_data.clear()
        super().update_bar(bar)

    # 配置相关方法
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        config_items = [
            ("rsi_window", "RSI周期", "spinbox", {"min": 5, "max": 100, "value": self.rsi_window}),
            ("rsi_long_threshold", "超买阈值", "doublespinbox", {"min": 60.0, "max": 90.0, "step": 1.0, "value": self.rsi_long_threshold}),
            ("rsi_short_threshold", "超卖阈值", "doublespinbox", {"min": 10.0, "max": 40.0, "step": 1.0, "value": self.rsi_short_threshold})
        ]
        return self.create_config_dialog(parent, "RSI配置", config_items)

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置"""
        self.rsi_window = config.get('rsi_window', self.rsi_window)
        self.rsi_long_threshold = config.get('rsi_long_threshold', self.rsi_long_threshold)
        self.rsi_short_threshold = config.get('rsi_short_threshold', self.rsi_short_threshold)
        self.rsi_data.clear()
        self.update()

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'rsi_window': self.rsi_window,
            'rsi_long_threshold': self.rsi_long_threshold,
            'rsi_short_threshold': self.rsi_short_threshold
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'rsi_window': 14,
            'rsi_long_threshold': 70.0,
            'rsi_short_threshold': 30.0
        }

    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return """
参数说明：
• RSI周期: 计算RSI的K线数量(建议14)
• 超买阈值: RSI超买线位置(通常70)
• 超卖阈值: RSI超卖线位置(通常30)

颜色说明：
• 黄色: 正常区域RSI线
• 红色: 超买区域RSI线
• 绿色: 超卖区域RSI线
• 白色虚线: 超买超卖参考线
        """
