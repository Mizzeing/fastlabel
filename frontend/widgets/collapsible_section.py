"""CollapsibleSection - 可折叠收纳面板

将任意 QWidget 包裹成带标题头的可折叠区域，
点击标题头切换展开/折叠状态。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSignal


class CollapsibleSection(QWidget):
    """可折叠收纳面板

    用法:
        section = CollapsibleSection("项目管理", my_widget)
        layout.addWidget(section)
    """

    toggled = pyqtSignal(bool)  # (expanded)

    def __init__(self, title: str, content: QWidget, parent=None,
                 expanded: bool = True):
        super().__init__(parent)
        self._content = content
        self._title = title
        self._expanded = expanded

        self._setup_ui()
        self._set_expanded(expanded)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 标题头（可点击的 QPushButton）──
        self._header = QPushButton()
        self._header.setObjectName("collapsible_header")
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setFocusPolicy(Qt.NoFocus)
        self._header.clicked.connect(self._on_toggle)
        layout.addWidget(self._header)

        # ── 内容区域 ──
        self._content.setParent(self)
        layout.addWidget(self._content)

    def _on_toggle(self):
        self._expanded = not self._expanded
        self._set_expanded(self._expanded)
        self.toggled.emit(self._expanded)

    def _set_expanded(self, expanded: bool):
        self._expanded = expanded
        self._content.setVisible(expanded)
        self._update_header_text()

    def _update_header_text(self):
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f" {arrow} {self._title}")

    def set_title(self, title: str):
        self._title = title
        self._update_header_text()

    def set_expanded(self, expanded: bool):
        self._set_expanded(expanded)

    def is_expanded(self) -> bool:
        return self._expanded

    @property
    def content(self) -> QWidget:
        return self._content
