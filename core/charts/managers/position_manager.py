#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓管理器
跟踪持仓状态，在图表上绘制持仓线和订单线
"""

import pyqtgraph as pg
from typing import Dict, Optional
from datetime import datetime

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import OrderData, TradeData, PositionData
from vnpy.trader.constant import Direction
from vnpy.trader.event import EVENT_POSITION
from vnpy.trader.ui import QtCore
from vnpy.chart.base import NORMAL_FONT


class PositionManager(QtCore.QObject):
    """持仓管理器 - 跟踪持仓并在图表上可视化"""

    # Qt信号
    position_synced = QtCore.Signal(str, int, float)  # (vt_symbol, position, price)
    position_line_updated = QtCore.Signal(str)  # (vt_symbol)
    order_line_added = QtCore.Signal(str, str)  # (vt_symbol, vt_orderid)
    order_line_removed = QtCore.Signal(str, str)  # (vt_symbol, vt_orderid)

    # 内部信号：用于跨线程更新UI
    _position_event_signal = QtCore.Signal(object)  # PositionData

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """
        初始化持仓管理器

        Args:
            main_engine: vnpy主引擎
            event_engine: vnpy事件引擎
        """
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine

        # 图表引用 {vt_symbol: chart}
        self.charts: Dict[str, any] = {}

        # 持仓线引用 {vt_symbol: {"long": InfiniteLine, "short": InfiniteLine}}
        self.position_lines: Dict[str, Dict[str, pg.InfiniteLine]] = {}

        # 订单线引用 {vt_symbol: {vt_orderid: InfiniteLine}}
        self.order_lines: Dict[str, Dict[str, pg.InfiniteLine]] = {}

        # 持仓数据 {vt_symbol: position}
        self.positions: Dict[str, int] = {}

        # 持仓数据缓存 {vt_symbol: {"long": PositionData, "short": PositionData}}
        self.position_data: Dict[str, Dict[str, PositionData]] = {}

        # 连接内部信号到主线程处理函数
        self._position_event_signal.connect(self._handle_position_event_in_main_thread)

        # 注册持仓事件监听
        self.event_engine.register(EVENT_POSITION, self.process_position_event)

    def register_chart(self, vt_symbol: str, chart) -> None:
        """
        注册图表

        Args:
            vt_symbol: 合约代码
            chart: EnhancedChartWidget实例
        """
        self.charts[vt_symbol] = chart
        self.order_lines[vt_symbol] = {}

    def sync_position_from_gateway(self, vt_symbol: str) -> None:
        """
        从网关同步持仓数据

        Args:
            vt_symbol: 合约代码
        """
        try:
            # 检查合约是否存在
            contract = self.main_engine.get_contract(vt_symbol)
            if not contract:
                print(f"合约 {vt_symbol} 不存在，请先连接网关并订阅合约")
                return

            # 获取所有持仓
            positions = self.main_engine.get_all_positions()

            # 查找该合约的多空持仓
            long_position = None
            short_position = None

            for pos in positions:
                if pos.vt_symbol == vt_symbol:
                    if pos.direction == Direction.LONG:
                        long_position = pos
                    elif pos.direction == Direction.SHORT:
                        short_position = pos

            long_pos = long_position.volume if long_position else 0
            short_pos = short_position.volume if short_position else 0

            # 计算净持仓
            net_pos = long_pos - short_pos

            # 更新持仓
            old_pos = self.positions.get(vt_symbol, 0)
            self.positions[vt_symbol] = net_pos

            # 记录持仓同步信息
            print(f"持仓同步成功: {vt_symbol} 多头:{long_pos}手 空头:{short_pos}手 净持仓:{net_pos}手 (原持仓:{old_pos}手)")

            # 更新多头持仓线
            if long_pos > 0 and long_position:
                self.update_position_line(vt_symbol, long_position.price, Direction.LONG, long_pos)
            else:
                self.remove_position_line(vt_symbol, Direction.LONG)

            # 更新空头持仓线
            if short_pos > 0 and short_position:
                self.update_position_line(vt_symbol, short_position.price, Direction.SHORT, short_pos)
            else:
                self.remove_position_line(vt_symbol, Direction.SHORT)

        except Exception as e:
            print(f"同步持仓失败: {str(e)}")

    def update_position_line(
        self,
        vt_symbol: str,
        price: float,
        direction: Direction,
        volume: int = None
    ) -> None:
        """
        更新持仓线（支持同时显示多空持仓）

        Args:
            vt_symbol: 合约代码
            price: 持仓价格
            direction: 持仓方向
            volume: 持仓数量（可选）
        """
        chart = self.charts.get(vt_symbol)
        if not chart:
            print(f"图表不存在: {vt_symbol}")
            return

        if not hasattr(chart, '_plots') or not chart._plots:
            print(f"图表plots不存在: {vt_symbol}")
            return

        plot = list(chart._plots.values())[0]

        # 根据方向设置不同的颜色和标签
        if direction == Direction.LONG:
            color = (255, 215, 0)  # 金黄色 - 多头
            direction_key = "long"
            label_text = f"多头持仓 @ {price:.1f} ({volume}手)" if volume else f"多头持仓 @ {price:.1f}"
        else:
            color = (138, 43, 226)  # 紫色 - 空头
            direction_key = "short"
            label_text = f"空头持仓 @ {price:.1f} ({volume}手)" if volume else f"空头持仓 @ {price:.1f}"

        # 初始化持仓线字典
        if vt_symbol not in self.position_lines:
            self.position_lines[vt_symbol] = {}

        # 如果已经有该方向的持仓线，先移除
        if direction_key in self.position_lines[vt_symbol]:
            try:
                plot.removeItem(self.position_lines[vt_symbol][direction_key])
            except Exception as e:
                print(f"移除旧持仓线时出错: {str(e)}")

        # 创建水平线
        position_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            label=label_text,
            pen=pg.mkPen(color, width=2, style=QtCore.Qt.DashLine),  # 加粗线条
            labelOpts={
                "color": color,
                "position": 0.15 if direction == Direction.LONG else 0.25,  # 多头在左侧，空头稍微靠右
                "anchors": [(0, 0), (0, 0)]
            }
        )

        # 设置更大的字体
        try:
            from vnpy.chart.base import NORMAL_FONT
            from PySide6.QtGui import QFont

            large_font = QFont(NORMAL_FONT)
            large_font.setPointSize(12)  # 增大字体到12号
            large_font.setBold(True)  # 加粗
            position_line.label.setFont(large_font)
        except Exception as e:
            print(f"设置持仓线字体时出错: {str(e)}")

        # 添加到图表
        try:
            plot.addItem(position_line)
            position_line.setValue(price)

            # 保存引用
            self.position_lines[vt_symbol][direction_key] = position_line
            print(f"成功添加持仓线: {label_text}")
            self.position_line_updated.emit(vt_symbol)

        except Exception as e:
            print(f"添加持仓线到图表时出错: {str(e)}")

    def remove_position_line(self, vt_symbol: str, direction: Direction = None) -> None:
        """
        移除持仓线

        Args:
            vt_symbol: 合约代码
            direction: 持仓方向（如果为None则移除所有持仓线）
        """
        if vt_symbol not in self.position_lines:
            return

        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]

        # 如果指定了方向，只移除该方向的持仓线
        if direction is not None:
            direction_key = "long" if direction == Direction.LONG else "short"
            if direction_key in self.position_lines[vt_symbol]:
                try:
                    plot.removeItem(self.position_lines[vt_symbol][direction_key])
                    del self.position_lines[vt_symbol][direction_key]
                    print(f"移除{direction.value}持仓线: {vt_symbol}")
                except Exception as e:
                    print(f"移除持仓线失败: {str(e)}")
        else:
            # 移除所有方向的持仓线
            for direction_key in list(self.position_lines[vt_symbol].keys()):
                try:
                    plot.removeItem(self.position_lines[vt_symbol][direction_key])
                    print(f"移除{direction_key}持仓线: {vt_symbol}")
                except Exception as e:
                    print(f"移除持仓线失败: {str(e)}")
            # 清空字典
            self.position_lines[vt_symbol] = {}

    def add_order_line(
        self,
        vt_symbol: str,
        vt_orderid: str,
        price: float,
        direction: Direction,
        volume: int = 0
    ) -> None:
        """
        添加订单线

        Args:
            vt_symbol: 合约代码
            vt_orderid: 订单ID
            price: 委托价格
            direction: 委托方向
            volume: 委托数量
        """
        chart = self.charts.get(vt_symbol)
        if not chart:
            return

        if not hasattr(chart, '_plots') or not chart._plots:
            return

        plot = list(chart._plots.values())[0]

        # 设置不同方向的委托线颜色
        if direction == Direction.LONG:
            color = (100, 200, 255)  # 亮蓝色，表示买入委托
            label_text = f"买入委托 @ {price:.1f} ({volume}手)" if volume > 0 else f"买入委托 @ {price:.1f}"
        else:
            color = (255, 150, 180)  # 亮粉色，表示卖出委托
            label_text = f"卖出委托 @ {price:.1f} ({volume}手)" if volume > 0 else f"卖出委托 @ {price:.1f}"

        # 初始化订单线字典
        if vt_symbol not in self.order_lines:
            self.order_lines[vt_symbol] = {}

        # 检查是否已存在相同的委托线（变化检测）
        if vt_orderid in self.order_lines[vt_symbol]:
            existing_line = self.order_lines[vt_symbol][vt_orderid]
            # 检查价格和标签是否相同
            if (hasattr(existing_line, 'value') and
                abs(existing_line.value() - price) < 0.01 and
                hasattr(existing_line, 'label') and
                existing_line.label.format == label_text):
                # 委托线没有变化，直接返回
                return
            # 有变化，先移除旧的委托线
            plot.removeItem(existing_line)

        # 创建水平线
        order_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            label=label_text,
            pen=pg.mkPen(color, width=1.5, style=QtCore.Qt.DotLine),  # 稍微加粗
            labelOpts={
                "color": color,
                "position": 0.85,  # 位置在右侧
                "anchors": [(1, 0), (1, 0)]
            }
        )

        # 设置字体
        try:
            from PySide6.QtGui import QFont

            order_font = QFont(NORMAL_FONT)
            order_font.setPointSize(11)  # 稍大字体
            order_line.label.setFont(order_font)
        except Exception:
            pass

        # 添加到图表
        try:
            plot.addItem(order_line)
            order_line.setValue(price)

            # 保存引用
            self.order_lines[vt_symbol][vt_orderid] = order_line
            print(f"成功添加委托线: {label_text} ({vt_orderid})")
            self.order_line_added.emit(vt_symbol, vt_orderid)

        except Exception as e:
            print(f"添加委托线失败: {str(e)}")

    def remove_order_line(self, vt_symbol: str, vt_orderid: str) -> None:
        """
        移除订单线

        Args:
            vt_symbol: 合约代码
            vt_orderid: 订单ID
        """
        if vt_symbol not in self.order_lines:
            return

        if vt_orderid not in self.order_lines[vt_symbol]:
            return

        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]

        try:
            plot.removeItem(self.order_lines[vt_symbol][vt_orderid])
            del self.order_lines[vt_symbol][vt_orderid]
            print(f"移除委托线: {vt_orderid}")
            self.order_line_removed.emit(vt_symbol, vt_orderid)
        except Exception as e:
            print(f"移除委托线失败: {str(e)}")

    def clear_all_order_lines(self, vt_symbol: str) -> None:
        """
        清除所有订单线

        Args:
            vt_symbol: 合约代码
        """
        if vt_symbol not in self.order_lines:
            return

        for vt_orderid in list(self.order_lines[vt_symbol].keys()):
            self.remove_order_line(vt_symbol, vt_orderid)

    def update_position(self, vt_symbol: str, position: int) -> None:
        """
        更新持仓数量

        Args:
            vt_symbol: 合约代码
            position: 持仓数量
        """
        self.positions[vt_symbol] = position

    def get_position(self, vt_symbol: str) -> int:
        """
        获取净持仓数量

        Args:
            vt_symbol: 合约代码

        Returns:
            净持仓数量（多头为正，空头为负）
        """
        return self.positions.get(vt_symbol, 0)

    def has_long_position(self, vt_symbol: str) -> bool:
        """
        是否有多头持仓

        Args:
            vt_symbol: 合约代码

        Returns:
            是否有多头持仓
        """
        if vt_symbol not in self.position_data:
            return False
        long_pos = self.position_data[vt_symbol].get("long")
        return long_pos is not None and long_pos.volume > 0

    def has_short_position(self, vt_symbol: str) -> bool:
        """
        是否有空头持仓

        Args:
            vt_symbol: 合约代码

        Returns:
            是否有空头持仓
        """
        if vt_symbol not in self.position_data:
            return False
        short_pos = self.position_data[vt_symbol].get("short")
        return short_pos is not None and short_pos.volume > 0

    def get_long_position(self, vt_symbol: str) -> int:
        """
        获取多头持仓数量

        Args:
            vt_symbol: 合约代码

        Returns:
            多头持仓数量
        """
        if vt_symbol not in self.position_data:
            return 0
        long_pos = self.position_data[vt_symbol].get("long")
        return long_pos.volume if long_pos else 0

    def get_short_position(self, vt_symbol: str) -> int:
        """
        获取空头持仓数量

        Args:
            vt_symbol: 合约代码

        Returns:
            空头持仓数量
        """
        if vt_symbol not in self.position_data:
            return 0
        short_pos = self.position_data[vt_symbol].get("short")
        return short_pos.volume if short_pos else 0

    def process_position_event(self, event: Event) -> None:
        """
        处理持仓事件（EVENT_POSITION）

        注意：此方法在vnpy事件线程中调用，不能直接操作UI
        通过信号转发到主线程处理

        Args:
            event: 持仓事件
        """
        position: PositionData = event.data
        vt_symbol = position.vt_symbol

        # 只处理已注册图表的合约
        if vt_symbol not in self.charts:
            return

        # 通过信号转发到主线程处理
        self._position_event_signal.emit(position)

    def _handle_position_event_in_main_thread(self, position: PositionData) -> None:
        """
        在主线程中处理持仓事件（通过信号调用）

        Args:
            position: 持仓数据
        """
        vt_symbol = position.vt_symbol

        # 初始化持仓数据缓存
        if vt_symbol not in self.position_data:
            self.position_data[vt_symbol] = {}

        # 获取旧的持仓数据
        old_long_pos = self.position_data[vt_symbol].get("long")
        old_short_pos = self.position_data[vt_symbol].get("short")

        # 分别缓存多头和空头持仓数据
        if position.direction == Direction.LONG:
            self.position_data[vt_symbol]["long"] = position
        else:
            self.position_data[vt_symbol]["short"] = position

        # 获取多空持仓
        long_pos = self.position_data[vt_symbol].get("long")
        short_pos = self.position_data[vt_symbol].get("short")

        long_volume = long_pos.volume if long_pos else 0
        short_volume = short_pos.volume if short_pos else 0

        # 计算净持仓（多头为正，空头为负）
        net_position = long_volume - short_volume

        # 获取旧的持仓记录
        old_position = self.positions.get(vt_symbol, 0)

        # 检查持仓是否真正发生变化
        old_long_volume = old_long_pos.volume if old_long_pos else 0
        old_short_volume = old_short_pos.volume if old_short_pos else 0
        old_long_price = old_long_pos.price if old_long_pos else 0
        old_short_price = old_short_pos.price if old_short_pos else 0

        long_changed = (long_volume != old_long_volume) or (long_pos and long_pos.price != old_long_price)
        short_changed = (short_volume != old_short_volume) or (short_pos and short_pos.price != old_short_price)

        # 如果持仓没有变化，直接返回
        if not long_changed and not short_changed:
            return

        # 更新持仓记录
        self.positions[vt_symbol] = net_position

        # 打印持仓变化日志（只在真正变化时打印）
        print(f"持仓变化: {vt_symbol} {position.direction.value} "
              f"{position.volume}手 @ {position.price:.1f}，"
              f"多头:{long_volume}手 空头:{short_volume}手 "
              f"净持仓:{net_position}手")

        # 分别更新多头和空头持仓线（只在变化时更新）
        if long_changed:
            if long_volume > 0 and long_pos:
                self.update_position_line(vt_symbol, long_pos.price, Direction.LONG, long_volume)
            else:
                self.remove_position_line(vt_symbol, Direction.LONG)

        if short_changed:
            if short_volume > 0 and short_pos:
                self.update_position_line(vt_symbol, short_pos.price, Direction.SHORT, short_volume)
            else:
                self.remove_position_line(vt_symbol, Direction.SHORT)

        # 发射持仓同步信号（使用净持仓）
        avg_price = position.price
        if net_position > 0 and long_pos:
            avg_price = long_pos.price
        elif net_position < 0 and short_pos:
            avg_price = short_pos.price

        self.position_synced.emit(vt_symbol, net_position, avg_price)

    def cleanup(self, vt_symbol: Optional[str] = None) -> None:
        """
        清理资源

        Args:
            vt_symbol: 合约代码，如果为None则清理所有
        """
        if vt_symbol:
            # 清理指定合约
            self.remove_position_line(vt_symbol)  # 会移除所有方向的持仓线
            self.clear_all_order_lines(vt_symbol)
            self.charts.pop(vt_symbol, None)
            self.order_lines.pop(vt_symbol, None)
            self.positions.pop(vt_symbol, None)
            self.position_data.pop(vt_symbol, None)
            self.position_lines.pop(vt_symbol, None)
        else:
            # 清理所有
            for symbol in list(self.charts.keys()):
                self.cleanup(symbol)

            # 注销事件监听
            self.event_engine.unregister(EVENT_POSITION, self.process_position_event)

            # 断开内部信号连接（避免重复断开引发异常）
            try:
                self._position_event_signal.disconnect()
            except Exception:
                pass  # 如果信号已经断开，忽略异常
