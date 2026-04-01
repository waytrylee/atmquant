#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略参数管理器

管理策略在不同品种上的最优参数配置，支持：
- 保存批量回测后的最优参数
- 策略初始化时自动加载最优参数
- 界面参数优先级高于配置文件参数
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
from loguru import logger
import re


class StrategyParamManager:
    """策略参数管理器"""

    def __init__(self, config_dir: str = None):
        """
        初始化参数管理器

        Args:
            config_dir: 参数配置文件目录（默认为项目根目录下的 config/strategy_params）
        """
        if config_dir is None:
            # 自动查找项目根目录
            project_root = self._find_project_root()
            config_dir = project_root / "config" / "strategy_params"
        else:
            config_dir = Path(config_dir)

        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _find_project_root(self) -> Path:
        """
        查找项目根目录

        通过查找包含 core/ 目录的父目录来确定项目根目录
        """
        # 从当前文件开始向上查找
        current = Path(__file__).resolve().parent

        # 最多向上查找5层
        for _ in range(5):
            if (current / "core").exists():
                return current
            current = current.parent

        # 如果找不到，返回当前文件的上两级目录（假设在 core/utils/ 下）
        return Path(__file__).resolve().parent.parent.parent

    def get_params(self, strategy_name: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取指定策略和品种的最优参数

        Args:
            strategy_name: 策略名称（如 "kalman_mean_reversion"）
            symbol: 品种代码（如 "rb2605" 或 "rb"）

        Returns:
            最优参数字典，如果不存在则返回 None
        """
        config_file = self.config_dir / f"{strategy_name}.json"

        if not config_file.exists():
            logger.debug(f"参数配置文件不存在: {config_file}")
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 提取品种代码（如 "rb2605" -> "rb"）
            symbol_code = self._extract_symbol_code(symbol)

            # 获取该品种的完整数据（大小写无关匹配）
            symbols = config.get("symbols", {})
            actual_key = self._find_symbol_key(symbols, symbol_code)
            symbol_data = symbols.get(actual_key) if actual_key else None

            if symbol_data:
                # 只返回策略参数，不包含性能指标和元数据
                params = symbol_data.get("params", {})
                logger.debug(f"找到 {strategy_name} 策略 {symbol_code} 品种的最优参数")
                return params
            else:
                logger.debug(f"未找到 {strategy_name} 策略 {symbol_code} 品种的参数配置")
                return None

        except Exception as e:
            logger.error(f"读取参数配置文件失败: {e}")
            return None

    def save_params(
        self,
        strategy_name: str,
        symbol: str,
        params: Dict[str, Any],
        performance: Optional[Dict[str, Any]] = None,
        source: str = ""
    ):
        """
        保存最优参数

        Args:
            strategy_name: 策略名称
            symbol: 品种代码
            params: 参数字典（仅包含策略参数）
            performance: 性能指标（可选）
            source: 参数来源（如 "batch_optimize_20260327"）
        """
        config_file = self.config_dir / f"{strategy_name}.json"

        # 加载现有配置
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 兼容旧格式：如果有 "params" 字段，迁移到 "symbols"
                if "params" in config and "symbols" not in config:
                    config["symbols"] = config.pop("params")
            except Exception as e:
                logger.warning(f"加载现有配置失败，将创建新配置: {e}")
                config = {
                    "strategy": strategy_name,
                    "last_updated": "",
                    "symbols": {}
                }
        else:
            config = {
                "strategy": strategy_name,
                "last_updated": "",
                "symbols": {}
            }

        # 提取品种代码
        symbol_code = self._extract_symbol_code(symbol)

        # 构建新的数据结构（参数、性能、元数据分离）
        symbol_data = {
            "params": params.copy(),  # 纯策略参数
            "performance": performance or {},  # 性能指标
            "metadata": {
                "source": source,
                "updated_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        # 更新配置（优先使用已有的 key，避免大小写不一致产生重复）
        existing_key = self._find_symbol_key(config["symbols"], symbol_code)
        config["symbols"][existing_key or symbol_code] = symbol_data
        config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 保存
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ {symbol_code} 最优参数已保存到 {config_file}")
        except Exception as e:
            logger.error(f"保存参数配置失败: {e}")

    def list_strategies(self) -> list:
        """列出所有有配置的策略"""
        strategies = []
        for config_file in self.config_dir.glob("*.json"):
            strategies.append(config_file.stem)
        return sorted(strategies)

    def list_symbols(self, strategy_name: str) -> list:
        """列出指定策略下所有有配置的品种"""
        config_file = self.config_dir / f"{strategy_name}.json"

        if not config_file.exists():
            return []

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return sorted(config.get("symbols", {}).keys())
        except Exception:
            return []

    def get_all_params(self, strategy_name: str) -> Dict[str, Any]:
        """获取指定策略的所有品种参数配置（完整数据，包含性能指标）"""
        config_file = self.config_dir / f"{strategy_name}.json"

        if not config_file.exists():
            return {}

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"读取配置失败: {e}")
            return {}

    def get_symbol_performance(self, strategy_name: str, symbol: str) -> Optional[Dict]:
        """
        获取某个品种的性能指标

        Args:
            strategy_name: 策略名称
            symbol: 品种代码

        Returns:
            性能指标字典
        """
        config_file = self.config_dir / f"{strategy_name}.json"

        if not config_file.exists():
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            symbol_code = self._extract_symbol_code(symbol)
            symbols = config.get("symbols", {})
            actual_key = self._find_symbol_key(symbols, symbol_code)
            symbol_data = symbols.get(actual_key) if actual_key else None

            if symbol_data:
                return symbol_data.get("performance", {})
            return None

        except Exception as e:
            logger.error(f"读取性能指标失败: {e}")
            return None

    def delete_symbol_params(self, strategy_name: str, symbol: str) -> bool:
        """删除指定品种的参数配置"""
        config_file = self.config_dir / f"{strategy_name}.json"

        if not config_file.exists():
            return False

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            symbol_code = self._extract_symbol_code(symbol)
            symbols = config.get("symbols", {})
            actual_key = self._find_symbol_key(symbols, symbol_code)

            if actual_key:
                del config["symbols"][actual_key]
                config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                logger.info(f"✓ 已删除 {strategy_name} 策略 {symbol_code} 品种的参数配置")
                return True
            else:
                logger.warning(f"未找到 {symbol_code} 品种的参数配置")
                return False

        except Exception as e:
            logger.error(f"删除参数配置失败: {e}")
            return False

    def _extract_symbol_code(self, symbol: str) -> str:
        """
        提取品种代码（rb2605 -> rb）

        Args:
            symbol: 品种代码（可能包含合约月份）

        Returns:
            纯品种代码（大写）
        """
        # 提取字母部分
        match = re.match(r"([A-Za-z]+)", symbol)
        return match.group(1).upper() if match else symbol.upper()

    def _find_symbol_key(self, symbols: dict, symbol_code: str) -> Optional[str]:
        """
        在 symbols 字典中查找匹配的 key（大小写无关）

        Args:
            symbols: JSON 中的 symbols 字典
            symbol_code: 标准化后的品种代码（大写）

        Returns:
            匹配到的实际 key，未找到返回 None
        """
        # 先精确匹配
        if symbol_code in symbols:
            return symbol_code
        # 大小写无关匹配
        target = symbol_code.upper()
        for key in symbols:
            if key.upper() == target:
                return key
        return None


# 全局单例实例
_param_manager_instance = None


def get_param_manager() -> StrategyParamManager:
    """获取参数管理器单例"""
    global _param_manager_instance
    if _param_manager_instance is None:
        _param_manager_instance = StrategyParamManager()
    return _param_manager_instance
