"""MainWindow - 主窗口

组装所有组件，管理应用状态，处理菜单和快捷键。
"""

from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QApplication,
    QAction, QMenu, QToolBar, QStatusBar, QLabel,
    QDockWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QKeySequence, QFont, QIcon, QPixmap

from pathlib import Path
from typing import Optional, List, Dict
import os

from backend.project.manager import ProjectManager
from backend.project.project import Project
from backend.dataset.manager import DatasetManager
from backend.annotation.manager import AnnotationManager
from backend.annotation.shape import Shape
from backend.annotation.bbox import BBox
from backend.export.yolo import YOLOExporter
from backend.utils.misc import DEFAULT_SHORTCUTS

from .widgets.image_view import ImageView
from .widgets.canvas import Mode
from .widgets.project_dock import ProjectDock
from .widgets.label_dock import LabelDock
from .widgets.property_dock import PropertyDock
from .widgets.class_dialog import ClassDialog
from .widgets.model_dock import ModelDock
from backend.inference.manager import InferenceManager


class MainWindow(QMainWindow):
    """FastLabel 主窗口"""

    def __init__(self):
        super().__init__()
        self._project: Optional[Project] = None
        self._project_manager = ProjectManager()
        self._dataset_manager = DatasetManager()
        self._annotation_manager = AnnotationManager()
        self._inference_manager = InferenceManager()

        # 当前图片
        self._current_image_id: Optional[int] = None

        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()
        self._update_title()
        self._update_ui_state()

    def _setup_ui(self):
        """初始化 UI"""
        self.setWindowTitle("FastLabel - AI 辅助标注平台")
        self.setMinimumSize(1280, 800)
        self.resize(1400, 900)

        # 全局样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QMenuBar {
                background-color: #2d2d2d;
                color: #cccccc;
                border-bottom: 1px solid #3d3d3d;
                font-size: 13px;
            }
            QMenuBar::item:selected {
                background-color: #0d6efd;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #0d6efd;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3d3d3d;
                margin: 4px 8px;
            }
            QStatusBar {
                background-color: #2d2d2d;
                color: #aaaaaa;
                border-top: 1px solid #3d3d3d;
                font-size: 12px;
            }
            QPushButton {
                background-color: #3d3d3d;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #0d6efd;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """)

        # ── 中心组件: ImageView ──
        self._image_view = ImageView()
        self.setCentralWidget(self._image_view)

        # ── Dock Widgets ──
        # 左侧：项目管理 + 模型管理（Tab 切换）
        self._project_dock = ProjectDock()
        self._project_dock.setMinimumWidth(220)
        self._project_dock.setMaximumWidth(400)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._project_dock)

        self._model_dock = ModelDock()
        self.addDockWidget(Qt.LeftDockWidgetArea, self._model_dock)
        self.tabifyDockWidget(self._project_dock, self._model_dock)
        self._project_dock.raise_()

        # 右侧：标注列表 + 属性面板（Tab 切换）
        self._label_dock = LabelDock()
        self.addDockWidget(Qt.RightDockWidgetArea, self._label_dock)

        self._property_dock = PropertyDock()
        self.addDockWidget(Qt.RightDockWidgetArea, self._property_dock)
        self.tabifyDockWidget(self._label_dock, self._property_dock)
        self._label_dock.raise_()

        # ── 菜单栏 ──
        self._setup_menus()

        # ── 状态栏 ──
        self._status_label = QLabel("就绪")
        self.statusBar().addWidget(self._status_label, 1)

        self._mode_label = QLabel("模式: 选择")
        self._mode_label.setStyleSheet("padding: 0 12px;")
        self.statusBar().addPermanentWidget(self._mode_label)

        self._class_label = QLabel("类别: -")
        self._class_label.setStyleSheet("padding: 0 12px;")
        self.statusBar().addPermanentWidget(self._class_label)

    def _setup_menus(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # ── 文件 ──
        file_menu = menubar.addMenu("文件(&F)")

        new_action = QAction("新建项目(&N)", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("打开项目(&O)", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        import_action = QAction("导入图片(&I)...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_images)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        export_action = QAction("导出 YOLO(&E)", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_export_yolo)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        close_action = QAction("关闭项目", self)
        close_action.triggered.connect(self._on_close_project)
        file_menu.addAction(close_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ── 编辑 ──
        edit_menu = menubar.addMenu("编辑(&E)")

        self._undo_action = QAction("撤销(&U)", self)
        self._undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self._undo_action.triggered.connect(self._on_undo)
        self._undo_action.setEnabled(False)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("重做(&R)", self)
        self._redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self._redo_action.triggered.connect(self._on_redo)
        self._redo_action.setEnabled(False)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        delete_action = QAction("删除选中", self)
        delete_action.setShortcut(QKeySequence("Delete"))
        delete_action.triggered.connect(self._on_delete_selected)
        edit_menu.addAction(delete_action)

        # ── 标注 ──
        annotate_menu = menubar.addMenu("标注(&A)")

        self._class_action = QAction("类别管理(&C)...", self)
        self._class_action.triggered.connect(self._on_class_management)
        annotate_menu.addAction(self._class_action)

        annotate_menu.addSeparator()

        select_mode_action = QAction("选择模式", self)
        select_mode_action.setShortcut(QKeySequence("S"))
        select_mode_action.triggered.connect(
            lambda: self._image_view.set_mode(Mode.SELECT))
        annotate_menu.addAction(select_mode_action)

        draw_mode_action = QAction("绘制模式", self)
        draw_mode_action.setShortcut(QKeySequence("W"))
        draw_mode_action.triggered.connect(
            lambda: self._image_view.set_mode(Mode.DRAW))
        annotate_menu.addAction(draw_mode_action)

        # ── 视图 ──
        view_menu = menubar.addMenu("视图(&V)")

        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        zoom_in_action.triggered.connect(self._image_view._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self._image_view._zoom_out)
        view_menu.addAction(zoom_out_action)

        fit_action = QAction("适应窗口", self)
        fit_action.triggered.connect(self._image_view._fit_window)
        view_menu.addAction(fit_action)

        # ── 导航 ──
        nav_menu = menubar.addMenu("导航(&N)")

        next_action = QAction("下一张", self)
        next_action.setShortcut(QKeySequence("D"))
        next_action.triggered.connect(self._on_next_image)
        nav_menu.addAction(next_action)

        prev_action = QAction("上一张", self)
        prev_action.setShortcut(QKeySequence("A"))
        prev_action.triggered.connect(self._on_prev_image)
        nav_menu.addAction(prev_action)

        # ── 帮助 ──
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于 FastLabel", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        shortcut_action = QAction("快捷键参考", self)
        shortcut_action.triggered.connect(self._on_show_shortcuts)
        help_menu.addAction(shortcut_action)

    def _setup_shortcuts(self):
        """设置全局快捷键"""
        pass  # 已在菜单中设置

    def _connect_signals(self):
        """连接信号"""
        # ProjectDock
        self._project_dock.image_selected.connect(self._on_image_selected)
        self._project_dock.project_opened.connect(self._on_project_opened)
        self._project_dock.import_images_requested.connect(self._on_import_images)

        # ImageView / Canvas
        canvas = self._image_view.canvas
        canvas.annotation_added.connect(self._on_annotation_added)
        canvas.annotation_selected.connect(self._on_annotation_selected)
        canvas.annotation_toggled.connect(self._on_annotation_toggled)
        canvas.annotation_changed.connect(self._on_annotation_changed)
        canvas.annotation_class_changed.connect(self._on_label_class_changed)
        canvas.mode_changed.connect(self._on_mode_changed)
        canvas.mode_changed.connect(self._image_view.sync_mode_buttons)

        # ImageView
        self._image_view.status_message.connect(self._on_status_message)

        # LabelDock
        self._label_dock.annotation_selected.connect(self._on_label_selected)
        self._label_dock.annotation_deleted.connect(self._on_label_deleted)
        self._label_dock.annotation_class_changed.connect(
            self._on_label_class_changed)

        # PropertyDock
        self._property_dock.property_changed.connect(
            self._on_annotation_changed)

        # Canvas 预测信号
        canvas.annotation_accept_requested.connect(self._on_accept_prediction)
        canvas.annotation_reject_requested.connect(self._on_reject_prediction)

        # ModelDock
        self._model_dock.load_model_requested.connect(self._on_load_model)
        self._model_dock.unload_model_requested.connect(self._on_unload_model)
        self._model_dock.auto_label_requested.connect(self._on_auto_label)
        self._model_dock.batch_label_requested.connect(self._on_batch_label)
        self._model_dock.accept_all_requested.connect(self._on_accept_all)
        self._model_dock.reject_all_requested.connect(self._on_reject_all)
        self._model_dock.conf_threshold_changed.connect(self._on_conf_threshold)

        # AnnotationManager
        self._annotation_manager.set_on_change(self._on_annotations_updated)
        self._annotation_manager.set_on_select_change(
            self._on_selection_updated)
        self._annotation_manager.set_on_predictions_change(
            self._on_predictions_updated)

    # ══════════════════════════════════════
    # 项目操作
    # ══════════════════════════════════════

    def _on_new_project(self):
        """新建项目"""
        # 通过 ProjectDock 创建
        self._project_dock._on_new_project()

    def _on_open_project(self):
        """打开项目"""
        self._project_dock._on_open_project()

    def _on_project_opened(self, project: Project):
        """项目已打开"""
        self._project = project
        self._dataset_manager.set_project(project)
        self._annotation_manager.clear()
        self._current_image_id = None

        # 加载第一个图片
        images = project.get_all_images()
        if images:
            self._load_image(images[0]['id'])
            self._project_dock.select_image(0)

        self._sync_classes()
        self._update_title()
        self._update_ui_state()
        self._status(f"已打开项目: {project.name}")

        # 自动加载上次使用的模型
        model_cfg = project.config.get('model')
        if model_cfg and isinstance(model_cfg, dict):
            model_path = model_cfg.get('path', '')
            threshold = model_cfg.get('conf_threshold', 0.25)
            from pathlib import Path
            if model_path and Path(model_path).exists():
                self._inference_manager.conf_threshold = threshold
                self._on_load_model(model_path)

    def _on_close_project(self):
        """关闭项目"""
        if self._project:
            # 保存当前标注
            self._save_current_annotations()
            self._project.close()
            self._project = None
            self._dataset_manager.set_project(None)
            self._annotation_manager.clear()
            self._current_image_id = None
            self._project_dock.set_project(None)
            self._update_title()
            self._update_ui_state()
            self._status("项目已关闭")

    def _on_import_images(self):
        """导入图片"""
        if not self._project:
            QMessageBox.warning(self, "提示", "请先打开一个项目")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片",
            str(Path.home()),
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp);;所有文件 (*)")

        if not files:
            return

        count = self._dataset_manager.import_images(files)
        if count > 0:
            self._project_dock.set_project(self._project)
            self._status(f"已导入 {count} 张图片")
            # 跳转到第一张
            images = self._project.get_all_images()
            if images and self._current_image_id is None:
                self._load_image(images[0]['id'])
                self._project_dock.select_image(0)
        else:
            self._status("没有新图片被导入（可能已存在）")

    # ══════════════════════════════════════
    # 图片导航
    # ══════════════════════════════════════

    def _on_image_selected(self, image_id: int):
        """选中图片"""
        if image_id != self._current_image_id:
            self._save_current_annotations()
            self._load_image(image_id)

    def _on_next_image(self):
        """下一张"""
        if self._current_image_id is None:
            return
        self._save_current_annotations()
        if self._dataset_manager.goto_next():
            img = self._dataset_manager.current_image
            if img:
                self._load_image(img['id'])
                idx = self._dataset_manager.current_index
                self._project_dock.select_image(idx)

    def _on_prev_image(self):
        """上一张"""
        if self._current_image_id is None:
            return
        self._save_current_annotations()
        if self._dataset_manager.goto_prev():
            img = self._dataset_manager.current_image
            if img:
                self._load_image(img['id'])
                idx = self._dataset_manager.current_index
                self._project_dock.select_image(idx)

    def _load_image(self, image_id: int):
        """加载并显示图片"""
        if not self._project:
            return

        img = self._project.get_image(image_id)
        if not img:
            return

        self._current_image_id = image_id

        # 加载图像
        img_array, w, h = self._dataset_manager.image_loader().load_image(
            img['path'])
        self._image_view.load_image(img_array)

        # 加载标注
        shapes = self._dataset_manager.load_annotations(image_id)
        self._annotation_manager.set_annotations(shapes)
        self._annotation_manager.clear_predictions()

        # 更新 UI
        self._image_view.update_annotations(shapes, None)
        self._label_dock.set_annotations(shapes)
        self._property_dock.set_shape(None)
        self._model_dock.set_prediction_count(0)

        # 设置导航
        images = self._project.get_all_images()
        for i, im in enumerate(images):
            if im['id'] == image_id:
                self._dataset_manager.set_current_index(i)
                self._image_view.set_image_nav(i, len(images))
                break

        # 更新画布
        canvas = self._image_view.canvas
        canvas.set_annotations_ref(self._annotation_manager.annotations)
        canvas.set_selected_ref(self._annotation_manager.selected)
        canvas.set_on_request_delete(self._on_request_delete)
        canvas.set_on_request_accept(self._on_accept_prediction)
        canvas.set_predictions(self._annotation_manager.predictions)
        if self._project:
            canvas.set_classes(self._project.get_classes())

        self._update_ui_state()
        self._status(f"已加载: {img['filename']} ({w}x{h})")

    # ══════════════════════════════════════
    # 标注操作
    # ══════════════════════════════════════

    def _on_annotation_added(self, shape: Shape):
        """添加标注"""
        if isinstance(shape, BBox) and self._current_image_id is not None:
            # 设置当前类别
            class_id = self._label_dock.get_current_class_id()
            classes = self._project.get_classes() if self._project else []
            label = ""
            for c in classes:
                if c['id'] == class_id:
                    label = c['name']
                    break
            shape.class_id = class_id
            shape.label = label

            self._annotation_manager.add(shape)
            self._image_view.update_annotations(
                self._annotation_manager.annotations,
                self._annotation_manager.selected)
            self._label_dock.set_annotations(
                self._annotation_manager.annotations)
            self._on_annotations_updated()
            self._status(f"添加标注: {label}")

    def _on_annotation_selected(self, shape: Optional[Shape]):
        """选中标注（来自 Canvas）"""
        try:
            if shape is None:
                self._annotation_manager.select(None)
            elif shape != self._annotation_manager.selected:
                self._annotation_manager.select(shape)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._status(f"选择出错: {e}")

    def _on_annotation_toggled(self, shape: Shape):
        """Ctrl+点击切换选中状态"""
        try:
            self._annotation_manager.toggle_select(shape)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._status(f"切换选中出错: {e}")

    def _on_label_selected(self, shape: Optional[Shape]):
        """标注列表选中（来自 LabelDock）"""
        if shape:
            self._annotation_manager.select(shape)

    def _on_label_deleted(self, shape: Shape):
        """从列表删除标注"""
        self._annotation_manager.delete(shape)

    def _on_label_class_changed(self, shape: Shape, class_id: int, label: str):
        """修改类别（多选时批量修改所有选中标注）"""
        if self._annotation_manager.selection_count > 1 and shape in self._annotation_manager.selected_shapes:
            self._annotation_manager.change_class_selected(class_id, label)
        else:
            self._annotation_manager.change_class(shape, class_id, label)

    def _on_request_delete(self, shape: Shape):
        """请求删除标注（来自 Canvas）"""
        self._annotation_manager.delete(shape)

    def _on_delete_selected(self):
        """删除当前选中的标注"""
        self._annotation_manager.delete_selected()

    def _on_annotation_changed(self):
        """标注属性变更"""
        self._image_view.update_annotations(
            self._annotation_manager.annotations,
            self._annotation_manager.selected)
        self._label_dock.set_annotations(
            self._annotation_manager.annotations)

    def _on_annotations_updated(self):
        """标注列表更新"""
        self._image_view.update_annotations(
            self._annotation_manager.annotations,
            self._annotation_manager.selected)
        self._label_dock.set_annotations(
            self._annotation_manager.annotations)

        # 更新 Undo/Redo 状态
        self._undo_action.setEnabled(self._annotation_manager.can_undo())
        self._redo_action.setEnabled(self._annotation_manager.can_redo())

    def _on_selection_updated(self):
        """选中状态更新（支持多选）"""
        selected_shapes = self._annotation_manager.selected_shapes
        primary = self._annotation_manager.selected
        canvas = self._image_view.canvas
        canvas.update_annotations(self._annotation_manager.annotations, primary)

        # 多选时标注列表全高亮
        if len(selected_shapes) > 1:
            self._label_dock.select_annotations(selected_shapes)
        else:
            self._label_dock.select_annotation(primary)

        self._property_dock.set_shape(
            primary if len(selected_shapes) <= 1 else None,
            self._project.get_classes() if self._project else [])

    def _save_current_annotations(self):
        """保存当前图片的标注到数据库"""
        if self._current_image_id is not None and self._project:
            self._dataset_manager.save_annotations(
                self._current_image_id,
                self._annotation_manager.annotations)

            # 更新项目面板
            self._project_dock.set_project(self._project)

    # ══════════════════════════════════════
    # Undo / Redo
    # ══════════════════════════════════════

    def _on_undo(self):
        self._annotation_manager.undo()

    def _on_redo(self):
        self._annotation_manager.redo()

    # ══════════════════════════════════════
    # 导出
    # ══════════════════════════════════════

    def _on_export_yolo(self):
        """导出 YOLO 格式"""
        if not self._project:
            QMessageBox.warning(self, "提示", "请先打开一个项目")
            return

        # 先保存当前
        self._save_current_annotations()

        try:
            exporter = YOLOExporter(self._project)
            exporter.export_all()
            export_path = self._project.path / 'exports' / 'data.yaml'
            self._status(f"YOLO 导出完成: {export_path}")
            QMessageBox.information(
                self, "导出成功",
                f"YOLO 格式标注已导出到:\n{export_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    # ══════════════════════════════════════
    # AI 辅助标注（推理）
    # ══════════════════════════════════════

    def _on_load_model(self, model_path: str):
        """加载模型"""
        if not self._project:
            QMessageBox.warning(self, "提示", "请先打开一个项目")
            return
        try:
            from pathlib import Path
            if not Path(model_path).exists():
                QMessageBox.warning(self, "提示", f"模型文件不存在:\n{model_path}")
                return

            self._inference_manager.load_model(model_path)
            info = self._inference_manager.get_model_info()
            self._model_dock.set_model_status(True, info['name'])
            self._model_dock.set_model_path(model_path)

            # 保存模型路径到项目配置
            if self._project:
                self._project.config.set('model', {
                    'path': model_path,
                    'conf_threshold': self._inference_manager.conf_threshold,
                })

            self._status(f"模型已加载: {info['name']}")
        except ImportError as e:
            QMessageBox.critical(self, "缺少依赖",
                                 f"请安装 Ultralytics:\npip install ultralytics\n\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _on_unload_model(self):
        """卸载模型"""
        self._inference_manager.unload_model()
        self._model_dock.set_model_status(False)
        self._annotation_manager.clear_predictions()
        self._canvas_update_predictions()
        if self._project:
            self._project.config.set('model', None)
        self._status("模型已卸载")

    def _on_conf_threshold(self, threshold: float):
        """置信度阈值变化"""
        self._inference_manager.conf_threshold = threshold

    def _ensure_prediction_classes(self, predictions):
        """确保预测类别在项目数据库中存在，修正 class_id 映射

        因为 YOLO 的 class_id（如 person=0, car=2）和项目数据库的 ID 可能不一致，
        这里按名称匹配，把预测的 class_id 修正为项目中的实际 ID。
        """
        if not self._project or not predictions:
            return
        # 按名称索引已有类别
        classes = self._project.get_classes()
        name_to_id = {c['name']: c['id'] for c in classes}
        id_to_name = {c['id']: c['name'] for c in classes}

        # 收集需要添加的类别（按名称去重）
        to_add = {}
        for p in predictions:
            if p.label not in name_to_id and p.label not in to_add:
                to_add[p.label] = p.class_id

        # 添加缺失类别
        for label, cid in to_add.items():
            self._project.add_class(label, '#00BFFF')

        # 重新获取类别映射
        classes = self._project.get_classes()
        name_to_id = {c['name']: c['id'] for c in classes}

        # 修正每个预测的 class_id 为项目实际的 ID
        for p in predictions:
            actual_id = name_to_id.get(p.label)
            if actual_id is not None:
                p.class_id = actual_id

        self._sync_classes()

    def _on_auto_label(self):
        """自动标注当前图片"""
        if not self._inference_manager.is_loaded:
            QMessageBox.warning(self, "提示", "请先加载模型")
            return
        if self._current_image_id is None:
            return

        img = self._project.get_image(self._current_image_id)
        if not img:
            return

        img_array, _, _ = self._dataset_manager.image_loader().load_image(img['path'])

        try:
            results = self._inference_manager.predict_and_filter(img_array)
        except Exception as e:
            QMessageBox.critical(self, "预测失败", str(e))
            return

        # 将预测结果转为 BBox
        from backend.annotation.bbox import BBox
        predictions = []
        for r in results:
            bbox = BBox(
                class_id=r.class_id,
                label=r.label,
                x=r.x,
                y=r.y,
                w=r.w,
                h=r.h,
                score=r.score,
            )
            predictions.append(bbox)

        # 确保类别存在（自动添加 YOLO 预测的类别到项目）
        self._ensure_prediction_classes(predictions)

        self._annotation_manager.set_predictions(predictions)
        self._canvas_update_predictions()
        self._model_dock.set_prediction_count(len(predictions))
        self._status(f"自动标注完成: {len(predictions)} 个预测 (Enter 接受, Del 拒绝)")

    def _on_batch_label(self):
        """批量标注所有图片"""
        if not self._inference_manager.is_loaded:
            QMessageBox.warning(self, "提示", "请先加载模型")
            return
        if not self._project:
            return

        images = self._project.get_all_images()
        unannotated = [img for img in images if img['num_annotations'] == 0]

        if not unannotated:
            QMessageBox.information(self, "提示", "所有图片已标注完成")
            return

        reply = QMessageBox.question(
            self, "批量标注",
            f"将对 {len(unannotated)} 张图片进行自动标注？\n"
            f"标注后请逐张确认预测结果。",
            QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        # 先收集所有预测类别，一次性注册到项目
        all_classes = set()
        for img in unannotated[:20]:  # 取样前20张收集类别
            img_array, _, _ = self._dataset_manager.image_loader().load_image(img['path'])
            try:
                results = self._inference_manager.predict_and_filter(img_array)
                for r in results:
                    all_classes.add((r.class_id, r.label))
            except Exception:
                continue

        # 注册所有缺失类别
        existing_ids = {c['id'] for c in self._project.get_classes()}
        for cid, label in all_classes:
            if cid not in existing_ids:
                self._project.add_class(label, '#00BFFF')
                existing_ids.add(cid)
        self._sync_classes()
        label_to_id = {c['name']: c['id'] for c in self._project.get_classes()}

        count = 0
        for img in unannotated:
            img_array, _, _ = self._dataset_manager.image_loader().load_image(img['path'])
            try:
                results = self._inference_manager.predict_and_filter(img_array)
            except Exception:
                continue

            from backend.annotation.bbox import BBox
            predictions = []
            for r in results:
                bbox = BBox(
                    class_id=label_to_id.get(r.label, r.class_id),
                    label=r.label,
                    x=r.x,
                    y=r.y,
                    w=r.w,
                    h=r.h,
                    score=r.score,
                )
                predictions.append(bbox)

            if predictions:
                self._project.save_all_annotations(img['id'],
                    [p.to_dict() for p in predictions])
                count += 1

        self._dataset_manager.refresh()
        self._project_dock.set_project(self._project)
        self._status(f"批量标注完成: 标注了 {count} 张图片")

        if self._current_image_id:
            self._load_image(self._current_image_id)

    def _on_accept_prediction(self, shape):
        """接受单个预测"""
        self._annotation_manager.accept_prediction(shape)
        self._canvas_update_predictions()
        self._model_dock.set_prediction_count(
            len(self._annotation_manager.predictions))
        self._status(f"已接受: {shape.label}")

    def _on_reject_prediction(self, shape):
        """拒绝单个预测"""
        self._annotation_manager.reject_prediction(shape)
        self._canvas_update_predictions()
        self._model_dock.set_prediction_count(
            len(self._annotation_manager.predictions))
        self._status(f"已拒绝: {shape.label}")

    def _on_accept_all(self, min_score: float):
        """全部接受"""
        count = self._annotation_manager.accept_all_predictions(min_score)
        if count > 0:
            self._save_current_annotations()
        self._canvas_update_predictions()
        self._model_dock.set_prediction_count(
            len(self._annotation_manager.predictions))
        self._status(f"已接受 {count} 个预测结果")

    def _on_reject_all(self, min_score: float):
        """全部拒绝"""
        count = self._annotation_manager.reject_all_predictions(min_score)
        self._canvas_update_predictions()
        self._model_dock.set_prediction_count(
            len(self._annotation_manager.predictions))
        self._status(f"已拒绝 {count} 个预测结果")

    def _canvas_update_predictions(self):
        """同步预测结果到 Canvas"""
        canvas = self._image_view.canvas
        canvas.set_predictions(self._annotation_manager.predictions)
        self._label_dock.set_annotations(
            self._annotation_manager.annotations)
        self._image_view.canvas.update()

    def _on_predictions_updated(self):
        """预测结果变更回调"""
        self._canvas_update_predictions()

    # ══════════════════════════════════════
    # 类别管理
    # ══════════════════════════════════════

    def _sync_classes(self):
        """同步类别到 UI"""
        if not self._project:
            return
        classes = self._project.get_classes()
        self._label_dock.set_classes(classes)
        self._image_view.canvas.set_classes(classes)

    def _on_class_management(self):
        """打开类别管理对话框"""
        if not self._project:
            QMessageBox.warning(self, "提示", "请先打开一个项目")
            return
        dialog = ClassDialog(self._project, self)
        dialog.classes_changed.connect(self._sync_classes)
        dialog.exec_()

    # ══════════════════════════════════════
    # UI 状态
    # ══════════════════════════════════════

    def _on_mode_changed(self, mode: str):
        """模式切换"""
        mode_names = {
            Mode.SELECT: "选择",
            Mode.DRAW: "绘制",
            Mode.PAN: "平移",
        }
        self._mode_label.setText(f"模式: {mode_names.get(mode, mode)}")

    def _on_status_message(self, message: str):
        """状态消息"""
        self._status(message)

    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(self, "关于 FastLabel",
                          "<h3>FastLabel v0.1.0</h3>"
                          "<p>AI 辅助标注平台</p>"
                          "<p>轻量级目标检测标注工具，支持 YOLO 格式。<br>"
                          "快捷键:</p>"
                          "<ul>"
                          "<li><b>W</b> 绘制模式 | <b>S</b> 选择模式 | <b>H</b> 平移</li>"
                          "<li><b>A/D</b> 上一张/下一张</li>"
                          "<li><b>Ctrl+Z</b> 撤销 | <b>Ctrl+Shift+Z</b> 重做</li>"
                          "<li><b>Delete</b> 删除选中</li>"
                          "<li><b>滑轮</b> 缩放 | <b>双击</b> 适应窗口</li>"
                          "</ul>")

    def _on_show_shortcuts(self):
        """快捷键参考"""
        shortcuts = DEFAULT_SHORTCUTS
        text = "快捷键参考:\n\n"
        for name, key in shortcuts.items():
            text += f"  {name}: {key}\n"
        QMessageBox.information(self, "快捷键参考", text)

    def _update_title(self):
        """更新窗口标题"""
        if self._project:
            self.setWindowTitle(
                f"FastLabel - {self._project.name}")
        else:
            self.setWindowTitle("FastLabel - AI 辅助标注平台")

    def _update_ui_state(self):
        """更新 UI 组件启用状态"""
        has_project = self._project is not None
        has_image = self._current_image_id is not None

        self._undo_action.setEnabled(
            has_image and self._annotation_manager.can_undo())
        self._redo_action.setEnabled(
            has_image and self._annotation_manager.can_redo())
        self._class_action.setEnabled(has_project)

    def _status(self, message: str):
        """状态栏显示消息"""
        self._status_label.setText(message)

    # ══════════════════════════════════════
    # 生命周期
    # ══════════════════════════════════════

    def closeEvent(self, event):
        """关闭窗口时保存"""
        if self._project:
            self._save_current_annotations()
            self._project.close()
        event.accept()
