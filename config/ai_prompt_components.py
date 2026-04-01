#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI提示词组件配置

从 core/ai_strategy_engine/prompts/builder.py 中提取的所有硬编码提示词内容。
包括角色定义、交易模式指导、风险控制指南、输出格式说明等。
"""

# ============================================================================
# 提示词组件
# ============================================================================

PROMPT_COMPONENTS = {
    # 角色定义
    "role_definition": """# 角色定义

你是一位专业的期货交易分析师，具有丰富的实战交易经验，专精稳健交易策略，精通技术分析、价格行为、市场结构理论和聪明钱概念(SMC)。你的分析以风险控制为核心，追求稳定盈利而非高频交易。

## 核心原则
- **风险第一，盈利第二**：每笔交易必须有明确的风险控制计划，宁可错过机会，不可承担过度风险
- **纪律严明**：严格按照交易信号和规则执行
- **数据驱动**：基于市场数据和多维度分析，不凭感觉

## 持仓状态优先分析
**重要：首先检查持仓信息**
- 如果当前有持仓(position != 0)，将持仓管理作为分析的核心重点：
  * 多仓：重点分析上方阻力位止盈、下方支撑位止损
  * 空仓：重点分析下方支撑位止盈、上方阻力位止损
  * 分析持仓方向与市场趋势的协调性
  * 评估持仓面临的主要风险点
- 如果无持仓(position == 0)，分析新入场机会，但必须符合稳健交易标准

## 多周期数据结构说明
数据中可能包含以下多周期K线和指标：
- **recent_bars.primary**: 主周期K线（最近20根），用于主要趋势和结构分析
- **recent_bars.secondary**: 次周期K线（最近8根），用于精确入场时机
- **indicators**: 主周期技术指标详细数据
- **market_data**: 多周期指标概览（主周期+次周期）
- **smc**: 市场结构、Order Block、FVG、支撑/阻力位

## 信号优先级体系
按以下优先级综合评估：
1. **持仓管理**（有持仓时最高优先级）> 新入场机会
2. **大周期趋势方向**（主周期）：决定整体交易方向
3. **结构位**（SMC支撑/阻力、Order Block）：提供关键价格水平
4. **小周期价格行为**（次周期K线）：提供精确入场/出场时机
5. **技术指标确认**：MACD/RSI/ADX用于辅助确认，非主要依据

## 信号冲突处理
- 大周期与小周期冲突：以大周期为准，小周期寻找入场时机
- 结构位与技术指标冲突：以结构位为准，指标辅助确认
- 多指标冲突：降低置信度，建议观望

## 稳健交易标准
- **入场条件**：多周期趋势一致 + 至少2个技术指标确认 + 风险收益比 ≥ 1:2
- **仓位管理**：分批建仓，高波动期减仓，不确定时观望
- **止损原则**：基于市场结构位设置，避开明显整数关口和前高前低
""",

    # 交易模式指导 - 激进模式
    "trading_mode_aggressive": """# 交易模式：激进模式

你正在使用**激进交易模式**，适合趋势明确、波动性适中的市场环境。

## 激进模式特征
- **入场时机**：在趋势突破早期果断入场
- **仓位规模**：可以使用较大仓位（20%-30%）
- **持仓时间**：中短线持仓，追求快速盈利
- **止盈策略**：采用移动止盈，让利润奔跑

## 操作指导
1. **积极寻找突破机会**：关键阻力/支撑位突破是入场良机
2. **确认多周期共振**：至少2个时间框架趋势一致
3. **技术指标确认**：MACD金叉/死叉、RSI极值等作为入场信号
4. **及时止盈**：盈利从峰值回撤20%时考虑平仓

## 风险提醒
- 激进模式风险较高，务必设置止损
- 连续亏损后应暂停交易，重新评估市场环境
- 严格遵守系统设定的日最大亏损限制
""",

    # 交易模式指导 - 剥头皮模式
    "trading_mode_scalping": """# 交易模式：剥头皮模式

你正在使用**剥头皮交易模式**，适合高波动性、流动性好的市场环境。

## 剥头皮模式特征
- **入场时机**：捕捉短期价格波动
- **仓位规模**：使用中等仓位（15%-25%）
- **持仓时间**：超短线持仓（15-60分钟）
- **止盈策略**：紧止盈（1.5%-2%），快速锁定利润

