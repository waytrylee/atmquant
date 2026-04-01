#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理工具
提供emoji过滤等文本处理功能
"""

import re


def remove_emojis(text: str) -> str:
    """
    移除文本中的emoji字符

    注意：此函数只移除真正的emoji表情符号，不影响中文、标点符号和Markdown标记

    Args:
        text: 输入文本

    Returns:
        移除emoji后的文本
    """
    if not isinstance(text, str):
        return str(text) if text else ""

    # 限制文本大小，避免内存问题
    if len(text) > 500000:  # 如果文本超过500KB，截断它
        text = text[:500000] + "\n\n... (内容过长，已截断)"

    try:
        # Emoji pattern - 只匹配真正的emoji表情符号
        # 使用更精确的范围，避免误删中文和标点符号
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons (😀-🙏)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs (🌀-🗿)
            "\U0001F680-\U0001F6FF"  # transport & map symbols (🚀-🛿)
            "\U0001F1E0-\U0001F1FF"  # flags (🇦-🇿)
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs (🤀-🧿)
            "\U0001FA00-\U0001FA6F"  # Chess Symbols (🨀-🩯)
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A (🩰-🫿)
            "\U00002600-\U000026FF"  # Miscellaneous Symbols (☀-⛿)
            "\U00002700-\U000027BF"  # Dingbats (✀-➿)
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended (🞀-🟿)
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C (🠀-🡿)
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text)
    except Exception as e:
        print(f"移除emoji时出错: {e}")
        return text
