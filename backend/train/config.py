"""训练配置

定义 TrainingConfig dataclass 和预设配置模板。
"""

from dataclasses import dataclass, asdict
from typing import Optional


# ── 预设配置模板 ──

TRAINING_PRESETS = {
    '快速 (快速迭代)': {
        'model_arch': 'yolov8n.pt',
        'epochs': 50,
        'batch': 16,
        'imgsz': 640,
        'optimizer': 'auto',
        'patience': 20,
        'augment': True,
    },
    '标准 (推荐)': {
        'model_arch': 'yolov8n.pt',
        'epochs': 100,
        'batch': 16,
        'imgsz': 640,
        'optimizer': 'auto',
        'patience': 50,
        'augment': True,
    },
    '精度优先': {
        'model_arch': 'yolov8s.pt',
        'epochs': 200,
        'batch': 8,
        'imgsz': 640,
        'optimizer': 'AdamW',
        'patience': 100,
        'augment': True,
        'cos_lr': True,
    },
}


# ── 常用模型架构列表 ──

COMMON_ARCHES = [
    'yolov8n.pt',   # nano
    'yolov8s.pt',   # small
    'yolov8m.pt',   # medium
    'yolov8l.pt',   # large
    'yolov8x.pt',   # xlarge
    'yolo11n.pt',   # yolo11 nano
    'yolo11s.pt',   # yolo11 small
    'yolo11m.pt',   # yolo11 medium
    'yolo11l.pt',   # yolo11 large
    'yolo11x.pt',   # yolo11 xlarge
]


@dataclass
class TrainingConfig:
    """YOLO 训练超参数

    所有与 ultralytics YOLO 训练相关的可控参数。
    to_ultralytics_kwargs() 转换为 model.train() 可用的 dict。
    """

    # ── 基础参数 ──
    model_arch: str = 'yolov8n.pt'     # 基础模型架构名称或路径
    epochs: int = 100                   # 训练轮数
    batch: int = 16                     # 批次大小（-1 自动）
    imgsz: int = 640                    # 输入图片尺寸（像素）
    device: str = ''                    # 计算设备：''=auto, 'cpu', '0', '0,1'

    # ── 优化器参数 ──
    optimizer: str = 'auto'             # SGD / Adam / AdamW / auto
    lr0: float = 0.01                   # 初始学习率
    lrf: float = 0.01                   # 最终学习率系数（lr0 * lrf）
    momentum: float = 0.937             # SGD 动量 / Adam beta1
    weight_decay: float = 0.0005        # 权重衰减系数
    cos_lr: bool = False                # 使用余弦学习率调度

    # ── 预热参数 ──
    warmup_epochs: float = 3.0          # 预热轮数
    warmup_momentum: float = 0.8        # 预热初始动量
    warmup_bias_lr: float = 0.1         # 预热偏置学习率

    # ── 数据参数 ──
    augment: bool = True                # 是否启用数据增强
    close_mosaic: int = 10              # 最后 N 轮关闭 mosaic 增强
    workers: int = 8                    # 数据加载线程数
    split: float = 0.9                  # 训练集比例（剩余为验证集）

    # ── 训练控制 ──
    patience: int = 50                  # Early stopping 等待轮数（0=禁用）
    seed: int = 0                       # 随机种子
    deterministic: bool = True          # 启用确定性训练（可复现）
    save_period: int = 10               # 每 N 轮保存一次检查点
    pretrained: bool = True             # 是否使用预训练权重
    resume_from: str = ''               # 增量训练：从检查点路径继续训练

    # ── 验证与日志 ──
    val: bool = True                    # 训练时验证
    plots: bool = False                 # 生成训练曲线图

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'TrainingConfig':
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid_keys})

    def to_ultralytics_kwargs(self) -> dict:
        """转换为 ultralytics YOLO model.train() 的参数"""
        # 自动检测可用设备
        device = self.device if self.device else None
        if device is None or device == 'auto':
            try:
                import torch
                if not torch.cuda.is_available() or torch.cuda.device_count() == 0:
                    device = 'cpu'
                else:
                    device = '0'  # 使用第一块 GPU
            except Exception:
                device = 'cpu'
        # CPU 训练时关闭 AMP 和减少 worker
        is_cpu = device == 'cpu'
        return {
            'epochs': self.epochs,
            'batch': min(self.batch, 8) if is_cpu else self.batch,  # CPU 降低 batch
            'imgsz': self.imgsz,
            'device': device,
            'optimizer': self.optimizer,
            'lr0': self.lr0,
            'lrf': self.lrf,
            'momentum': self.momentum,
            'weight_decay': self.weight_decay,
            'cos_lr': self.cos_lr,
            'warmup_epochs': self.warmup_epochs,
            'warmup_momentum': self.warmup_momentum,
            'warmup_bias_lr': self.warmup_bias_lr,
            'augment': self.augment,
            'close_mosaic': self.close_mosaic,
            'workers': 0 if is_cpu else self.workers,
            'patience': self.patience,
            'seed': self.seed,
            'deterministic': self.deterministic,
            'save_period': self.save_period,
            'pretrained': self.pretrained,
            'val': self.val,
            'plots': False,
            'amp': False,        # CPU 强制关闭 AMP
            'fraction': 1.0,
            'project': '',
            'name': 'train',
            'exist_ok': True,
            'verbose': False,
        }
