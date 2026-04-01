"""
增强的回测UI组件
提供更丰富的回测指标显示和优化结果管理功能
"""
import csv
from typing import Dict, List, Any
from copy import copy

import numpy as np
from vnpy.trader.ui import QtWidgets, QtCore, QtGui


class EnhancedStatisticsMonitor(QtWidgets.QWidget):
    """
    增强的统计指标监控器 - 双列布局
    左列显示核心指标，右列显示辅助指标
    """

    # 左列指标分组 - 核心指标（22项）
    LEFT_INDICATORS = {
        "【收益指标】": [
            ("total_return", "总收益率"),
            ("annual_return", "年化收益"),
            ("daily_return", "日均收益率"),
            ("total_net_pnl", "总盈亏"),
            ("daily_net_pnl", "日均盈亏"),
        ],
        "【风险指标】": [
            ("max_drawdown", "最大回撤"),
            ("max_ddpercent", "百分比最大回撤"),
            ("max_drawdown_duration", "最大回撤天数"),
            ("return_std", "收益标准差"),
        ],
        "【风险调整收益】": [
            ("sharpe_ratio", "夏普比率"),
            ("ewm_sharpe", "EWM Sharpe"),
            ("sortino_ratio", "索提诺比率"),
            ("calmar_ratio", "卡尔马比率"),
            ("return_drawdown_ratio", "收益回撤比"),
        ],
        "【交易统计】": [
            ("win_rate", "胜率"),
            ("average_win_loss_ratio", "平均盈亏比"),
            ("profit_factor", "获利因子"),
            ("average_trade", "平均每笔盈亏"),
            ("max_consecutive_wins", "最大连续盈利次数"),
            ("max_consecutive_losses", "最大连续亏损次数"),
            ("optimal_position_ratio", "最优仓位比例"),
        ],
        "【综合评分】": [
            ("overall_rating", "综合评分"),
        ],
    }

    # 右列指标分组 - 辅助指标（23项）
    RIGHT_INDICATORS = {
        "【基础信息】": [
            ("start_date", "首个交易日"),
            ("end_date", "最后交易日"),
            ("total_days", "总交易日"),
            ("profit_days", "盈利交易日"),
            ("loss_days", "亏损交易日"),
            ("capital", "起始资金"),
            ("end_balance", "结束资金"),
        ],
        "【持仓统计】": [
            ("average_holding_time_days", "平均持仓时间(天)"),
            ("max_holding_time_days", "最大持仓时间(天)"),
            ("min_holding_time_days", "最小持仓时间(天)"),
            ("median_holding_time_days", "中位数持仓时间(天)"),
        ],
        "【成本统计】": [
            ("total_commission", "总手续费"),
            ("total_slippage", "总滑点"),
            ("total_turnover", "总成交额"),
            ("total_trade_count", "总成交笔数"),
            ("long_trade_count", "多头笔数"),
            ("short_trade_count", "空头笔数"),
            ("daily_commission", "日均手续费"),
            ("daily_slippage", "日均滑点"),
            ("daily_turnover", "日均成交额"),
            ("daily_trade_count", "日均成交笔数"),
        ],
        "【统计数据】": [
            ("monthly_statistics", "月度统计数据"),
            ("interval_statistics", "半小时区间统计"),
        ],
    }

    # 为了向后兼容，保留原有的KEY_NAME_MAP
    KEY_NAME_MAP = {}
    for group_items in LEFT_INDICATORS.values():
        for key, name in group_items:
            KEY_NAME_MAP[key] = name
    for group_items in RIGHT_INDICATORS.values():
        for key, name in group_items:
            KEY_NAME_MAP[key] = name

    def __init__(self) -> None:
        """"""
        super().__init__()

        self.cells: Dict[str, QtWidgets.QTableWidgetItem] = {}

        # 创建左右两个表格
        self.left_table = QtWidgets.QTableWidget()
        self.right_table = QtWidgets.QTableWidget()

        self.init_ui()

    def init_ui(self) -> None:
        """"""
        # 创建水平布局
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 初始化左表格（核心指标）
        self._init_table(self.left_table, self.LEFT_INDICATORS)

        # 初始化右表格（辅助指标）
        self._init_table(self.right_table, self.RIGHT_INDICATORS)

        # 设置宽度比例 55:45
        layout.addWidget(self.left_table, 55)
        layout.addWidget(self.right_table, 45)

        self.setLayout(layout)

    def _init_table(
        self,
        table: QtWidgets.QTableWidget,
        indicators: Dict[str, List[tuple]]
    ) -> None:
        """初始化单个表格"""
        # 计算总行数（包括分组标题行）
        total_rows = sum(len(items) + 1 for items in indicators.values())
        table.setRowCount(total_rows)

        # 设置列
        table.setColumnCount(1)
        table.horizontalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)

        # 设置样式
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(20)  # 数据行高度

        # 设置字体
        font = table.font()
        font.setPointSize(11)
        table.setFont(font)

        # 创建标签和单元格
        labels = []
        current_row = 0

        for group_name, group_items in indicators.items():
            # 分组标题行
            labels.append("")
            group_cell = QtWidgets.QTableWidgetItem(group_name)
            group_cell.setTextAlignment(QtCore.Qt.AlignCenter)
            group_cell.setFlags(QtCore.Qt.ItemIsEnabled)

            # 分组标题加粗
            font = group_cell.font()
            font.setBold(True)
            group_cell.setFont(font)

            table.setItem(current_row, 0, group_cell)
            table.setRowHeight(current_row, 24)  # 分组标题行高度
            current_row += 1

            # 数据行
            for key, name in group_items:
                labels.append(name)
                cell = QtWidgets.QTableWidgetItem()
                table.setItem(current_row, 0, cell)
                self.cells[key] = cell

                # 特殊处理统计数据
                if key in ["monthly_statistics", "interval_statistics"]:
                    cell.setTextAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
                    cell.setFlags(cell.flags() | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

                current_row += 1

        table.setVerticalHeaderLabels(labels)

    def clear_data(self) -> None:
        """"""
        for cell in self.cells.values():
            cell.setText("")

    def set_data(self, data: Dict[str, Any]) -> None:
        """"""
        data = copy(data)

        # 特殊处理统计数据的格式 - 使用 DataFrame.to_string()
        # 注意：不修改原始数据，只转换用于显示的字符串
        for key in ["monthly_statistics", "interval_statistics"]:
            if key in data and data[key] is not None:
                # 创建显示用的字符串，但不修改原始数据
                display_value = ""
                # 如果是 DataFrame，使用 to_string(index=False)
                if hasattr(data[key], 'to_string'):
                    display_value = data[key].to_string(index=False)
                # 如果不是字符串，转换为字符串
                elif not isinstance(data[key], str):
                    display_value = str(data[key])
                else:
                    display_value = data[key]
                # 保存显示用的字符串（使用特殊键名）
                data[f"{key}_display"] = display_value

        # 格式化数值数据
        format_map = {
            # 百分比格式
            "win_rate": "{:.2%}",
            "optimal_position_ratio": "{:.2%}",
            "total_return": "{:.2f}%",
            "annual_return": "{:.2f}%",
            "daily_return": "{:.2f}%",
            "return_std": "{:.2f}%",
            "max_ddpercent": "{:.2f}%",

            # 带千位分隔符的金额格式
            "capital": "{:,.2f}",
            "end_balance": "{:,.2f}",
            "total_net_pnl": "{:,.2f}",
            "total_commission": "{:,.2f}",
            "total_slippage": "{:,.2f}",
            "total_turnover": "{:,.2f}",
            "daily_net_pnl": "{:,.2f}",
            "daily_commission": "{:,.2f}",
            "daily_slippage": "{:,.2f}",
            "daily_turnover": "{:,.2f}",

            # 普通小数格式
            "max_drawdown": "{:.2f}",
            "average_win_loss_ratio": "{:.2f}",
            "sharpe_ratio": "{:.2f}",
            "sortino_ratio": "{:.2f}",
            "ewm_sharpe": "{:.2f}",
            "calmar_ratio": "{:.2f}",
            "return_drawdown_ratio": "{:.2f}",
            "daily_trade_count": "{:.2f}",
            "profit_factor": "{:.2f}",
            "average_trade": "{:,.2f}",
            "overall_rating": "{:.4f}",

            # 持仓时间统计
            "average_holding_time_days": "{:.2f}",
            "max_holding_time_days": "{:.2f}",
            "min_holding_time_days": "{:.2f}",
            "median_holding_time_days": "{:.2f}",

            # 整数格式 - 处理可能的NaN值
            "max_consecutive_wins": "int",
            "max_consecutive_losses": "int",
        }

        # 应用格式化
        for key, fmt in format_map.items():
            if key in data and data[key] is not None:
                try:
                    # 特殊处理整数格式
                    if fmt == "int":
                        if isinstance(data[key], (int, float)) and not np.isnan(data[key]):
                            data[key] = str(int(data[key]))
                        else:
                            data[key] = "0"
                    # 处理可能的非数值类型
                    elif isinstance(data[key], (int, float)) and not np.isnan(data[key]):
                        data[key] = fmt.format(data[key])
                    else:
                        data[key] = "N/A"
                except (ValueError, TypeError):
                    if fmt == "int":
                        data[key] = "0"
                    else:
                        data[key] = "N/A"

        # 更新单元格内容
        for key, cell in self.cells.items():
            # 对于统计数据，使用显示用的字符串
            if key in ["monthly_statistics", "interval_statistics"]:
                value = data.get(f"{key}_display", "")
            else:
                value = data.get(key, "")
            cell.setText(str(value))

            # 如果是统计数据，自动调整行高
            if key in ["monthly_statistics", "interval_statistics"] and value:
                # 找到该单元格所在的表格
                table = None
                for row in range(self.right_table.rowCount()):
                    if self.right_table.item(row, 0) == cell:
                        table = self.right_table
                        break

                if table:
                    metrics = QtGui.QFontMetrics(cell.font())
                    text_height = metrics.boundingRect(
                        0, 0, table.columnWidth(0), 1000,
                        QtCore.Qt.TextWordWrap | QtCore.Qt.AlignLeft,
                        str(value)
                    ).height()
                    table.setRowHeight(table.row(cell), text_height + 20)


class NumericTableWidgetItem(QtWidgets.QTableWidgetItem):
    """支持正确数值排序的表格项"""

    def __lt__(self, other):
        if isinstance(other, QtWidgets.QTableWidgetItem):
            try:
                # 优先使用存储在DisplayRole中的数值进行比较
                my_value = self.data(QtCore.Qt.DisplayRole)
                other_value = other.data(QtCore.Qt.DisplayRole)

                if my_value is not None and other_value is not None:
                    try:
                        return float(my_value) < float(other_value)
                    except (ValueError, TypeError):
                        pass

                # 如果无法直接比较，则获取文本并尝试转换
                my_text = self.text().replace('%', '').replace(',', '')
                other_text = other.text().replace('%', '').replace(',', '')

                return float(my_text) < float(other_text)
            except (ValueError, TypeError):
                return super().__lt__(other)
        return super().__lt__(other)


class EnhancedOptimizationResultMonitor(QtWidgets.QDialog):
    """
    增强的参数优化结果监控器
    提供更丰富的优化结果显示和保存功能
    """

    def __init__(
        self,
        result_values: List,
        target_display: str
    ) -> None:
        """"""
        super().__init__()

        self.result_values = result_values
        self.target_display = target_display
        self.current_sort_column = 1  # 默认按综合评分排序
        self.is_ascending = False  # 默认降序

        self.init_ui()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle("参数优化结果")
        self.resize(1400, 600)

        # 创建主布局
        main_layout = QtWidgets.QVBoxLayout()

        # 创建工具栏
        toolbar_layout = QtWidgets.QHBoxLayout()

        # 增强的筛选条件
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems([
            "全部",
            "综合评分>0.5", 
            "综合评分>0.7",
            "夏普比率>1", 
            "夏普比率>1.5",
            "最大回撤<5%",
            "最大回撤<10%", 
            "胜率>60%",
            "胜率>70%",
            "获利因子>1.5",
            "获利因子>2.0",
            "盈亏比>1.5",
            "盈亏比>2.0",
            "优质策略(综合评分>0.6且夏普>1且回撤<10%)",
            "高收益策略(总收益>20%且夏普>1)",
            "低风险策略(最大回撤<5%且夏普>0.5)"
        ])
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        toolbar_layout.addWidget(QtWidgets.QLabel("筛选条件:"))
        toolbar_layout.addWidget(self.filter_combo)

        toolbar_layout.addStretch()

        # 导出按钮
        export_button = QtWidgets.QPushButton("导出CSV")
        export_button.clicked.connect(self.export_csv)
        toolbar_layout.addWidget(export_button)

        # 导出详细报告按钮
        export_detail_button = QtWidgets.QPushButton("导出详细报告")
        export_detail_button.clicked.connect(self.export_detailed_report)
        toolbar_layout.addWidget(export_detail_button)

        main_layout.addLayout(toolbar_layout)

        # 创建表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(12)
        self.table.setRowCount(len(self.result_values))
        self.table.setHorizontalHeaderLabels([
            "参数",
            "综合评分",
            "夏普比率",
            "EWM Sharpe",
            "最大回撤(%)",
            "胜率",
            "盈亏比",
            "获利因子",
            "卡尔马比率",
            "索提诺比率",
            "总收益率(%)",
            "平均持仓时间(天)"
        ])

        # 启用排序和双击编辑
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)

        # 设置表格样式
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # 填充数据
        self.populate_table()

        # 初始按综合评分降序排序
        self.table.sortItems(1, QtCore.Qt.DescendingOrder)

        main_layout.addWidget(self.table)

        # 状态栏
        self.status_label = QtWidgets.QLabel(f"共 {len(self.result_values)} 条结果")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

    def populate_table(self):
        """填充表格数据"""
        for n, tp in enumerate(self.result_values):
            setting = tp[0]
            statistics = tp[2]

            # 参数
            setting_cell = QtWidgets.QTableWidgetItem(str(setting))
            self.table.setItem(n, 0, setting_cell)

            # 各项指标
            indicators = [
                ("overall_rating", 1, 4),
                ("sharpe_ratio", 2, 2),
                ("ewm_sharpe", 3, 2),
                ("max_ddpercent", 4, 2),
                ("win_rate", 5, 2, True),  # 百分比格式
                ("average_win_loss_ratio", 6, 2),
                ("profit_factor", 7, 2),
                ("calmar_ratio", 8, 2),
                ("sortino_ratio", 9, 2),
                ("total_return", 10, 2),
                ("average_holding_time_days", 11, 2)
            ]

            for indicator_data in indicators:
                key = indicator_data[0]
                col = indicator_data[1]
                decimals = indicator_data[2]
                is_percentage = len(indicator_data) > 3 and indicator_data[3]

                value = statistics.get(key, 0)
                
                cell = NumericTableWidgetItem()
                cell.setData(QtCore.Qt.DisplayRole, float(value))
                
                if is_percentage:
                    cell.setText(f"{value:.{decimals}%}")
                else:
                    cell.setText(f"{value:.{decimals}f}")
                
                # 不设置背景色，使用默认颜色

                self.table.setItem(n, col, cell)

        # 调整列宽
        self.table.resizeColumnsToContents()

    def on_header_clicked(self, logical_index):
        """处理表头点击事件"""
        if self.current_sort_column == logical_index:
            self.is_ascending = not self.is_ascending
        else:
            self.is_ascending = False
            self.current_sort_column = logical_index

        self.table.sortItems(
            logical_index,
            QtCore.Qt.AscendingOrder if self.is_ascending else QtCore.Qt.DescendingOrder
        )

    def on_item_double_clicked(self, item):
        """双击显示详细信息"""
        row = item.row()
        if row < len(self.result_values):
            statistics = self.result_values[row][2]
            self.show_detailed_statistics(statistics)

    def show_detailed_statistics(self, statistics):
        """显示详细统计信息"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("详细统计信息")
        dialog.resize(600, 800)

        layout = QtWidgets.QVBoxLayout()
        
        # 创建文本显示区域
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        
        # 格式化统计信息
        text = self.format_detailed_statistics(statistics)
        text_edit.setPlainText(text)
        
        layout.addWidget(text_edit)
        
        # 关闭按钮
        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec_()

    def format_detailed_statistics(self, statistics):
        """格式化详细统计信息"""
        lines = []
        lines.append("=" * 50)
        lines.append("详细回测统计报告")
        lines.append("=" * 50)
        
        # 基础信息
        lines.append("\n【基础信息】")
        lines.append(f"回测期间: {statistics.get('start_date', 'N/A')} - {statistics.get('end_date', 'N/A')}")
        lines.append(f"总交易日: {statistics.get('total_days', 0)}")
        lines.append(f"起始资金: {statistics.get('capital', 0):,.2f}")
        lines.append(f"结束资金: {statistics.get('end_balance', 0):,.2f}")
        
        # 收益指标
        lines.append("\n【收益指标】")
        lines.append(f"总收益率: {statistics.get('total_return', 0):.2f}%")
        lines.append(f"年化收益率: {statistics.get('annual_return', 0):.2f}%")
        lines.append(f"日均收益率: {statistics.get('daily_return', 0):.2f}%")
        
        # 风险指标
        lines.append("\n【风险指标】")
        lines.append(f"最大回撤: {statistics.get('max_drawdown', 0):.2f}")
        lines.append(f"最大回撤百分比: {statistics.get('max_ddpercent', 0):.2f}%")
        lines.append(f"收益标准差: {statistics.get('return_std', 0):.2f}%")
        
        # 风险调整收益指标
        lines.append("\n【风险调整收益指标】")
        lines.append(f"夏普比率: {statistics.get('sharpe_ratio', 0):.2f}")
        lines.append(f"EWM夏普比率: {statistics.get('ewm_sharpe', 0):.2f}")
        lines.append(f"索提诺比率: {statistics.get('sortino_ratio', 0):.2f}")
        lines.append(f"卡尔马比率: {statistics.get('calmar_ratio', 0):.2f}")
        lines.append(f"收益回撤比: {statistics.get('return_drawdown_ratio', 0):.2f}")
        
        # 交易统计
        lines.append("\n【交易统计】")
        lines.append(f"胜率: {statistics.get('win_rate', 0):.2%}")
        lines.append(f"平均盈亏比: {statistics.get('average_win_loss_ratio', 0):.2f}")
        lines.append(f"获利因子: {statistics.get('profit_factor', 0):.2f}")
        lines.append(f"平均每笔盈亏: {statistics.get('average_trade', 0):.2f}")
        lines.append(f"最大连续盈利: {statistics.get('max_consecutive_wins', 0)}")
        lines.append(f"最大连续亏损: {statistics.get('max_consecutive_losses', 0)}")
        lines.append(f"最优仓位比例: {statistics.get('optimal_position_ratio', 0):.2%}")
        
        # 持仓统计
        lines.append("\n【持仓统计】")
        lines.append(f"平均持仓时间: {statistics.get('average_holding_time_days', 0):.2f}天")
        
        # 成本统计
        lines.append("\n【成本统计】")
        lines.append(f"总手续费: {statistics.get('total_commission', 0):,.2f}")
        lines.append(f"总滑点: {statistics.get('total_slippage', 0):,.2f}")
        lines.append(f"总成交金额: {statistics.get('total_turnover', 0):,.2f}")
        lines.append(f"总成交笔数: {statistics.get('total_trade_count', 0)}")
        
        # 综合评分
        lines.append("\n【综合评分】")
        lines.append(f"综合评分: {statistics.get('overall_rating', 0):.4f}")
        
        return "\n".join(lines)


    def apply_filter(self):
        """应用筛选条件"""
        filter_text = self.filter_combo.currentText()
        
        for row in range(self.table.rowCount()):
            should_show = True
            
            try:
                # 获取各列数据
                rating = float(self.table.item(row, 1).text()) if self.table.item(row, 1) else 0
                sharpe = float(self.table.item(row, 2).text()) if self.table.item(row, 2) else 0
                ewm_sharpe = float(self.table.item(row, 3).text()) if self.table.item(row, 3) else 0
                max_dd = abs(float(self.table.item(row, 4).text())) if self.table.item(row, 4) else 100
                win_rate_text = self.table.item(row, 5).text() if self.table.item(row, 5) else "0%"
                win_rate = float(win_rate_text.replace('%', '')) / 100 if '%' in win_rate_text else float(win_rate_text)
                avg_ratio = float(self.table.item(row, 6).text()) if self.table.item(row, 6) else 0
                profit_factor = float(self.table.item(row, 7).text()) if self.table.item(row, 7) else 0
                calmar = float(self.table.item(row, 8).text()) if self.table.item(row, 8) else 0
                sortino = float(self.table.item(row, 9).text()) if self.table.item(row, 9) else 0
                total_return = float(self.table.item(row, 10).text()) if self.table.item(row, 10) else 0
                
                # 应用筛选条件
                if filter_text == "综合评分>0.5":
                    should_show = rating > 0.5
                elif filter_text == "综合评分>0.7":
                    should_show = rating > 0.7
                elif filter_text == "夏普比率>1":
                    should_show = sharpe > 1
                elif filter_text == "夏普比率>1.5":
                    should_show = sharpe > 1.5
                elif filter_text == "最大回撤<5%":
                    should_show = max_dd < 5
                elif filter_text == "最大回撤<10%":
                    should_show = max_dd < 10
                elif filter_text == "胜率>60%":
                    should_show = win_rate > 0.6
                elif filter_text == "胜率>70%":
                    should_show = win_rate > 0.7
                elif filter_text == "获利因子>1.5":
                    should_show = profit_factor > 1.5
                elif filter_text == "获利因子>2.0":
                    should_show = profit_factor > 2.0
                elif filter_text == "盈亏比>1.5":
                    should_show = avg_ratio > 1.5
                elif filter_text == "盈亏比>2.0":
                    should_show = avg_ratio > 2.0
                elif filter_text == "优质策略(综合评分>0.6且夏普>1且回撤<10%)":
                    should_show = rating > 0.6 and sharpe > 1 and max_dd < 10
                elif filter_text == "高收益策略(总收益>20%且夏普>1)":
                    should_show = total_return > 20 and sharpe > 1
                elif filter_text == "低风险策略(最大回撤<5%且夏普>0.5)":
                    should_show = max_dd < 5 and sharpe > 0.5
                    
            except (ValueError, AttributeError):
                should_show = False
            
            self.table.setRowHidden(row, not should_show)
        
        self.update_status_label()

    def update_status_label(self):
        """更新状态标签"""
        visible_count = sum(1 for row in range(self.table.rowCount()) 
                           if not self.table.isRowHidden(row))
        self.status_label.setText(f"显示 {visible_count} / {len(self.result_values)} 条结果")

    def export_csv(self):
        """导出CSV文件"""
        import os
        from datetime import datetime
        
        # 获取当前项目的绝对目录
        # 当前文件路径: /path/to/ATMTrader/vnpy_ctabacktester/ui/enhanced_widget.py
        # 需要向上2级到达项目根目录: /path/to/ATMTrader/
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../vnpy_ctabacktester/ui/
        vnpy_ctabacktester_dir = os.path.dirname(current_file_dir)  # .../vnpy_ctabacktester/
        project_root = os.path.dirname(vnpy_ctabacktester_dir)  # .../ATMTrader/
        results_dir = os.path.join(project_root, "backtests", "results")
        
        # 创建results目录（如果不存在）
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
        
        # 生成默认文件名（包含时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"optimization_results_{timestamp}.csv"
        default_path = os.path.join(results_dir, default_filename)
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出优化结果", default_path, "CSV(*.csv)")

        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # 写入表头
                headers = [self.table.horizontalHeaderItem(i).text() 
                          for i in range(self.table.columnCount())]
                writer.writerow(headers)

                # 写入数据
                for row in range(self.table.rowCount()):
                    if not self.table.isRowHidden(row):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

            QtWidgets.QMessageBox.information(self, "导出成功", f"结果已导出到: {path}")
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "导出失败", f"导出过程中发生错误: {str(e)}")

    def export_detailed_report(self):
        """导出详细报告"""
        import os
        from datetime import datetime
        
        # 获取当前项目的绝对目录
        # 当前文件路径: /path/to/ATMTrader/vnpy_ctabacktester/ui/enhanced_widget.py
        # 需要向上2级到达项目根目录: /path/to/ATMTrader/
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../vnpy_ctabacktester/ui/
        vnpy_ctabacktester_dir = os.path.dirname(current_file_dir)  # .../vnpy_ctabacktester/
        project_root = os.path.dirname(vnpy_ctabacktester_dir)  # .../ATMTrader/
        reports_dir = os.path.join(project_root, "backtests", "reports")
        
        # 创建reports目录（如果不存在）
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # 生成默认文件名（包含时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"optimization_detailed_report_{timestamp}.txt"
        default_path = os.path.join(reports_dir, default_filename)
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出详细报告", default_path, "文本文件(*.txt)")

        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("参数优化详细报告\n")
                f.write("=" * 80 + "\n\n")
                
                for i, tp in enumerate(self.result_values):
                    if not self.table.isRowHidden(i):
                        setting = tp[0]
                        statistics = tp[2]
                        
                        f.write(f"结果 {i+1}: {setting}\n")
                        f.write("-" * 60 + "\n")
                        f.write(self.format_detailed_statistics(statistics))
                        f.write("\n\n")

            QtWidgets.QMessageBox.information(self, "导出成功", f"详细报告已导出到: {path}")

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "导出失败", f"导出过程中发生错误: {str(e)}")


class MonthlyStatisticsChartWidget(QtWidgets.QWidget):
    """月度统计图表组件 - 使用 matplotlib"""

    def __init__(self):
        super().__init__()
        self.monthly_data = None
        self.canvas = None
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

    def update_data(self, monthly_statistics):
        """更新月度统计数据"""
        if monthly_statistics is None:
            return

        # 如果是 DataFrame，转换为 dict
        if hasattr(monthly_statistics, 'to_dict'):
            # DataFrame 转换为 dict，每行作为一个字典
            self.monthly_data = monthly_statistics.to_dict('index')
        else:
            self.monthly_data = monthly_statistics

        self.plot_chart()

    def plot_chart(self):
        """绘制图表"""
        if not self.monthly_data:
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import matplotlib
            matplotlib.use('Qt5Agg')

            # 清除旧的 canvas
            if self.canvas:
                self.layout().removeWidget(self.canvas)
                self.canvas.deleteLater()
                self.canvas = None

            # 准备数据
            months = []
            pnl_values = []

            for month, stats in sorted(self.monthly_data.items()):
                if isinstance(stats, dict):
                    months.append(str(month))
                    pnl_values.append(stats.get('total_pnl', 0))

            if not months:
                return

            # 创建图表
            fig = Figure(figsize=(8, 4), facecolor='white')
            ax = fig.add_subplot(111)
            ax.set_facecolor('white')

            # 绘制柱状图
            colors = ['green' if v >= 0 else 'red' for v in pnl_values]
            ax.bar(months, pnl_values, color=colors, alpha=0.7)

            # 设置样式
            ax.set_ylabel('盈亏 (元)', fontsize=10)
            ax.set_xlabel('月份', fontsize=10)
            ax.set_title('月度统计', fontsize=12, fontweight='bold')
            ax.tick_params(labelsize=9)
            ax.grid(True, alpha=0.3)

            # 添加零线
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

            # 旋转 x 轴标签
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            fig.tight_layout()

            # 创建 canvas 并添加到布局
            self.canvas = FigureCanvas(fig)
            self.layout().addWidget(self.canvas)
            self.canvas.draw()

        except Exception as e:
            print(f"绘制月度统计图表失败: {e}")

    def clear_data(self):
        """清空数据"""
        self.monthly_data = None
        if self.canvas:
            self.layout().removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None


class IntervalStatisticsChartWidget(QtWidgets.QWidget):
    """半小时区间统计图表组件 - 使用 matplotlib"""

    def __init__(self):
        super().__init__()
        self.interval_data = None
        self.canvas = None
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

    def update_data(self, interval_statistics):
        """更新区间统计数据"""
        if interval_statistics is None:
            return

        # 如果是 DataFrame，转换为 dict
        if hasattr(interval_statistics, 'to_dict'):
            # DataFrame 转换为 dict，每行作为一个字典
            self.interval_data = interval_statistics.to_dict('index')
        else:
            self.interval_data = interval_statistics

        self.plot_chart()

    def plot_chart(self):
        """绘制图表"""
        if not self.interval_data:
            return

        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            import matplotlib
            matplotlib.use('Qt5Agg')

            # 清除旧的 canvas
            if self.canvas:
                self.layout().removeWidget(self.canvas)
                self.canvas.deleteLater()
                self.canvas = None

            # 准备数据
            intervals = []
            pnl_values = []

            for interval, stats in sorted(self.interval_data.items()):
                if isinstance(stats, dict):
                    intervals.append(str(interval))
                    pnl_values.append(stats.get('total_pnl', 0))

            if not intervals:
                return

            # 创建图表
            fig = Figure(figsize=(10, 4), facecolor='white')
            ax = fig.add_subplot(111)
            ax.set_facecolor('white')

            # 绘制柱状图
            colors = ['green' if v >= 0 else 'red' for v in pnl_values]
            ax.bar(intervals, pnl_values, color=colors, alpha=0.7)

            # 设置样式
            ax.set_ylabel('盈亏 (元)', fontsize=10)
            ax.set_xlabel('时间区间', fontsize=10)
            ax.set_title('半小时区间统计', fontsize=12, fontweight='bold')
            ax.tick_params(labelsize=9)
            ax.grid(True, alpha=0.3)

            # 添加零线
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

            # 旋转 x 轴标签
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            fig.tight_layout()

            # 创建 canvas 并添加到布局
            self.canvas = FigureCanvas(fig)
            self.layout().addWidget(self.canvas)
            self.canvas.draw()

        except Exception as e:
            print(f"绘制区间统计图表失败: {e}")

    def clear_data(self):
        """清空数据"""
        self.interval_data = None
        if self.canvas:
            self.layout().removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None
