"""ClassMappingDialog - 模型类别映射配置对话框

让用户将模型输出的 class_id（索引）映射到项目中的类别名称。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QFrame, QMessageBox,
    QScrollArea, QWidget, QGridLayout,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from typing import List, Dict, Optional


class ClassMappingDialog(QDialog):
    """类别映射配置对话框"""

    def __init__(self, model_class_names: List[str],
                 project_classes: List[Dict],
                 current_mapping: Optional[Dict[int, str]] = None,
                 parent=None):
        """初始化

        Args:
            model_class_names: 模型输出的类别名称列表 [name0, name1, ...]
            project_classes: 项目类别列表 [{'id':..., 'name':...}, ...]
            current_mapping: 当前映射 {model_index: project_class_name}
        """
        super().__init__(parent)
        self._model_names = model_class_names
        self._project_classes = sorted(project_classes, key=lambda c: c['id'])
        self._current_mapping = current_mapping or {}
        self._result_mapping: Dict[int, str] = {}
        self._combos: List[QComboBox] = []
        self._setup_ui()
        self.setWindowTitle("模型类别映射")
        self.setMinimumWidth(500)
        self.setModal(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 说明文字
        info = QLabel(
            "设置模型输出的每个索引对应项目中的哪个类别。\n"
            "模型输出 index → 自动映射到选中的项目类别。"
        )
        info.setStyleSheet("color: #aaaaaa; font-size: 12px; padding: 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3d3d3d;")
        layout.addWidget(sep)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)

        # 表头
        header_idx = QLabel("模型索引")
        header_idx.setStyleSheet("font-weight: bold; color: #cccccc; padding: 4px;")
        header_name = QLabel("模型输出名称")
        header_name.setStyleSheet("font-weight: bold; color: #cccccc; padding: 4px;")
        header_map = QLabel("映射到项目类别")
        header_map.setStyleSheet("font-weight: bold; color: #cccccc; padding: 4px;")

        grid.addWidget(header_idx, 0, 0)
        grid.addWidget(header_name, 0, 1)
        grid.addWidget(header_map, 0, 2)

        # 项目类别名称列表（用于下拉框）
        proj_names = [""] + [c['name'] for c in self._project_classes]

        # 每行一个模型类别
        for i, name in enumerate(self._model_names):
            # 索引
            idx_label = QLabel(str(i))
            idx_label.setStyleSheet("color: #888888; padding: 4px;")
            idx_label.setAlignment(Qt.AlignCenter)
            grid.addWidget(idx_label, i + 1, 0)

            # 模型原始名称
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #cccccc; padding: 4px;")
            grid.addWidget(name_label, i + 1, 1)

            # 映射下拉框
            combo = QComboBox()
            combo.addItems(proj_names)
            combo.setMinimumWidth(150)
            combo.setStyleSheet("""
                QComboBox {
                    background-color: #3d3d3d; color: #cccccc;
                    border: 1px solid #555555; border-radius: 3px;
                    padding: 4px; font-size: 12px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #3d3d3d; color: #cccccc;
                    selection-background-color: #0d6efd;
                }
            """)

            # 恢复已有映射
            mapped_name = self._current_mapping.get(i, "")
            if mapped_name and mapped_name in proj_names:
                combo.setCurrentText(mapped_name)
            else:
                # 自动猜测：模型名称和项目类别名称相同时自动匹配
                for c in self._project_classes:
                    if c['name'] == name:
                        combo.setCurrentText(name)
                        break

            grid.addWidget(combo, i + 1, 2)
            self._combos.append(combo)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, 1)

        # 分隔线
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #3d3d3d;")
        layout.addWidget(sep2)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        hint = QLabel("未映射的索引将跳过预测")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        btn_layout.addWidget(hint)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton { padding: 6px 16px; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("✅ 确认映射")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #0b5ed7; }
        """)
        ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _on_accept(self):
        """确认映射"""
        mapping = {}
        for i, combo in enumerate(self._combos):
            selected = combo.currentText().strip()
            if selected:
                mapping[i] = selected

        if not mapping:
            QMessageBox.warning(self, "提示", "请至少映射一个类别")
            return

        self._result_mapping = mapping
        self.accept()

    def get_mapping(self) -> Dict[int, str]:
        """获取映射结果 {model_index: project_class_name}"""
        return self._result_mapping

    @staticmethod
    def get_mapping_interactive(model_names: List[str],
                                 project_classes: List[Dict],
                                 current_mapping: Optional[Dict[int, str]] = None,
                                 parent=None) -> Optional[Dict[int, str]]:
        """类方法：直接弹出对话框并返回映射结果"""
        dialog = ClassMappingDialog(model_names, project_classes,
                                     current_mapping, parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_mapping()
        return None
