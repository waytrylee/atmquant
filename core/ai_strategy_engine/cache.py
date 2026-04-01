#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI决策缓存系统

从core/ai_backtester/aicache.py迁移，实现SHA256哈希的决策缓存。
避免在相同上下文下重复调用AI模型，节省API成本和时间。

使用方式：
    from core.ai_strategy_engine.cache import AICache, compute_cache_key

    # 创建缓存实例
    cache = AICache(cache_path=".cache/ai_cache.json")

    # 讣算缓存键
    key = compute_cache_key(context, "default", datetime.now())

    # 检查缓存
    cached = cache.get(key)
    if cached:
        return cached

    # 缓存新决策
    cache.put(key, "default", datetime.now(), decision)
"""

import json
import hashlib
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from threading import RLock
from loguru import logger


@dataclass
class CachedDecision:
    """缓存的AI决策"""
    key: str
    variant: str
    datetime: datetime
    decision: Dict[str, Any]

    def to_dict(self) -> Dict:
        """转换为字典（序列化为ISO格式）"""
        return {
            "key": self.key,
            "variant": self.variant,
            "datetime": self.datetime.isoformat(),
            "decision": self.decision
        }


class AICache:
    """AI决策缓存管理器

    使用SHA256哈希作为缓存键，包含：
    - 提示词变体
    - 时间戳
    - 完整的上下文数据（账户、持仓、市场数据等）

    支持跨回测共享缓存，降低API调用成本。

    特性：
    - 线程安全（使用RLock）
    - 持久化存储（JSON格式）
    - 自动加载已有缓存
    """

    def __init__(self, cache_path: Optional[str] = None):
        """初始化缓存管理器

        Args:
            cache_path: 缓存文件路径（默认为ai_cache.json）
        """
        self.cache_path = cache_path or "ai_cache.json"
        self.entries: Dict[str, CachedDecision] = {}
        self.lock = RLock()

        # 加载已有缓存
        self._load()
        logger.info(f"AICache初始化完成，缓存路径: {self.cache_path}")

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的决策

        Args:
            cache_key: 缓存键（SHA256哈希）

        Returns:
            Optional[Dict]: 缓存的决策，如果不存在返回None
        """
        with self.lock:
            if cache_key in self.entries:
                entry = self.entries[cache_key]
                return entry.decision
            return None

    def put(
        self,
        cache_key: str,
        variant: str,
        datetime_obj: datetime,
        decision: Dict[str, Any]
    ) -> None:
        """保存决策到缓存

        Args:
            cache_key: 缓存键
            variant: 提示词变体
            datetime_obj: 时间（datetime对象）
            decision: AI决策结果
        """
        with self.lock:
            entry = CachedDecision(
                key=cache_key,
                variant=variant,
                datetime=datetime_obj,
                decision=decision
            )
            self.entries[cache_key] = entry

            # 保存到磁盘
            self._save()

    def _save(self) -> None:
        """保存缓存到磁盘"""
        try:
            data = {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "entries": [e.to_dict() for e in self.entries.values()]
            }

            path = Path(self.cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存AI缓存失败: {e}")

    def _load(self) -> None:
        """从磁盘加载缓存"""
        try:
            path = Path(self.cache_path)
            if not path.exists():
                return

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 恢复entries
            loaded_count = 0
            for entry_data in data.get("entries", []):
                # 支持多种时间格式（向后兼容）
                dt = entry_data.get("datetime") or entry_data.get("timestamp")
                if isinstance(dt, str):
                    # ISO 格式字符串
                    dt = datetime.fromisoformat(dt)
                elif isinstance(dt, int):
                    # 毫秒时间戳（向后兼容）
                    dt = datetime.fromtimestamp(dt / 1000)
                elif not isinstance(dt, datetime):
                    # 跳过无效条目
                    continue

                entry = CachedDecision(
                    key=entry_data["key"],
                    variant=entry_data["variant"],
                    datetime=dt,
                    decision=entry_data["decision"]
                )
                self.entries[entry.key] = entry
                loaded_count += 1

            logger.info(f"从缓存加载了 {loaded_count} 条记录")

        except Exception as e:
            logger.warning(f"加载AI缓存失败: {e}")

    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.entries.clear()
        self._save()
        logger.info("缓存已清空")

    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.entries)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                "total_entries": len(self.entries),
                "cache_path": str(self.cache_path),
                "variants": list(set(e.variant for e in self.entries.values()))
            }


def compute_cache_key(
    context: Dict[str, Any],
    variant: str,
    datetime_obj: datetime
) -> str:
    """计算缓存键

    基于市场数据和指标生成SHA256哈希。
    **关键**：只包含"输入"信息，不包含"状态"信息（账户、持仓），
    这样相同时间点的回测才能命中缓存。

    Args:
        context: 决策上下文
        variant: 提示词变体
        datetime_obj: 时间（datetime对象）

    Returns:
        str: SHA256哈希字符串（64字符）
    """
    def _normalize_for_cache(obj: Any) -> Any:
        """嵌套指标字典等结构稳定序列化（浮点四舍五入）。"""
        if isinstance(obj, dict):
            return {k: _normalize_for_cache(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (list, tuple)):
            return [_normalize_for_cache(x) for x in obj]
        if isinstance(obj, float):
            return round(obj, 4)
        if isinstance(obj, (int, str, bool)) or obj is None:
            return obj
        return str(obj)

    # 构建用于哈希的payload
    # 只包含"输入"信息，不包含"状态"信息
    market = context.get("market", {})
    indicators = context.get("indicators", {})

    payload = {
        # 提示词变体（影响AI输出）
        "variant": variant,
        # 时间（相同时间应该命中缓存）
        "datetime": datetime_obj.isoformat(),
        # 品种
        "symbol": context.get("symbol", market.get("symbol", "")),
        # 市场数据（输入）
        "market": {
            "current_price": round(market.get("current_price", 0), 2),
            "open": round(market.get("open", 0), 2),
            "high": round(market.get("high", 0), 2),
            "low": round(market.get("low", 0), 2),
            "volume": market.get("volume", 0),
        },
        # 技术指标（嵌套：ema/sma/macd/rsi/dmi/boll/atr）
        "indicators": _normalize_for_cache(indicators),
    }

    # 转换为JSON并计算哈希
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    hash_bytes = hashlib.sha256(payload_str.encode()).digest()
    return hash_bytes.hex()


def create_ai_cache(cache_path: Optional[str] = None) -> AICache:
    """创建AI缓存实例（工厂函数）

    Args:
        cache_path: 缓存文件路径

    Returns:
        AICache: 缓存管理器实例
    """
    return AICache(cache_path=cache_path)
