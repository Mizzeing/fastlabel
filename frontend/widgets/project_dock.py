"""ProjectDock - 项目管理侧边栏

显示项目文件树、图片列表和项目信息。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QInputDialog, QSplitter, QFrame, QToolButton, QProgressBar,
    QMenu, QAction, QApplication,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize,
)
from PyQt5.QtGui import (
    QIcon, QFont, QColor, QBrush,
)
from pathlib import Path
from typing import Optional, List, Callable, Dict


class ProjectDock(QWidget):
    """项目管理面板"""

    # 信号
    image_selected = pyqtSignal(int)         # 选中图片 (image_id)
    project_opened = pyqtSignal(object)      # 项目打开
    project_closed = pyqtSignal()
    import_images_requested = pyqtSignal()   # 请求导入图片
    image_delete_requested = pyqtSignal(int) # 删除图片 (image_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._setup_ui()

    def _setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 项目信息 ──
        self._info_label = QLabel("未打开项目")
        self._info_label.setObjectName("project_info_label")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # ── 操作按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)

        self._new_btn = QPushButton("新建")
        self._new_btn.setToolTip("创建新项目")
        self._new_btn.clicked.connect(self._on_new_project)
        btn_layout.addWidget(self._new_btn)

        self._open_btn = QPushButton("打开")
        self._open_btn.setToolTip("打开已有项目")
        self._open_btn.clicked.connect(self._on_open_project)
        btn_layout.addWidget(self._open_btn)

        self._import_btn = QPushButton("导入")
        self._import_btn.setToolTip("导入图片到当前项目")
        self._import_btn.clicked.connect(self.import_images_requested.emit)
        self._import_btn.setEnabled(False)
        btn_layout.addWidget(self._import_btn)

        self._delete_btn = QPushButton("删除")
        self._delete_btn.setObjectName("project_delete_btn")
        self._delete_btn.setToolTip("删除选中的项目（不可恢复）")
        self._delete_btn.clicked.connect(self._on_delete_project)
        btn_layout.addWidget(self._delete_btn)

        layout.addLayout(btn_layout)

        # ── 项目列表 ──
        self._project_tree = QTreeWidget()
        self._project_tree.setHeaderHidden(True)
        self._project_tree.setRootIsDecorated(True)
        self._project_tree.setAnimated(True)
        self._project_tree.itemDoubleClicked.connect(self._on_tree_item_clicked)
        self._project_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._project_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._project_tree.setObjectName("project_tree")
        layout.addWidget(self._project_tree, 1)

        # ── 图片列表 ──
        img_header = QLabel("📷 图片列表")
        img_header.setObjectName("project_image_header")
        layout.addWidget(img_header)

        self._image_list = QListWidget()
        self._image_list.setSelectionMode(QListWidget.SingleSelection)
        self._image_list.itemDoubleClicked.connect(self._on_image_clicked)
        self._image_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._image_list.customContextMenuRequested.connect(self._on_image_context_menu)
        self._image_list.setObjectName("project_image_list")
        layout.addWidget(self._image_list, 1)

        # ── 进度 ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("project_progress_bar")
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        self._refresh_project_list()

    # ── 项目管理 ──

    def set_project(self, project):
        self._project = project
        if project:
            proj_info = project.config.get('project', {})
            self._info_label.setText(
                f"📁 {proj_info.get('name', project.name)}\n"
                f"{proj_info.get('description', '')}"
            )
            self._import_btn.setEnabled(True)

            # 刷新图片列表
            self._refresh_image_list()

            # 刷新项目信息
            self._update_stats()

            # 在项目树中高亮
            self._highlight_project_in_tree(project.name)
        else:
            self._info_label.setText("未打开项目")
            self._import_btn.setEnabled(False)
            self._image_list.clear()
            self._progress_bar.setVisible(False)

    def _update_stats(self):
        if not self._project:
            return
        stats = self._project.get_stats()
        self._info_label.setText(
            f"📁 {self._project.name}\n"
            f"图片: {stats['total_images']} | "
            f"已标: {stats['annotated_images']}\n"
            f"标注: {stats['total_annotations']} | "
            f"类别: {stats['class_count']}"
        )
        if stats['total_images'] > 0:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(int(stats['progress']))
            self._progress_bar.setFormat(
                f"进度: {stats['annotated_images']}/{stats['total_images']} "
                f"({stats['progress']:.0f}%)"
            )
        else:
            self._progress_bar.setVisible(False)

    def _refresh_project_list(self):
        """刷新项目树"""
        self._project_tree.clear()

        from backend.project.manager import ProjectManager
        pm = ProjectManager()
        projects = pm.list_projects()

        if not projects:
            item = QTreeWidgetItem(self._project_tree, ["暂无项目，点击「新建」创建"])
            item.setForeground(0, QBrush(QColor("#888888")))
            return

        for p in projects:
            item = QTreeWidgetItem(self._project_tree, [p['name']])
            item.setData(0, Qt.UserRole, p['path'])
            item.setToolTip(0, f"路径: {p['path']}\n"
                               f"图片: {p['image_count']} 张\n"
                               f"创建: {p.get('created_at', '')[:10]}")

    def _refresh_image_list(self):
        """刷新图片列表"""
        self._image_list.clear()
        if not self._project:
            return

        images = self._project.get_all_images()
        for img in images:
            item = QListWidgetItem()
            status_icon = "✅" if img['num_annotations'] > 0 else "⬜"
            text = f"{status_icon}  {img['filename']}"
            if img['num_annotations'] > 0:
                text += f" ({img['num_annotations']})"
            item.setText(text)
            item.setData(Qt.UserRole, img['id'])
            self._image_list.addItem(item)

    def select_image(self, index: int):
        """选中指定索引的图片"""
        if 0 <= index < self._image_list.count():
            self._image_list.setCurrentRow(index)

    def _highlight_project_in_tree(self, project_name: str):
        """在项目树中高亮指定项目"""
        for i in range(self._project_tree.topLevelItemCount()):
            item = self._project_tree.topLevelItem(i)
            if item and item.text(0) == project_name:
                self._project_tree.setCurrentItem(item)
                break

    # ── 事件处理 ──

    def _on_new_project(self):
        """新建项目"""
        name, ok = QInputDialog.getText(self, "新建项目", "项目名称:")
        if ok and name:
            from backend.project.manager import ProjectManager
            pm = ProjectManager()
            try:
                project = pm.create_project(name)
                self.set_project(project)
                self.project_opened.emit(project)
                self._refresh_project_list()
            except FileExistsError as e:
                QMessageBox.warning(self, "错误", str(e))

    def _on_open_project(self):
        """打开项目"""
        from backend.project.manager import ProjectManager
        pm = ProjectManager()

        # 首先尝试从列表中选择
        # 也可以文件对话框选择
        path = QFileDialog.getExistingDirectory(
            None, "选择项目目录", str(pm.base_dir))
        if path:
            try:
                project = pm.open_project(path)
                self.set_project(project)
                self.project_opened.emit(project)
                self._refresh_project_list()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开项目失败: {e}")

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """双击项目树中的项目"""
        path = item.data(0, Qt.UserRole)
        if path:
            from backend.project.manager import ProjectManager
            pm = ProjectManager()
            try:
                project = pm.open_project(path)
                self.set_project(project)
                self.project_opened.emit(project)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开项目失败: {e}")

    def _on_image_clicked(self, item: QListWidgetItem):
        """双击图片"""
        image_id = item.data(Qt.UserRole)
        if image_id is not None:
            self.image_selected.emit(image_id)

    def _on_image_context_menu(self, pos):
        """图片列表右键菜单"""
        item = self._image_list.itemAt(pos)
        if not item or not self._project:
            return
        image_id = item.data(Qt.UserRole)
        if image_id is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("🗑 删除此图片")
        delete_action.setIcon(self.style().standardIcon(
            self.style().SP_TrashIcon))
        delete_action.triggered.connect(
            lambda: self.image_delete_requested.emit(image_id))
        menu.exec_(self._image_list.mapToGlobal(pos))

    def _on_delete_project(self):
        """删除选中的项目"""
        # 优先使用项目树选中项，其次当前打开的项目
        target = None
        items = self._project_tree.selectedItems()
        if items:
            path = items[0].data(0, Qt.UserRole)
            if path:
                target = Path(path).name
        if not target and self._project:
            target = self._project.name

        if not target:
            QMessageBox.information(self, "提示", "请先在项目列表中选中要删除的项目")
            return

        if not target:
            QMessageBox.information(self, "提示", "请先在项目列表中选中要删除的项目")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要永久删除项目「{target}」吗？\n"
            f"该操作不可恢复，所有图片和标注将被删除。",
            QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            from backend.project.manager import ProjectManager
            pm = ProjectManager()

            # 如果删除的是当前项目，先关闭
            if self._project and self._project.name == target:
                self._project.close()
                self._project = None
                self.set_project(None)
                self.project_closed.emit()

            pm.delete_project(target)
            self._refresh_project_list()
            QMessageBox.information(self, "完成", f"项目「{target}」已删除")

    def _on_tree_context_menu(self, pos):
        """项目树右键菜单"""
        item = self._project_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        menu = QMenu(self)
        open_action = menu.addAction("打开项目")
        open_action.triggered.connect(
            lambda: self._on_tree_item_clicked(item, 0))

        menu.addSeparator()

        delete_action = menu.addAction("🗑 删除项目")
        delete_action.setIcon(self.style().standardIcon(
            self.style().SP_TrashIcon))
        delete_action.triggered.connect(self._on_delete_project)

        menu.exec_(self._project_tree.mapToGlobal(pos))
