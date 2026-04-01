#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON修复工具

修复AI响应中常见的JSON格式问题，如中文引号、中文括号等。
实现parseFullDecisionResponse设计。
"""

import json
import re
from typing import Optional


def repair_json(json_str: str) -> str:
    """修复JSON字符串中的常见问题

    修复内容：
    1. 中文引号 → ASCII引号
    2. 中文括号 → ASCII括号
    3. 中文冒号 → ASCII冒号
    4. 中文逗号 → ASCII逗号
    5. 移除不可见字符

    Args:
        json_str: 待修复的JSON字符串

    Returns:
        str: 修复后的JSON字符串
    """
    if not json_str:
        return json_str

    # 1. 移除不可见字符（保留常用符号）
    result = remove_invisible_runes(json_str)

    # 2. 修复字符编码
    result = fix_missing_quotes(result)

    return result


def remove_invisible_runes(text: str) -> str:
    """移除不可见字符

    保留常用ASCII符号和中文，移除其他不可见字符。
    """
    # 保留ASCII可打印字符、中文、常用符号
    pattern = r'[^\x20-\x7E\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\n\r\t]'
    return re.sub(pattern, '', text)


def fix_missing_quotes(s: str) -> str:
    """修复字符编码问题

    将中文标点符号转换为ASCII对应符号。
    """
    # 中文引号 → ASCII引号
    s = s.replace('"', '"')
    s = s.replace('"', '"')
    s = s.replace(''', "'")
    s = s.replace(''', "'")

    # 中文括号 → ASCII括号
    s = s.replace('［', '[')
    s = s.replace('］', ']')
    s = s.replace('｛', '{')
    s = s.replace('｝', '}')
    s = s.replace('（', '(')
    s = s.replace('）', ')')

    # 中文冒号 → ASCII冒号
    s = s.replace('：', ':')

    # 中文逗号 → ASCII逗号
    s = s.replace('，', ',')

    # 中文分号 → ASCII分号
    s = s.replace('；', ';')

    return s


def extract_json_block(text: str) -> Optional[str]:
    """从文本中提取JSON块

    支持多种格式：
    1. ```json ... ``` 代码块
    2. ``` ... ``` 代码块
    3. 裸JSON对象
    4. JSON数组

    Args:
        text: 输入文本

    Returns:
        Optional[str]: 提取的JSON字符串，如果未找到返回None
    """
    # 1. 尝试提取 ```json ... ``` 代码块
    json_block_pattern = r'```json\s*(.*?)\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. 尝试提取 ``` ... ``` 代码块
    code_block_pattern = r'```\s*(.*?)\s*```'
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # 验证是否是JSON
        if content.startswith(('{', '[')):
            return content

    # 3. 尝试提取裸JSON对象（支持嵌套）
    # 匹配从 { 到匹配的 }
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx >= 0:
                return text[start_idx:i+1]

    # 4. 尝试提取JSON数组
    bracket_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '[':
            if bracket_count == 0:
                start_idx = i
            bracket_count += 1
        elif char == ']':
            bracket_count -= 1
            if bracket_count == 0 and start_idx >= 0:
                return text[start_idx:i+1]

    return None


def safe_json_loads(text: str, default: Optional[dict] = None) -> Optional[dict]:
    """安全地解析JSON，支持自动修复

    Args:
        text: JSON文本
        default: 解析失败时返回的默认值

    Returns:
        Optional[dict]: 解析后的字典，失败返回default
    """
    if default is None:
        default = {}

    if not text:
        return default

    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 尝试提取JSON块
    json_block = extract_json_block(text)
    if json_block:
        try:
            return json.loads(json_block)
        except json.JSONDecodeError:
            pass

    # 3. 尝试修复后解析
    try:
        repaired = repair_json(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 4. 尝试提取并修复
    if json_block:
        try:
            repaired = repair_json(json_block)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    return default
