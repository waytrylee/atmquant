#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可扩展ViewBox组件
支持在边缘拖拽延伸x轴和y轴
"""

from datetime import timedelta
import pyqtgraph as pg
from vnpy.trader.ui import QtCore


class ExtendableViewBox(pg.ViewBox):
    """
    增强版ViewBox，支持在最右边拖拽延伸x轴，在顶部/底部拖拽延伸y轴
    """

    def __init__(self, chart_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chart_widget = chart_widget
        self._is_dragging_right = False
        self._is_dragging_top = False
        self._is_dragging_bottom = False
        self._drag_start_pos = None
        self._original_y_range = None

    def mousePressEvent(self, ev):
        """重写鼠标按下事件"""
        is_ctrl_pressed = (
            ev.modifiers() == QtCore.Qt.ControlModifier
            or ev.modifiers() == QtCore.Qt.MetaModifier
        )

        if ev.button() == QtCore.Qt.LeftButton:
            if is_ctrl_pressed:
                super().mousePressEvent(ev)
                return

            pos = self.mapSceneToView(ev.scenePos())
            x_pos = pos.x()
            y_pos = pos.y()

            view_range = self.viewRange()
            y_range = view_range[1]

            # 检查是否在数据范围的右边（X轴延伸）
            data_count = self.chart_widget._manager.get_count()
            if x_pos > data_count - 1:
                self._is_dragging_right = True
                self._drag_start_pos = x_pos
                ev.accept()
                return

            # 检查Y轴区域
            y_range_height = y_range[1] - y_range[0]
            top_threshold = y_range[1] - y_range_height * 0.1
            bottom_threshold = y_range[0] + y_range_height * 0.1

            if y_pos > top_threshold:
                self._is_dragging_top = True
                self._drag_start_pos = y_pos
                self._original_y_range = y_range
                ev.accept()
                return
            elif y_pos < bottom_threshold:
                self._is_dragging_bottom = True
                self._drag_start_pos = y_pos
                self._original_y_range = y_range
                ev.accept()
                return

        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """重写鼠标移动事件"""
        if self._is_dragging_right and self._drag_start_pos is not None:
            self._handle_x_drag(ev)
            return
        elif self._is_dragging_top and self._drag_start_pos is not None:
            self._handle_y_top_drag(ev)
            return
        elif self._is_dragging_bottom and self._drag_start_pos is not None:
            self._handle_y_bottom_drag(ev)
            return

        super().mouseMoveEvent(ev)

    def _handle_x_drag(self, ev):
        """处理X轴拖拽"""
        pos = self.mapSceneToView(ev.scenePos())
        x_pos = pos.x()
        drag_distance = x_pos - self._drag_start_pos
        data_count = self.chart_widget._manager.get_count()
        new_right_ix = data_count - 1 + max(0, drag_distance)

        if new_right_ix >= data_count - 1:
            self.chart_widget._right_ix = int(new_right_ix)
            self.chart_widget._update_x_range()
        ev.accept()

    def _handle_y_top_drag(self, ev):
        """处理Y轴顶部拖拽"""
        pos = self.mapSceneToView(ev.scenePos())
        y_pos = pos.y()
        drag_distance = y_pos - self._drag_start_pos
        original_height = self._original_y_range[1] - self._original_y_range[0]

        # 防止除零错误
        if original_height == 0:
            ev.accept()
            return

        if drag_distance > 0:
            extend_ratio = min(drag_distance / original_height, 3.0)
            new_top = self._original_y_range[1] + original_height * extend_ratio
            new_bottom = self._original_y_range[0]
        else:
            shrink_ratio = min(abs(drag_distance) / original_height, 0.8)
            new_top = self._original_y_range[1] - original_height * shrink_ratio
            new_bottom = self._original_y_range[0]
            if new_top <= new_bottom:
                new_top = new_bottom + original_height * 0.1

        self.setYRange(new_bottom, new_top, padding=0)
        ev.accept()

    def _handle_y_bottom_drag(self, ev):
        """处理Y轴底部拖拽"""
        pos = self.mapSceneToView(ev.scenePos())
        y_pos = pos.y()
        drag_distance = y_pos - self._drag_start_pos
        original_height = self._original_y_range[1] - self._original_y_range[0]

        # 防止除零错误
        if original_height == 0:
            ev.accept()
            return

        if drag_distance < 0:
            extend_ratio = min(abs(drag_distance) / original_height, 3.0)
            new_top = self._original_y_range[1]
            new_bottom = self._original_y_range[0] - original_height * extend_ratio
        else:
            shrink_ratio = min(drag_distance / original_height, 0.8)
            new_top = self._original_y_range[1]
            new_bottom = self._original_y_range[0] + original_height * shrink_ratio
            if new_bottom >= new_top:
                new_bottom = new_top - original_height * 0.1

        self.setYRange(new_bottom, new_top, padding=0)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        """重写鼠标释放事件"""
        if self._is_dragging_right or self._is_dragging_top or self._is_dragging_bottom:
            self._is_dragging_right = False
            self._is_dragging_top = False
            self._is_dragging_bottom = False
            self._drag_start_pos = None
            self._original_y_range = None
            ev.accept()
            return

        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        """重写鼠标双击事件，双击顶部或底部区域重置Y轴范围"""
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.mapSceneToView(ev.scenePos())
            y_pos = pos.y()
            view_range = self.viewRange()
            y_range = view_range[1]
            y_range_height = y_range[1] - y_range[0]
            top_threshold = y_range[1] - y_range_height * 0.2
            bottom_threshold = y_range[0] + y_range_height * 0.2

            if y_pos > top_threshold or y_pos < bottom_threshold:
                self.enableAutoRange(axis=self.YAxis)
                ev.accept()
                return

        super().mouseDoubleClickEvent(ev)
