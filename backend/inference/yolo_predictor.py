"""YOLOPredictor - YOLOv8/v11 预测器实现

通过 Ultralytics 库加载 YOLO 模型进行目标检测。
支持 .pt (PyTorch) 和 .engine (TensorRT) 格式。
"""

import numpy as np
from typing import List, Optional
from .base import BasePredictor, PredictionResult, SegmentationPredictionResult


class YOLOPredictor(BasePredictor):
    """YOLO 模型预测器"""

    def __init__(self):
        self._model = None
        self._model_path: Optional[str] = None
        self._class_names: List[str] = []

    @property
    def name(self) -> str:
        return f"YOLO ({self._model_path})" if self._model_path else "YOLO (未加载)"

    @property
    def model_type(self) -> str:
        return "yolo"

    def load(self, model_path: str):
        """加载 YOLO 模型

        Args:
            model_path: .pt 或 .engine 文件路径
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError(
                "请先安装 Ultralytics: pip install ultralytics")

        self._model = YOLO(model_path)
        self._model_path = model_path
        self._class_names = list(self._model.names.values())

    def predict(self, image: np.ndarray,
                conf_threshold: float = 0.25,
                iou_threshold: float = 0.45) -> List[PredictionResult]:
        """执行 YOLO 预测

        支持检测和分割模型：
        - 检测模型：返回 BBox PredictionResult
        - 分割模型：返回带多边形点的 SegmentationPredictionResult

        Args:
            image: RGB 图像 (H, W, 3)
            conf_threshold: 置信度阈值 (0~1)
            iou_threshold: NMS IoU 阈值 (0~1)

        Returns:
            PredictionResult 列表（归一化坐标）
        """
        if self._model is None:
            raise RuntimeError("模型未加载，请先调用 load()")

        img_h, img_w = image.shape[:2]
        results = self._model(image, verbose=False,
                              conf=conf_threshold, iou=iou_threshold)

        if len(results) == 0:
            return []

        detections = []
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return detections

        # 判断是否为分割模型
        is_seg = hasattr(results[0], 'masks') and results[0].masks is not None

        if is_seg:
            # 分割模型：提取多边形点
            masks = results[0].masks
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                score = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = results[0].names[cls_id]

                # 提取多边形点
                points = []
                if i < len(masks.xy):
                    poly_xy = masks.xy[i]  # 绝对坐标 (N, 2)
                    if len(poly_xy) >= 3:
                        points = [
                            (float(p[0]) / img_w, float(p[1]) / img_h)
                            for p in poly_xy
                        ]

                detections.append(SegmentationPredictionResult(
                    class_id=cls_id,
                    label=label,
                    x=x1 / img_w,
                    y=y1 / img_h,
                    w=(x2 - x1) / img_w,
                    h=(y2 - y1) / img_h,
                    score=score,
                    points=points,
                ))
        else:
            # 检测模型：标准 BBox
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                score = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = results[0].names[cls_id]

                detections.append(PredictionResult(
                    class_id=cls_id,
                    label=label,
                    x=x1 / img_w,
                    y=y1 / img_h,
                    w=(x2 - x1) / img_w,
                    h=(y2 - y1) / img_h,
                    score=score,
                ))

        return detections

    def is_loaded(self) -> bool:
        return self._model is not None

    def unload(self):
        self._model = None
        self._model_path = None
        self._class_names = []

    @property
    def class_names(self) -> List[str]:
        return self._class_names

    @property
    def model_path(self) -> Optional[str]:
        return self._model_path
