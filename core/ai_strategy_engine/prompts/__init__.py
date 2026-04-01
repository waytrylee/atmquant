#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提示词管理模块

整合数据字典和风险指南，生成完整的系统提示词和用户提示词。
"""

from .builder import PromptBuilder

__all__ = ["PromptBuilder"]
