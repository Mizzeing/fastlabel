"""BasePredictor - 预测器抽象基类

所有模型预测器（YOLO / RT-DETR / SAM / GroundingDINO）实现统一接口。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
import numpy as np


class PredictionResult:
    """预测结果数据结构

    x, y, w, h 均为归一化坐标 (0~1)，与 BBox 存储格式一致。
    """

    def __init__(self, class_id: int, label: str,
                 x: float, y: float, w: float, h: float,
                 score: float):
        self.class_id = class_id
        self.label = label
        self.x = x          # 归一化左上角 X
        self.y = y          # 归一化左上角 Y
        self.w = w          # 归一化宽度
        self.h = h          # 归一化高度
        self.score = score

    def to_dict(self) -> dict:
        return {
            'class_id': self.class_id,
            'label': self.label,
            'x': self.x,
            'y': self.y,
            'w': self.w,
            'h': self.h,
            'score': self.score,
        }

    def __repr__(self):
        return (f"Pred({self.label}, "
                f"({self.x:.3f},{self.y:.3f},{self.w:.3f},{self.h:.3f}), "
                f"{self.score:.3f})")


class BasePredictor(ABC):
    """预测器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """模型名称"""
        pass

    @property
    @abstractmethod
    def model_type(self) -> str:
        """模型类型: 'yolo', 'rt-detr', 'sam' 等"""
        pass

    @abstractmethod
    def load(self, model_path: str):
        """加载模型权重"""
        pass

    @abstractmethod
    def predict(self, image: np.ndarray,
                conf_threshold: float = 0.25) -> List[PredictionResult]:
        """对单张图片进行预测

        Args:
            image: RGB 图像 numpy 数组 (H, W, 3)
            conf_threshold: 置信度阈值

        Returns:
            PredictionResult 列表
        """
        pass

    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return False

    @abstractmethod
    def unload(self):
        """卸载模型，释放显存/内存"""
        pass
