"""TrainDock - 训练管理面板

提供 YOLO 模型训练的完整 UI：
- 数据集统计概览
- 训练参数配置（预设 / 手动）
- 增量训练支持
- 开始 / 停止训练
- 训练进度、指标、日志实时显示
- 训练完成后自动加载模型
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QTextEdit, QProgressBar,
    QFrame, QFileDialog, QMessageBox, QToolButton,
    QGroupBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCursor
from pathlib import Path
from typing import Optional

from backend.train.config import TrainingConfig, TRAINING_PRESETS, COMMON_ARCHES
from backend.train.trainer import YOLOTrainer, TrainingProgress


# ════════════════════════════════════════════════════════════════
# TrainingWorker - 在 QThread 中运行训练的 QObject
# ════════════════════════════════════════════════════════════════


class TrainingWorker(QObject):
    """训练工作线程——封装 YOLOTrainer，通过 Qt 信号与 UI 通信

    注意：数据集导出（export_dataset）必须在主线程完成（SQLite 非线程安全），
    传入 data_yaml_path 后 worker 只负责执行 YOLO 训练。
    """

    progress_updated = pyqtSignal(object)   # TrainingProgress
    log_message = pyqtSignal(str)           # 文本行
    finished = pyqtSignal(bool, str)        # (成功, 消息)
    model_saved = pyqtSignal(str)           # 模型路径

    def __init__(self, project, config: TrainingConfig, data_yaml_path: str):
        super().__init__()
        self._project = project
        self._config = config
        self._data_yaml_path = data_yaml_path
        self._trainer: Optional[YOLOTrainer] = None
        self._should_stop = False

    def stop(self):
        self._should_stop = True
        if self._trainer:
            try:
                self._trainer.stop()
            except Exception:
                pass

    def run(self):
        """在线程中执行训练（通过 QThread.started 信号触发）"""
        self._should_stop = False

        try:
            # ── 1. 初始化训练器 ──
            self._trainer = YOLOTrainer(self._project, self._config)
            self.log_message.emit(f"数据集已就绪: {Path(self._data_yaml_path).name}")
            self.log_message.emit("开始训练...")

            if self._should_stop:
                self.finished.emit(False, "训练已取消")
                return

            # ── 2. 执行训练（数据已在主线程导出）──
            self._trainer.train(
                Path(self._data_yaml_path),
                on_progress=lambda p: self.progress_updated.emit(p),
                on_log=lambda msg: self.log_message.emit(msg),
                on_model_saved=lambda path: self.model_saved.emit(str(path)),
                save_record=False,  # 训练记录由主线程保存
            )

            # ── 3. 完成 ──
            if self._should_stop:
                self.finished.emit(False, "训练已停止")
            else:
                self.finished.emit(True, "训练完成！模型已保存到项目目录。")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_message.emit(f"错误: {e}")
            self.log_message.emit(traceback.format_exc())
            self.finished.emit(False, f"训练失败: {e}")


# ════════════════════════════════════════════════════════════════
# TrainDock - 训练管理面板
# ════════════════════════════════════════════════════════════════


class TrainDock(QWidget):
    """训练管理面板"""

    # 信号
    training_started = pyqtSignal()          # 训练开始
    training_finished = pyqtSignal(bool)     # 训练结束（是否成功）
    model_saved = pyqtSignal(str)            # 新模型已保存（路径）
    load_model_requested = pyqtSignal(str)   # 加载训练好的模型

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._worker: Optional[TrainingWorker] = None
        self._thread: Optional[QThread] = None
        self._is_training = False

        self._setup_ui()
        self._update_ui_state()
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)

    # ── UI 构建 ──

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # ══════════════════════════════════════
        # 标题
        # ══════════════════════════════════════
        title = QLabel("🏋️ 训练管理")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #cccccc; padding: 4px 0;")
        layout.addWidget(title)

        # ══════════════════════════════════════
        # 数据集统计
        # ══════════════════════════════════════
        self._stats_label = QLabel("数据集: 请先打开项目")
        self._stats_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 0;")
        layout.addWidget(self._stats_label)

        layout.addWidget(self._make_sep())

        # ══════════════════════════════════════
        # 训练预设
        # ══════════════════════════════════════
        preset_layout = QHBoxLayout()
        preset_label = QLabel("预设方案:")
        preset_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        preset_layout.addWidget(preset_label)

        self._preset_combo = QComboBox()
        self._preset_combo.addItem("自定义")
        for name in TRAINING_PRESETS:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._preset_combo.setStyleSheet(self._combo_style())
        preset_layout.addWidget(self._preset_combo, 1)
        layout.addLayout(preset_layout)

        # ══════════════════════════════════════
        # 训练参数网格
        # ══════════════════════════════════════
        param_grid = QGridLayout()
        param_grid.setSpacing(4)

        row = 0
        # 架构
        param_grid.addWidget(self._make_label("架构:"), row, 0)
        self._arch_combo = QComboBox()
        for a in COMMON_ARCHES:
            self._arch_combo.addItem(a)
        self._arch_combo.setEditable(True)
        self._arch_combo.setCurrentText('yolov8n.pt')
        self._arch_combo.currentTextChanged.connect(self._mark_custom_preset)
        self._arch_combo.setStyleSheet(self._combo_style())
        param_grid.addWidget(self._arch_combo, row, 1)
        row += 1

        # 轮数
        param_grid.addWidget(self._make_label("轮数:"), row, 0)
        self._epochs_spin = QSpinBox()
        self._epochs_spin.setRange(1, 1000)
        self._epochs_spin.setValue(100)
        self._epochs_spin.setSuffix(" epoch")
        self._epochs_spin.valueChanged.connect(self._mark_custom_preset)
        self._epochs_spin.setStyleSheet(self._spin_style())
        param_grid.addWidget(self._epochs_spin, row, 1)
        row += 1

        # 批次
        param_grid.addWidget(self._make_label("批次:"), row, 0)
        self._batch_spin = QSpinBox()
        self._batch_spin.setRange(1, 256)
        self._batch_spin.setValue(16)
        self._batch_spin.valueChanged.connect(self._mark_custom_preset)
        self._batch_spin.setStyleSheet(self._spin_style())
        param_grid.addWidget(self._batch_spin, row, 1)
        row += 1

        # 图片尺寸
        param_grid.addWidget(self._make_label("尺寸:"), row, 0)
        self._imgsz_spin = QSpinBox()
        self._imgsz_spin.setRange(32, 1280)
        self._imgsz_spin.setSingleStep(32)
        self._imgsz_spin.setValue(640)
        self._imgsz_spin.setSuffix(" px")
        self._imgsz_spin.valueChanged.connect(self._mark_custom_preset)
        self._imgsz_spin.setStyleSheet(self._spin_style())
        param_grid.addWidget(self._imgsz_spin, row, 1)
        row += 1

        # 设备
        param_grid.addWidget(self._make_label("设备:"), row, 0)
        self._device_combo = QComboBox()
        for dev in ['auto', 'cpu', '0', '1', '0,1']:
            self._device_combo.addItem(dev)
        self._device_combo.currentTextChanged.connect(self._mark_custom_preset)
        self._device_combo.setStyleSheet(self._combo_style())
        param_grid.addWidget(self._device_combo, row, 1)

        layout.addLayout(param_grid)

        # ══════════════════════════════════════
        # 增量训练
        # ══════════════════════════════════════
        incr_layout = QHBoxLayout()
        self._resume_cb = QCheckBox("增量训练")
        self._resume_cb.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self._resume_cb.toggled.connect(self._on_resume_toggled)
        incr_layout.addWidget(self._resume_cb)

        self._resume_path_btn = QPushButton("选择检查点")
        self._resume_path_btn.setEnabled(False)
        self._resume_path_btn.clicked.connect(self._on_browse_resume)
        self._resume_path_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        incr_layout.addWidget(self._resume_path_btn)

        self._resume_path_label = QLabel("")
        self._resume_path_label.setStyleSheet("color: #666666; font-size: 9px;")
        self._resume_path_label.setWordWrap(True)
        incr_layout.addWidget(self._resume_path_label, 1)
        layout.addLayout(incr_layout)

        # ══════════════════════════════════════
        # 高级参数（可折叠）
        # ══════════════════════════════════════
        self._advanced_btn = QPushButton("▸ 高级参数")
        self._advanced_btn.setCheckable(True)
        self._advanced_btn.setStyleSheet("""
            QPushButton {
                text-align: left; background: transparent; border: none;
                color: #888888; font-size: 11px; padding: 4px 0;
            }
            QPushButton:hover { color: #cccccc; }
            QPushButton:checked { color: #0d6efd; }
        """)
        self._advanced_btn.toggled.connect(self._toggle_advanced)
        layout.addWidget(self._advanced_btn)

        self._advanced_widget = QWidget()
        self._advanced_widget.setVisible(False)
        adv_layout = QGridLayout(self._advanced_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(4)

        # 优化器
        adv_layout.addWidget(self._make_label("优化器:"), 0, 0)
        self._optimizer_combo = QComboBox()
        for opt in ['auto', 'SGD', 'Adam', 'AdamW']:
            self._optimizer_combo.addItem(opt)
        self._optimizer_combo.setStyleSheet(self._combo_style())
        adv_layout.addWidget(self._optimizer_combo, 0, 1)

        # 学习率
        adv_layout.addWidget(self._make_label("学习率:"), 1, 0)
        self._lr_spin = QDoubleSpinBox()
        self._lr_spin.setRange(0.00001, 1.0)
        self._lr_spin.setSingleStep(0.001)
        self._lr_spin.setDecimals(5)
        self._lr_spin.setValue(0.01)
        self._lr_spin.setStyleSheet(self._spin_style())
        adv_layout.addWidget(self._lr_spin, 1, 1)

        # 耐心值 (early stopping)
        adv_layout.addWidget(self._make_label("早停耐心:"), 2, 0)
        self._patience_spin = QSpinBox()
        self._patience_spin.setRange(0, 500)
        self._patience_spin.setValue(50)
        self._patience_spin.setSuffix(" epoch")
        self._patience_spin.setStyleSheet(self._spin_style())
        adv_layout.addWidget(self._patience_spin, 2, 1)

        # 数据增强
        self._augment_cb = QCheckBox("数据增强")
        self._augment_cb.setChecked(True)
        self._augment_cb.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        adv_layout.addWidget(self._augment_cb, 3, 0, 1, 2)

        # 训练/验证 分割
        adv_layout.addWidget(self._make_label("训练集比例:"), 4, 0)
        self._split_spin = QDoubleSpinBox()
        self._split_spin.setRange(0.5, 0.99)
        self._split_spin.setSingleStep(0.05)
        self._split_spin.setDecimals(2)
        self._split_spin.setValue(0.9)
        self._split_spin.setStyleSheet(self._spin_style())
        adv_layout.addWidget(self._split_spin, 4, 1)

        layout.addWidget(self._advanced_widget)

        # ══════════════════════════════════════
        # 操作按钮
        # ══════════════════════════════════════
        layout.addWidget(self._make_sep())

        self._train_btn = QPushButton("🚀 开始训练")
        self._train_btn.setToolTip("导出标注数据并开始训练 YOLO 模型")
        self._train_btn.clicked.connect(self._on_start_training)
        self._train_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 8px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #0b5ed7; }
            QPushButton:disabled { background-color: #3d3d3d; color: #888888; }
        """)
        layout.addWidget(self._train_btn)

        self._stop_btn = QPushButton("⏹ 停止训练")
        self._stop_btn.setToolTip("停止当前训练（将保存当前检查点）")
        self._stop_btn.clicked.connect(self._on_stop_training)
        self._stop_btn.setVisible(False)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 8px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #bb2d3b; }
        """)
        layout.addWidget(self._stop_btn)

        # 自动加载选项
        self._auto_load_cb = QCheckBox("训练完成后自动加载模型")
        self._auto_load_cb.setChecked(True)
        self._auto_load_cb.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self._auto_load_cb)

        # ══════════════════════════════════════
        # 训练进度
        # ══════════════════════════════════════
        self._progress_group = QWidget()
        self._progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self._progress_group)
        progress_layout.setContentsMargins(0, 4, 0, 0)
        progress_layout.setSpacing(4)

        # 进度条 + epoch
        epoch_layout = QHBoxLayout()
        self._epoch_label = QLabel("Epoch: 0/0")
        self._epoch_label.setStyleSheet("color: #00ccff; font-size: 11px; font-weight: bold;")
        epoch_layout.addWidget(self._epoch_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(16)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555555; border-radius: 3px;
                background: #2d2d2d; text-align: center; font-size: 10px; color: #cccccc;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0d6efd, stop:1 #00ccff);
                border-radius: 2px;
            }
        """)
        epoch_layout.addWidget(self._progress_bar, 1)
        progress_layout.addLayout(epoch_layout)

        # 指标网格
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(4)

        self._loss_label = self._make_metric_label("损失: -")
        metrics_grid.addWidget(self._make_metric_title("损失"), 0, 0)
        metrics_grid.addWidget(self._loss_label, 1, 0)

        self._map50_label = self._make_metric_label("mAP50: -")
        metrics_grid.addWidget(self._make_metric_title("mAP50"), 0, 1)
        metrics_grid.addWidget(self._map50_label, 1, 1)

        self._map50_95_label = self._make_metric_label("mAP50-95: -")
        metrics_grid.addWidget(self._make_metric_title("mAP50-95"), 0, 2)
        metrics_grid.addWidget(self._map50_95_label, 1, 2)

        self._lr_label = self._make_metric_label("LR: -")
        metrics_grid.addWidget(self._make_metric_title("学习率"), 2, 0)
        metrics_grid.addWidget(self._lr_label, 3, 0)

        self._time_label = self._make_metric_label("已用: -")
        metrics_grid.addWidget(self._make_metric_title("已用时间"), 2, 1)
        metrics_grid.addWidget(self._time_label, 3, 1)

        self._remain_label = self._make_metric_label("剩余: -")
        metrics_grid.addWidget(self._make_metric_title("预计剩余"), 2, 2)
        metrics_grid.addWidget(self._remain_label, 3, 2)

        progress_layout.addLayout(metrics_grid)

        layout.addWidget(self._progress_group)

        # ══════════════════════════════════════
        # 训练日志
        # ══════════════════════════════════════
        log_header = QLabel("训练日志")
        log_header.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(log_header)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMinimumHeight(60)
        self._log_text.setMaximumHeight(200)
        self._log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a; color: #cccccc;
                border: 1px solid #3d3d3d; border-radius: 3px;
                padding: 4px; font-family: 'Courier New', monospace; font-size: 10px;
            }
        """)
        layout.addWidget(self._log_text)

        # 清空日志按钮
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setFixedWidth(80)
        clear_log_btn.setStyleSheet("font-size: 9px; padding: 2px 4px;")
        clear_log_btn.clicked.connect(self._log_text.clear)
        layout.addWidget(clear_log_btn, 0, Qt.AlignRight)

        layout.addStretch()

    # ── 样式辅助 ──

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3d3d3d;")
        sep.setFixedHeight(2)
        return sep

    def _make_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        return label

    def _make_metric_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #666666; font-size: 9px;")
        return label

    def _make_metric_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #00ccff; font-size: 11px; font-weight: bold;")
        return label

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #3d3d3d; color: #cccccc;
                border: 1px solid #555555; border-radius: 3px;
                padding: 2px 4px; font-size: 11px; min-height: 18px;
            }
            QComboBox::drop-down { border: none; width: 16px; }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d; color: #cccccc;
                selection-background-color: #0d6efd; font-size: 11px;
            }
        """

    def _spin_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background-color: #3d3d3d; color: #cccccc;
                border: 1px solid #555555; border-radius: 3px;
                padding: 2px 4px; font-size: 11px; min-height: 18px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                border: none; width: 12px;
            }
        """

    # ── 预设 ──

    def _on_preset_changed(self, preset_name: str):
        """选择预设方案时自动填充参数"""
        if preset_name == "自定义":
            return
        preset = TRAINING_PRESETS.get(preset_name)
        if not preset:
            return

        # 阻断信号避免重复标记
        self._preset_combo.blockSignals(True)
        for key in ['arch', 'epochs', 'batch', 'imgsz', 'optimizer', 'patience', 'augment']:
            widgets = {
                'arch': self._arch_combo,
                'epochs': self._epochs_spin,
                'batch': self._batch_spin,
                'imgsz': self._imgsz_spin,
                'optimizer': self._optimizer_combo,
                'patience': self._patience_spin,
                'augment': self._augment_cb,
            }
            w = widgets.get(key)
            if w and key in preset:
                val = preset[key]
                if isinstance(w, QComboBox):
                    w.setCurrentText(str(val))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(val))
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.setValue(val)

        self._preset_combo.blockSignals(False)
        self._preset_combo.setCurrentText(preset_name)

    def _mark_custom_preset(self):
        """用户手动修改参数时切回自定义预设"""
        if self._preset_combo.currentText() != "自定义":
            self._preset_combo.blockSignals(True)
            self._preset_combo.setCurrentText("自定义")
            self._preset_combo.blockSignals(False)

    # ── 增量训练 ──

    def _on_resume_toggled(self, checked: bool):
        self._resume_path_btn.setEnabled(checked)
        if not checked:
            self._resume_path_label.setText("")

    def _on_browse_resume(self):
        """选择用于增量训练的检查点"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模型检查点", str(Path.home()),
            "模型文件 (*.pt *.engine *.onnx);;所有文件 (*)")
        if path:
            self._resume_path_label.setText(Path(path).name)
            self._resume_path_label.setToolTip(path)
            self._resume_path_btn.setText("更换检查点")

    # ── 高级参数折叠 ──

    def _toggle_advanced(self, checked: bool):
        self._advanced_widget.setVisible(checked)
        self._advanced_btn.setText("▾ 高级参数" if checked else "▸ 高级参数")

    # ── 训练控制 ──

    def _on_start_training(self):
        """开始训练"""
        if self._is_training or not self._project:
            return

        # 构建训练配置
        config = self._build_config()

        # 确认训练
        stats = self._project.get_stats()
        if stats['total_images'] == 0:
            QMessageBox.warning(self, "提示", "项目中没有图片，请先导入图片")
            return
        if stats['annotated_images'] == 0:
            QMessageBox.warning(self, "提示", "项目中没有标注数据，请先标注图片")
            return

        reply = QMessageBox.question(
            self, "开始训练",
            f"即将开始训练 YOLO 模型：\n"
            f"  架构: {config.model_arch}\n"
            f"  数据集: {stats['annotated_images']}/{stats['total_images']} 张已标注\n"
            f"  类别: {stats['class_count']}\n"
            f"  轮数: {config.epochs} | 批次: {config.batch}\n\n"
            f"训练期间界面可能响应变慢，是否继续？",
            QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        self._start_training(config)

    def _build_config(self) -> TrainingConfig:
        """从 UI 控件读取训练参数"""
        resume_path = ""
        if self._resume_cb.isChecked():
            path_text = self._resume_path_label.text()
            if path_text:
                resume_path = self._resume_path_label.toolTip() or path_text

        return TrainingConfig(
            model_arch=self._arch_combo.currentText(),
            epochs=self._epochs_spin.value(),
            batch=self._batch_spin.value(),
            imgsz=self._imgsz_spin.value(),
            device=self._device_combo.currentText(),
            optimizer=self._optimizer_combo.currentText(),
            lr0=self._lr_spin.value(),
            patience=self._patience_spin.value(),
            augment=self._augment_cb.isChecked(),
            split=self._split_spin.value(),
            resume_from=resume_path,
        )

    def _start_training(self, config: TrainingConfig):
        """在后台线程中启动训练"""
        # ── 1. 在主线程导出数据集（SQLite 非线程安全）──
        self._log("正在导出标注数据到 YOLO 格式...")
        try:
            trainer = YOLOTrainer(self._project, config)
            data_yaml = trainer.export_dataset()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"数据集导出出错:\n{e}")
            return

        if data_yaml is None:
            QMessageBox.warning(self, "导出失败", "项目中没有标注数据，请先标注图片")
            return

        stats = self._project.get_stats()
        n_train = int(stats['annotated_images'] * config.split)
        n_val = stats['annotated_images'] - n_train
        self._log(f"数据集导出完成：{stats['annotated_images']} 张标注图片 → "
                  f"{n_train} 训练 / {n_val} 验证")

        # ── 2. 准备 worker 和线程 ──
        self._worker = TrainingWorker(self._project, config, str(data_yaml))
        self._thread = QThread(self)

        self._worker.moveToThread(self._thread)

        # 信号连接
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.log_message.connect(self._on_log)
        self._worker.finished.connect(self._on_training_finished)
        self._worker.model_saved.connect(self._on_model_saved)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)

        # ── UI 状态变更 ──
        self._is_training = True
        self._train_btn.setVisible(False)
        self._stop_btn.setVisible(True)
        self._progress_group.setVisible(True)
        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._update_metric_labels(0.0, 0.0, 0.0, 0.0, 0.0)
        self._epoch_label.setText("Epoch: 0/{}".format(config.epochs))
        self._set_params_enabled(False)

        self.training_started.emit()

        # ── 3. 启动线程 ──
        self._thread.start()

    def _on_stop_training(self):
        """停止训练"""
        if self._worker and self._is_training:
            self._worker.stop()
            self._log("⏹ 正在停止训练（等待当前轮次完成）...")

    # ── 训练回调 ──

    def _on_progress(self, progress: TrainingProgress):
        """训练进度更新"""
        pct = int(progress.epoch / max(progress.total_epochs, 1) * 100)
        self._progress_bar.setValue(pct)
        self._epoch_label.setText(f"Epoch: {progress.epoch}/{progress.total_epochs}")

        self._update_metric_labels(
            progress.loss,
            progress.mAP50,
            progress.mAP50_95,
            progress.current_lr,
            progress.precision,
        )

        # 时间
        elapsed = progress.time_elapsed
        self._time_label.setText(f"已用: {self._format_time(elapsed)}")
        if progress.time_remaining > 0:
            self._remain_label.setText(f"剩余: ~{self._format_time(progress.time_remaining)}")
        else:
            self._remain_label.setText("剩余: 计算中...")

    def _on_log(self, message: str):
        """日志消息"""
        self._log(message)

    def _on_model_saved(self, model_path: str):
        """模型保存回调"""
        self._log(f"📦 模型已保存: {model_path}")
        self.model_saved.emit(model_path)

        # 如果勾选了自动加载
        if self._auto_load_cb.isChecked():
            self._log(f"🔄 正在自动加载模型...")
            self.load_model_requested.emit(model_path)

    def _on_training_finished(self, success: bool, message: str):
        """训练完成（在 main thread 中执行）"""
        self._is_training = False
        self._train_btn.setVisible(True)
        self._stop_btn.setVisible(False)
        self._set_params_enabled(True)

        if success:
            self._progress_bar.setValue(100)
            self._epoch_label.setText("Epoch: 完成 ✓")
            # 在 main thread 保存训练记录（避免 YAML 并发写入）
            self._save_training_record()
        else:
            self._log(f"⛔ {message}")

        # 清理线程
        if self._thread:
            self._thread.quit()
            self._thread.wait(3000)
            self._thread = None
        self._worker = None

        self._log(message)
        self.training_finished.emit(success)

    def _save_training_record(self):
        """在 main thread 保存训练记录到项目配置"""
        if not self._project:
            return
        try:
            config = self._build_config()
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            records = self._project.config.get('training_history') or []
            if not isinstance(records, list):
                records = []
            records.append({
                'timestamp': timestamp,
                'model_arch': config.model_arch,
                'epochs': config.epochs,
                'batch': config.batch,
                'imgsz': config.imgsz,
                'created_at': datetime.now().isoformat(),
            })
            if len(records) > 20:
                records = records[-20:]
            self._project.config.set('training_history', records)
            self._log(f"📝 训练记录已保存")
        except Exception as e:
            self._log(f"⚠️ 保存训练记录失败: {e}")

    # ── UI 辅助 ──

    def _update_metric_labels(self, loss=0.0, map50=0.0, map50_95=0.0,
                               lr=0.0, precision=0.0):
        """更新指标显示"""
        self._loss_label.setText(f"损失: {loss:.4f}" if loss > 0 else "损失: 计算中...")
        self._map50_label.setText(f"mAP50: {map50:.4f}" if map50 > 0 else "mAP50: -")
        self._map50_95_label.setText(f"mAP50-95: {map50_95:.4f}" if map50_95 > 0 else "mAP50-95: -")
        self._lr_label.setText(f"LR: {lr:.6f}" if lr > 0 else "LR: -")

    def _log(self, message: str):
        """追加日志"""
        self._log_text.append(message)
        # 自动滚动到底部
        cursor = self._log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._log_text.setTextCursor(cursor)
        # 限制行数
        doc = self._log_text.document()
        if doc.blockCount() > 500:
            cursor = QTextCursor(doc.begin())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _set_params_enabled(self, enabled: bool):
        """启用/禁用训练参数控件"""
        self._preset_combo.setEnabled(enabled)
        self._arch_combo.setEnabled(enabled)
        self._epochs_spin.setEnabled(enabled)
        self._batch_spin.setEnabled(enabled)
        self._imgsz_spin.setEnabled(enabled)
        self._device_combo.setEnabled(enabled)
        self._resume_cb.setEnabled(enabled)
        self._resume_path_btn.setEnabled(enabled and self._resume_cb.isChecked())
        self._advanced_btn.setEnabled(enabled)

        # 高级参数也要禁用
        for w in [
            self._optimizer_combo, self._lr_spin,
            self._patience_spin, self._augment_cb, self._split_spin,
        ]:
            w.setEnabled(enabled)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 0:
            return "-"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        elif minutes > 0:
            return f"{minutes}:{secs:02d}"
        else:
            return f"0:{secs:02d}"

    # ── 更新 UI 状态 ──

    def _update_ui_state(self):
        """根据项目状态更新 UI"""
        has_project = self._project is not None
        self._train_btn.setEnabled(has_project and not self._is_training)
        self._preset_combo.setEnabled(has_project and not self._is_training)
        self._set_params_enabled(has_project and not self._is_training)

    def set_project(self, project):
        """设置当前项目，更新统计信息"""
        self._project = project
        if project:
            stats = project.get_stats()
            self._stats_label.setText(
                f"📊 {stats['total_images']} 图片 | "
                f"{stats['annotated_images']} 已标注 | "
                f"{stats['class_count']} 类别"
            )
            self._stats_label.setStyleSheet("color: #00cc66; font-size: 11px; padding: 2px 0;")
        else:
            self._stats_label.setText("数据集: 请先打开项目")
            self._stats_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 0;")

        self._update_ui_state()

    def update_stats(self):
        """刷新统计信息（标注变更后调用）"""
        if self._project:
            self.set_project(self._project)

    def reset(self):
        """重置训练状态（项目关闭时调用）"""
        if self._is_training:
            self._on_stop_training()
        self._project = None
        self._progress_group.setVisible(False)
        self._train_btn.setVisible(True)
        self._stop_btn.setVisible(False)
        self._log_text.clear()
        self._stats_label.setText("数据集: 请先打开项目")
        self._stats_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 0;")
        self._update_ui_state()
