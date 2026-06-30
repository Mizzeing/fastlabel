#!/usr/bin/env python3
"""
FastLabel - AI 辅助标注平台

轻量级目标检测标注工具，围绕「人工标注 → 训练 → 自动标注 → 修正」闭环设计。

第一阶段 (MVP) 功能:
    - 项目管理: 新建/打开/关闭项目
    - 图片浏览: 导入图片，前后切换
    - BBox 标注: 绘制矩形框、选择、移动、调整大小
    - 类别管理: 添加/编辑/删除标注类别
    - YOLO 导出: 导出为 YOLO 格式
    - Undo/Redo: 撤销和重做

使用方式:
    python main.py

依赖:
    pip install -r requirements.txt
"""

import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from frontend.main_window import MainWindow


def main():
    """FastLabel 入口函数"""
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FastLabel")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("FastLabel")

    # 全局样式 (QDarkStyle 轻量版)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
