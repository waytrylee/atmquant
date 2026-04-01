#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风控监控器
监控tick数据触发止损/止盈和价格预警
"""

import pyqtgraph as pg
from typing import Dict, List, Optional
from datetime import datetime

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import TickData
from vnpy.trader.constant import Direction
from vnpy.trader.ui import QtCore
from vnpy.trader.event import EVENT_TICK
from vnpy.chart.base import NORMAL_FONT

from core.logging.alert_manager import alert_manager


class RiskMonitor(QtCore.QObject):
    """风控监控器 - 监控止损止盈和价格预警"""

    # Qt信号
    stop_loss_triggered = QtCore.Signal(str, float)  # (vt_symbol, price)
    take_profit_triggered = QtCore.Signal(str, float)  # (vt_symbol, price)
    price_alert_triggered = QtCore.Signal(str, float)  # (vt_symbol, price)
    stop_line_updated = QtCore.Signal(str)  # (vt_symbol)

    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        trading_manager,  # TradingManager
        position_manager  # PositionManager
    ):
        """
        初始化风控监控器

        Args:
            main_engine: vnpy主引擎
            event_engine: vnpy事件引擎
            trading_manager: 交易管理器
            position_manager: 持仓管理器
        """
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.trading_manager = trading_manager
        self.position_manager = position_manager

        # 图表引用 {vt_symbol: chart}
        self.charts: Dict[str, any] = {}

        # 止损止盈设置 {vt_symbol: config}
        self.stop_loss_config: Dict[str, Dict] = {}
        self.take_profit_config: Dict[str, Dict] = {}

        # 价格预警列表 {vt_symbol: [alerts]}
        self.price_alerts: Dict[str, List[Dict]] = {}

        # 风控线引用
        self.stop_loss_lines: Dict[str, pg.InfiniteLine] = {}
        self.take_profit_lines: Dict[str, pg.InfiniteLine] = {}
        self.alert_lines: Dict[str, Dict[str, pg.InfiniteLine]] = {}  # {vt_symbol: {alert_id: line}}

        # 上一个tick {vt_symbol: TickData}
        self.last_ticks: Dict[str, TickData] = {}

        # 注册tick事件
        self.event_engine.register(EVENT_TICK, self.process_tick_event)

    def register_chart(self, vt_symbol: str, chart) -> None:
        """
        注册图表

        Args:
            vt_symbol: 合约代码
            chart: EnhancedChartWidget实例
        """
        self.charts[vt_symbol] = chart
        self.price_alerts[vt_symbol] = []
        self.alert_lines[vt_symbol] = {}

    def set_stop_loss(
        self,
        vt_symbol: str,
        price: float,
        direction: Direction,
        enabled: bool
    ) -> None:
        """
        设置止损

        Args:
            vt_symbol: 合约代码
            price: 止损价格
            direction: 持仓方向
            enabled: 是否启用
        """
        self.stop_loss_config[vt_symbol] = {
            "price": price,
            "direction": direction,
            "enabled": enabled
        }

        if enabled and price > 0:
            self.add_stop_loss_line(vt_symbol, price)
        else:
            self.remove_stop_loss_line(vt_symbol)

        print(f"设置止损: {vt_symbol} - {'启用' if enabled else '禁用'} @ {price}")

    def set_take_profit(
        self,
        vt_symbol: str,
        price: float,
        direction: Direction,
        enabled: bool
    ) -> None:
        """
        设置止盈

        Args:
            vt_symbol: 合约代码
            price: 止盈价格
            direction: 持仓方向
            enabled: 是否启用
        """
        self.take_profit_config[vt_symbol] = {
            "price": price,
            "direction": direction,
            "enabled": enabled
        }

        if enabled and price > 0:
            self.add_take_profit_line(vt_symbol, price)
        else:
            self.remove_take_profit_line(vt_symbol)

        print(f"设置止盈: {vt_symbol} - {'启用' if enabled else '禁用'} @ {price}")

    def add_price_alert(self, vt_symbol: str, price: float) -> str:
        """
        添加价格预警

        Args:
            vt_symbol: 合约代码
            price: 预警价格

        Returns:
            alert_id: 预警ID
        """
        # 生成预警ID
        alert_id = f"alert_{vt_symbol}_{int(datetime.now().timestamp() * 1000)}"

        # 添加到预警列表
        if vt_symbol not in self.price_alerts:
            self.price_alerts[vt_symbol] = []

        self.price_alerts[vt_symbol].append({
            "id": alert_id,
            "price": price,
            "triggered": False
        })

        # 添加预警线
        self.add_price_alert_line(vt_symbol, alert_id, price)

        print(f"添加价格预警: {vt_symbol} @ {price}")
        return alert_id

    def process_tick_event(self, event: Event) -> None:
        """
        处理tick事件

        Args:
            event: tick事件
        """
        tick: TickData = event.data
        vt_symbol = tick.vt_symbol

        # 检查止损止盈
        self.check_stop_conditions(tick)

        # 检查价格预警
        self.check_price_alerts(tick)

        # 保存tick
        self.last_ticks[vt_symbol] = tick

    def check_stop_conditions(self, tick: TickData) -> None:
        """
        检查止损止盈条件

        Args:
            tick: tick数据
        """
        vt_symbol = tick.vt_symbol
        position = self.position_manager.get_position(vt_symbol)

        if position == 0:  # 没有持仓，不检查
            return

        # 检查止损
        if vt_symbol in self.stop_loss_config:
            config = self.stop_loss_config[vt_symbol]
            if config["enabled"] and config["price"] > 0:
                # 多头止损 - 价格跌破止损线
                if position > 0 and tick.last_price <= config["price"]:
                    print(f"触发多头止损: 当前价格 {tick.last_price} <= 止损价格 {config['price']}")
                    self.trading_manager.sell(vt_symbol, tick.last_price, abs(position))
                    alert_manager.send_alert(
                        content=f"触发多头止损: 价格 {tick.last_price}, 平仓 {position}手",
                        symbol=vt_symbol,
                        force_send=True
                    )
                    self.stop_loss_triggered.emit(vt_symbol, tick.last_price)
                    self.reset_stop_settings(vt_symbol)
                    return

                # 空头止损 - 价格涨破止损线
                elif position < 0 and tick.last_price >= config["price"]:
                    print(f"触发空头止损: 当前价格 {tick.last_price} >= 止损价格 {config['price']}")
                    self.trading_manager.cover(vt_symbol, tick.last_price, abs(position))
                    alert_manager.send_alert(
                        content=f"触发空头止损: 价格 {tick.last_price}, 平仓 {abs(position)}手",
                        symbol=vt_symbol,
                        force_send=True
                    )
                    self.stop_loss_triggered.emit(vt_symbol, tick.last_price)
                    self.reset_stop_settings(vt_symbol)
                    return

        # 检查止盈
        if vt_symbol in self.take_profit_config:
            config = self.take_profit_config[vt_symbol]
            if config["enabled"] and config["price"] > 0:
                # 多头止盈 - 价格涨破止盈线
                if position > 0 and tick.last_price >= config["price"]:
                    print(f"触发多头止盈: 当前价格 {tick.last_price} >= 止盈价格 {config['price']}")
                    self.trading_manager.sell(vt_symbol, tick.last_price, abs(position))
                    alert_manager.send_alert(
                        content=f"触发多头止盈: 价格 {tick.last_price}, 平仓 {position}手",
                        symbol=vt_symbol,
                        force_send=True
                    )
                    self.take_profit_triggered.emit(vt_symbol, tick.last_price)
                    self.reset_stop_settings(vt_symbol)
                    return

                # 空头止盈 - 价格跌破止盈线
                elif position < 0 and tick.last_price <= config["price"]:
                    print(f"触发空头止盈: 当前价格 {tick.last_price} <= 止盈价格 {config['price']}")
                    self.trading_manager.cover(vt_symbol, tick.last_price, abs(position))
                    alert_manager.send_alert(
                        content=f"触发空头止盈: 价格 {tick.last_price}, 平仓 {abs(position)}手",
                        symbol=vt_symbol,
                        force_send=True
                    )
                    self.take_profit_triggered.emit(vt_symbol, tick.last_price)
                    self.reset_stop_settings(vt_symbol)
                    return

    def check_price_alerts(self, tick: TickData) -> None:
        """
        检查价格预警

        Args:
            tick: tick数据
        """
        vt_symbol = tick.vt_symbol

        if vt_symbol not in self.price_alerts:
            return

        # 获取上一个价格
        prev_price = self.last_ticks[vt_symbol].last_price if vt_symbol in self.last_ticks else tick.last_price
        curr_price = tick.last_price

        # 检查所有预警
        for alert in self.price_alerts[vt_symbol][:]:  # 复制列表以便安全删除
            if alert["triggered"]:
                continue

            price = alert["price"]

            # 价格穿过预警线触发预警
            if (prev_price < price and curr_price >= price) or (prev_price > price and curr_price <= price):
                alert["triggered"] = True
                print(f"价格预警触发: {price}, 当前价格: {curr_price}")
                alert_manager.send_alert(
                    content=f"价格预警触发: {price}, 当前价格: {curr_price}",
                    symbol=vt_symbol,
                    force_send=True
                )

                # 移除预警线
                self.remove_price_alert_line(vt_symbol, alert["id"])

                # 从预警列表中移除
                self.price_alerts[vt_symbol].remove(alert)
                self.price_alert_triggered.emit(vt_symbol, price)

    def reset_stop_settings(self, vt_symbol: str) -> None:
        """
        重置止损止盈设置

        Args:
            vt_symbol: 合约代码
        """
        # 清空配置
        self.stop_loss_config.pop(vt_symbol, None)
        self.take_profit_config.pop(vt_symbol, None)

        # 移除风控线
        self.remove_stop_loss_line(vt_symbol)
        self.remove_take_profit_line(vt_symbol)

        print(f"已重置止损止盈设置: {vt_symbol}")

    def add_stop_loss_line(self, vt_symbol: str, price: float) -> None:
        """添加止损线"""
        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]

        # 如果已有止损线，先移除
        if vt_symbol in self.stop_loss_lines:
            plot.removeItem(self.stop_loss_lines[vt_symbol])

        # 止损线 - 亮绿色虚线
        color = (0, 255, 0)
        label_text = f"止损 @ {price:.1f}"

        stop_loss_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            label=label_text,
            pen=pg.mkPen(color, width=1, style=QtCore.Qt.DashLine),
            labelOpts={
                "color": color,
                "position": 0.95,
                "anchors": [(1, 1), (1, 1)]
            }
        )

        # 设置与持仓线相同的字体大小
        try:
            from PySide6.QtGui import QFont
            large_font = QFont(NORMAL_FONT)
            large_font.setPointSize(12)  # 增大字体到12号
            large_font.setBold(True)  # 加粗
            stop_loss_line.label.setFont(large_font)
        except Exception as e:
            print(f"设置止损线字体时出错: {str(e)}")

        plot.addItem(stop_loss_line)
        stop_loss_line.setValue(price)
        self.stop_loss_lines[vt_symbol] = stop_loss_line
        self.stop_line_updated.emit(vt_symbol)

    def remove_stop_loss_line(self, vt_symbol: str) -> None:
        """移除止损线"""
        if vt_symbol not in self.stop_loss_lines:
            return

        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]
        plot.removeItem(self.stop_loss_lines[vt_symbol])
        del self.stop_loss_lines[vt_symbol]

    def add_take_profit_line(self, vt_symbol: str, price: float) -> None:
        """添加止盈线"""
        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]

        # 如果已有止盈线，先移除
        if vt_symbol in self.take_profit_lines:
            plot.removeItem(self.take_profit_lines[vt_symbol])

        # 止盈线 - 番茄红色虚线
        color = (255, 99, 71)
        label_text = f"止盈 @ {price:.1f}"

        take_profit_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            label=label_text,
            pen=pg.mkPen(color, width=1, style=QtCore.Qt.DashLine),
            labelOpts={
                "color": color,
                "position": 0.95,
                "anchors": [(1, 1), (1, 1)]
            }
        )

        # 设置与持仓线相同的字体大小
        try:
            from PySide6.QtGui import QFont
            large_font = QFont(NORMAL_FONT)
            large_font.setPointSize(12)  # 增大字体到12号
            large_font.setBold(True)  # 加粗
            take_profit_line.label.setFont(large_font)
        except Exception as e:
            print(f"设置止盈线字体时出错: {str(e)}")

        plot.addItem(take_profit_line)
        take_profit_line.setValue(price)
        self.take_profit_lines[vt_symbol] = take_profit_line
        self.stop_line_updated.emit(vt_symbol)

    def remove_take_profit_line(self, vt_symbol: str) -> None:
        """移除止盈线"""
        if vt_symbol not in self.take_profit_lines:
            return

        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]
        plot.removeItem(self.take_profit_lines[vt_symbol])
        del self.take_profit_lines[vt_symbol]

    def add_price_alert_line(self, vt_symbol: str, alert_id: str, price: float) -> None:
        """添加价格预警线"""
        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]

        # 预警线 - 橙色虚线
        color = (255, 140, 0)
        label_text = f"预警 @ {price:.1f}"

        alert_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            label=label_text,
            pen=pg.mkPen(color, width=1, style=QtCore.Qt.DashLine),
            labelOpts={
                "color": color,
                "position": 0.5,
                "anchors": [(0.5, 0.5), (0.5, 0.5)]
            }
        )

        # 设置与持仓线相同的字体大小
        try:
            from PySide6.QtGui import QFont
            large_font = QFont(NORMAL_FONT)
            large_font.setPointSize(12)  # 增大字体到12号
            large_font.setBold(True)  # 加粗
            alert_line.label.setFont(large_font)
        except Exception as e:
            print(f"设置预警线字体时出错: {str(e)}")

        plot.addItem(alert_line)
        alert_line.setValue(price)

        if vt_symbol not in self.alert_lines:
            self.alert_lines[vt_symbol] = {}
        self.alert_lines[vt_symbol][alert_id] = alert_line

    def remove_price_alert_line(self, vt_symbol: str, alert_id: str) -> None:
        """移除价格预警线"""
        if vt_symbol not in self.alert_lines:
            return

        if alert_id not in self.alert_lines[vt_symbol]:
            return

        chart = self.charts.get(vt_symbol)
        if not chart or not hasattr(chart, '_plots'):
            return

        plot = list(chart._plots.values())[0]
        plot.removeItem(self.alert_lines[vt_symbol][alert_id])
        del self.alert_lines[vt_symbol][alert_id]

    def cleanup(self, vt_symbol: Optional[str] = None) -> None:
        """
        清理资源

        Args:
            vt_symbol: 合约代码，如果为None则清理所有
        """
        if vt_symbol:
            # 清理指定合约
            self.remove_stop_loss_line(vt_symbol)
            self.remove_take_profit_line(vt_symbol)

            if vt_symbol in self.alert_lines:
                for alert_id in list(self.alert_lines[vt_symbol].keys()):
                    self.remove_price_alert_line(vt_symbol, alert_id)

            self.charts.pop(vt_symbol, None)
            self.stop_loss_config.pop(vt_symbol, None)
            self.take_profit_config.pop(vt_symbol, None)
            self.price_alerts.pop(vt_symbol, None)
            self.alert_lines.pop(vt_symbol, None)
            self.last_ticks.pop(vt_symbol, None)
        else:
            # 清理所有
            for symbol in list(self.charts.keys()):
                self.cleanup(symbol)

            # 注销事件监听
            self.event_engine.unregister(EVENT_TICK, self.process_tick_event)
