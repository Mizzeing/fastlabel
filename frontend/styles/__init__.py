"""样式加载模块

将分散的 .qss 文件合并加载，供 app.setStyleSheet() 使用。
"""

from pathlib import Path
from typing import Optional

# 按加载顺序排列的样式文件列表（后面文件可覆盖前面文件的选择器）
_QSS_FILES = [
    "base.qss",
    "components.qss",
    "dialogs.qss",
    "docks.qss",
    "canvas.qss",
]

_cache: Optional[str] = None


def load_styles() -> str:
    """加载所有 .qss 样式文件并合并为一个样式字符串

    Returns:
        合并后的完整样式字符串，适合传给 app.setStyleSheet()
    """
    global _cache
    if _cache is not None:
        return _cache

    styles_dir = Path(__file__).resolve().parent
    parts: list[str] = []

    for fname in _QSS_FILES:
        path = styles_dir / fname
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
        else:
            print(f"[styles] 警告: 未找到样式文件 {fname}")

    _cache = "\n".join(parts)
    return _cache


def reload_styles() -> str:
    """清除缓存并重新加载（用于调试/开发）"""
    global _cache
    _cache = None
    return load_styles()
