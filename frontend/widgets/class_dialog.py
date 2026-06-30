"""ClassDialog - 类别管理对话框

管理项目的标注类别（添加、编辑、删除）。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QColorDialog, QHeaderView, QMessageBox, QInputDialog,
    QGroupBox, QFormLayout, QWidget, QFrame, QToolButton,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont
from typing import List, Dict, Optional


class ClassDialog(QDialog):
    """类别管理对话框"""

    classes_changed = pyqtSignal()  # 类别列表已变更

    # 预定义颜色
    PRESET_COLORS = [
        '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF',
        '#00FFFF', '#FF8000', '#80FF00', '#0080FF', '#FF0080',
        '#8000FF', '#00FF80', '#FF4040', '#40FF40', '#4040FF',
    ]

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self._project = project
        self._classes: List[Dict] = []
        self._editing_id: Optional[int] = None

        self.setWindowTitle("类别管理")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self._setup_ui()
        self._load_classes()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(12)

        # ── 左侧：列表 ──
        left = QVBoxLayout()
        left.setSpacing(4)

        left.addWidget(QLabel("当前类别:"))
        left.addWidget(QLabel(
            "快捷键: 1~9 快速切换类别",
            styleSheet="color: #888888; font-size: 11px;"))

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["颜色", "名称", "快捷键"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                font-size: 12px;
                gridline-color: #3d3d3d;
            }
            QTableWidget::item:selected {
                background-color: #0d6efd;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 4px;
                border: 1px solid #3d3d3d;
                font-weight: bold;
            }
        """)
        left.addWidget(self._table, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加")
        self._add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self._add_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        btn_layout.addWidget(self._delete_btn)

        left.addLayout(btn_layout)
        layout.addLayout(left, 1)

        # ── 右侧：编辑 ──
        right = QVBoxLayout()
        right.setSpacing(8)

        edit_group = QGroupBox("编辑类别")
        edit_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        edit_form = QFormLayout(edit_group)
        edit_form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("输入类别名称")
        self._name_edit.setStyleSheet("""
            QLineEdit {
                background-color: #3d3d3d;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0d6efd;
            }
        """)
        edit_form.addRow("名称:", self._name_edit)

        self._shortcut_edit = QLineEdit()
        self._shortcut_edit.setPlaceholderText("如: 1, 2, 3...")
        self._shortcut_edit.setMaxLength(1)
        edit_form.addRow("快捷键:", self._shortcut_edit)

        # 颜色选择
        color_layout = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(40, 28)
        self._color_btn.setStyleSheet(
            "background-color: #FFFFFF; border-radius: 3px;")
        self._color_btn.clicked.connect(self._on_pick_color)
        color_layout.addWidget(self._color_btn)

        self._color_hex = QLabel("#FFFFFF")
        self._color_hex.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        color_layout.addWidget(self._color_hex)
        color_layout.addStretch()
        edit_form.addRow("颜色:", color_layout)

        # 预设色块
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(2)
        for c in self.PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(
                f"background-color: {c}; border-radius: 3px;")
            btn.clicked.connect(lambda checked, color=c: self._set_color(color))
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        edit_form.addRow("", preset_layout)

        # 保存按钮
        self._save_btn = QPushButton("保存修改")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #888888;
            }
        """)
        edit_form.addRow(self._save_btn)

        right.addWidget(edit_group)
        right.addStretch()

        # 关闭按钮
        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        right.addWidget(self._close_btn)

        layout.addLayout(right, 1)

    def _load_classes(self):
        """加载类别数据"""
        if not self._project:
            return
        self._classes = self._project.get_classes()
        self._refresh_table()

    def _refresh_table(self):
        """刷新列表"""
        self._table.setRowCount(len(self._classes))

        for row, cls in enumerate(self._classes):
            # 颜色
            color_item = QTableWidgetItem()
            color_item.setBackground(
                QColor(cls.get('color', '#FFFFFF')))
            color_item.setToolTip(cls.get('color', ''))
            self._table.setItem(row, 0, color_item)

            # 名称
            name_item = QTableWidgetItem(cls['name'])
            name_item.setData(Qt.UserRole, cls['id'])
            self._table.setItem(row, 1, name_item)

            # 快捷键
            shortcut = cls.get('shortcut_key', cls.get('shortcut', ''))
            shortcut_item = QTableWidgetItem(shortcut)
            self._table.setItem(row, 2, shortcut_item)

    def _on_selection_changed(self):
        """选中行变更"""
        rows = self._table.selectedItems()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._classes):
                cls = self._classes[row]
                self._editing_id = cls['id']
                self._name_edit.setText(cls['name'])
                self._shortcut_edit.setText(
                    cls.get('shortcut_key', cls.get('shortcut', '')))
                self._set_color(cls.get('color', '#FFFFFF'))
                self._save_btn.setEnabled(True)
                self._delete_btn.setEnabled(True)
                return

        self._editing_id = None
        self._name_edit.clear()
        self._shortcut_edit.clear()
        self._set_color('#FFFFFF')
        self._save_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

    def _on_add(self):
        """添加新类别"""
        if not self._project:
            return
        name, ok = QInputDialog.getText(self, "添加类别", "类别名称:")
        if ok and name:
            name = name.strip()
            if not name:
                return
            # 检查是否重名
            if self._project.config.get_class_by_name(name):
                QMessageBox.warning(self, "提示", f"类别「{name}」已存在")
                return
            # 自动分配颜色
            color = self.PRESET_COLORS[len(self._classes) % len(self.PRESET_COLORS)]
            self._project.add_class(name, color)
            self._load_classes()
            self.classes_changed.emit()

    def _on_delete(self):
        """删除选中的类别"""
        if self._editing_id is None or not self._project:
            return

        cls = next((c for c in self._classes if c['id'] == self._editing_id), None)
        if not cls:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除类别「{cls['name']}」吗？\n"
            f"该类别下的所有标注也将被删除。",
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self._project.remove_class(self._editing_id)
            self._editing_id = None
            self._load_classes()
            self.classes_changed.emit()

    def _on_save(self):
        """保存类别修改"""
        if self._editing_id is None or not self._project:
            return

        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "类别名称不能为空")
            return

        shortcut = self._shortcut_edit.text().strip()
        color = self._color_hex.text()

        self._project.config.update_class(
            self._editing_id, name=name, color=color,
            shortcut=shortcut)
        self._project.sync_classes_from_config()
        self._load_classes()
        self.classes_changed.emit()

    def _on_pick_color(self):
        """打开颜色选择器"""
        color = QColorDialog.getColor()
        if color.isValid():
            self._set_color(color.name())

    def _set_color(self, hex_color: str):
        """设置当前颜色"""
        self._color_btn.setStyleSheet(
            f"background-color: {hex_color}; border-radius: 3px;")
        self._color_hex.setText(hex_color)
