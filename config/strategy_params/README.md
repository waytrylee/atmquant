# 策略参数自动加载系统

## 概述

这套系统用于管理策略在不同品种上的最优参数配置，支持：
- ✅ 批量回测后自动保存最优参数
- ✅ 策略初始化时自动加载最优参数
- ✅ 界面参数优先级高于配置文件参数
- ✅ 所有策略自动支持（继承自 BaseCtaStrategy）

## 参数优先级

```
界面参数 > 配置文件参数 > 默认参数
```

- **界面参数**：在 CTA 回测界面手动设置的参数（最高优先级）
- **配置文件参数**：批量回测后保存的最优参数
- **默认参数**：策略类中定义的默认值

## 使用方式

### 1. 保存最优参数

在批量回测脚本中，找到最优参数后调用保存方法：

```python
from core.utils.strategy_param_manager import get_param_manager

# 获取参数管理器
param_manager = get_param_manager()

# 保存最优参数
param_manager.save_params(
    strategy_name="kalman_mean_reversion",  # 策略名称（下划线格式）
    symbol="rb",                            # 品种代码
    params={
        "bar_window": 60,
        "boll_period": 20,
        "rsi_oversold": 30.0,
        # ... 其他参数
    },
    performance={
        "sharpe": 1.85,      # 性能指标（可选）
        "total_pnl": 25000,
        "win_rate": 0.62,
    },
    source="batch_optimize_20260327"  # 来源标识
)
```

### 2. 策略自动加载

策略初始化时会自动加载最优参数，**无需任何代码修改**：

```python
# 创建策略实例
strategy = KalmanMeanReversionStrategy(
    cta_engine=engine,
    strategy_name="test",
    vt_symbol="rb2605.SHFE",
    setting={}  # 空字典 -> 自动加载配置文件参数
)

# 参数已自动加载
print(strategy.bar_window)    # 60 (从配置文件加载)
print(strategy.boll_period)   # 20 (从配置文件加载)
```

### 3. 界面参数优先

```python
# 在回测界面设置部分参数
setting = {
    "bar_window": 30,      # 界面设置
    "rsi_oversold": 25.0,  # 界面设置
}

strategy = KalmanMeanReversionStrategy(
    cta_engine=engine,
    strategy_name="test",
    vt_symbol="rb2605.SHFE",
    setting=setting
)

print(strategy.bar_window)      # 30 (使用界面值)
print(strategy.boll_period)     # 20 (从配置文件加载)
print(strategy.rsi_oversold)    # 25.0 (使用界面值)
print(strategy.stop_loss_atr)   # 2.0 (从配置文件加载)
```

## 管理工具

### 查看所有策略参数

```bash
python scripts/manage_strategy_params.py list
```

输出示例：
```
策略: kalman_mean_reversion
  最后更新: 2026-03-27 13:20:38
  品种数量: 3
  - RB     | 1h   | Sharpe: 1.85   | PnL: ¥25,000      | WinRate: 62.0%
  - UR     | 15m  | Sharpe: 1.52   | PnL: ¥18,500      | WinRate: 58.0%
  - L      | 15m  | Sharpe: 1.53   | PnL: ¥19,846      | WinRate: 59.6%
```

### 查看单个品种详细参数

```bash
python scripts/manage_strategy_params.py show kalman_mean_reversion rb
```

输出示例：
```
【交易参数】
  bar_window                = 60
  boll_period               = 20
  rsi_oversold              = 30.0
  ...

【性能指标】
  sharpe                    = 1.85
  total_pnl                 = ¥25,000
  win_rate                  = 62.0%
  ...

【来源信息】
  source                    = batch_optimize_20260327
  updated_time              = 2026-03-27 13:20:38
```

### 导出参数到文件

```bash
python scripts/manage_strategy_params.py export kalman_mean_reversion
```

### 删除品种参数

```bash
python scripts/manage_strategy_params.py delete kalman_mean_reversion rb
```

## 配置文件格式

参数保存在 `config/strategy_params/` 目录下，每个策略一个 JSON 文件：

```json
{
  "strategy": "kalman_mean_reversion",
  "last_updated": "2026-03-27 13:20:38",
  "params": {
    "RB": {
      "bar_window": 60,
      "boll_period": 20,
      "rsi_oversold": 30.0,
      "sharpe": 1.85,
      "total_pnl": 25000,
      "win_rate": 0.62,
      "source": "batch_optimize_20260327"
    },
    "UR": {
      ...
    }
  }
}
```

## 集成到批量回测脚本

### 方式1：在优化循环中保存

```python
from core.utils.strategy_param_manager import get_param_manager

symbols = ["rb", "UR", "l", "MA", "jm"]
param_manager = get_param_manager()

for symbol in symbols:
    # 执行优化
    best_params, performance = optimize_symbol(symbol)

    # 保存最优参数
    param_manager.save_params(
        strategy_name="kalman_mean_reversion",
        symbol=symbol,
        params=best_params,
        performance=performance,
        source=f"batch_optimize_{datetime.now().strftime('%Y%m%d')}"
    )

    print(f"✓ {symbol} 最优参数已保存")
```

### 方式2：手动整理后保存

参考 [scripts/example_save_optimized_params.py](scripts/example_save_optimized_params.py)

## 注意事项

1. **策略命名规则**：
   - `KalmanMeanReversionStrategy` → `kalman_mean_reversion`
   - `BollRSIStrategy` → `boll_rsi`
   - 自动转换，无需手动指定

2. **品种代码提取**：
   - `rb2605` → `RB`
   - `UR405` → `UR`
   - 自动提取字母部分并大写

3. **参数类型转换**：
   - 自动根据策略默认参数类型进行转换
   - 支持布尔值、整数、浮点数、字符串

4. **不影响回测界面**：
   - 界面参数永远优先
   - 配置文件只提供"智能默认值"

## 测试验证

运行测试脚本验证功能：

```bash
python scripts/test_param_auto_loading.py
```

## 示例文件

- [参数管理器](core/utils/strategy_param_manager.py)
- [基类实现](core/strategies/base_strategy.py)
- [管理工具](scripts/manage_strategy_params.py)
- [示例脚本](scripts/example_save_optimized_params.py)
- [测试脚本](scripts/test_param_auto_loading.py)