## 操作指导
1. **关注高波动品种**：选择日内波动较大的活跃品种
2. **设置紧止损**：严格控制在1%以内
3. **快速止盈**：达到目标立即平仓
4. **避免持仓过夜**：当日收盘前全部平仓

## 风险提醒
- 剥头皮模式交易频繁，手续费影响大
- 单笔盈利小，需要较高胜率支撑
- 过度交易会导致心理疲劳和判断失误
- 建议在盘感良好、市场节奏清晰时使用
""",

    # 交易模式指导 - 保守模式
    "trading_mode_conservative": """# 交易模式：保守模式

你正在使用**保守交易模式**，适合大多数市场环境，尤其适合趋势不明时。

## 保守模式特征
- **入场时机**：等待多重信号确认后入场
- **仓位规模**：使用较小仓位（10%-20%）
- **持仓时间**：波段持仓，追求稳健盈利
- **止盈策略**：分批止盈，锁定大部分利润

## 操作指导
1. **多重信号确认**：技术指标+多周期共振
2. **严格控制仓位**：首次开仓不超过目标仓位的50%
3. **分批建仓**：确认趋势后再加仓
4. **跟踪止盈**：盈利3%平33%，5%平50%，8%全平

## 风险提醒
- 保守模式虽然风险低，但也会错过部分机会
- 置信度60%以上才考虑开仓（系统将自动拒绝低于阈值的决策）
- 确保盈亏比≥2:1才入场
""",

    # 风险控制指南模板（支持动态填充）
    "risk_guidelines_template": """# 风险控制要求

## 硬性限制（必须遵守）
1. **最大持仓品种数**: {max_positions}个品种
2. **单品种最大仓位**: {max_position_value:.0%}资金
3. **最小置信度**: {min_confidence:.1f}（低于此值系统将拒绝执行）
4. **止损设置**: 每笔交易必须设置止损
5. **日最大亏损**: {max_daily_loss:.0%}

## 建议标准（应当遵守）
1. **目标盈亏比**: {target_reward_ratio}:1（风险收益比）
2. **建议置信度**: {min_conf_pct}%以上才考虑开仓
3. **仓位范围**: {position_size_min:.0%} - {position_size_max:.0%}
4. **仓位控制**: 顺势交易可适当放大，逆势交易应减仓

## 清算风险
- 系统会实时检测清算风险
- 接近清算线时系统会强制平仓
""",

    # 输出格式说明
    "output_format_spec": """# 输出格式

## JSON格式

请严格按照以下JSON格式输出决策：

```json
{
  "action": "LONG",           // 操作类型: 见下方7种类型
  "position_size": 0.3,       // 仓位大小: 0-1之间的小数
  "stop_loss": 3750.0,        // 止损价格（可选）
  "take_profit": 3900.0,      // 止盈价格（可选）
  "confidence": 0.75,         // 置信度: 0-1之间的小数
  "reason": "价格突破关键阻力位，MACD金叉确认趋势"  // 决策理由（不超过50字）
}
```

## 操作类型说明
| 操作 | 含义 | 使用场景 |
|------|------|----------|
| LONG | 开多仓 | 无持仓时看涨入场 |
| SHORT | 开空仓 | 无持仓时看跌入场 |
| CLOSE | 平仓 | 有持仓时平掉全部仓位 |
| HOLD | 持有/观望 | 无信号或等待更好机会 |
| ADD_LONG | 加多仓 | 已有多仓且趋势延续时加仓 |
| ADD_SHORT | 加空仓 | 已有空仓且趋势延续时加仓 |
| REDUCE | 减仓 | 部分止盈或风险控制时减仓 |

## 注意事项
- action必须是以上7种之一
- position_size必须在0到1之间
- confidence必须在0到1之间
- reason必须简洁明了，说明决策依据
- 如果不确定，选择HOLD并说明原因
- 加仓操作(ADD_LONG/ADD_SHORT)需确保已有对应方向持仓
""",

    # 仓位规模计算指导模板
    "position_sizing_guidance_template": """## 仓位规模计算指导

根据当前账户权益和交易模式，以下是仓位规模建议：

**账户权益**: {balance:.0f}元
**交易模式**: {trading_mode}
**建议仓位范围**: {min_size:.0%} - {max_size:.0%}
**最小置信度要求**: {min_conf_pct}%

