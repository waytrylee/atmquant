#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据字典系统

定义AI需要理解的所有市场数据字段，支持中英文双语。
"""

from .futures_schema import FuturesSchema, FieldDefinition

__all__ = ["FuturesSchema", "FieldDefinition"]
