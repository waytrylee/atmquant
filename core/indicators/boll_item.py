#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带指标 - 完全按照参考代码样式
"""

from typing import Dict, Tuple, Any
import numpy as np
from vnpy.trader.object import BarData
from vnpy.chart.item import CandleItem
from vnpy.trader.ui import QtGui, QtCore, QtWidgets
import pyqtgraph as pg

from .indicator_base import ConfigurableIndicator
from .calculators.boll_calculator import BollCalculator


class BollItem(CandleItem, ConfigurableIndicator):
    """
    布林带指标 - 参考原始代码样式
    """

    def __init__(self, manager, boll_window: int = 20, std_dev: float = 2.0):
        """
        初始化布林带指标
        """
        super().__init__(manager)
        
        # 参数设置
        self.boll_window = boll_window
        self.std_dev = std_dev
        
        # 创建画笔 - 完全按照参考代码
        # 创建代表中轨（移动平均线）的笔，灰白色，加粗
        self.white_pen: QtGui.QPen = pg.mkPen(color=(255, 255, 255), width=3)
        # 创建代表上轨的笔，亮蓝色，粗虚线
        self.upper_pen: QtGui.QPen = pg.mkPen(color=(0, 191, 255), width=2, style=QtCore.Qt.PenStyle.DashLine)
        # 创建代表下轨的笔，亮绿色，粗虚线
        self.lower_pen: QtGui.QPen = pg.mkPen(color=(50, 205, 50), width=2, style=QtCore.Qt.PenStyle.DashLine)
        # 区域填充颜色
        self.fill_brush = pg.mkBrush(color=(100, 149, 237, 35))  # 淡蓝色半透明
        
        # 数据缓存
        self.boll_data = {}

    def _ensure_calculated(self) -> None:
        """全量计算 BOLL 数据（惰性 + 缓存），委托给 BollCalculator"""
        if self.boll_data:
            return
        bars = self._manager.get_all_bars()
        if not bars or len(bars) < self.boll_window:
            return

        close_array = np.array([bar.close_price for bar in bars])
        upper_array, middle_array, lower_array = BollCalculator.compute_arrays(
            close_array, self.boll_window, self.std_dev
        )

        for n in range(len(upper_array)):
            if not np.isnan(upper_array[n]):
                self.boll_data[n] = {
                    "upper": float(upper_array[n]),
                    "middle": float(middle_array[n]),
                    "lower": float(lower_array[n]),
                }

    def get_boll_value(self, ix: int):
        """获取指定索引的 BOLL 值"""
        if ix < self.boll_window - 1:
            return 0
        self._ensure_calculated()
        return self.boll_data.get(ix, 0)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        绘制K线与布林带 - 完全按照参考代码样式
        """
        boll_value = self.get_boll_value(ix)
        last_boll_value = self.get_boll_value(ix - 1)

        # Create objects
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)

        if last_boll_value == 0:
            # 如果没有前一个值，不绘制任何内容
            pass
        else:
            # 填充上下轨之间的区域
            path = QtGui.QPainterPath()
            path.moveTo(ix - 1, last_boll_value["upper"])
            path.lineTo(ix, boll_value["upper"])
            path.lineTo(ix, boll_value["lower"])
            path.lineTo(ix - 1, last_boll_value["lower"])
            path.closeSubpath()
            painter.setBrush(self.fill_brush)
            painter.setPen(pg.mkPen(None))  # 无边框
            painter.drawPath(path)
            
            # 绘制上轨线
            start_point = QtCore.QPointF(ix - 1, last_boll_value["upper"])
            end_point = QtCore.QPointF(ix, boll_value["upper"])
            painter.setPen(self.upper_pen)
            painter.drawLine(start_point, end_point)

            # 绘制中轨线（注释掉，和参考代码一致）
            # start_point = QtCore.QPointF(ix - 1, last_boll_value["middle"])
            # end_point = QtCore.QPointF(ix, boll_value["middle"])
            # painter.setPen(self.white_pen)
            # painter.drawLine(start_point, end_point)

            # 绘制下轨线
            start_point = QtCore.QPointF(ix - 1, last_boll_value["lower"])
            end_point = QtCore.QPointF(ix, boll_value["lower"])
            painter.setPen(self.lower_pen)
            painter.drawLine(start_point, end_point)

        # Finish
        painter.end()
        return picture

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前布林带数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1

        # 使用get_boll_value确保数据被计算（即使指标被隐藏）
        boll_value = self.get_boll_value(ix)
        if boll_value == 0:
            return {}

        # 获取前一个数据
        prev_boll_value = self.get_boll_value(ix - 1)
        if prev_boll_value == 0:
            prev_boll_value = None

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        upper = boll_value['upper']
        middle = boll_value['middle']
        lower = boll_value['lower']

        # 计算布林带宽度
        width = upper - lower

        # 判断挤压状态
        squeeze = False
        if prev_boll_value:
            prev_width = prev_boll_value['upper'] - prev_boll_value['lower']
            if width < prev_width * 0.8:
                squeeze = True

        return {
            "upper": round(upper, 2),
            "middle": round(middle, 2),
            "lower": round(lower, 2),
            "previous_upper": round(prev_boll_value['upper'], 2) if prev_boll_value else None,
            "previous_middle": round(prev_boll_value['middle'], 2) if prev_boll_value else None,
            "previous_lower": round(prev_boll_value['lower'], 2) if prev_boll_value else None,
            "width": round(width, 2),
            "squeeze": squeeze,
            "current_price": round(current_price, 2),
            "parameters": {
                "window": self.boll_window,
                "std_dev": self.std_dev
            }
        }

    def get_info_text(self, ix: int) -> str:
        """获取布林带信息文本，包含数值和交易指导"""
        if ix in self.boll_data:
            boll_value = self.boll_data[ix]
            info_lines = []

            # 基础信息
            info_lines.append(f"BOLL({self.boll_window},{self.std_dev:.1f})")
            info_lines.append(f"上轨: {boll_value['upper']:.2f}")
            info_lines.append(f"中轨: {boll_value['middle']:.2f}")
            info_lines.append(f"下轨: {boll_value['lower']:.2f}")

            # 获取当前价格
            bar = self._manager.get_bar(ix)
            if not bar:
                return "\n".join(info_lines)

            price = bar.close_price
            upper = boll_value['upper']
            lower = boll_value['lower']
            middle = boll_value['middle']
            width = upper - lower

            # 获取前一个数据用于趋势分析
            prev_ix = ix - 1
            prev_price = None
            prev_width = None
            prev_boll = None

            if prev_ix >= 0 and prev_ix in self.boll_data:
                prev_bar = self._manager.get_bar(prev_ix)
                if prev_bar:
                    prev_price = prev_bar.close_price
                prev_boll = self.boll_data[prev_ix]
                prev_width = prev_boll['upper'] - prev_boll['lower']

            # 计算价格在布林带中的位置百分比
            bb_position = (price - lower) / width if width > 0 else 0.5
            info_lines.append(f"位置: {bb_position*100:.1f}% (0%=下轨, 100%=上轨)")

            # 价格位置分析 - 针对商品期货优化
            if price > upper:
                deviation = (price - upper) / width * 100
                info_lines.append(f"突破上轨 - 强势超买 (+{deviation:.1f}%)")
                if deviation > 20:
                    info_lines.append("极度突破 - 警惕短期回调风险")
                else:
                    info_lines.append("策略: 强势突破可持有，设止损在上轨")
            elif price < lower:
                deviation = (lower - price) / width * 100
                info_lines.append(f"跌破下轨 - 弱势超卖 (-{deviation:.1f}%)")
                if deviation > 20:
                    info_lines.append("极度突破 - 关注短期反弹机会")
                else:
                    info_lines.append("策略: 弱势突破可观望，等反弹确认")
            elif bb_position > 0.8:
                info_lines.append("接近上轨 - 偏强区域")
                info_lines.append("操作: 准备减仓或设移动止盈")
            elif bb_position < 0.2:
                info_lines.append("接近下轨 - 偏弱区域")
                info_lines.append("操作: 准备加仓或等反弹信号")
            elif 0.4 <= bb_position <= 0.6:
                info_lines.append("中轨附近 - 关键位置")
                info_lines.append("观察: 突破中轨方向决定后续操作")

            # 价格与中轨关系分析
            if prev_price and prev_boll:
                middle_cross = False

                if prev_price <= prev_boll['middle'] and price > middle:
                    info_lines.append("突破中轨 - 转强信号")
                    info_lines.append("策略: 可尝试做多，止损设在中轨下方")
                    middle_cross = True
                elif prev_price >= prev_boll['middle'] and price < middle:
                    info_lines.append("跌破中轨 - 转弱信号")
                    info_lines.append("策略: 可尝试做空，止损设在中轨上方")
                    middle_cross = True

                # 价格变化速度分析
                if not middle_cross:
                    price_change = abs(price - prev_price)
                    if price_change > width * 0.15:
                        if price > prev_price:
                            info_lines.append("价格急速上涨 - 动能强劲")
                            info_lines.append("警惕: 快速上涨后易出现调整")
                        else:
                            info_lines.append("价格急速下跌 - 抛压沉重")
                            info_lines.append("警惕: 快速下跌后易出现反弹")

            # 布林带宽度分析 - 波动性指标
            width_change = None
            if prev_width and prev_width > 0:
                width_change = (width - prev_width) / prev_width * 100

                if width_change > 8:
                    info_lines.append(f"急速扩张 (+{width_change:.1f}%) - 高波动来临")
                    info_lines.append("市场特征: 趋势行情启动，波动加剧")
                    info_lines.append("策略: 顺势操作，扩大止损空间")
                elif width_change > 3:
                    info_lines.append(f"温和扩张 (+{width_change:.1f}%) - 波动增加")
                    info_lines.append("市场特征: 行情开始活跃")
                    info_lines.append("策略: 关注方向选择，准备顺势")
                elif width_change < -8:
                    info_lines.append(f"急速收缩 ({width_change:.1f}%) - 波动骤减")
                    info_lines.append("市场特征: 酝酿重大变盘")
                    info_lines.append("策略: 控制仓位，等待突破")
                elif width_change < -3:
                    info_lines.append(f"温和收缩 ({width_change:.1f}%) - 整理阶段")
                    info_lines.append("市场特征: 进入整理期")
                    info_lines.append("策略: 区间操作为主")
                else:
                    info_lines.append(f"稳定 ({width_change:+.1f}%) - 波动持平")

            # 布林带宽度比率分析 - 绝对波动水平
            width_ratio = width / middle * 100 if middle > 0 else 0

            if width_ratio < 2:
                info_lines.append(f"极度收敛 (宽度比{width_ratio:.1f}%)")
                info_lines.append("重要信号: 重大变盘在即")
                info_lines.append("操作: 准备捕捉突破，设双向止损")
            elif width_ratio < 4:
                info_lines.append(f"收敛中 (宽度比{width_ratio:.1f}%)")
                info_lines.append("市场状态: 震荡整理，等待突破")
            elif width_ratio > 15:
                info_lines.append(f"极度发散 (宽度比{width_ratio:.1f}%)")
                info_lines.append("警惕信号: 波动过度，趋势末期")
                info_lines.append("操作: 谨慎追高杀跌，准备反转")
            elif width_ratio > 10:
                info_lines.append(f"发散中 (宽度比{width_ratio:.1f}%)")
                info_lines.append("市场状态: 趋势行情，波动较大")

            # 布林带上下轨突破分析
            if prev_price and prev_boll:
                # 上轨突破
                if prev_price <= prev_boll['upper'] and price > upper:
                    if width_change and width_change > 5:
                        info_lines.append("上轨突破+扩张 - 强势突破有效")
                        info_lines.append("策略: 可追涨，止损设在布林带中轨")
                    else:
                        info_lines.append("上轨突破+收缩 - 假突破可能")
                        info_lines.append("策略: 谨慎追涨，等待确认")

                # 下轨突破
                elif prev_price >= prev_boll['lower'] and price < lower:
                    if width_change and width_change > 5:
                        info_lines.append("下轨突破+扩张 - 弱势突破有效")
                        info_lines.append("策略: 可追跌，止损设在布林带中轨")
                    else:
                        info_lines.append("下轨突破+收缩 - 假突破可能")
                        info_lines.append("策略: 谨慎追跌，等待确认")

            # 经典布林带策略提示
            if bb_position > 0.8 and width_change and width_change > 5:
                info_lines.append("经典策略: 布林带开口+接近上轨")
                info_lines.append("操作: 强势行情，持有多单，移动止盈")
            elif bb_position < 0.2 and width_change and width_change > 5:
                info_lines.append("经典策略: 布林带开口+接近下轨")
                info_lines.append("操作: 弱势行情，持有空单，移动止盈")
            elif 0.3 <= bb_position <= 0.7 and width_ratio < 3:
                info_lines.append("经典策略: 布林带收口+中轨附近")
                info_lines.append("操作: 震荡行情，高抛低吸，突破追单")

            # 布林带压力支撑分析
            distance_to_upper = (upper - price) / price * 100
            distance_to_lower = (price - lower) / price * 100
            distance_to_middle = abs(price - middle) / price * 100

            if distance_to_middle < 0.5:
                info_lines.append(f"紧贴中轨 ({distance_to_middle:.2f}%) - 方向待定")
                info_lines.append("关键位: 中轨突破决定短期方向")
            elif price > middle:
                info_lines.append(f"上方空间: {distance_to_upper:.1f}% 至上轨")
                if distance_to_upper < 1:
                    info_lines.append("提示: 接近上轨阻力，注意回落")
            else:
                info_lines.append(f"下方空间: {distance_to_lower:.1f}% 至下轨")
                if distance_to_lower < 1:
                    info_lines.append("提示: 接近下轨支撑，注意反弹")

            return "\n".join(info_lines)
        else:
            return f"BOLL({self.boll_window}) - 数据不足"

    def update_history(self, history) -> None:
        """重写update_history，清除缓存触发重算"""
        self.boll_data.clear()
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """重写update_bar，清除缓存让下次访问触发重算"""
        self.boll_data.clear()
        super().update_bar(bar)

    def clear_all(self) -> None:
        """清除所有数据"""
        super().clear_all()
        self.boll_data.clear()
        self._bar_picutures.clear()
        self.update()

    # ConfigurableIndicator接口实现
    def get_config_params(self) -> Dict:
        """返回可配置参数"""
        return {
            'boll_window': {
                'name': '布林带周期',
                'type': 'int',
                'value': self.boll_window,
                'min': 5,
                'max': 200,
                'step': 1
            },
            'std_dev': {
                'name': '标准差倍数',
                'type': 'float',
                'value': self.std_dev,
                'min': 0.5,
                'max': 3.0,
                'step': 0.1
            }
        }

    def update_config(self, config: Dict) -> None:
        """更新配置"""
        if 'boll_window' in config:
            self.boll_window = config['boll_window']
        if 'std_dev' in config:
            self.std_dev = config['std_dev']
        
        # 清空缓存，重新计算
        self.boll_data.clear()
        self.clear_all()
    
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        config_items = [
            ("boll_window", "布林带周期", "spinbox", {"min": 5, "max": 200, "value": self.boll_window}),
            ("std_dev", "标准差倍数", "doublespinbox", {"min": 0.5, "max": 3.0, "step": 0.1, "value": self.std_dev})
        ]
        
        return self.create_config_dialog(parent, "布林带配置", config_items)
    
    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return "布林带参数说明：\n• 周期越大，布林带越平滑\n• 标准差倍数越大，布林带越宽"
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置"""
        if 'boll_window' in config:
            self.boll_window = config['boll_window']
        if 'std_dev' in config:
            self.std_dev = config['std_dev']
        
        # 清空缓存，重新计算
        self.boll_data.clear()
        self.clear_all()
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'boll_window': self.boll_window,
            'std_dev': self.std_dev
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'boll_window': 20,
            'std_dev': 2.0
        }