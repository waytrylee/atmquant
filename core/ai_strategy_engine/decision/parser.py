#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强响应解析器

支持思维链提取和JSON修复的AI决策解析器。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List

from utils.json_repair import extract_json_block, repair_json, safe_json_loads


@dataclass
class ParsedDecision:
    """解析后的决策对象"""
    action: str                   # LONG/SHORT/CLOSE/HOLD
    position_size: float          # 仓位大小
    confidence: float             # 置信度
    reason: str                   # 决策理由
    reasoning: str = ""           # 思维链（新增）
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: dict = field(default_factory=dict)  # 元数据


class EnhancedDecisionParser:
    """增强的决策解析器

    支持：
    1. 思维链提取（支持多种格式）
    2. JSON自动修复
    3. 更健壮的解析逻辑
    4. 安全回退机制
    """

    # 支持的7种操作类型
    VALID_ACTIONS = {
        "LONG",      # 开多
        "SHORT",     # 开空
        "CLOSE",     # 平仓
        "HOLD",      # 持仓
        "ADD_LONG",  # 加多
        "ADD_SHORT", # 加空
        "REDUCE",    # 减仓
    }

    def parse(self, response: Any) -> ParsedDecision:
        """解析AI响应

        Args:
            response: AI原始响应

        Returns:
            ParsedDecision: 包含决策、思维链、元数据的对象
        """
        try:
            # 1. 提取思维链
            reasoning = self._extract_reasoning(response)

            # 2. 提取决策内容
            decision_content = self._extract_decision_content(response)

            # 3. 尝试解析为JSON
            decision_json = self._parse_as_json(decision_content)

            # 4. 验证决策
            decision = self._validate_and_normalize(decision_json)

            # 5. 构建返回对象
            return ParsedDecision(
                action=decision.get("action", "HOLD"),
                position_size=decision.get("position_size", 0),
                confidence=decision.get("confidence", 0.5),
                reason=decision.get("reason", ""),
                reasoning=reasoning,
                stop_loss=decision.get("stop_loss"),
                take_profit=decision.get("take_profit"),
                metadata={
                    "parse_method": decision_json.get("_parse_method", "unknown"),
                    "confidence_score": decision_json.get("_confidence_score", 0.0),
                }
            )
        except Exception as e:
            # 安全回退：返回HOLD决策
            return self._get_safe_fallback_decision(response, str(e))

    def _get_safe_fallback_decision(self, response: Any, error: str) -> ParsedDecision:
        """获取安全回退决策

        当解析失败时，返回一个保守的HOLD决策。

        Args:
            response: AI原始响应
            error: 错误信息

        Returns:
            ParsedDecision: 安全的HOLD决策
        """
        from loguru import logger

        logger.warning(f"JSON解析失败，使用安全回退: {error}")

        # 尝试从响应中提取动作
        action = self._extract_action_from_text(str(response))

        return ParsedDecision(
            action=action,
            position_size=0,
            confidence=0.0,
            reason=f"解析失败，安全持有。错误: {error[:100]}",
            reasoning="",
            metadata={
                "parse_method": "safe_fallback",
                "confidence_score": 0.0,
                "parse_error": error[:200],
            }
        )

    def _extract_reasoning(self, response: Any) -> str:
        """提取思维链

        支持多种格式：
        1. <thinking>标签（Claude）
        2. <reasoning>标签
        3. reasoning/thought_process JSON字段
        4. 特殊标记（"思考过程："、"分析过程："等）

        Args:
            response: AI响应

        Returns:
            str: 提取的思维链文本
        """
        text = str(response)

        # 1. 尝试提取 <thinking> 标签（Claude格式）
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
        if thinking_match:
            return thinking_match.group(1).strip()

        # 2. 尝试提取 <reasoning> 标签
        reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', text, re.DOTALL)
        if reasoning_match:
            return reasoning_match.group(1).strip()

        # 3. 尝试提取JSON字段
        try:
            data = safe_json_loads(text)
            if isinstance(data, dict):
                if "reasoning" in data:
                    return str(data["reasoning"])
                if "thought_process" in data:
                    return str(data["thought_process"])
                if "analysis" in data:
                    return str(data["analysis"])
        except:
            pass

        # 4. 尝试提取特殊标记（中英文）
        patterns = [
            r'思考过程[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
            r'分析过程[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
            r'Reasoning[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
            r'Thought Process[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
            r'Analysis[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
            r'思维链[:：]\s*(.*?)(?=\n\n|\n[A-Z]|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                reasoning = match.group(1).strip()
                # 限制长度
                if len(reasoning) > 2000:
                    reasoning = reasoning[:2000]
                return reasoning

        return ""

    def _extract_decision_content(self, response: Any) -> str:
        """提取决策内容

        从响应中提取包含决策的部分，去除思维链等无关内容。

        Args:
            response: AI响应

        Returns:
            str: 决策内容
        """
        text = str(response)

        # 1. 尝试提取 <decision> 标签
        decision_match = re.search(r'<decision>(.*?)</decision>', text, re.DOTALL)
        if decision_match:
            return decision_match.group(1).strip()

        # 2. 尝试提取JSON代码块
        json_block = extract_json_block(text)
        if json_block:
            return json_block

        # 3. 移除思维链标签
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL)
        text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)

        return text.strip()

    def _parse_as_json(self, content: str) -> dict:
        """解析为JSON（支持自动修复）

        Args:
            content: 待解析内容

        Returns:
            dict: 解析后的决策字典
        """
        # 1. 尝试直接解析
        result = safe_json_loads(content)
        if result:
            result["_parse_method"] = "direct_json"
            return result

        # 2. 尝试从文本中提取决策
        return {
            "_parse_method": "text_fallback",
            "_confidence_score": 0.0,
            "action": self._extract_action_from_text(content),
            "position_size": self._extract_position_size_from_text(content),
            "confidence": self._extract_confidence_from_text(content),
            "reason": self._extract_reason_from_text(content),
        }

    def _validate_and_normalize(self, decision: dict) -> dict:
        """验证并规范化决策

        Args:
            decision: 原始决策字典

        Returns:
            dict: 规范化后的决策
        """
        return {
            "action": self._validate_action(decision.get("action")),
            "position_size": self._validate_position_size(decision.get("position_size")),
            "confidence": self._validate_confidence(decision.get("confidence")),
            "reason": self._validate_reason(decision.get("reason", "")),
            "stop_loss": decision.get("stop_loss"),
            "take_profit": decision.get("take_profit"),
        }

    def _validate_action(self, action: Any) -> str:
        """验证操作类型

        Args:
            action: 原始操作类型

        Returns:
            str: 验证后的操作类型
        """
        if not action:
            return "HOLD"

        action_str = str(action).upper()
        if action_str in self.VALID_ACTIONS:
            return action_str

        # 尝试从文本中提取
        return self._extract_action_from_text(action_str)

    def _validate_position_size(self, position_size: Any) -> float:
        """验证仓位大小

        Args:
            position_size: 原始仓位大小

        Returns:
            float: 验证后的仓位大小（0-1之间）
        """
        if position_size is None:
            return 0.0

        try:
            size = float(position_size)
            # 限制在 0-1 之间
            return max(0.0, min(1.0, size))
        except (ValueError, TypeError):
            return 0.0

    def _validate_confidence(self, confidence: Any) -> float:
        """验证置信度

        Args:
            confidence: 原始置信度

        Returns:
            float: 验证后的置信度（0-1之间）
        """
        if confidence is None:
            return 0.5

        try:
            conf = float(confidence)
            # 限制在 0-1 之间
            return max(0.0, min(1.0, conf))
        except (ValueError, TypeError):
            return 0.5

    def _validate_reason(self, reason: Any) -> str:
        """验证决策理由

        Args:
            reason: 原始理由

        Returns:
            str: 验证后的理由
        """
        if not reason:
            return ""

        reason_str = str(reason).strip()
        # 限制长度
        if len(reason_str) > 200:
            reason_str = reason_str[:200]
        return reason_str

    def _extract_action_from_text(self, text: str) -> str:
        """从文本中提取操作类型（增强版）"""
        text_upper = text.upper()

        # 按优先级查找
        for action in self.VALID_ACTIONS:
            if action in text_upper:
                return action

        # 查找中文关键词
        keywords = {
            "LONG": ["做多", "开多", "买入", "买多", "做多单"],
            "SHORT": ["做空", "开空", "卖出", "卖空", "做空单"],
            "CLOSE": ["平仓", "平多", "平空", "平多单", "平空单", "全部平仓"],
        }

        for action, kw_list in keywords.items():
            if any(kw in text for kw in kw_list):
                return action

        return "HOLD"

    def _extract_position_size_from_text(self, text: str) -> float:
        """从文本中提取仓位大小（增强版）"""
        patterns = [
            r'仓位[:：]\s*([0-9.]+)',
            r'position[:：]\s*([0-9.]+)',
            r'([0-9.]+)%?\s*的仓位',
            r'使用资金\s*的\s*([0-9.]+)%?',
            r'position[_\s]?size[:：]\s*([0-9.]+)',
            r'开仓比例[:：]\s*([0-9.]+)%?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if value > 1:
                    value = value / 100
                return min(max(value, 0), 1)

        return 0.5

    def _extract_confidence_from_text(self, text: str) -> float:
        """从文本中提取置信度（增强版）"""
        patterns = [
            r'置信度[:：]\s*([0-9.]+)',
            r'confidence[:：]\s*([0-9.]+)',
            r'信心[:：]\s*([0-9.]+)',
            r'([0-9.]+)%?\s*的置信度',
            r'置信度\s*([0-9.]+)%?',
            r'把握[:：]\s*([0-9.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if value > 1:
                    value = value / 100
                return min(max(value, 0), 1)

        return 0.5

    def _extract_reason_from_text(self, text: str) -> str:
        """从文本中提取决策理由（增强版）"""
        patterns = [
            r'理由[:：]\s*([^\n。]+)',
            r'reason[:：]\s*([^\n。]+)',
            r'原因[:：]\s*([^\n。]+)',
            r'因为[:：]\s*([^\n。]+)',
            r'依据[:：]\s*([^\n。]+)',
            r'建议[:：]\s*([^\n。]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reason = match.group(1).strip()
                if len(reason) <= 200:
                    return reason

        # 如果没有匹配到，尝试提取决策后面的文本
        decision_pos = -1
        for action in self.VALID_ACTIONS:
            pos = text.upper().find(action)
            if pos != -1:
                decision_pos = max(decision_pos, pos)

        if decision_pos >= 0:
            # 提取决策后的100个字符
            after_decision = text[decision_pos + len(action):decision_pos + len(action) + 100]
            # 移除常见的无关词
            reason = re.sub(r'^(，|,|。|\s)*', '', after_decision)
            reason = reason.split('\n')[0].strip()
            if len(reason) > 10:
                return reason[:100]

        return ""