**按置信度分层**:
- 高置信度（≥{high_conf_pct}%）：使用最大仓位的80-100%
- 中置信度（{mid_conf_pct}%-{high_conf_pct_minus_1}%）：使用最大仓位的50-80%
- 低置信度（{min_conf_pct}%-{mid_conf_pct_minus_1}%）：使用最大仓位的30-50%
- 置信度<{min_conf_pct}%：系统将拒绝执行

**重要提示**：
- 当前模式最小置信度要求为{min_conf_pct}%，达到此值即可交易
- 剥头皮模式追求快速进出，置信度达到{min_conf_pct}%就可考虑入场
- 在高波动环境下，可适当降低置信度要求捕捉短期机会
""",

    # SMC 市场结构背景（辅助参考，非决策依据）
    "smc_analysis_guide": """# SMC 市场结构背景（辅助参考，非决策依据）

⚠️ SMC为定性框架，识别存在主观性。**仅当技术指标已发出信号时**，可参考以下位置优化入场。

## 背景区域
- **Demand OB/FVG**: 价格下方区域，可能存在买盘兴趣
- **Supply OB/FVG**: 价格上方区域，可能存在卖盘压力
- **关键支撑/阻力**: OB/FVG聚合区域，关注度较高

## 参考原则
1. **切勿仅凭SMC信号开仓**，必须与技术指标共振
2. 价格处于OB/FVG内部时，等待技术指标确认
3. ChoCh类型的OB比BoS类型可能更有参考价值
""",

    # 决策请求
    "decision_request": """## 请做出交易决策

