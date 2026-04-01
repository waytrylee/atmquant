#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易管理器
通过MainEngine执行交易操作，跟踪订单状态
"""

from typing import Dict, List, Optional
from datetime import datetime

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import OrderData, TradeData, OrderRequest
from vnpy.trader.constant import Direction, Offset, OrderType, Status
from vnpy.trader.event import EVENT_ORDER, EVENT_TRADE
from vnpy.trader.ui import QtCore


class TradingManager(QtCore.QObject):
    """交易管理器 - 处理交易操作和订单跟踪"""

    # Qt信号
    order_submitted = QtCore.Signal(str, str)  # (vt_symbol, vt_orderid)
    order_updated = QtCore.Signal(str, object)  # (vt_symbol, OrderData)
    trade_received = QtCore.Signal(str, object)  # (vt_symbol, TradeData)
    position_updated = QtCore.Signal(str, int)  # (vt_symbol, position)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """
        初始化交易管理器

        Args:
            main_engine: vnpy主引擎
            event_engine: vnpy事件引擎
        """
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine

        # 订单跟踪 {vt_symbol: {vt_orderid: OrderData}}
        self.active_orders: Dict[str, Dict[str, OrderData]] = {}

        # 持仓跟踪 {vt_symbol: position}
        self.positions: Dict[str, int] = {}

        # 注册事件监听
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

    def buy(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        买入开仓

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型（限价/市价）

        Returns:
            vt_orderid: 订单ID，失败返回None
        """
        return self._send_order(
            vt_symbol=vt_symbol,
            direction=Direction.LONG,
            offset=Offset.OPEN,
            price=price,
            volume=volume,
            order_type=order_type
        )

    def sell(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        卖出平仓（平多）

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID
        """
        return self._send_order(
            vt_symbol=vt_symbol,
            direction=Direction.SHORT,
            offset=Offset.CLOSE,
            price=price,
            volume=volume,
            order_type=order_type
        )

    def short(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        卖出开仓

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID
        """
        return self._send_order(
            vt_symbol=vt_symbol,
            direction=Direction.SHORT,
            offset=Offset.OPEN,
            price=price,
            volume=volume,
            order_type=order_type
        )

    def cover(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        买入平仓（平空）

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID
        """
        return self._send_order(
            vt_symbol=vt_symbol,
            direction=Direction.LONG,
            offset=Offset.CLOSE,
            price=price,
            volume=volume,
            order_type=order_type
        )

    def close_long(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        平多头仓位

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID
        """
        return self.sell(vt_symbol, price, volume, order_type)

    def close_short(
        self,
        vt_symbol: str,
        price: float,
        volume: int,
        order_type: OrderType = OrderType.LIMIT
    ) -> Optional[str]:
        """
        平空头仓位

        Args:
            vt_symbol: 合约代码
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID
        """
        return self.cover(vt_symbol, price, volume, order_type)

    def close_all_positions(
        self,
        vt_symbol: str,
        price: float,
        order_type: OrderType = OrderType.LIMIT
    ) -> List[str]:
        """
        一键平仓所有持仓（同时平掉多空仓位）

        Args:
            vt_symbol: 合约代码
            price: 价格
            order_type: 订单类型

        Returns:
            订单ID列表
        """
        vt_orderids = []

        # 从MainEngine获取实际持仓数据
        positions = self.main_engine.get_all_positions()

        long_volume = 0
        short_volume = 0

        for pos in positions:
            if pos.vt_symbol == vt_symbol:
                if pos.direction == Direction.LONG:
                    long_volume = pos.volume
                elif pos.direction == Direction.SHORT:
                    short_volume = pos.volume

        # 平多头持仓
        if long_volume > 0:
            vt_orderid = self.sell(vt_symbol, price, long_volume, order_type)
            if vt_orderid:
                vt_orderids.append(vt_orderid)
                print(f"平多头持仓: {long_volume}手")

        # 平空头持仓
        if short_volume > 0:
            vt_orderid = self.cover(vt_symbol, price, short_volume, order_type)
            if vt_orderid:
                vt_orderids.append(vt_orderid)
                print(f"平空头持仓: {short_volume}手")

        if not vt_orderids:
            print(f"{vt_symbol} 当前无持仓")

        return vt_orderids

    def cancel_order(self, vt_orderid: str) -> bool:
        """
        撤销订单

        Args:
            vt_orderid: 订单ID

        Returns:
            是否成功发送撤单请求
        """
        # 从active_orders中查找订单
        for vt_symbol, orders in self.active_orders.items():
            if vt_orderid in orders:
                order = orders[vt_orderid]
                # 创建撤单请求
                cancel_req = order.create_cancel_request()
                # 发送撤单请求
                self.main_engine.cancel_order(cancel_req, order.gateway_name)
                return True

        print(f"订单 {vt_orderid} 未找到")
        return False

    def cancel_all_orders(self, vt_symbol: str) -> None:
        """
        撤销指定合约的所有活动订单

        Args:
            vt_symbol: 合约代码
        """
        orders = self.active_orders.get(vt_symbol, {})
        for vt_orderid in list(orders.keys()):
            self.cancel_order(vt_orderid)

    def _send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: int,
        order_type: OrderType
    ) -> Optional[str]:
        """
        发送订单（内部方法）

        Args:
            vt_symbol: 合约代码
            direction: 方向
            offset: 开平
            price: 价格
            volume: 数量
            order_type: 订单类型

        Returns:
            vt_orderid: 订单ID（如果转换为多个订单，返回第一个）
        """
        # 获取合约信息
        contract = self.main_engine.get_contract(vt_symbol)
        if not contract:
            print(f"合约 {vt_symbol} 不存在")
            return None

        # 创建订单请求
        req = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            offset=offset,
            reference="ChartTrader"
        )

        # 对于平仓订单，使用OffsetConverter自动转换今昨仓（针对SHFE/INE）
        # lock=False: 不锁仓
        # net=False: 使用SHFE模式，自动区分平今/平昨
        order_reqs = self.main_engine.convert_order_request(
            req=req,
            gateway_name=contract.gateway_name,
            lock=False,
            net=False
        )

        # 发送所有转换后的订单
        vt_orderids = []
        for order_req in order_reqs:
            vt_orderid = self.main_engine.send_order(order_req, contract.gateway_name)
            if vt_orderid:
                vt_orderids.append(vt_orderid)
                # 初始化订单跟踪
                if vt_symbol not in self.active_orders:
                    self.active_orders[vt_symbol] = {}
                # 发射订单提交信号
                self.order_submitted.emit(vt_symbol, vt_orderid)

        # 返回第一个订单ID（如果有多个订单被拆分）
        return vt_orderids[0] if vt_orderids else None

    def process_order_event(self, event: Event) -> None:
        """
        处理订单事件

        Args:
            event: 订单事件
        """
        order: OrderData = event.data
        vt_symbol = order.vt_symbol

        # 初始化订单字典
        if vt_symbol not in self.active_orders:
            self.active_orders[vt_symbol] = {}

        # 更新订单状态
        if order.is_active():
            # 活动订单：添加或更新
            self.active_orders[vt_symbol][order.vt_orderid] = order
        else:
            # 非活动订单：移除
            self.active_orders[vt_symbol].pop(order.vt_orderid, None)

        # 发射订单更新信号
        self.order_updated.emit(vt_symbol, order)

    def process_trade_event(self, event: Event) -> None:
        """
        处理成交事件

        Args:
            event: 成交事件
        """
        trade: TradeData = event.data
        vt_symbol = trade.vt_symbol

        # 更新持仓
        if vt_symbol not in self.positions:
            self.positions[vt_symbol] = 0

        # 根据方向和开平更新持仓
        if trade.direction == Direction.LONG:
            if trade.offset == Offset.OPEN:
                self.positions[vt_symbol] += trade.volume
            else:  # CLOSE
                self.positions[vt_symbol] -= trade.volume
        else:  # SHORT
            if trade.offset == Offset.OPEN:
                self.positions[vt_symbol] -= trade.volume
            else:  # CLOSE
                self.positions[vt_symbol] += trade.volume

        # 发射成交和持仓更新信号
        self.trade_received.emit(vt_symbol, trade)
        self.position_updated.emit(vt_symbol, self.positions[vt_symbol])

    def get_position(self, vt_symbol: str) -> int:
        """
        获取持仓

        Args:
            vt_symbol: 合约代码

        Returns:
            持仓数量（正数为多头，负数为空头）
        """
        return self.positions.get(vt_symbol, 0)

    def get_active_orders(self, vt_symbol: str) -> Dict[str, OrderData]:
        """
        获取活动订单

        Args:
            vt_symbol: 合约代码

        Returns:
            活动订单字典
        """
        return self.active_orders.get(vt_symbol, {})

    def cleanup(self) -> None:
        """清理资源"""
        self.event_engine.unregister(EVENT_ORDER, self.process_order_event)
        self.event_engine.unregister(EVENT_TRADE, self.process_trade_event)
