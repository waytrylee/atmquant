#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化数据格式化器

将量化数据格式化为AI可读的文本，用于插入用户提示词。
"""

from core.ai_strategy_engine.quantitative.data_provider import (
    OIChangeData,
    PriceChangeData,
    MarketRankingData,
)


class QuantitativeDataFormatter:
    """量化数据格式化器

    将量化数据格式化为AI提示词中的文本。
    """

    # 趋势描述常量
    _OI_TREND_DESC = {
        "rapidly_increasing": "[快速] 增长（资金大量流入）",
        "increasing": "[稳步] 增长（资金持续流入）",
        "stable": "[稳定]",
        "decreasing": "[减少] 资金流出",
        "rapidly_decreasing": "[快速减少] 资金大量流出",
    }

    def format_oi_change(self, oi_data: OIChangeData) -> str:
        """格式化持仓量变化数据

        Args:
            oi_data: 持仓量变化数据

        Returns:
            str: 格式化后的文本
        """
        lines = [
            f"### {oi_data.symbol} 持仓量变化",
            "",
            f"**当前持仓量**: {oi_data.current_oi:,}手",
            f"**20日平均**: {oi_data.oi_avg_20:,}手",
            "",
            "**持仓量变化**:",
        ]

        if oi_data.oi_delta_1h != 0:
            lines.append(f"- 1小时: {oi_data.oi_delta_1h:+,}手 ({oi_data.oi_delta_1h_pct:+.2f}%)")
        if oi_data.oi_delta_4h != 0:
            lines.append(f"- 4小时: {oi_data.oi_delta_4h:+,}手 ({oi_data.oi_delta_4h_pct:+.2f}%)")
        if oi_data.oi_delta_24h != 0:
            lines.append(f"- 24小时: {oi_data.oi_delta_24h:+,}手 ({oi_data.oi_delta_24h_pct:+.2f}%)")

        # 趋势解读
        trend = oi_data.get_oi_trend()
        lines.append("")
        lines.append(f"**趋势**: {self._OI_TREND_DESC.get(trend, '未知')}")

        # OI解读
        lines.append("")
        lines.append("**OI变化解读**:")
        price_24h = getattr(oi_data, 'price_change_24h_pct', 0)
        if oi_data.oi_delta_24h_pct > 2 and price_24h > 1:
            lines.append("- OI增加 + 价格上涨 = **强多头趋势**（新多单开仓）")
        elif oi_data.oi_delta_24h_pct > 2 and price_24h < -1:
            lines.append("- OI增加 + 价格下跌 = **强空头趋势**（新空单开仓）")
        elif oi_data.oi_delta_24h_pct < -2 and price_24h > 1:
            lines.append("- OI减少 + 价格上涨 = **空头平仓**（可能反转）")
        elif oi_data.oi_delta_24h_pct < -2 and price_24h < -1:
            lines.append("- OI减少 + 价格下跌 = **多头平仓**（可能反转）")
        else:
            lines.append("- OI变化不明显，观望")

        return "\n".join(lines)

    def format_price_change(self, price_data: PriceChangeData) -> str:
        """格式化价格变化数据

        Args:
            price_data: 价格变化数据

        Returns:
            str: 格式化后的文本
        """
        lines = [
            f"### {price_data.symbol} 价格变化",
            "",
            f"**当前价格**: {price_data.current_price:.2f}元/吨",
            "",
            "**价格变化**:",
        ]

        if price_data.price_delta_1h_pct != 0:
            lines.append(f"- 1小时: {price_data.price_delta_1h_pct:+.2f}%")
        if price_data.price_delta_4h_pct != 0:
            lines.append(f"- 4小时: {price_data.price_delta_4h_pct:+.2f}%")
        if price_data.price_delta_24h_pct != 0:
            lines.append(f"- 24小时: {price_data.price_delta_24h_pct:+.2f}%")

        if price_data.volatility_20d > 0:
            lines.append("")
            lines.append(f"**20日波动率**: {price_data.volatility_20d:.2f}%")

        return "\n".join(lines)

    def format_market_ranking(self, ranking_data: MarketRankingData) -> str:
        """格式化市场排名数据

        Args:
            ranking_data: 市场排名数据

        Returns:
            str: 格式化后的文本
        """
        sections = []

        # OI增长榜
        if ranking_data.oi_growth_top:
            sections.append("## 持仓量增长榜")
            sections.append("")
            for i, item in enumerate(ranking_data.oi_growth_top[:5], 1):
                category_tag = f" [{item.category}]" if item.category else ""
                sections.append(
                    f"{i}. {item.symbol}{category_tag}: "
                    f"{item.change_pct:+.2f}% ({item.value:+,}手)"
                )
            sections.append("")

        # 价格涨幅榜
        if ranking_data.price_gainer_top:
            sections.append("## 价格涨幅榜")
            sections.append("")
            for i, item in enumerate(ranking_data.price_gainer_top[:5], 1):
                category_tag = f" [{item.category}]" if item.category else ""
                sections.append(
                    f"{i}. {item.symbol}{category_tag}: "
                    f"{item.change_pct:+.2f}%"
                )
            sections.append("")

        # 成交活跃榜
        if ranking_data.volume_active_top:
            sections.append("## 成交活跃榜")
            sections.append("")
            for i, item in enumerate(ranking_data.volume_active_top[:5], 1):
                category_tag = f" [{item.category}]" if item.category else ""
                sections.append(
                    f"{i}. {item.symbol}{category_tag}: "
                    f"{item.value:,.0f}手"
                )

        return "\n".join(sections)

    def format_oi_interpretation_guide(self) -> str:
        """格式化OI解读指南

        Returns:
            str: OI解读指南
        """
        return """## 持仓量(OI)变化解读指南

持仓量(OI)是指未平仓合约的总和。OI变化可以反映资金流向和市场趋势：

- **OI增加 + 价格上涨** = 强多头趋势（新多单开仓，资金流入做多）
- **OI增加 + 价格下跌** = 强空头趋势（新空单开仓，资金流入做空）
- **OI减少 + 价格上涨** = 空头平仓（空头止损离场，可能反转）
- **OI减少 + 价格下跌** = 多头平仓（多头止损离场，可能反转）

**关键原则**：
1. 结合价格变化一起分析OI变化，才能判断趋势真实性
2. OI增加表示资金流入，趋势可能更持续
3. OI减少表示资金流出，趋势可能减弱或反转
4. 关注OI异常变化（±5%以上）作为交易信号"""


def format_oi_for_prompt(oi_data: OIChangeData) -> str:
    """快捷函数：格式化OI数据用于提示词

    Args:
        oi_data: OI变化数据

    Returns:
        str: 格式化后的文本
    """
    formatter = QuantitativeDataFormatter()
    return formatter.format_oi_change(oi_data)


def format_ranking_for_prompt(ranking_data: MarketRankingData) -> str:
    """快捷函数：格式化市场排名数据用于提示词

    Args:
        ranking_data: 市场排名数据

    Returns:
        str: 格式化后的文本
    """
    formatter = QuantitativeDataFormatter()
    return formatter.format_market_ranking(ranking_data)
