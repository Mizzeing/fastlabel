"""FastLabel 推理模块 - 统一模型推理接口

支持 YOLO / RT-DETR / SAM 等模型，所有预测器统一返回：
[{'class_id': int, 'label': str, 'x': float, 'y': float,
  'w': float, 'h': float, 'score': float}, ...]
其中 x,y,w,h 为归一化坐标 (0~1)。
"""

from .base import BasePredictor, PredictionResult
from .yolo_predictor import YOLOPredictor
from .manager import InferenceManager
