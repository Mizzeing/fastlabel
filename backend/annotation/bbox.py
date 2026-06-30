"""BBox - 矩形框标注"""

from dataclasses import dataclass, field
from typing import Optional
from .shape import Shape


@dataclass
class BBox(Shape):
    """矩形框标注

    使用归一化坐标 (0~1)，独立于图像尺寸。
    x, y: 左上角坐标
    w, h: 宽高
    """
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    def to_dict(self) -> dict:
        return {
            'annotation_id': self.annotation_id,
            'class_id': self.class_id,
            'label': self.label,
            'x': self.x,
            'y': self.y,
            'w': self.w,
            'h': self.h,
            'score': self.score,
            'visible': self.visible,
            'locked': self.locked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BBox':
        return cls(
            annotation_id=data.get('annotation_id', ''),
            class_id=data['class_id'],
            label=data.get('label', ''),
            x=data['x'],
            y=data['y'],
            w=data['w'],
            h=data['h'],
            score=data.get('score', 1.0),
            visible=data.get('visible', True),
            locked=data.get('locked', False),
        )

    def copy(self) -> 'BBox':
        return BBox(
            annotation_id=self.annotation_id,
            class_id=self.class_id,
            label=self.label,
            x=self.x,
            y=self.y,
            w=self.w,
            h=self.h,
            score=self.score,
            visible=self.visible,
            locked=self.locked,
        )

    def scale(self, sx: float, sy: float):
        self.x *= sx
        self.y *= sy
        self.w *= sx
        self.h *= sy

    def get_center(self) -> tuple:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def contains_point(self, px: float, py: float) -> bool:
        """判断像素坐标点是否在框内"""
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def iou(self, other: 'BBox') -> float:
        """计算 IoU"""
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.w, other.x + other.w)
        y2 = min(self.y + self.h, other.y + other.h)

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = self.w * self.h
        area2 = other.w * other.h
        union = area1 + area2 - inter

        return inter / union if union > 0 else 0.0

    def area(self) -> float:
        return self.w * self.h