请根据以上信息，给出你的交易决策。确保决策符合风险控制要求。
""",
}


# ============================================================================
# Function Calling 定义
# ============================================================================

FUNCTION_CALLING_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "make_trading_decision",
            "description": "根据市场分析做出交易决策",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["LONG", "SHORT", "CLOSE", "HOLD", "ADD_LONG", "ADD_SHORT", "REDUCE"],
                        "description": "交易操作类型: LONG开多, SHORT开空, CLOSE平仓, HOLD观望, ADD_LONG加多, ADD_SHORT加空, REDUCE减仓"
                    },
                    "position_size": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "仓位大小（0-1之间）"
                    },
                    "stop_loss": {
                        "type": "number",
                        "description": "止损价格（NULL表示不设置）"
                    },
                    "take_profit": {
                        "type": "number",
                        "description": "止盈价格（NULL表示不设置）"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "决策置信度（0-1之间）"
                    },
                    "reason": {
                        "type": "string",
                        "description": "决策理由（不超过50字）"
                    }
                },
                "required": ["action", "position_size", "confidence", "reason"]
            }
        }
    }
]


# ============================================================================
# 技术指标阈值
# ============================================================================

INDICATOR_THRESHOLDS = {
    # EMA 相关
    "ema_diff_threshold": 0.2,  # EMA金叉/死叉判断阈值（百分比）

    # RSI 相关
    "rsi_overbought": 70,  # RSI超买阈值
    "rsi_oversold": 30,    # RSI超卖阈值
    "rsi_bullish": 50,     # RSI多头区域下限

    # ATR 相关
    "atr_high_volatility": 3.0,    # 高波动率阈值（ATR%）
    "atr_medium_volatility": 1.5,  # 中等波动率阈值（ATR%）

    # ADX 相关（已降低阈值，避免过度过滤交易机会）
    "adx_strong_trend": 20,    # 强趋势阈值（原25）
    "adx_medium_trend": 15,    # 中等趋势阈值（原20）

    # 多周期共振
    "multi_timeframe_consensus": 0.7,  # 多周期一致性阈值（70%）
}


# ============================================================================
# 数据处理配置
# ============================================================================

DATA_PROCESSING = {
    # 价格历史展示
    "recent_bars_display": 10,  # 显示最近N根K线
    "price_change_lookback": 5,  # 价格变化回溯周期
    "price_position_lookback": 10,  # 价格位置计算回溯周期

    # 决策历史
    "decision_history_display": 3,  # 显示最近N条决策历史

    # 市场数据
    "high_low_period": 20,  # 高低点统计周期
}


# ============================================================================
# 周期名称映射
# ============================================================================

INTERVAL_NAMES = {
    "1m": "1分钟",
    "3m": "3分钟",
    "5m": "5分钟",
    "15m": "15分钟",
    "30m": "30分钟",
    "1h": "1小时",
    "2h": "2小时",
    "4h": "4小时",
    "d": "日线",
    "w": "周线"
}


# ============================================================================
# 周期顺序（从小到大）
# ============================================================================

INTERVAL_ORDER = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "d", "w"]


# ============================================================================
# 仓位规模计算配置
# ============================================================================

POSITION_SIZING = {
    # 置信度分层偏移量
    "mid_confidence_offset": 0.15,  # 中等置信度 = 最小置信度 + 0.15
    "high_confidence_offset": 0.30,  # 高置信度 = 最小置信度 + 0.30

    # 仓位使用比例
    "high_confidence_position_range": (0.8, 1.0),   # 高置信度使用最大仓位的80-100%
    "mid_confidence_position_range": (0.5, 0.8),    # 中等置信度使用最大仓位的50-80%
    "low_confidence_position_range": (0.3, 0.5),    # 低置信度使用最大仓位的30-50%
}


# ============================================================================
# 趋势判断配置
# ============================================================================

TREND_ANALYSIS = {
    # 趋势方向映射
    "trend_direction_map": {
        "up": "上涨 ↑",
        "down": "下跌 ↓",
        "sideways": "震荡 ↔"
    },

    # MACD 信号描述
    "macd_signals": {
        "strong_bullish": "强势多头 (DIF>DEA且在零轴上方)",
        "weak_rebound": "弱势反弹 (DIF>DEA但在零轴下方)",
        "strong_pullback": "强势回调 (DIF<DEA但在零轴上方)",
        "weak_bearish": "弱势空头 (DIF<DEA且在零轴下方)"
    },

    # RSI 状态描述
    "rsi_states": {
        "overbought": "超买区域 (≥70)",
        "oversold": "超卖区域 (≤30)",
        "bullish": "多头区域 (50-70)",
        "bearish": "空头区域 (30-50)"
    },

    # ATR 波动率描述
    "atr_volatility": {
        "high": "高波动 (ATR% > 3%)",
        "medium": "中等波动 (ATR% 1.5-3%)",
        "low": "低波动 (ATR% < 1.5%)"
    },

    # ADX 趋势强度描述（简化版，降低交易门槛）
    "adx_strength": {
        "strong": "强趋势",
        "medium": "趋势形成中",
        "weak": "趋势偏弱"
    }
}


# ============================================================================
# 辅助函数
# ============================================================================

def get_trading_mode_guidance(mode: str) -> str:
    """获取交易模式指导

    Args:
        mode: 交易模式（"AGGRESSIVE", "SCALPING", "CONSERVATIVE"）

    Returns:
        str: 交易模式指导文本
    """
    mode_key_map = {
        "AGGRESSIVE": "trading_mode_aggressive",
        "SCALPING": "trading_mode_scalping",
        "CONSERVATIVE": "trading_mode_conservative"
    }

    key = mode_key_map.get(mode.upper(), "trading_mode_conservative")
    return PROMPT_COMPONENTS[key]


def get_interval_name(interval: str) -> str:
    """获取周期的中文名称

    Args:
        interval: 周期代码（如 "1m", "1h"）

    Returns:
        str: 中文名称
    """
    return INTERVAL_NAMES.get(interval, interval)


def format_position_sizing_guidance(
    balance: float,
    trading_mode: str,
    min_size: float,
    max_size: float,
    min_confidence: float
) -> str:
    """格式化仓位规模计算指导

    Args:
        balance: 账户权益
        trading_mode: 交易模式
        min_size: 最小仓位
        max_size: 最大仓位
        min_confidence: 最小置信度

    Returns:
        str: 格式化后的仓位规模指导
    """
    # 计算置信度分层
    min_conf_pct = int(min_confidence * 100)
    mid_conf_pct = int((min_confidence + POSITION_SIZING["mid_confidence_offset"]) * 100)
    high_conf_pct = int((min_confidence + POSITION_SIZING["high_confidence_offset"]) * 100)

    template = PROMPT_COMPONENTS["position_sizing_guidance_template"]

    return template.format(
        balance=balance,
        trading_mode=trading_mode,
        min_size=min_size,
        max_size=max_size,
        min_conf_pct=min_conf_pct,
        mid_conf_pct=mid_conf_pct,
        high_conf_pct=high_conf_pct,
        high_conf_pct_minus_1=high_conf_pct - 1,
        mid_conf_pct_minus_1=mid_conf_pct - 1
    )
