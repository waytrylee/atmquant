# AI模块配置文件说明

本文档说明 ATMTrader AI 模块的配置文件系统。

## 配置文件概览

AI 模块使用集中式配置管理，所有硬编码参数都已迁移到配置文件中。这样做的好处：

- ✅ **灵活性**: 修改配置文件即可调整参数，无需修改代码
- ✅ **一致性**: 所有模块使用统一的配置，避免参数不一致
- ✅ **可维护性**: 配置和代码分离，易于维护和版本控制
- ✅ **可扩展性**: 添加新的交易模式、指标参数只需修改配置文件

## 配置文件列表

### 1. [ai_prompt_components.py](ai_prompt_components.py)

**用途**: 提示词组件配置，用于 AI 策略引擎的提示词构建

**包含内容**:
- `PROMPT_COMPONENTS`: 8个提示词组件（角色定义、交易模式指导、风险指南等）
- `FUNCTION_CALLING_SCHEMA`: Function Calling 定义
- `INDICATOR_THRESHOLDS`: 9个技术指标阈值（EMA、RSI、ATR、ADX等）
- `DATA_PROCESSING`: 5个数据处理参数
- `INTERVAL_NAMES`: 10个周期名称映射（中文）
- `INTERVAL_ORDER`: 周期顺序列表
- `POSITION_SIZING`: 仓位计算配置
- `TREND_ANALYSIS`: 趋势分析描述

**使用场景**:
- 自定义 AI 提示词内容
- 调整技术指标阈值（如 RSI 超买超卖线）
- 修改数据处理参数（如显示的 K 线数量）

**示例**:
```python
# 修改 RSI 阈值
INDICATOR_THRESHOLDS = {
    "rsi_overbought": 75,  # 从 70 改为 75
    "rsi_oversold": 25,    # 从 30 改为 25
    # ...
}
```

### 2. [ai_strategy_config.py](ai_strategy_config.py)

**用途**: AI 策略引擎配置，包含风险管理、交易模式、AI 参数等

**包含内容**:
- `RISK_LIMITS`: 风险限制（硬限制 + 软限制）
- `TRADING_MODES`: 3种交易模式配置（激进、保守、剥头皮）
- `AI_CONFIG`: AI 配置参数
- `RISK_MANAGEMENT`: 风险管理参数
- `POSITION_SIZING`: 仓位计算参数
- `DECISION_VALIDATION`: 决策验证参数
- `DECISION_PARSING`: 决策解析参数
- `DECISION_EXECUTION`: 决策执行参数
- `SYMBOL_SELECTION`: 品种选择参数

**使用场景**:
- 调整风险控制参数（最大持仓、仓位比例、止损止盈）
- 自定义交易模式
- 修改 AI 决策参数

**示例**:
```python
# 修改保守模式的参数
TRADING_MODES = {
    "conservative": {
        "position_size_range": (0.05, 0.15),  # 降低仓位范围
        "min_confidence": 0.75,               # 提高置信度要求
        "stop_loss_pct": 0.015,               # 收紧止损
        # ...
    },
}
```

### 3. [ai_backtest_config.py](ai_backtest_config.py)

**用途**: AI 回测引擎配置，包含回测参数、存储配置、检查点配置等

**包含内容**:
- `BACKTEST_DEFAULTS`: 10个回测默认参数
- `STORAGE_CONFIG`: 8个存储配置（目录、文件名）
- `CHECKPOINT_CONFIG`: 4个检查点配置
- `ACCOUNT_CONFIG`: 账户配置
- `MULTI_TIMEFRAME_CONFIG`: 多周期配置
- `CACHE_CONFIG`: 缓存配置
- `API_COST_ESTIMATION`: API 成本估算参数

**使用场景**:
- 修改回测默认参数（初始资金、决策间隔、手续费等）
- 自定义存储路径和文件名
- 调整检查点保存频率

**示例**:
```python
# 修改回测默认参数
BACKTEST_DEFAULTS = {
    "initial_balance": 200000,      # 增加初始资金
    "decision_interval": 10,        # 降低决策频率
    "fee_rate": 0.00005,            # 降低手续费率
    # ...
}
```

### 4. [ai_indicators_config.py](ai_indicators_config.py)

**用途**: 技术指标配置，包含指标参数、时间周期映射、默认合约规格等

**包含内容**:
- `INDICATOR_PARAMS`: 5个技术指标参数（EMA、MACD、RSI、ATR、ADX）
- `DATAFEED_CONFIG`: 数据源配置
- `TIMEFRAME_DURATION_MS`: 10个时间周期映射（毫秒）
- `DEFAULT_CONTRACT_SPECS`: 默认合约规格
- `BAR_AGGREGATION_WINDOWS`: K 线聚合窗口
- `TREND_THRESHOLDS`: 趋势判断阈值

**使用场景**:
- 修改技术指标参数（如 EMA 周期、RSI 周期）
- 添加新的时间周期
- 调整默认合约规格

