"""LabelDock - 标注列表面板

显示当前图片的所有标注，支持选中、删除、修改类别。
"""

from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton,
    QLabel, QToolButton, QComboBox, QFrame,
    QMenu, QAction, QAbstractItemView,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize,
)
from PyQt5.QtGui import (
    QColor, QBrush, QFont,
)
from typing import Optional, List, Dict, Callable

from backend.annotation.shape import Shape
from backend.annotation.bbox import BBox
from backend.annotation.polygon import Polygon
from backend.utils.misc import get_class_color


class LabelDock(QDockWidget):
    """标注列表面板"""

    # 信号
    annotation_selected = pyqtSignal(object)     # 选中标注
    annotation_deleted = pyqtSignal(object)      # 删除标注
    annotation_class_changed = pyqtSignal(object, int, str)  # 标注, 新class_id, 新label

    def __init__(self, parent=None):
        super().__init__("标注列表", parent)
        self._annotations: List[Shape] = []
        self._classes: List[Dict] = []
        self._last_selected: Optional[Shape] = None  # 跟踪最后选中的标注
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(200)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        main = QWidget()
        layout = QVBoxLayout(main)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 工具栏 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(2)

        self._delete_btn = QToolButton()
        self._delete_btn.setText("🗑 删除")
        self._delete_btn.setToolTip("删除选中标注 (Del)")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        toolbar.addWidget(self._delete_btn)

        self._clear_btn = QToolButton()
        self._clear_btn.setText("清空")
        self._clear_btn.setToolTip("清空当前图片所有标注")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        toolbar.addWidget(self._clear_btn)

        toolbar.addStretch()
        self._count_label = QLabel("0 个标注")
        self._count_label.setStyleSheet("color: #888888; font-size: 11px;")
        toolbar.addWidget(self._count_label)

        layout.addLayout(toolbar)

        # ── 类别选择 ──
        class_layout = QHBoxLayout()
        class_layout.setSpacing(2)
        class_layout.addWidget(QLabel("类别:"))

        self._class_combo = QComboBox()
        self._class_combo.setMinimumWidth(100)
        self._class_combo.currentIndexChanged.connect(self._on_class_changed)
        class_layout.addWidget(self._class_combo, 1)

        layout.addLayout(class_layout)

        # ── 标注列表 ──
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.setObjectName("label_list")
        layout.addWidget(self._list, 1)

        self.setWidget(main)

    # ── 数据更新 ──

    def set_annotations(self, annotations: List[Shape]):
        """更新标注列表"""
        self._annotations = annotations
        self._refresh_list()

    def set_classes(self, classes: List[Dict]):
        """更新类别列表"""
        self._classes = classes
        current = self._class_combo.currentText()
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        for c in classes:
            color = c.get('color', '#FFFFFF')
            self._class_combo.addItem(f"● {c['name']}")
            self._class_combo.setItemData(
                self._class_combo.count() - 1, c['id'], Qt.UserRole)
        self._class_combo.blockSignals(False)

        # 恢复选中
        idx = self._class_combo.findText(current)
        if idx >= 0:
            self._class_combo.setCurrentIndex(idx)

    def select_annotation(self, shape: Optional[Shape]):
        """选中列表中对应的单个项"""
        self._last_selected = shape
        if shape is None:
            self._list.blockSignals(True)
            self._list.clearSelection()
            self._list.blockSignals(False)
            return

        for i, ann in enumerate(self._annotations):
            if ann is shape:
                self._list.blockSignals(True)
                self._list.setCurrentRow(i)
                self._list.blockSignals(False)
                return

    def select_annotations(self, shapes: List[Shape]):
        """多选：高亮列表中的多个项"""
        self._list.blockSignals(True)
        self._list.clearSelection()
        for i, ann in enumerate(self._annotations):
            if ann in shapes:
                self._list.item(i).setSelected(True)
                self._last_selected = ann
        self._list.blockSignals(False)

    def get_current_class_id(self) -> int:
        """获取当前选中的类别 ID"""
        idx = self._class_combo.currentIndex()
        if idx >= 0:
            return self._class_combo.itemData(idx, Qt.UserRole)
        return 0

    # ── 刷新 ──

    def _refresh_list(self):
        self._list.blockSignals(True)
        self._list.clear()

        for i, ann in enumerate(self._annotations):
            color = QColor(get_class_color(ann.class_id))
            label = ann.label if ann.label else f"Class {ann.class_id}"

            if isinstance(ann, BBox):
                text = f"[{i+1}] {label}"
                if ann.score < 1.0:
                    text += f" ({ann.score:.2f})"
                text += f"\n  ({ann.x:.3f}, {ann.y:.3f}) {ann.w:.3f}x{ann.h:.3f}"
            elif isinstance(ann, Polygon):
                text = f"[{i+1}] {label} 🏁"
                if ann.score < 1.0:
                    text += f" ({ann.score:.2f})"
                text += f"\n  {len(ann.points)} 个顶点"
            else:
                text = f"[{i+1}] {label}"

            item = QListWidgetItem(text)
            item.setForeground(QColor("#cccccc"))
            item.setBackground(QColor(color.red(), color.green(),
                                      color.blue(), 20))
            self._list.addItem(item)

        self._count_label.setText(f"{len(self._annotations)} 个标注")
        self._delete_btn.setEnabled(len(self._annotations) > 0)
        self._clear_btn.setEnabled(len(self._annotations) > 0)

        self._list.blockSignals(False)

    # ── 事件处理 ──

    def _get_target_annotation(self) -> Optional[Shape]:
        """获取当前操作目标标注（优先列表选中项，其次最后选中项）"""
        # 从列表选中行获取
        row = self._list.currentRow()
        if 0 <= row < len(self._annotations):
            self._last_selected = self._annotations[row]
            return self._last_selected
        # 从最后跟踪的选中项获取
        if self._last_selected and self._last_selected in self._annotations:
            return self._last_selected
        return None

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self._annotations):
            self._last_selected = self._annotations[row]
            self.annotation_selected.emit(self._last_selected)

    def _on_delete(self):
        ann = self._get_target_annotation()
        if ann:
            self.annotation_deleted.emit(ann)

    def _on_clear(self):
        # 逐个删除（用 list() 拷贝避免迭代中修改）
        for ann in list(self._annotations):
            self.annotation_deleted.emit(ann)

    def _on_class_changed(self, idx: int):
        """切换绘制用的类别"""
        if idx >= 0:
            class_id = self._class_combo.itemData(idx, Qt.UserRole)
            # 查找实际类别名
            for c in self._classes:
                if c['id'] == class_id:
                    # 更新当前绘制类别（由外部处理）
                    pass

    def _show_context_menu(self, pos):
        """右键菜单：支持修改类别和删除"""
        # 用 itemAt(pos) 获取右键点击的 item，而不是 currentRow
        item = self._list.itemAt(pos)
        if item is None:
            return
        row = self._list.row(item)
        if row < 0 or row >= len(self._annotations):
            return

        ann = self._annotations[row]
        # 选中该项
        self.annotation_selected.emit(ann)

        menu = QMenu(self)

        if isinstance(ann, (BBox, Polygon)):
            # ── 修改类别子菜单 ──
            class_menu = menu.addMenu("📋 修改类别")
            for c in self._classes:
                action = class_menu.addAction(f"● {c['name']}")
                action.setData(c['id'])
                action.triggered.connect(
                    lambda checked, cid=c['id'], nm=c['name']:
                    self.annotation_class_changed.emit(ann, cid, nm))

            menu.addSeparator()

            # ── 删除 ──
            delete_action = menu.addAction("🗑 删除 (Del)")
            delete_action.triggered.connect(
                lambda: self.annotation_deleted.emit(ann))

        menu.exec_(self._list.mapToGlobal(pos))
