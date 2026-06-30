"""InferenceManager - 推理管理器

统筹模型加载、预测、置信度过滤。
"""

import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Callable
from .base import BasePredictor, PredictionResult
from .yolo_predictor import YOLOPredictor


PREDICTOR_REGISTRY = {
    'yolo': YOLOPredictor,
    # 后续扩展: 'rtdetr': RTDETRPredictor, 'sam': SAMPredictor
}


class InferenceManager:
    """推理管理器

    支持动态加载/切换模型、单张/批量预测、置信度过滤。
    """

    def __init__(self):
        self._predictor: Optional[BasePredictor] = None
        self._conf_threshold: float = 0.25
        self._last_predictions: List[PredictionResult] = []
        self._on_predictions_changed: Optional[Callable] = None

    # ── 事件回调 ──

    def set_on_predictions_changed(self, callback: Optional[Callable]):
        self._on_predictions_changed = callback

    def _notify(self):
        if self._on_predictions_changed:
            self._on_predictions_changed()

    # ── 模型管理 ──

    @property
    def is_loaded(self) -> bool:
        return self._predictor is not None and self._predictor.is_loaded()

    @property
    def predictor(self) -> Optional[BasePredictor]:
        return self._predictor

    @property
    def conf_threshold(self) -> float:
        return self._conf_threshold

    @conf_threshold.setter
    def conf_threshold(self, value: float):
        self._conf_threshold = max(0.01, min(0.99, value))

    def load_model(self, model_path: str, model_type: str = 'yolo') -> bool:
        """加载模型

        Args:
            model_path: 模型文件路径
            model_type: 模型类型 ('yolo', ...)

        Returns:
            是否加载成功
        """
        # 先卸载旧模型
        self.unload_model()

        predictor_cls = PREDICTOR_REGISTRY.get(model_type)
        if predictor_cls is None:
            raise ValueError(f"不支持的模型类型: {model_type}，可选: {list(PREDICTOR_REGISTRY.keys())}")

        try:
            self._predictor = predictor_cls()
            self._predictor.load(model_path)
            self.clear_predictions()
            return True
        except Exception as e:
            self._predictor = None
            raise e

    def unload_model(self):
        """卸载当前模型"""
        if self._predictor:
            self._predictor.unload()
            self._predictor = None
        self.clear_predictions()

    def get_model_info(self) -> Dict:
        """获取当前模型信息"""
        if not self.is_loaded:
            return {'loaded': False, 'name': '无模型', 'type': ''}
        return {
            'loaded': True,
            'name': self._predictor.name,
            'type': self._predictor.model_type,
        }

    # ── 预测 ──

    def predict(self, image: np.ndarray,
                conf_threshold: Optional[float] = None) -> List[PredictionResult]:
        """对单张图片进行预测

        Args:
            image: RGB 图像 (H, W, 3)
            conf_threshold: 可选，覆盖默认置信度阈值

        Returns:
            预测结果列表
        """
        if not self.is_loaded:
            return []

        threshold = conf_threshold if conf_threshold is not None else self._conf_threshold
        results = self._predictor.predict(image, conf_threshold=threshold)
        self._last_predictions = results
        self._notify()
        return results

    def predict_and_filter(self, image: np.ndarray) -> List[PredictionResult]:
        """预测并按当前置信度阈值过滤"""
        results = self.predict(image)
        return [r for r in results if r.score >= self._conf_threshold]

    def clear_predictions(self):
        """清空预测结果"""
        self._last_predictions = []
        self._notify()

    @property
    def last_predictions(self) -> List[PredictionResult]:
        return self._last_predictions