**示例**:
```python
# 修改 EMA 参数
INDICATOR_PARAMS = {
    "ema": {
        "fast": 10,  # 从 12 改为 10
        "slow": 30,  # 从 26 改为 30
    },
    # ...
}
```

## 配置文件依赖关系

```
ai_prompt_components.py
    ↓ (被引用)
prompts/builder.py

ai_strategy_config.py
    ↓ (被引用)
risk/limits.py
modes/modes.py
engine.py

ai_backtest_config.py
    ↓ (被引用)
config.py
account.py

ai_indicators_config.py
    ↓ (被引用)
config.py
datafeed.py
```

## 配置修改指南

### 1. 修改配置文件

直接编辑配置文件中的参数值：

```python
# config/ai_strategy_config.py
RISK_LIMITS = {
    "hard_limits": {
        "max_positions": 5,  # 从 3 改为 5
        # ...
    },
}
```

### 2. 重启应用

配置文件在模块导入时加载，修改后需要重启应用才能生效：

```bash
# 重启主程序
python main.py

# 或重新运行回测脚本
python scripts/run_ai_backtest.py
```

### 3. 验证配置

可以通过以下方式验证配置是否生效：

```python
# 验证风险限制
from config.ai_strategy_config import RISK_LIMITS
print(RISK_LIMITS["hard_limits"]["max_positions"])  # 应该输出 5

# 验证回测默认值
from config.ai_backtest_config import BACKTEST_DEFAULTS
print(BACKTEST_DEFAULTS["initial_balance"])  # 应该输出修改后的值
```

## 配置最佳实践

### 1. 版本控制

建议将配置文件纳入版本控制，但要注意：

```bash
# 提交配置文件
git add config/ai_*.py
git commit -m "feat: 调整风险参数"

# 不要提交包含敏感信息的配置
# 如 API key 应该通过环境变量或 .env 文件管理
```

### 2. 环境隔离

为不同环境使用不同的配置：

```python
# config/ai_strategy_config.py
import os

# 根据环境变量选择配置
ENV = os.getenv("TRADING_ENV", "production")

if ENV == "development":
    RISK_LIMITS = {
        "hard_limits": {
            "max_positions": 1,  # 开发环境限制更严格
            # ...
        },
    }
else:
    RISK_LIMITS = {
        "hard_limits": {
            "max_positions": 3,  # 生产环境
            # ...
        },
    }
```

### 3. 配置验证

添加配置验证逻辑，确保参数合法：

```python
# config/ai_strategy_config.py
def validate_risk_limits():
    """验证风险限制配置"""
    hard_limits = RISK_LIMITS["hard_limits"]

    assert hard_limits["max_positions"] > 0, "max_positions 必须大于 0"
    assert 0 < hard_limits["max_position_value"] <= 1, "max_position_value 必须在 (0, 1] 范围内"
    assert 0 < hard_limits["min_confidence"] <= 1, "min_confidence 必须在 (0, 1] 范围内"

    print("✅ 风险限制配置验证通过")

# 在模块加载时验证
validate_risk_limits()
```

### 4. 配置文档

为每个配置项添加详细的注释：

```python
RISK_LIMITS = {
    "hard_limits": {
        # 最大持仓品种数
        # 说明：同时持有的品种数量上限，超过此值系统将拒绝开仓
        # 建议：新手 1-2，有经验 3-5
        "max_positions": 3,

        # 单品种最大仓位比例
        # 说明：单个品种占用资金的最大比例，范围 (0, 1]
        # 建议：保守 0.2，激进 0.3-0.5
        "max_position_value": 0.3,
        # ...
    },
}
```

## 常见问题

### Q1: 修改配置后不生效？

**A**: 配置文件在模块导入时加载，需要重启应用。如果使用 Jupyter Notebook，需要重启 kernel。

### Q2: 如何恢复默认配置？

**A**: 从 git 仓库恢复原始配置文件：

```bash
git checkout config/ai_strategy_config.py
```

### Q3: 配置文件可以动态加载吗？

**A**: 当前版本在模块导入时加载配置。如需动态加载，可以添加 reload 函数：

```python
# 在配置文件中添加
def reload_config():
    """重新加载配置"""
    import importlib
    import sys

    # 重新导入模块
    if 'config.ai_strategy_config' in sys.modules:
        importlib.reload(sys.modules['config.ai_strategy_config'])
```

### Q4: 如何为不同策略使用不同配置？

**A**: 可以在策略初始化时传入自定义配置：

```python
from core.ai_strategy_engine.engine import AIStrategyEngine, AIStrategyConfig

# 为特定策略创建自定义配置
custom_config = AIStrategyConfig(
    max_position_size=0.5,  # 覆盖默认值
    trading_mode="conservative",  # 通过trading_mode设置min_confidence
)

engine = AIStrategyEngine(custom_config)
```

## 相关文档

- [AI 回测模块 README](../core/ai_backtester/README.md)
- [AI 策略引擎 README](../core/ai_strategy_engine/README.md)
- [项目主 README](../README.md)
- [CLAUDE.md 开发指南](../CLAUDE.md)
