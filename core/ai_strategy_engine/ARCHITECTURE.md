## 关键设计决策

### 1. 为什么保留 ai_core？

虽然 `ai_core` 和 `ai_strategy_engine` 有一些重复的组件，但它们服务于不同的场景：

- `ai_strategy_engine` 是**决策引擎**，专注于生成和执行交易决策
- `ai_core` 是**统一接口层**，为实盘策略提供更高级的抽象

### 2. 为什么将 market_analysis_prompts.py 移到 charts/？

这个文件包含的提示词专门用于图表AI分析，不涉及交易决策。将其放在 `core/charts/prompts/` 更符合其用途。

### 3. 继承关系已移除

- `PromptBuilder` 不再继承 `PromptManager`
- `EnhancedDecisionParser` 不再继承 `ResponseParser`

这些类现在是独立的实现，继承关系带来的复杂度已被消除。

### 4. 上下文构建器的位置

- `ContextBuilder` 从 `ai_decision` 移到 `ai_strategy_engine/context/`
- `UnifiedContextBuilder` 和 `MultiSymbolContextBuilder` 保留在 `ai_core/`

这反映了它们的用途：
- `ContextBuilder`: 用于决策引擎的上下文构建
- `UnifiedContextBuilder` 等: 用于实盘策略的统一接口

## 版本历史
## 关键设计决策

### 1. 模块架构

经过合并优化，`ai_core` 已整合到 `ai_strategy_engine`：

- `ai_strategy_engine` 现在同时支持：
  - **回测模式**: 使用 `run_cycle()` 方法
  - **实盘模式**: 使用 `decide()` 方法
- 两种模式共享相同的组件（parser, validator, risk manager）

### 2. 为什么合并？

原先 `ai_core` 是 `ai_strategy_engine` 的冗余封装，两者：
- 使用相同的核心组件
- 有相似的决策流程
- 产生不必要的维护成本

合并后：
- 单一入口点
- 减少代码重复
- 更清晰的架构

### 3. 继承关系已移除

- `PromptBuilder` 不再继承 `PromptManager`
- `EnhancedDecisionParser` 不再继承 `ResponseParser`

### 4. 上下文构建器

`ContextBuilder` 现在同时支持：
- 单品种场景
- 多品种场景（通过 `MultiSymbolContextBuilder` 子类）

## 版本历史

- **2026-03-06**: 合并 `ai_core` 到 `ai_strategy_engine`
- **2026-01-26**: 移除 ai_decision 模块，合并功能到 ai_strategy_engine
- **2026-01-26**: 将 market_analysis_prompts.py 移到 core/charts/prompts/
- **2026-01-26**: 移除 PromptBuilder 和 EnhancedDecisionParser 的继承关系
- **2026-01-26**: 添加 ai_core 模块文档说明
