"""YOLOTrainer - YOLO 模型训练器

支持一键训练（从预训练权重开始）和增量训练（从已有检查点继续）。
使用 ultralytics YOLO 训练 API，通过回调机制报告进度。
无 GUI 依赖，可在任意线程使用。
"""

import time
import shutil
import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime

from ..project.project import Project
from .config import TrainingConfig, is_seg_model

logger = logging.getLogger(__name__)


class TrainingProgress:
    """训练进度快照——从 ultralytics 回调中收集，通过信号传递给 UI"""

    def __init__(self):
        self.epoch: int = 0
        self.total_epochs: int = 0
        self.loss: float = 0.0
        self.mAP50: float = 0.0
        self.mAP50_95: float = 0.0
        self.precision: float = 0.0
        self.recall: float = 0.0
        self.current_lr: float = 0.0
        self.time_elapsed: float = 0.0       # 秒
        self.time_remaining: float = 0.0      # 秒
        self.stage: str = ''                   # preparing / training / done / error
        self.error: str = ''


class YOLOTrainer:
    """核心训练逻辑——线程安全，通过回调与 GUI 通信"""

    def __init__(self, project: Project, config: Optional[TrainingConfig] = None):
        self.project = project
        self.config = config or TrainingConfig()
        self._should_stop = False
        self._start_time = 0.0
        self._trainer_ref = None

    # ── 控制 ──

    def stop(self):
        """请求停止训练"""
        self._should_stop = True
        if self._trainer_ref is not None:
            try:
                self._trainer_ref.stop = True
            except Exception:
                pass

    @property
    def is_stop_requested(self) -> bool:
        return self._should_stop

    @staticmethod
    def _resolve_model_path(model_arch: str) -> Optional[Path]:
        """解析模型文件路径，按优先级查找：

        1. 如果是完整路径（含 /），检查该路径
        2. mostpt/ 目录下（最优先）
        3. 项目根目录
        4. Ultralytics cache 目录

        返回的路径必须 > 3MB 才视为有效（过滤损坏文件）。
        """
        p = Path(model_arch)

        def _is_valid(file: Path) -> bool:
            return file.exists() and file.is_file() and file.stat().st_size > 3_000_000

        # 1. 完整路径
        if ('/' in model_arch or '\\' in model_arch) and _is_valid(p):
            return p.resolve()

        # 2. 搜索目录（mostpt 优先）
        root = Path(__file__).parent.parent.parent  # fastlabel 根目录
        search_dirs = [
            root / 'mostpt',
            Path.cwd() / 'mostpt',
            root,
            Path.cwd(),
        ]
        for d in search_dirs:
            candidate = (d / p.name).resolve()
            if _is_valid(candidate):
                return candidate

        return None

    # ── 数据集导出 ──

    def export_dataset(self) -> Optional[Path]:
        """将项目标注导出为 YOLO 训练格式，生成 training_data.yaml

        - 检测模型 → 5 列标签（class_id cx cy w h）
        - 分割模型 → N 列标签（class_id x1 y1 x2 y2 ...），
          多边形坐标已归一化 (0~1)，不带 bbox 前缀。
          对纯 bbox 标注自动用框四角生成 4 点多边形。
        """
        # 判断模型类型（分割模型需要导出多边形点）
        seg_mode = is_seg_model(self.config.model_arch)

        # 收集有标注的图片
        all_images = self.project.get_all_images()
        annotated = [img for img in all_images if img['num_annotations'] > 0]

        if not annotated:
            return None

        # 类别 ID 映射：项目 class_id → YOLO 0-index 索引
        # 项目类别可能从 1 开始编号，但 YOLO 训练必须从 0 开始
        classes = self.project.get_classes()
        class_id_map = {c['id']: i for i, c in enumerate(classes)}
        nc = len(classes)

        # 导出标签
        labels_dir = self.project.path / 'labels'
        labels_dir.mkdir(parents=True, exist_ok=True)
        for img in annotated:
            annotations = self.project.get_annotations(img['id'])
            if not annotations:
                continue
            img_path = Path(img['path'])
            label_path = labels_dir / f"{img_path.stem}.txt"
            with open(label_path, 'w') as f:
                for ann in annotations:
                    yolo_id = class_id_map.get(ann['class_id'])
                    if yolo_id is None or yolo_id >= nc:
                        continue  # 跳过无效类别
                    cx = ann['x'] + ann['width'] / 2
                    cy = ann['y'] + ann['height'] / 2
                    if seg_mode and ann.get('type') == 'polygon' and ann.get('points'):
                        # 分割格式：class_id x1_norm y1_norm x2_norm y2_norm ...
                        # 注意：pts 已经是归一化坐标 (0~1)，无需再次归一化
                        # 也不带 bbox 前缀；Ultralytics YOLOv8-seg 期望纯多边形坐标
                        try:
                            import json as _json
                            pts = _json.loads(ann['points'])
                            seg_coords = ' '.join(
                                f"{p[0]:.6f} {p[1]:.6f}" for p in pts
                            )
                            f.write(f"{yolo_id} {seg_coords}\n")
                        except Exception:
                            # 点数据异常时用框四角回退
                            # 从数据库读取 bbox，对 polygon 类型可能为 0（旧版存储）
                            x1 = ann.get('x', 0.0)
                            y1 = ann.get('y', 0.0)
                            w = ann.get('width', 0.0)
                            h = ann.get('height', 0.0)
                            # 如果 bbox 为零旧数据，从 points 反算
                            if not (x1 or y1 or w or h):
                                _pts = _json.loads(ann.get('points', '[]'))
                                if _pts:
                                    xs = [p[0] for p in _pts]
                                    ys = [p[1] for p in _pts]
                                    x1 = min(xs); y1 = min(ys)
                                    x2 = max(xs); y2 = max(ys)
                                else:
                                    x2 = x1 + w; y2 = y1 + h
                            else:
                                x2 = x1 + w; y2 = y1 + h
                            f.write(f"{yolo_id} {x1:.6f} {y1:.6f} {x2:.6f} {y1:.6f} "
                                    f"{x2:.6f} {y2:.6f} {x1:.6f} {y2:.6f}\n")
                    elif seg_mode:
                        # 纯 bbox 标注 + 分割模型 → 用框四角生成 4 点多边形
                        # 注意：bbox 坐标已归一化
                        x1 = ann.get('x', 0.0)
                        y1 = ann.get('y', 0.0)
                        w = ann.get('width', 0.0)
                        h = ann.get('height', 0.0)
                        x2 = x1 + w; y2 = y1 + h
                        f.write(f"{yolo_id} {x1:.6f} {y1:.6f} {x2:.6f} {y1:.6f} "
                                f"{x2:.6f} {y2:.6f} {x1:.6f} {y2:.6f}\n")
                    else:
                        # 5 列格式：yolo_index cx cy w h
                        f.write(f"{yolo_id} {cx:.6f} {cy:.6f} "
                                f"{ann['width']:.6f} {ann['height']:.6f}\n")

        # 按比例分割训练 / 验证集
        import random
        random.seed(self.config.seed)
        random.shuffle(annotated)

        split_idx = max(1, int(len(annotated) * self.config.split))
        train_set = annotated[:split_idx]
        val_set = annotated[split_idx:]

        # 写入文件列表
        cache_dir = self.project.path / 'cache'
        cache_dir.mkdir(parents=True, exist_ok=True)

        train_file = cache_dir / 'train.txt'
        val_file = cache_dir / 'val.txt'

        with open(train_file, 'w') as f:
            for img in train_set:
                f.write(f"{img['path']}\n")
        with open(val_file, 'w') as f:
            for img in val_set:
                f.write(f"{img['path']}\n")

        # 生成 data.yaml
        import yaml
        classes = self.project.get_classes()
        data_yaml = {
            'path': str(self.project.path.absolute()),
            'train': str(train_file.absolute()),
            'val': str(val_file.absolute()),
            'nc': len(classes),
            'names': [c['name'] for c in classes],
        }

        data_yaml_path = cache_dir / 'training_data.yaml'
        with open(data_yaml_path, 'w') as f:
            yaml.dump(data_yaml, f, default_flow_style=False)

        return data_yaml_path

    # ── 训练 ──

    def train(
        self,
        data_yaml: Path,
        on_progress: Optional[Callable[[TrainingProgress], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_model_saved: Optional[Callable[[Path], None]] = None,
        save_record: bool = True,
    ) -> Optional[Path]:
        """执行 YOLO 训练

        Args:
            data_yaml: 数据集配置文件 (training_data.yaml) 路径
            on_progress: 每轮结束触发，传递 TrainingProgress
            on_log: 日志消息回调
            on_model_saved: 模型保存回调（检查点 / 最终模型）
            save_record: 是否在 config.yaml 中保存训练记录

        Returns:
            最佳模型路径，失败或被中断返回 None
        """
        self._should_stop = False
        self._start_time = time.time()

        # ── 准备输出目录 ──
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = self.project.path / 'models' / f'train_{timestamp}'
        output_dir.mkdir(parents=True, exist_ok=True)

        if on_log:
            on_log(f"📂 输出目录: {output_dir}")
            on_log(f"📊 数据集: {data_yaml}")
            on_log(f"🧠 模型架构: {self.config.model_arch}")
            on_log(f"🔄 训练轮数: {self.config.epochs}")
            on_log(f"📦 批次大小: {self.config.batch}")
            on_log(f"🖼️  图片尺寸: {self.config.imgsz}")

        # 读取训练集数量
        try:
            with open(data_yaml.parent / 'train.txt') as f:
                n_train = len(f.readlines())
            if on_log:
                on_log(f"📷 训练样本: {n_train}")
                on_log(f"🏷️  项目类别: {len(self.project.get_classes())}")
        except Exception:
            pass

        # ── 构建训练参数 ──
        kwargs = self.config.to_ultralytics_kwargs()
        kwargs['project'] = str(output_dir.parent)
        kwargs['name'] = output_dir.name
        kwargs['exist_ok'] = True
        kwargs['verbose'] = False

        # ── 进度状态 ──
        progress = TrainingProgress()
        progress.total_epochs = self.config.epochs
        progress.stage = 'training'

        # ── 回调函数 ──
        # 使用闭包持引用，以便训练结束后清理

        def _on_fit_epoch_end(trainer):
            """每轮（含验证）结束时的回调"""
            if self._should_stop:
                trainer.stop = True
                return

            progress.epoch = trainer.epoch + 1

            # 损失（可能是 tensor，用 detach 避免警告）
            if hasattr(trainer, 'loss') and trainer.loss is not None:
                loss_val = trainer.loss
                if hasattr(loss_val, 'detach'):
                    loss_val = loss_val.detach()
                progress.loss = float(loss_val)

            # 学习率（兼容多种格式：float、list of float、list of dict、tensor）
            if hasattr(trainer, 'lr') and trainer.lr is not None:
                try:
                    lrs = trainer.lr if isinstance(trainer.lr, (list, tuple)) else [trainer.lr]
                    first = lrs[0] if lrs else 0.0
                    # dict 格式 → 提取 lr 键
                    if isinstance(first, dict):
                        first = first.get('lr', 0.0)
                    # tensor → 转标量
                    if hasattr(first, 'item'):
                        first = first.item()
                    progress.current_lr = float(first)
                except Exception:
                    progress.current_lr = 0.0

            # 评估指标
            if hasattr(trainer, 'metrics') and trainer.metrics:
                metrics = trainer.metrics
                progress.mAP50 = float(metrics.get('metrics/mAP50(B)', 0.0))
                progress.mAP50_95 = float(metrics.get('metrics/mAP50-95(B)', 0.0))
                progress.precision = float(metrics.get('metrics/precision(B)', 0.0))
                progress.recall = float(metrics.get('metrics/recall(B)', 0.0))

            # 时间统计
            progress.time_elapsed = time.time() - self._start_time
            if progress.epoch > 0:
                avg_time = progress.time_elapsed / progress.epoch
                remaining = progress.total_epochs - progress.epoch
                progress.time_remaining = avg_time * remaining

            if on_progress:
                on_progress(progress)

        def _on_train_epoch_end(trainer):
            """每轮训练结束（验证前）回调——主要用于日志"""
            if on_log and not self._should_stop:
                try:
                    # 安全获取 loss
                    loss_val = 0.0
                    if hasattr(trainer, 'loss') and trainer.loss is not None:
                        loss_val = trainer.loss
                        if hasattr(loss_val, 'detach'):
                            loss_val = loss_val.detach()
                        if hasattr(loss_val, 'item'):
                            loss_val = loss_val.item()
                        loss_val = float(loss_val)

                    # 安全获取 lr
                    lr_val = 0.0
                    if hasattr(trainer, 'lr') and trainer.lr is not None:
                        raw = trainer.lr
                        first = raw[0] if isinstance(raw, (list, tuple)) else raw
                        if isinstance(first, dict):
                            first = first.get('lr', 0.0)
                        if hasattr(first, 'item'):
                            first = first.item()
                        lr_val = float(first)

                    on_log(
                        f"Epoch {trainer.epoch + 1:3d}/{self.config.epochs} | "
                        f"Loss: {loss_val:.4f} | "
                        f"LR: {lr_val:.6f}"
                    )
                except Exception:
                    pass

        def _on_train_end(trainer):
            """训练结束回调"""
            if on_log:
                on_log("训练阶段完成，正在保存模型...")

            # 从训练输出复制最佳模型到项目根模型目录
            best_src = Path(trainer.best) if hasattr(trainer, 'best') else None
            if best_src and best_src.exists():
                project_model = self.project.path / 'models' / 'best.pt'
                shutil.copy2(str(best_src), str(project_model))
                if on_model_saved:
                    on_model_saved(project_model)
                if on_log:
                    on_log(f"✅ 最佳模型已保存: {project_model}")

            # 保存训练记录（由调用方选择是否保存，避免线程安全问题）
            if save_record:
                self._save_training_record(timestamp, output_dir)

        # ── 注册回调（直接操作 default_callbacks dict）──
        from ultralytics.utils.callbacks import default_callbacks

        default_callbacks['on_fit_epoch_end'].append(_on_fit_epoch_end)
        default_callbacks['on_train_epoch_end'].append(_on_train_epoch_end)
        default_callbacks['on_train_end'].append(_on_train_end)

        # ── 执行训练 ──
        try:
            from ultralytics import YOLO
            # import os
            # # 禁止 ultralytics 联网下载（全部使用本地文件）
            # os.environ['ULTRALYTICS_HUB'] = '0'

            # 解析模型路径：优先本地文件，尝试多个位置
            resume_path = self.config.resume_from
            if resume_path and Path(resume_path).exists():
                # 增量训练
                if on_log:
                    on_log(f"🔄 增量训练模式: 从已有模型继续训练")
                    on_log(f"   检查点: {resume_path}")
                model = YOLO(str(resume_path))
            else:
                # 尝试查找本地模型文件
                model_path = self._resolve_model_path(self.config.model_arch)
                if model_path:
                    if on_log:
                        on_log(f"📁 从本地加载: {model_path}")
                    model = YOLO(str(model_path))
                else:
                    # 从 ultralytics hub 下载到 mostpt/ 缓存
                    root = Path(__file__).parent.parent.parent
                    mostpt_dir = root / 'mostpt'
                    mostpt_dir.mkdir(parents=True, exist_ok=True)
                    model_name = self.config.model_arch.rsplit('/', 1)[-1]
                    local_pt = mostpt_dir / model_name

                    if local_pt.exists():
                        if on_log:
                            on_log(f"📁 从 mostpt/ 加载: {local_pt}")
                        model = YOLO(str(local_pt))
                    else:
                        if on_log:
                            on_log(f"🌐 从 Ultralytics Hub 下载并缓存到 mostpt/: {local_pt}")
                        model = YOLO(self.config.model_arch)
                        # 缓存下载的文件到 mostpt/
                        try:
                            cache_path = Path.home() / '.cache' / 'ultralytics' / 'weights' / model_name
                            if cache_path.exists():
                                shutil.copy2(str(cache_path), str(local_pt))
                                if on_log:
                                    on_log(f"💾 已缓存: {local_pt}")
                        except Exception:
                            pass

            # 保存 trainer 引用以便外部停止
            self._trainer_ref = None

            if on_log:
                on_log("🚀 开始训练...")
                if kwargs.get('device') == 'cpu':
                    on_log("⚠️ 使用 CPU 训练（速度较慢）")

            if on_log:
                on_log(f"{'='*50}")

            # 阻塞调用——训练进行中
            model.train(data=str(data_yaml), **kwargs)

            # 获取 trainer 引用（训练结束后 trainer 仍然可用）
            self._trainer_ref = getattr(model, 'trainer', None)

            # ── 完成 ──
            progress.stage = 'done'
            progress.epoch = progress.total_epochs
            if on_progress:
                on_progress(progress)
            if on_log:
                on_log(f"{'='*50}")
                on_log("🎉 训练完成！")

            # 确定最终模型路径
            best_path = output_dir / 'weights' / 'best.pt'
            if best_path.exists():
                project_model = self.project.path / 'models' / 'best.pt'
                return project_model
            elif (output_dir / 'weights' / 'last.pt').exists():
                return output_dir / 'weights' / 'last.pt'
            return None

        except Exception as e:
            progress.stage = 'error'
            progress.error = str(e)
            if on_progress:
                on_progress(progress)
            if on_log:
                on_log(f"❌ 训练出错: {e}")
            import traceback
            on_log(traceback.format_exc())
            raise

        finally:
            # ── 清理回调 ──
            for key, cb in [
                ('on_fit_epoch_end', _on_fit_epoch_end),
                ('on_train_epoch_end', _on_train_epoch_end),
                ('on_train_end', _on_train_end),
            ]:
                try:
                    lst = default_callbacks.get(key, [])
                    if cb in lst:
                        lst.remove(cb)
                except (ValueError, AttributeError):
                    pass

    # ── 训练记录持久化 ──

    def _save_training_record(self, timestamp: str, output_dir: Path):
        """将本次训练记录保存到项目 config.yaml"""
        try:
            records = self.project.config.get('training_history') or []
            if not isinstance(records, list):
                records = []
            record = {
                'timestamp': timestamp,
                'output_dir': str(output_dir),
                'model_arch': self.config.model_arch,
                'epochs': self.config.epochs,
                'batch': self.config.batch,
                'imgsz': self.config.imgsz,
                'created_at': datetime.now().isoformat(),
            }
            records.append(record)
            # 只保留最近 20 条
            if len(records) > 20:
                records = records[-20:]
            self.project.config.set('training_history', records)
        except Exception as e:
            logger.warning(f"保存训练记录失败: {e}")
