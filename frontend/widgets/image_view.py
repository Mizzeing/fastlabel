"""ImageView - 图像查看器

封装 Canvas，提供工具栏、缩放控件和模式切换。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolBar,
    QToolButton, QLabel, QSlider, QAction, QButtonGroup,
    QFrame, QSizePolicy, QSpinBox,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize,
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont,
)
from typing import Optional
import numpy as np

from .canvas import Canvas, Mode
from backend.annotation.shape import Shape


class ImageView(QWidget):
    """图像查看器 - 包含画布和导航工具栏"""

    mode_changed = pyqtSignal(str)
    annotation_added = pyqtSignal(object)
    annotation_selected = pyqtSignal(object)
    annotation_changed = pyqtSignal()
    image_changed = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        # 连接 Canvas 信号
        self.canvas.mode_changed.connect(self.mode_changed.emit)
        self.canvas.annotation_added.connect(self.annotation_added.emit)
        self.canvas.annotation_selected.connect(self.annotation_selected.emit)
        self.canvas.annotation_changed.connect(self.annotation_changed.emit)
        self.canvas.image_changed.connect(self.image_changed.emit)
        self.canvas.status_message.connect(self.status_message.emit)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 工具条 ──
        toolbar = QFrame()
        toolbar.setFrameShape(QFrame.StyledPanel)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3d3d3d;
            }
            QToolButton {
                color: #cccccc;
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 4px 8px;
                margin: 2px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #3d3d3d;
                border-color: #555555;
            }
            QToolButton:checked {
                background-color: #0d6efd;
                color: white;
            }
            QLabel {
                color: #aaaaaa;
                font-size: 12px;
                padding: 0 8px;
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.setSpacing(2)

        # 模式按钮组
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        self._select_btn = QToolButton()
        self._select_btn.setText("选择 (S)")
        self._select_btn.setCheckable(True)
        self._select_btn.setChecked(True)
        self._select_btn.setToolTip("选择/编辑模式 [S]")
        self._mode_group.addButton(self._select_btn, 0)

        self._draw_btn = QToolButton()
        self._draw_btn.setText("绘制 (W)")
        self._draw_btn.setCheckable(True)
        self._draw_btn.setToolTip("绘制矩形框 [W]")
        self._mode_group.addButton(self._draw_btn, 1)

        self._pan_btn = QToolButton()
        self._pan_btn.setText("平移 (H)")
        self._pan_btn.setCheckable(True)
        self._pan_btn.setToolTip("平移视图 [H]")
        self._mode_group.addButton(self._pan_btn, 2)

        self._mode_group.buttonClicked[int].connect(self._on_mode_clicked)

        toolbar_layout.addWidget(self._select_btn)
        toolbar_layout.addWidget(self._draw_btn)
        toolbar_layout.addWidget(self._pan_btn)
        toolbar_layout.addWidget(self._make_separator())

        # 缩放控件
        toolbar_layout.addWidget(QLabel("缩放:"))

        self._zoom_out_btn = QToolButton()
        self._zoom_out_btn.setText("-")
        self._zoom_out_btn.setToolTip("缩小 (Ctrl+-)")
        self._zoom_out_btn.clicked.connect(self._zoom_out)
        self._zoom_out_btn.setFixedSize(28, 28)
        toolbar_layout.addWidget(self._zoom_out_btn)

        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(10, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.valueChanged.connect(self._on_slider_zoom)
        toolbar_layout.addWidget(self._zoom_slider)

        self._zoom_in_btn = QToolButton()
        self._zoom_in_btn.setText("+")
        self._zoom_in_btn.setToolTip("放大 (Ctrl+=)")
        self._zoom_in_btn.clicked.connect(self._zoom_in)
        self._zoom_in_btn.setFixedSize(28, 28)
        toolbar_layout.addWidget(self._zoom_in_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(50)
        toolbar_layout.addWidget(self._zoom_label)

        self._fit_btn = QToolButton()
        self._fit_btn.setText("适应")
        self._fit_btn.setToolTip("适应窗口 (双击)")
        self._fit_btn.clicked.connect(self._fit_window)
        toolbar_layout.addWidget(self._fit_btn)

        toolbar_layout.addStretch()

        # 图片导航
        toolbar_layout.addWidget(self._make_separator())
        self._nav_label = QLabel("0 / 0")
        toolbar_layout.addWidget(self._nav_label)

        layout.addWidget(toolbar)

        # ── 画布 ──
        self.canvas = Canvas()
        layout.addWidget(self.canvas, 1)

    def _make_separator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #555555;")
        sep.setFixedWidth(2)
        return sep

    def _on_mode_clicked(self, idx: int):
        modes = [Mode.SELECT, Mode.DRAW, Mode.PAN]
        if 0 <= idx < len(modes):
            self.canvas.set_mode(modes[idx])

    def set_mode(self, mode: str):
        self.canvas.set_mode(mode)
        self.sync_mode_buttons(mode)

    def sync_mode_buttons(self, mode: str):
        """同步工具栏按钮状态（不触发 canvas.set_mode，避免循环）"""
        idx_map = {Mode.SELECT: 0, Mode.DRAW: 1, Mode.PAN: 2}
        idx = idx_map.get(mode, 0)
        for i in range(3):
            btn = self._mode_group.button(i)
            if btn:
                btn.setChecked(i == idx)

    def load_image(self, image_array: np.ndarray):
        self.canvas.load_image(image_array)

    def update_annotations(self, annotations: list, selected=None):
        self.canvas.update_annotations(annotations, selected)

    def set_image_nav(self, current: int, total: int):
        self._nav_label.setText(f"{current + 1} / {total}")

    # ── 缩放操作 ──

    def _zoom_in(self):
        self.canvas._scale *= 1.2
        self.canvas._scale = min(50.0, self.canvas._scale)
        self._sync_zoom_slider()
        self.canvas.update()

    def _zoom_out(self):
        self.canvas._scale /= 1.2
        self.canvas._scale = max(0.1, self.canvas._scale)
        self._sync_zoom_slider()
        self.canvas.update()

    def _fit_window(self):
        self.canvas._fit_to_widget()
        self._sync_zoom_slider()
        self.canvas.update()

    def _on_slider_zoom(self, value: int):
        self.canvas._scale = value / 100.0
        self._zoom_label.setText(f"{value}%")
        self.canvas.update()

    def _sync_zoom_slider(self):
        pct = int(self.canvas._scale * 100)
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(pct)
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{pct}%")

    @property
    def canvas_widget(self) -> Canvas:
        return self.canvas
