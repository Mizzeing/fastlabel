"""PropertyDock - 属性面板

显示和编辑选中标注的详细属性。
"""

from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QCheckBox, QGroupBox, QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from typing import Optional, Dict, List, Callable

from backend.annotation.shape import Shape
from backend.annotation.bbox import BBox
from backend.annotation.polygon import Polygon


class PropertyDock(QDockWidget):
    """属性面板 - 显示/编辑选中标注的属性"""

    # 信号
    property_changed = pyqtSignal()  # 属性已被修改

    def __init__(self, parent=None):
        super().__init__("属性", parent)
        self._shape: Optional[Shape] = None
        self._classes: List[Dict] = []
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self):
        self.setMinimumWidth(200)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── 标注 ID ──
        self._id_label = QLabel("未选中")
        self._id_label.setObjectName("property_id_label")
        layout.addWidget(self._id_label)

        # ── 位置属性 ──
        pos_group = QGroupBox("位置（归一化）")
        pos_group.setObjectName("property_pos_group")
        pos_layout = QFormLayout(pos_group)
        pos_layout.setSpacing(4)

        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(0, 1)
        self._x_spin.setDecimals(4)
        self._x_spin.setSingleStep(0.01)
        self._x_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addRow("X:", self._x_spin)

        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(0, 1)
        self._y_spin.setDecimals(4)
        self._y_spin.setSingleStep(0.01)
        self._y_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addRow("Y:", self._y_spin)

        self._w_spin = QDoubleSpinBox()
        self._w_spin.setRange(0, 1)
        self._w_spin.setDecimals(4)
        self._w_spin.setSingleStep(0.01)
        self._w_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addRow("W:", self._w_spin)

        self._h_spin = QDoubleSpinBox()
        self._h_spin.setRange(0, 1)
        self._h_spin.setDecimals(4)
        self._h_spin.setSingleStep(0.01)
        self._h_spin.valueChanged.connect(self._on_value_changed)
        pos_layout.addRow("H:", self._h_spin)

        layout.addWidget(pos_group)

        # ── 类别 ──
        class_group = QGroupBox("类别")
        class_group.setObjectName("property_pos_group")
        class_layout = QVBoxLayout(class_group)
        class_layout.setSpacing(4)

        self._class_combo = QComboBox()
        self._class_combo.currentIndexChanged.connect(self._on_class_combo_changed)
        class_layout.addWidget(self._class_combo)

        layout.addWidget(class_group)

        layout.addStretch()
        self.setWidget(main)

    # ── 数据更新 ──

    def set_shape(self, shape: Optional[Shape], classes: List[Dict] = None):
        """设置当前显示的标注"""
        self._shape = shape
        if classes is not None:
            self._classes = classes
            self._refresh_classes()

        if shape is None:
            self.setVisible(False)
            return

        self.setVisible(True)

        # 更新 ID
        type_label = "Polygon" if isinstance(shape, Polygon) else "BBox"
        self._id_label.setText(f"ID: {shape.annotation_id} | "
                               f"{type_label}: {shape.label}")

        # 更新位置
        if isinstance(shape, BBox):
            self._block_signals(True)
            self._x_spin.setValue(shape.x)
            self._y_spin.setValue(shape.y)
            self._w_spin.setValue(shape.w)
            self._h_spin.setValue(shape.h)
            self._block_signals(False)
        elif isinstance(shape, Polygon):
            self._block_signals(True)
            self._x_spin.setValue(shape.get_bbox()[0])
            self._y_spin.setValue(shape.get_bbox()[1])
            self._w_spin.setValue(shape.get_bbox()[2])
            self._h_spin.setValue(shape.get_bbox()[3])
            self._block_signals(False)

        # 更新类别选择
        for i in range(self._class_combo.count()):
            cid = self._class_combo.itemData(i, Qt.UserRole)
            if cid == shape.class_id:
                self._class_combo.blockSignals(True)
                self._class_combo.setCurrentIndex(i)
                self._class_combo.blockSignals(False)
                break

    def _refresh_classes(self):
        current_id = None
        if self._class_combo.currentIndex() >= 0:
            current_id = self._class_combo.itemData(
                self._class_combo.currentIndex(), Qt.UserRole)

        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        for c in self._classes:
            self._class_combo.addItem(f"● {c['name']}")
            self._class_combo.setItemData(
                self._class_combo.count() - 1, c['id'], Qt.UserRole)

        # 恢复（此时信号仍阻塞，不会触发 _on_class_combo_changed）
        if current_id is not None:
            for i in range(self._class_combo.count()):
                if self._class_combo.itemData(i, Qt.UserRole) == current_id:
                    self._class_combo.setCurrentIndex(i)
                    break
        self._class_combo.blockSignals(False)

    def _block_signals(self, block: bool):
        self._x_spin.blockSignals(block)
        self._y_spin.blockSignals(block)
        self._w_spin.blockSignals(block)
        self._h_spin.blockSignals(block)

    # ── 事件处理 ──

    def _on_value_changed(self, value):
        """属性值变更"""
        if self._shape is None:
            return
        if isinstance(self._shape, BBox):
            self._shape.x = self._x_spin.value()
            self._shape.y = self._y_spin.value()
            self._shape.w = self._w_spin.value()
            self._shape.h = self._h_spin.value()
            self.property_changed.emit()
        # Polygon 的包围盒属性只读（通过顶点编辑调整）

    def _on_class_combo_changed(self, idx: int):
        """类别更改"""
        if self._shape is None or idx < 0:
            return
        class_id = self._class_combo.itemData(idx, Qt.UserRole)
        label = self._class_combo.itemText(idx).replace('● ', '')
        if class_id is not None:
            self._shape.class_id = class_id
            self._shape.label = label
            self.property_changed.emit()
