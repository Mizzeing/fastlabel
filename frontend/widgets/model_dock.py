"""ModelDock - 模型管理面板

加载模型、置信度调节、自动标注、接受/拒绝预测。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog,
    QFrame, QMessageBox, QToolButton,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor
from pathlib import Path
from typing import Optional


class ModelDock(QWidget):
    """模型管理面板"""

    # 信号
    load_model_requested = pyqtSignal(str)              # 加载模型
    unload_model_requested = pyqtSignal()               # 卸载模型
    auto_label_requested = pyqtSignal()                 # 自动标注当前图
    batch_label_requested = pyqtSignal()                # 批量标注
    accept_all_requested = pyqtSignal(float)            # 全部接受（带阈值）
    reject_all_requested = pyqtSignal(float)            # 全部拒绝
    conf_threshold_changed = pyqtSignal(float)          # 置信度阈值变化
    iou_threshold_changed = pyqtSignal(float)           # IoU 阈值变化
    class_mapping_requested = pyqtSignal()              # 配置类别映射

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_loaded = False
        self._prediction_count = 0
        self._model_path = ""  # 保存完整路径
        self._last_browse_dir = str(Path.home())  # 记住上次浏览目录
        self._setup_ui()
        self.setMaximumWidth(320)  # 防止被长路径撑开

    def _setup_ui(self):
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── 模型状态 ──
        self._status_label = QLabel("⚪ 模型: 未加载")
        self._status_label.setObjectName("model_status_label")
        self._status_label.setStyleSheet("QLabel { color: #aaaaaa; background-color: #2d2d2d; }")
        layout.addWidget(self._status_label)

        # ── 模型路径 ──
        path_layout = QHBoxLayout()
        self._path_label = QLabel()
        self._path_label.setText("未选择模型")
        self._path_label.setMinimumWidth(20)
        self._path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._path_label.setTextFormat(Qt.PlainText)
        self._path_label.setObjectName("model_path_label")
        path_layout.addWidget(self._path_label, 1)

        self._browse_btn = QToolButton()
        self._browse_btn.setText("📂")
        self._browse_btn.setToolTip("选择模型文件")
        self._browse_btn.clicked.connect(self._on_browse_model)
        path_layout.addWidget(self._browse_btn)
        layout.addLayout(path_layout)

        # ── 加载/卸载按钮 ──
        btn_layout = QHBoxLayout()
        self._load_btn = QPushButton("加载模型")
        self._load_btn.setToolTip("加载选中的模型文件")
        self._load_btn.clicked.connect(self._on_load_model)
        btn_layout.addWidget(self._load_btn)

        self._unload_btn = QPushButton("卸载")
        self._unload_btn.setToolTip("卸载当前模型释放显存")
        self._unload_btn.clicked.connect(self._on_unload_model)
        self._unload_btn.setEnabled(False)
        self._unload_btn.setObjectName("model_unload_btn")
        btn_layout.addWidget(self._unload_btn)
        layout.addLayout(btn_layout)

        # ── 分隔线 ──
        layout.addWidget(self._make_sep())

        # ── 置信度阈值 ──
        thresh_header = QLabel("置信度阈值")
        thresh_header.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: bold;")
        layout.addWidget(thresh_header)
        threshold_layout = QHBoxLayout()
        self._threshold_slider = QSlider(Qt.Horizontal)
        self._threshold_slider.setRange(5, 95)      # 0.05 ~ 0.95
        self._threshold_slider.setValue(25)          # 默认 0.25
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        self._threshold_slider.setObjectName("model_threshold_slider")
        threshold_layout.addWidget(self._threshold_slider, 1)

        self._threshold_label = QLabel("0.25")
        self._threshold_label.setFixedWidth(36)
        self._threshold_label.setStyleSheet("color: #00ccff; font-weight: bold;")
        threshold_layout.addWidget(self._threshold_label)
        layout.addLayout(threshold_layout)

        # ── IoU 阈值 ──
        iou_layout = QHBoxLayout()
        iou_label = QLabel("IoU 阈值")
        iou_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        iou_layout.addWidget(iou_label)

        self._iou_slider = QSlider(Qt.Horizontal)
        self._iou_slider.setRange(10, 90)       # 0.10 ~ 0.90
        self._iou_slider.setValue(45)            # 默认 0.45
        self._iou_slider.valueChanged.connect(self._on_iou_changed)
        self._iou_slider.setObjectName("iou_slider")
        iou_layout.addWidget(self._iou_slider, 1)

        self._iou_label = QLabel("0.45")
        self._iou_label.setFixedWidth(36)
        self._iou_label.setStyleSheet("color: #00ccff; font-weight: bold;")
        iou_layout.addWidget(self._iou_label)
        layout.addLayout(iou_layout)

        # ── 类别映射 ──
        mapping_layout = QHBoxLayout()
        self._mapping_btn = QPushButton("📋 类别映射")
        self._mapping_btn.setToolTip("配置模型输出索引到项目类别的映射关系")
        self._mapping_btn.clicked.connect(self._on_class_mapping)
        self._mapping_btn.setEnabled(False)
        mapping_layout.addWidget(self._mapping_btn)

        self._mapping_status = QLabel("未配置")
        self._mapping_status.setStyleSheet("color: #888888; font-size: 10px;")
        mapping_layout.addWidget(self._mapping_status)
        layout.addLayout(mapping_layout)

        # ── 分隔线 ──
        layout.addWidget(self._make_sep())

        # ── 自动标注按钮 ──
        self._auto_btn = QPushButton("🎯 自动标注当前图片")
        self._auto_btn.setToolTip("使用模型自动检测当前图片 (Enter 接受)")
        self._auto_btn.clicked.connect(self.auto_label_requested.emit)
        self._auto_btn.setEnabled(False)
        self._auto_btn.setObjectName("model_auto_btn")
        layout.addWidget(self._auto_btn)

        self._batch_btn = QPushButton("📦 批量标注所有图片")
        self._batch_btn.setToolTip("对所有未标注图片运行模型")
        self._batch_btn.clicked.connect(self.batch_label_requested.emit)
        self._batch_btn.setEnabled(False)
        layout.addWidget(self._batch_btn)

        # ── 分隔线 ──
        layout.addWidget(self._make_sep())

        # ── 预测结果统计 ──
        self._pred_count_label = QLabel("预测: 0 个结果")
        self._pred_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._pred_count_label)

        # ── 接受/拒绝 ──
        action_layout = QHBoxLayout()
        self._accept_all_btn = QPushButton("✅ 全部接受")
        self._accept_all_btn.setToolTip("接受所有高于阈值的预测 (Ctrl+Enter)")
        self._accept_all_btn.clicked.connect(self._on_accept_all)
        self._accept_all_btn.setEnabled(False)
        action_layout.addWidget(self._accept_all_btn)

        self._reject_all_btn = QPushButton("❌ 全部拒绝")
        self._reject_all_btn.setToolTip("拒绝所有高于阈值的预测")
        self._reject_all_btn.clicked.connect(self._on_reject_all)
        self._reject_all_btn.setEnabled(False)
        action_layout.addWidget(self._reject_all_btn)
        layout.addLayout(action_layout)

        # ── 快捷键提示 ──
        tips = QLabel("Enter 接受选中  |  Del 拒绝选中")
        tips.setStyleSheet("color: #666666; font-size: 10px; padding: 4px;")
        tips.setAlignment(Qt.AlignCenter)
        layout.addWidget(tips)

        layout.addStretch()
        # no setWidget — ModelDock is now a QWidget

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3d3d3d;")
        sep.setFixedHeight(2)
        return sep

    # ── 状态更新 ──

    def set_model_status(self, loaded: bool, name: str = ""):
        """更新模型状态显示"""
        self._model_loaded = loaded
        if loaded:
            self._status_label.setText(f"🟢 模型: {name}")
            self._status_label.setStyleSheet("QLabel { color: #00cc66; background-color: #1d3d1d; }")
            self._load_btn.setEnabled(False)
            self._unload_btn.setEnabled(True)
            self._auto_btn.setEnabled(True)
            self._batch_btn.setEnabled(True)
            self._mapping_btn.setEnabled(True)
        else:
            self._status_label.setText("⚪ 模型: 未加载")
            self._status_label.setStyleSheet("QLabel { color: #aaaaaa; background-color: #2d2d2d; }")
            self._load_btn.setEnabled(True)
            self._unload_btn.setEnabled(False)
            self._auto_btn.setEnabled(False)
            self._batch_btn.setEnabled(False)
            self._mapping_btn.setEnabled(False)
            self._mapping_status.setText("未配置")
            self._mapping_status.setStyleSheet("color: #888888; font-size: 10px;")
            self.set_prediction_count(0)
            self._model_path = ""
            self._path_label.setText("未选择模型")
            self._path_label.setToolTip("")

    def set_prediction_count(self, count: int):
        """更新预测数量"""
        self._prediction_count = count
        self._pred_count_label.setText(f"预测: {count} 个结果")
        self._accept_all_btn.setEnabled(count > 0)
        self._reject_all_btn.setEnabled(count > 0)

    def get_threshold(self) -> float:
        """获取当前置信度阈值"""
        return self._threshold_slider.value() / 100.0

    def set_model_path(self, path: str):
        """设置显示路径，过长时自动截断"""
        self._model_path = path
        from pathlib import Path
        p = Path(path)
        display = path
        if len(display) > 40:
            display = f".../{p.parent.name}/{p.name}"
        if len(display) > 40:
            display = f".../{p.name}"
        self._path_label.setText(display)
        self._path_label.setToolTip(path)

    def set_model_class_names(self, names: list):
        """保存模型输出类别名称列表"""
        self._model_class_names = names

    def set_mapping_status(self, configured: bool, detail: str = ""):
        """更新映射状态"""
        self._mapping_btn.setEnabled(True)
        if configured:
            self._mapping_status.setText(f"✓ {detail}" if detail else "✓ 已配置")
            self._mapping_status.setStyleSheet("color: #00cc66; font-size: 10px;")
        else:
            self._mapping_status.setText("未配置")
            self._mapping_status.setStyleSheet("color: #888888; font-size: 10px;")

    # ── 事件处理 ──

    def _on_browse_model(self):
        """选择模型文件"""
        path, _ = QFileDialog.getOpenFileName(
            None, "选择模型文件", self._last_browse_dir,
            "模型文件 (*.pt *.engine *.onnx);;所有文件 (*)")
        if path:
            self._last_browse_dir = str(Path(path).parent)
            self.set_model_path(path)
            self._on_load_model()

    def _on_load_model(self):
        """加载模型"""
        path = self._model_path
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "提示", "请先选择有效的模型文件")
            return
        self.load_model_requested.emit(path)

    def _on_unload_model(self):
        """卸载模型"""
        self.unload_model_requested.emit()

    def _on_class_mapping(self):
        """配置类别映射"""
        self.class_mapping_requested.emit()

    def _on_threshold_changed(self, value: int):
        """置信度滑块变化"""
        threshold = value / 100.0
        self._threshold_label.setText(f"{threshold:.2f}")
        self.conf_threshold_changed.emit(threshold)

    def _on_iou_changed(self, value: int):
        """IoU 阈值滑块变化"""
        threshold = value / 100.0
        self._iou_label.setText(f"{threshold:.2f}")
        self.iou_threshold_changed.emit(threshold)

    def get_iou_threshold(self) -> float:
        """获取当前 IoU 阈值"""
        return self._iou_slider.value() / 100.0

    def _on_accept_all(self):
        """接受全部"""
        self.accept_all_requested.emit(self.get_threshold())

    def _on_reject_all(self):
        """拒绝全部"""
        self.reject_all_requested.emit(self.get_threshold())
