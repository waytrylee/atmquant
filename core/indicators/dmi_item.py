#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DMI方向性运动指标
基于vnpy ChartItem实现的DMI技术指标
"""

from typing import Dict, Any, Tuple
import numpy as np
import pyqtgraph as pg

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData
from vnpy.chart.item import ChartItem
from vnpy.chart.manager import BarManager

from .indicator_base import ConfigurableIndicator
from .calculators.dmi_calculator import DMICalculator


class DmiItem(ChartItem, ConfigurableIndicator):
    """
    DMI方向性运动指标
    参考原始代码风格，支持参数配置
    """
    
    def __init__(self, manager: BarManager, N: int = 14, M: int = 7):
        """初始化DMI指标"""
        super().__init__(manager)
        
        # 参数设置
        self.N = N
        self.M = M
        
        # 颜色配置
        self.white_pen: QtGui.QPen = pg.mkPen(color=(255, 255, 255), width=1)
        self.yellow_pen: QtGui.QPen = pg.mkPen(color=(255, 255, 0), width=1)
        self.magenta_pen: QtGui.QPen = pg.mkPen(color=(255, 0, 255), width=1)
        self.red_pen: QtGui.QPen = pg.mkPen(color=(255, 0, 0), width=1)
        self.green_pen: QtGui.QPen = pg.mkPen(color=(0, 255, 0), width=1)
        self.ref_pen: QtGui.QPen = pg.mkPen(color=(127, 127, 127, 127), width=1, style=QtCore.Qt.DashLine)
        
        # 缓存设置
        self._values_ranges: Dict[Tuple[int, int], Tuple[float, float]] = {}
        
        # 数据缓存
        self.dmi_data: Dict[int, Tuple[float, float, float, float]] = {}  # (PDI,MDI,ADX,ADXR)
        self._needs_recalc = True

    def _ensure_calculated(self) -> None:
        """全量计算 DMI 指标，委托给 DMICalculator"""
        if not self._needs_recalc and self.dmi_data:
            return

        bars = self._manager.get_all_bars()
        if not bars or len(bars) < self.N + self.M:
            return

        highs = np.array([bar.high_price for bar in bars])
        lows = np.array([bar.low_price for bar in bars])
        closes = np.array([bar.close_price for bar in bars])

        try:
            pdi, mdi, adx, adxr = DMICalculator.compute_arrays(
                highs, lows, closes, self.N, self.M
            )

            self.dmi_data.clear()
            for n in range(len(adx)):
                if not any(np.isnan(v) for v in [pdi[n], mdi[n], adx[n], adxr[n]]):
                    self.dmi_data[n] = (float(pdi[n]), float(mdi[n]), float(adx[n]), float(adxr[n]))
            self._needs_recalc = False
        except Exception:
            pass

    def update_history(self, history) -> None:
        """重写update_history方法"""
        self.dmi_data.clear()
        self._needs_recalc = True
        super().update_history(history)

    def update_bar(self, bar: BarData) -> None:
        """重写update_bar方法"""
        self._needs_recalc = True
        super().update_bar(bar)

    def _get_dmi_value(self, ix: int) -> Tuple[float, float, float, float]:
        """获取指定索引的 DMI 值"""
        invalid_data = (np.nan, np.nan, np.nan, np.nan)
        if ix < 0:
            return invalid_data
        self._ensure_calculated()
        return self.dmi_data.get(ix, invalid_data)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """绘制DMI"""
        # 创建绘图对象
        picture = QtGui.QPicture()
        painter = QtGui.QPainter(picture)

        if ix > self.N + self.M:
            # 画参考线
            painter.setPen(self.ref_pen)
            for ref in [20.0, 50, 80]:
                painter.drawLine(QtCore.QPointF(ix-0.5, ref), QtCore.QPointF(ix+0.5, ref))

            # 画4根线
            dmi_value = self._get_dmi_value(ix)
            last_dmi_value = self._get_dmi_value(ix - 1)
            
            # 确保获取了有效的DMI值
            if np.isnan(dmi_value[0]) or np.isnan(last_dmi_value[0]):
                # 如果无效，标记需要重算
                self._needs_recalc = True
                dmi_value = self._get_dmi_value(ix)
                last_dmi_value = self._get_dmi_value(ix - 1)
            
            pens = [self.white_pen, self.yellow_pen, self.magenta_pen, self.green_pen]
            for i in range(4):
                if np.isnan(dmi_value[i]) or np.isnan(last_dmi_value[i]):
                    continue
                end_point0 = QtCore.QPointF(ix, dmi_value[i])
                start_point0 = QtCore.QPointF(ix - 1, last_dmi_value[i])
                painter.setPen(pens[i])
                painter.drawLine(start_point0, end_point0)

            # 多空颜色标示
            pdi, mdi = dmi_value[0], dmi_value[1]
            if not(np.isnan(pdi) or np.isnan(mdi)):
                if abs(pdi - mdi) > 1e-2:
                    painter.setPen(pg.mkPen(color=(168, 0, 0) if pdi > mdi else (0, 168, 0), width=3))
                    painter.drawLine(QtCore.QPointF(ix, pdi), QtCore.QPointF(ix, mdi))

        painter.end()
        return picture

    def boundingRect(self) -> QtCore.QRectF:
        """返回边界矩形"""
        min_y, max_y = self.get_y_range()
        rect = QtCore.QRectF(
            0,
            min_y,
            len(self._bar_picutures),
            max_y - min_y
        )
        return rect

    def get_y_range(self, min_ix: int = None, max_ix: int = None) -> Tuple[float, float]:
        """获取Y轴范围"""
        return (0.0, 100.0)  # DMI指标范围固定为0-100

    def get_current_values(self) -> Dict[str, Any]:
        """
        获取当前指标值，用于AI分析

        Returns:
            包含当前DMI数据的字典
        """
        bars = self._manager.get_all_bars()
        if not bars:
            return {}

        ix = len(bars) - 1

        # 使用_get_dmi_value确保数据被计算（即使指标被隐藏）
        dmi_values = self._get_dmi_value(ix)
        if all(np.isnan(val) for val in dmi_values):
            return {}

        pdi, mdi, adx, adxr = dmi_values

        # 获取前一个数据
        prev_dmi_values = self._get_dmi_value(ix - 1)
        prev_pdi = prev_dmi_values[0] if not all(np.isnan(val) for val in prev_dmi_values) else None
        prev_mdi = prev_dmi_values[1] if not all(np.isnan(val) for val in prev_dmi_values) else None

        # 获取当前价格
        bar = bars[ix]
        current_price = bar.close_price if bar else 0

        # 确定趋势
        trend = "neutral"
        if pdi > mdi:
            trend = "up"
        elif mdi > pdi:
            trend = "down"

        # 确定趋势强度
        strength = "weak"
        adx_strength = adx if adx else 0
        if adx_strength > 40:
            strength = "strong"
        elif adx_strength > 25:
            strength = "moderate"

        return {
            "pdi": round(pdi, 2),
            "mdi": round(mdi, 2),
            "adx": round(adx, 2),
            "adxr": round(adxr, 2),
            "previous_pdi": round(prev_pdi, 2) if prev_pdi is not None else None,
            "previous_mdi": round(prev_mdi, 2) if prev_mdi is not None else None,
            "trend": trend,
            "trend_strength": strength,
            "current_price": round(current_price, 2),
            "adx_trend_strength": "strong" if adx_strength > 40 else "moderate" if adx_strength > 25 else "weak"
        }

    def get_info_text(self, ix: int) -> str:
        """获取DMI信息文本，包含数值和交易指导"""
        if ix in self.dmi_data:
            pdi, mdi, adx, adxr = self.dmi_data[ix]

            # 基础信息
            info_lines = [
                f"DMI({self.N},{self.M}):",
                f"PDI: {pdi:.2f}",
                f"MDI: {mdi:.2f}",
                f"ADX: {adx:.2f}",
                f"ADXR: {adxr:.2f}",
            ]

            # 获取前一个数据用于趋势判断
            prev_ix = ix - 1
            if prev_ix in self.dmi_data:
                prev_pdi, prev_mdi, prev_adx, prev_adxr = self.dmi_data[prev_ix]

                # PDI与MDI对比分析 - 方向判断
                pdi_mdi_diff = abs(pdi - mdi)

                if pdi > mdi:
                    info_lines.append(f"趋势方向: 多头占优 (PDI>MDI)")
                    if pdi_mdi_diff > 20:
                        info_lines.append(f"多头强度: 极强 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 强势多头行情")
                    elif pdi_mdi_diff > 10:
                        info_lines.append(f"多头强度: 较强 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 稳定多头行情")
                    else:
                        info_lines.append(f"多头强度: 温和 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 多头略占上风")

                elif mdi > pdi:
                    info_lines.append(f"趋势方向: 空头占优 (MDI>PDI)")
                    if pdi_mdi_diff > 20:
                        info_lines.append(f"空头强度: 极强 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 强势空头行情")
                    elif pdi_mdi_diff > 10:
                        info_lines.append(f"空头强度: 较强 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 稳定空头行情")
                    else:
                        info_lines.append(f"空头强度: 温和 (差值{pdi_mdi_diff:.1f})")
                        info_lines.append("市场状态: 空头略占上风")
                else:
                    info_lines.append("趋势方向: 多空平衡")
                    info_lines.append("市场状态: 方向不明，观望为主")

                # PDI和MDI交叉分析 - 关键买卖信号
                if prev_pdi <= prev_mdi and pdi > mdi:
                    info_lines.append("PDI上穿MDI - 黄金交叉")
                    if adx > 25:
                        info_lines.append("信号强度: 强 (ADX>25)")
                        info_lines.append("操作: 积极做多，趋势启动")
                    elif adx > 20:
                        info_lines.append("信号强度: 中等 (ADX>20)")
                        info_lines.append("操作: 谨慎做多，观察确认")
                    else:
                        info_lines.append("信号强度: 弱 (ADX<20)")
                        info_lines.append("操作: 等待ADX上升确认")

                elif prev_pdi >= prev_mdi and pdi < mdi:
                    info_lines.append("MDI上穿PDI - 死亡交叉")
                    if adx > 25:
                        info_lines.append("信号强度: 强 (ADX>25)")
                        info_lines.append("操作: 积极做空，趋势启动")
                    elif adx > 20:
                        info_lines.append("信号强度: 中等 (ADX>20)")
                        info_lines.append("操作: 谨慎做空，观察确认")
                    else:
                        info_lines.append("信号强度: 弱 (ADX<20)")
                        info_lines.append("操作: 等待ADX上升确认")

                # ADX趋势强度分析 - 核心指标
                if adx > 50:
                    info_lines.append("趋势强度: 极强趋势 (ADX>50)")
                    info_lines.append("特征: 单边行情，顺势为王")
                    if pdi > mdi:
                        info_lines.append("策略: 坚定持有多单，不轻易止盈")
                    else:
                        info_lines.append("策略: 坚定持有空单，不轻易止盈")
                elif adx > 40:
                    info_lines.append("趋势强度: 强趋势 (ADX>40)")
                    info_lines.append("特征: 明确趋势，顺势操作")
                    if pdi > mdi:
                        info_lines.append("策略: 持有多单，回调加仓")
                    else:
                        info_lines.append("策略: 持有空单，反弹加仓")
                elif adx > 25:
                    info_lines.append("趋势强度: 中等趋势 (ADX>25)")
                    info_lines.append("特征: 趋势形成，可顺势操作")
                    if pdi > mdi:
                        info_lines.append("策略: 做多为主，注意止损")
                    else:
                        info_lines.append("策略: 做空为主，注意止损")
                elif adx > 20:
                    info_lines.append("趋势强度: 弱趋势 (ADX>20)")
                    info_lines.append("特征: 趋势不明确")
                    info_lines.append("策略: 谨慎操作，轻仓为主")
                else:
                    info_lines.append("趋势强度: 无趋势 (ADX<20)")
                    info_lines.append("特征: 震荡市场，无明确方向")
                    info_lines.append("策略: 区间操作或观望")

                # ADX变化趋势分析
                adx_change = adx - prev_adx
                if abs(adx_change) > 3:
                    if adx_change > 0:
                        info_lines.append(f"ADX急速上升 (+{adx_change:.1f}) - 趋势强化")
                        info_lines.append("信号: 趋势行情启动或加速")
                    else:
                        info_lines.append(f"ADX急速下降 ({adx_change:.1f}) - 趋势减弱")
                        info_lines.append("信号: 趋势行情衰竭，准备调整")
                elif abs(adx_change) > 1:
                    if adx_change > 0:
                        info_lines.append(f"ADX稳步上升 (+{adx_change:.1f})")
                    else:
                        info_lines.append(f"ADX稳步下降 ({adx_change:.1f})")

                # ADX与ADXR对比 - 趋势加速或减速判断
                adx_adxr_diff = adx - adxr
                if abs(adx_adxr_diff) > 5:
                    if adx_adxr_diff > 0:
                        info_lines.append(f"ADX>ADXR (差值{adx_adxr_diff:.1f}) - 趋势加速")
                        info_lines.append("动能: 新趋势力量强劲")
                    else:
                        info_lines.append(f"ADX<ADXR (差值{abs(adx_adxr_diff):.1f}) - 趋势减速")
                        info_lines.append("动能: 趋势力量衰减")

                # ADX拐点分析 - 重要转折信号
                if prev_adx > adx and adx > 40:
                    info_lines.append("ADX高位回落 - 趋势衰竭信号")
                    info_lines.append("警惕: 强趋势可能进入尾声")
                    info_lines.append("操作: 准备获利了结")
                elif prev_adx < adx and adx > 25 and prev_adx < 20:
                    info_lines.append("ADX突破20 - 趋势启动信号")
                    info_lines.append("机会: 新趋势行情开始")
                    info_lines.append("操作: 顺势建仓")

                # PDI和MDI的绝对位置分析
                if pdi > 40 and mdi < 20:
                    info_lines.append("PDI极强MDI极弱 - 单边多头")
                    info_lines.append("市场: 典型牛市特征")
                elif mdi > 40 and pdi < 20:
                    info_lines.append("MDI极强PDI极弱 - 单边空头")
                    info_lines.append("市场: 典型熊市特征")
                elif pdi > 30 and mdi > 30:
                    info_lines.append("PDI和MDI双高 - 震荡激烈")
                    info_lines.append("市场: 多空争夺激烈")
                elif pdi < 20 and mdi < 20:
                    info_lines.append("PDI和MDI双低 - 趋势不明")
                    info_lines.append("市场: 盘整阶段，方向未定")

                # PDI/MDI变化率分析
                pdi_change = pdi - prev_pdi
                mdi_change = mdi - prev_mdi

                if abs(pdi_change) > 5 or abs(mdi_change) > 5:
                    if pdi_change > 5:
                        info_lines.append(f"PDI急升 (+{pdi_change:.1f}) - 多头力量激增")
                    elif pdi_change < -5:
                        info_lines.append(f"PDI急降 ({pdi_change:.1f}) - 多头力量减弱")

                    if mdi_change > 5:
                        info_lines.append(f"MDI急升 (+{mdi_change:.1f}) - 空头力量激增")
                    elif mdi_change < -5:
                        info_lines.append(f"MDI急降 ({mdi_change:.1f}) - 空头力量减弱")

                # DMI经典组合信号
                if pdi > mdi and adx > 25 and adx > adxr:
                    info_lines.append("经典多头组合 - PDI>MDI且ADX>25且上升")
                    info_lines.append("最佳信号: 积极做多")
                elif mdi > pdi and adx > 25 and adx > adxr:
                    info_lines.append("经典空头组合 - MDI>PDI且ADX>25且上升")
                    info_lines.append("最佳信号: 积极做空")
                elif adx < 20 and abs(pdi - mdi) < 5:
                    info_lines.append("经典震荡组合 - ADX<20且PDI≈MDI")
                    info_lines.append("策略建议: 观望或区间操作")

                # 趋势持续性判断
                if adx > 25:
                    # 检查连续周期的ADX
                    consecutive_adx_high = 1
                    check_ix = prev_ix
                    while check_ix >= 0 and check_ix in self.dmi_data:
                        if self.dmi_data[check_ix][2] > 25:
                            consecutive_adx_high += 1
                            check_ix -= 1
                        else:
                            break

                    if consecutive_adx_high >= 5:
                        info_lines.append(f"趋势持续 ({consecutive_adx_high}周期) - 趋势成熟")
                        info_lines.append("提示: 长期趋势，注意顶底背离")

            else:
                # 没有前一个数据时的基本判断
                if pdi > mdi:
                    info_lines.append("趋势: 多头")
                elif mdi > pdi:
                    info_lines.append("趋势: 空头")
                else:
                    info_lines.append("趋势: 平衡")

                if adx > 25:
                    info_lines.append("强度: 有趋势")
                else:
                    info_lines.append("强度: 弱势或震荡")

            return "\n".join(info_lines)

        return f"DMI({self.N},{self.M}) - 数据不足"
    
    def clear_all(self) -> None:
        """清除所有数据"""
        super().clear_all()
        self.dmi_data.clear()
        self._bar_picutures.clear()
        self._needs_recalc = True
        self.update()

    # 配置相关方法
    def get_config_dialog(self, parent: QtWidgets.QWidget) -> QtWidgets.QDialog:
        """获取配置对话框"""
        config_items = [
            ("N", "PDI/MDI周期", "spinbox", {"min": 5, "max": 50, "value": self.N}),
            ("M", "ADX/ADXR周期", "spinbox", {"min": 3, "max": 30, "value": self.M})
        ]
        return self.create_config_dialog(parent, "DMI配置", config_items)

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置"""
        self.N = config.get('N', self.N)
        self.M = config.get('M', self.M)
        
        # 重新初始化
        self.dmi_data.clear()
        self._values_ranges.clear()
        self._needs_recalc = True
        self.update()

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {'N': self.N, 'M': self.M}

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {'N': 14, 'M': 14}

    def _get_config_help_text(self) -> str:
        """获取配置帮助文本"""
        return """
参数说明：
• PDI/MDI周期: 正负方向指标的计算周期(建议14)
• ADX/ADXR周期: 平均趋向指标的计算周期(建议7)

颜色说明：
• 白色线: PDI(正方向指标)
• 黄色线: MDI(负方向指标)
• 紫色线: ADX(平均趋向指标)
• 绿色线: ADXR(趋向平均值)
• 红/绿连线: PDI与MDI的强弱关系
        """
