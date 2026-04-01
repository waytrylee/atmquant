#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国期货数据字典

定义所有AI需要理解的市场数据字段。
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List


@dataclass
class FieldDefinition:
    """字段定义

    定义单个数据字段的信息。
    """
    name: str                    # 字段名（代码中使用）
    name_cn: str                 # 中文名
    description: str             # 描述
    formula: Optional[str] = None       # 计算公式
    unit: Optional[str] = None          # 单位
    example: Any = None                 # 示例值

    def to_dict(self) -> dict:
        """转换为字典

        Returns:
            dict: 字段定义字典
        """
        return {
            "name": self.name,
            "display_name": self.name_cn,
            "description": self.description,
            "formula": self.formula,
            "unit": self.unit,
            "example": self.example
        }


class FuturesSchema:
    """中国期货数据字典

    定义所有AI需要理解的市场数据字段。
    """

    # ===== 价格字段 =====
    PRICE_FIELDS: Dict[str, FieldDefinition] = {
        "open": FieldDefinition(
            name="open",
            name_cn="开盘价",
            description="K线周期内的第一笔成交价",
            formula=None,
            unit="元/吨",
            example=3800.0
        ),
        "high": FieldDefinition(
            name="high",
            name_cn="最高价",
            description="K线周期内的最高成交价",
            formula=None,
            unit="元/吨",
            example=3850.0
        ),
        "low": FieldDefinition(
            name="low",
            name_cn="最低价",
            description="K线周期内的最低成交价",
            formula=None,
            unit="元/吨",
            example=3780.0
        ),
        "close": FieldDefinition(
            name="close",
            name_cn="收盘价",
            description="K线周期内的最后一笔成交价",
            formula=None,
            unit="元/吨",
            example=3820.0
        ),
        "volume": FieldDefinition(
            name="volume",
            name_cn="成交量",
            description="K线周期内的成交总量",
            formula="sum(每笔成交量)",
            unit="手",
            example=12500
        ),
        "open_interest": FieldDefinition(
            name="open_interest",
            name_cn="持仓量",
            description="当前未平仓的合约总数",
            formula="sum(所有多头持仓) = sum(所有空头持仓)",
            unit="手",
            example=150000
        ),
    }

    # ===== 技术指标字段 =====
    INDICATOR_FIELDS: Dict[str, FieldDefinition] = {
        "sma": FieldDefinition(
            name="sma",
            name_cn="简单移动平均线",
            description="过去N根K线收盘价的算术平均值",
            formula="SMA(close, N) = sum(close[i-N+1:i+1]) / N",
            unit="元/吨",
            example=3810.0
        ),
        "ema": FieldDefinition(
            name="ema",
            name_cn="指数移动平均线",
            description="对最近价格赋予更大权重的移动平均线",
            formula="EMA(today) = α * close(today) + (1-α) * EMA(yesterday)\nα = 2 / (N + 1)",
            unit="元/吨",
            example=3815.0
        ),
        "macd": FieldDefinition(
            name="macd",
            name_cn="MACD指标",
            description="趋势跟踪动量指标",
            formula="MACD = EMA(12) - EMA(26)\nSignal = EMA(MACD, 9)\nHistogram = MACD - Signal",
            unit="元/吨",
            example=15.5
        ),
        "rsi": FieldDefinition(
            name="rsi",
            name_cn="相对强弱指标",
            description="衡量价格变动的速度和变化",
            formula="RSI = 100 - (100 / (1 + RS))\nRS = 平均涨幅 / 平均跌幅",
            unit="%",
            example=65.3
        ),
        "atr": FieldDefinition(
            name="atr",
            name_cn="平均真实波幅",
            description="衡量市场波动性的指标",
            formula="TR = max(high-low, |high-close_prev|, |low-close_prev|)\nATR = SMA(TR, N)",
            unit="元/吨",
            example=45.0
        ),
        "boll_upper": FieldDefinition(
            name="boll_upper",
            name_cn="布林带上轨",
            description="布林带通道的上边界",
            formula="Upper = SMA(N) + K * StdDev(close, N)\n通常K=2",
            unit="元/吨",
            example=3900.0
        ),
        "boll_middle": FieldDefinition(
            name="boll_middle",
            name_cn="布林带中轨",
            description="布林带通道的中线（即移动平均线）",
            formula="Middle = SMA(N)",
            unit="元/吨",
            example=3820.0
        ),
        "boll_lower": FieldDefinition(
            name="boll_lower",
            name_cn="布林带下轨",
            description="布林带通道的下边界",
            formula="Lower = SMA(N) - K * StdDev(close, N)\n通常K=2",
            unit="元/吨",
            example=3740.0
        ),
    }

    # ===== 账户字段 =====
    ACCOUNT_FIELDS: Dict[str, FieldDefinition] = {
        "balance": FieldDefinition(
            name="balance",
            name_cn="账户总资金",
            description="账户的权益总额",
            formula="总资金 = 可用资金 + 占用保证金 + 浮动盈亏",
            unit="元",
            example=100000.0
        ),
        "available": FieldDefinition(
            name="available",
            name_cn="可用资金",
            description="当前可以用于开仓的资金",
            formula="可用资金 = 总资金 - 占用保证金 - 冻结资金",
            unit="元",
            example=85000.0
        ),
        "position_value": FieldDefinition(
            name="position_value",
            name_cn="持仓市值",
            description="当前持仓的市场价值",
            formula="持仓市值 = 持仓数量 × 当前价格 × 合约乘数",
            unit="元",
            example=50000.0
        ),
        "margin_used": FieldDefinition(
            name="margin_used",
            name_cn="占用保证金",
            description="当前持仓占用的保证金",
            formula="占用保证金 = 持仓市值 / 杠杆倍数",
            unit="元",
            example=10000.0
        ),
        "unrealized_pnl": FieldDefinition(
            name="unrealized_pnl",
            name_cn="浮动盈亏",
            description="当前持仓的未实现盈亏",
            formula="浮动盈亏 = (当前价格 - 开仓价) × 持仓数量 × 合约乘数 × 方向",
            unit="元",
            example=1500.0
        ),
        "total_pnl": FieldDefinition(
            name="total_pnl",
            name_cn="总盈亏",
            description="已平仓盈亏与浮动盈亏的总和",
            formula="总盈亏 = 已平仓盈亏 + 浮动盈亏",
            unit="元",
            example=5000.0
        ),
    }

    # ===== 持仓字段 =====
    POSITION_FIELDS: Dict[str, FieldDefinition] = {
        "symbol": FieldDefinition(
            name="symbol",
            name_cn="品种代码",
            description="期货合约的唯一标识符",
            formula="格式：品种+月份+交易所（如rb2605.SHFE）",
            unit=None,
            example="rb2605.SHFE"
        ),
        "direction": FieldDefinition(
            name="direction",
            name_cn="持仓方向",
            description="持有多头还是空头",
            formula="long=多头（看涨）, short=空头（看跌）",
            unit=None,
            example="long"
        ),
        "size": FieldDefinition(
            name="size",
            name_cn="持仓数量",
            description="持有的合约数量",
            formula=None,
            unit="手",
            example=10
        ),
        "entry_price": FieldDefinition(
            name="entry_price",
            name_cn="开仓价",
            description="建仓时的成交价格",
            formula=None,
            unit="元/吨",
            example=3800.0
        ),
        "current_price": FieldDefinition(
            name="current_price",
            name_cn="当前价",
            description="最新的市场价格",
            formula=None,
            unit="元/吨",
            example=3820.0
        ),
        "deposit_rate": FieldDefinition(
            name="deposit_rate",
            name_cn="保证金率",
            description="开仓所需的保证金比例",
            formula="保证金 = 持仓市值 × 保证金率",
            unit="%",
            example=0.07
        ),
        "liquidation_price": FieldDefinition(
            name="liquidation_price",
            name_cn="强平价",
            description="达到强平条件的价格",
            formula="强平价 = 开仓价 ± (保证金 / 持仓数量 / 合约乘数)",
            unit="元/吨",
            example=3420.0
        ),
    }

    def get_schema_definition(self, category: str) -> Dict[str, dict]:
        """获取指定类别的Schema定义

        Args:
            category: 类别名称 ("PRICE", "INDICATOR", "ACCOUNT", "POSITION")

        Returns:
            dict: 字段定义字典
        """
        field_map = getattr(self, f"{category}_FIELDS", {})
        return {
            name: field.to_dict()
            for name, field in field_map.items()
        }

    def get_full_schema(self) -> str:
        """生成完整的Schema说明（用于插入系统提示词）

        Returns:
            str: 完整的Schema说明文本
        """
        sections = []

        # 1. 字段定义
        for category in ["PRICE", "INDICATOR", "ACCOUNT", "POSITION"]:
            fields = self.get_schema_definition(category)
            section = self._format_schema_section(category, fields)
            sections.append(section)

        # 2. 交易规则（移除OI相关解读）
        sections.append(self._get_trading_rules_without_oi())

        return "\n\n".join(sections)

    def _get_oi_interpretation_guide(self) -> str:
        """获取持仓量(OI)解读指南

        Returns:
            str: OI解读指南
        """
        return """## 持仓量(OI)变化解读

持仓量(OI)是指未平仓合约的总和。OI变化可以反映资金流向和市场趋势真实性：

| OI变化 | 价格变化 | 市场含义 | 操作建议 |
|--------|----------|----------|----------|
| 增加 | 上涨 | **强多头趋势**（新多单开仓，资金流入）| 跟随做多 |
| 增加 | 下跌 | **强空头趋势**（新空单开仓，资金流入）| 跟随做空 |
| 减少 | 上涨 | **空头平仓**（空头止损，可能反转）| 谨慎追多 |
| 减少 | 下跌 | **多头平仓**（多头止损，可能反转）| 谨慎追空 |

**关键原则**：
1. 结合价格变化一起分析OI变化，才能判断趋势真实性
2. OI增加表示资金流入，趋势可能更持续
3. OI减少表示资金流出，趋势可能减弱或反转
4. 关注OI异常变化（±5%以上）作为交易信号
5. OI创历史新高/低时，通常预示着大行情"""

    def _get_trading_rules_without_oi(self) -> str:
        """获取交易规则（不含OI相关内容）

        Returns:
            str: 交易规则
        """
        # 动态获取配置值
        from config.ai_strategy_config import RISK_LIMITS, TRADING_MODES

        max_positions = RISK_LIMITS["hard_limits"]["max_positions"]
        max_position_value = int(RISK_LIMITS["hard_limits"]["max_position_value"] * 100)
        max_daily_loss = int(RISK_LIMITS["hard_limits"]["max_daily_loss"] * 100)
        target_reward_ratio = RISK_LIMITS["soft_limits"]["target_reward_ratio"]

        # 获取默认模式（激进）的置信度阈值
        default_min_conf = TRADING_MODES.get("aggressive", {}).get("min_confidence", 0.55)
        min_conf_pct = int(default_min_conf * 100)

        return f"""## 交易规则与风险控制

### 风险管理规则（硬限制）
| 规则 | 限制 | 说明 |
|------|------|------|
| 最大持仓品种数 | {max_positions}个 | 同时持有的品种数量上限 |
| 单品种最大仓位 | {max_position_value}%资金 | 单个品种的最大仓位比例 |
| 最小置信度 | {default_min_conf:.2f} | 低于此值系统将拒绝执行 |
| 日最大亏损 | {max_daily_loss}% | 达到此限制停止当日交易 |
| 止损设置 | 必须 | 每笔交易必须设置止损 |

### 入场信号标准
| 信号类型 | 条件 | 说明 |
|----------|------|------|
| 成交量放大 | 2倍以上均量 | 放量突破通常意味着强趋势 |
| 多周期共振 | 至少2个周期 | 多时间框架趋势一致时入场 |
| 置信度 | ≥{min_conf_pct}% | 建议置信度{min_conf_pct}%以上才开仓 |

### 出场信号标准
| 信号类型 | 条件 | 说明 |
|----------|------|------|
| 跟踪止盈 | 从峰值回撤30% | 锁定大部分利润 |
| 硬止损 | -{max_daily_loss}% | 严格控制单笔最大损失 |
| 趋势反转 | 价格反向+技术指标背离 | 趋势改变，考虑离场 |

### 仓位控制原则
- **顺势加仓**：只在盈利仓位上加仓，最多加2次
- **分批止盈**：盈利3%平33%，5%平50%，8%全平
- **避免追亏损**：永远不要在亏损仓位上加仓摊平

### 常见错误警告
[WARNING] **错误1**：混淆已实现盈亏和未实现盈亏
- 已实现盈亏已经计入账户余额，不应重复计算

[WARNING] **错误2**：忽略杠杆对盈亏的影响
- 3x杠杆时，价格涨1%，实际盈利约3%

[WARNING] **错误3**：不关注Peak PnL（峰值盈亏）
- 当前PnL接近Peak PnL时，应考虑止盈锁定利润"""

    def _get_trading_rules(self) -> str:
        """获取交易规则

        Returns:
            str: 交易规则
        """
        return """## 交易规则与风险控制

### 风险管理规则（硬限制）
| 规则 | 限制 | 说明 |
|------|------|------|
| 最大持仓品种数 | 3个 | 同时持有的品种数量上限 |
| 单品种最大仓位 | 30%资金 | 单个品种的最大仓位比例 |
| 最小置信度 | 0.5 | 低于此值系统将拒绝执行 |
| 日最大亏损 | 5% | 达到此限制停止当日交易 |
| 止损设置 | 必须 | 每笔交易必须设置止损 |

### 入场信号标准
| 信号类型 | 条件 | 说明 |
|----------|------|------|
| 成交量放大 | 2倍以上均量 | 放量突破通常意味着强趋势 |
| OI显著变化 | 1小时变化>2% | 大额资金进出导致OI显著变化 |
| 多周期共振 | 至少2个周期 | 多时间框架趋势一致时入场 |
| 置信度 | ≥0.7 | 建议置信度0.7以上才开仓 |

### 出场信号标准
| 信号类型 | 条件 | 说明 |
|----------|------|------|
| 跟踪止盈 | 从峰值回撤30% | 锁定大部分利润 |
| 硬止损 | -5% | 严格控制单笔最大损失 |
| 趋势反转 | OI反向+价格反向 | 资金流向改变，考虑离场 |

### 仓位控制原则
- **顺势加仓**：只在盈利仓位上加仓，最多加2次
- **分批止盈**：盈利3%平33%，5%平50%，8%全平
- **避免追亏损**：永远不要在亏损仓位上加仓摊平

### 常见错误警告
[WARNING] **错误1**：混淆已实现盈亏和未实现盈亏
- 已实现盈亏已经计入账户余额，不应重复计算

[WARNING] **错误2**：忽略杠杆对盈亏的影响
- 3x杠杆时，价格涨1%，实际盈利约3%

[WARNING] **错误3**：不关注Peak PnL（峰值盈亏）
- 当前PnL接近Peak PnL时，应考虑止盈锁定利润

[WARNING] **错误4**：忽略持仓量(OI)变化
- 结合OI变化判断趋势的真实性和持续性"""

    def _format_schema_section(self, category: str, fields: Dict[str, dict]) -> str:
        """格式化Schema章节

        Args:
            category: 类别名称
            fields: 字段定义字典

        Returns:
            str: 格式化后的章节文本
        """
        category_names = {
            "PRICE": "## 价格数据",
            "INDICATOR": "## 技术指标",
            "ACCOUNT": "## 账户信息",
            "POSITION": "## 持仓信息"
        }

        category_name = category_names.get(category, f"## {category}")
        lines = [category_name, "\n"]

        for field_name, field_def in fields.items():
            lines.append(f"### {field_def['display_name']} (`{field_name}`)")
            lines.append(f"- **说明**: {field_def['description']}")
            if field_def['formula']:
                lines.append(f"- **计算公式**: ```\n{field_def['formula']}\n```")
            if field_def['unit']:
                lines.append(f"- **单位**: {field_def['unit']}")
            lines.append(f"- **示例值**: `{field_def['example']}`\n")

        return "\n".join(lines)


# 创建全局实例
futures_schema = FuturesSchema()
