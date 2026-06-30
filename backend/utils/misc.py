"""Miscellaneous utility functions"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# ── 颜色工具 ──

# 预定义标注颜色
ANNOTATION_COLORS = [
    '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
    '#FF8000', '#80FF00', '#0080FF', '#FF0080', '#8000FF', '#00FF80',
    '#FF4040', '#40FF40', '#4040FF', '#FFFF40', '#FF40FF', '#40FFFF',
    '#FF8040', '#80FF40', '#4080FF', '#FF4080', '#8040FF', '#40FF80',
]

def get_class_color(class_id: int) -> str:
    """根据类别 ID 获取颜色"""
    return ANNOTATION_COLORS[class_id % len(ANNOTATION_COLORS)]

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """十六进制颜色转 RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r: int, g: int, b: int) -> str:
    """RGB 转十六进制颜色"""
    return f'#{r:02x}{g:02x}{b:02x}'

# ── 路径工具 ──

def ensure_dir(path: str) -> Path:
    """确保目录存在"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_project_dir() -> Path:
    """获取项目根目录下的 projects 目录"""
    base = Path.cwd() / 'projects'
    base.mkdir(parents=True, exist_ok=True)
    return base

# ── 快捷键 ──

# 默认快捷键映射
DEFAULT_SHORTCUTS = {
    'next_image': 'D',          # 下一张
    'prev_image': 'A',          # 上一张
    'save': 'Ctrl+S',           # 保存
    'undo': 'Ctrl+Z',           # 撤销
    'redo': 'Ctrl+Shift+Z',     # 重做
    'delete': 'Delete',         # 删除选中
    'zoom_in': 'Ctrl+=',        # 放大
    'zoom_out': 'Ctrl+-',       # 缩小
    'fit_window': 'Ctrl+0',     # 适应窗口
    'select_mode': 'S',         # 选择模式
    'draw_mode': 'W',           # 绘制模式
    'next_class': 'Tab',        # 下一个类别
    'prev_class': 'Shift+Tab',  # 上一个类别
    'confirm': 'Enter',         # 确认
    'cancel': 'Escape',         # 取消
}
