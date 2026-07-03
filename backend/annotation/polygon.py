"""Polygon - 多边形标注

用于实例分割标注，存储归一化的多边形顶点坐标列表。
YOLO 分割格式: class_id x1 y1 x2 y2 ... xn yn
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .shape import Shape


@dataclass
class Polygon(Shape):
    """多边形标注

    使用归一化坐标 (0~1)，独立于图像尺寸。
    points: 顶点列表 [(x1, y1), (x2, y2), ..., (xn, yn)]
    """
    points: List[Tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'annotation_id': self.annotation_id,
            'class_id': self.class_id,
            'label': self.label,
            'type': 'polygon',
            'points': [[float(x), float(y)] for x, y in self.points],
            'score': self.score,
            'visible': self.visible,
            'locked': self.locked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Polygon':
        points_data = data.get('points', [])
        points = [(float(p[0]), float(p[1])) for p in points_data]
        return cls(
            annotation_id=data.get('annotation_id', ''),
            class_id=data['class_id'],
            label=data.get('label', ''),
            points=points,
            score=data.get('score', 1.0),
            visible=data.get('visible', True),
            locked=data.get('locked', False),
        )

    def copy(self) -> 'Polygon':
        return Polygon(
            annotation_id=self.annotation_id,
            class_id=self.class_id,
            label=self.label,
            points=[(x, y) for x, y in self.points],
            score=self.score,
            visible=self.visible,
            locked=self.locked,
        )

    def scale(self, sx: float, sy: float):
        self.points = [(x * sx, y * sy) for x, y in self.points]

    def get_bbox(self) -> Tuple[float, float, float, float]:
        """计算包围盒 (x, y, w, h) 归一化坐标"""
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        x = min(xs)
        y = min(ys)
        w = max(xs) - x
        h = max(ys) - y
        return (x, y, w, h)

    def contains_point(self, px: float, py: float) -> bool:
        """射线法判断点是否在多边形内（归一化坐标）"""
        if len(self.points) < 3:
            return False

        inside = False
        n = len(self.points)
        j = n - 1
        for i in range(n):
            xi, yi = self.points[i]
            xj, yj = self.points[j]
            # 射线法：从点向右水平发射，统计与边的交点
            if ((yi > py) != (yj > py)) and \
               (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def area(self) -> float:
        """多边形面积（归一化坐标空间，鞋带公式）"""
        if len(self.points) < 3:
            return 0.0
        n = len(self.points)
        s = 0.0
        for i in range(n):
            x1, y1 = self.points[i]
            x2, y2 = self.points[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return abs(s) / 2.0

    def get_short_repr(self) -> str:
        return f"{self.label}({len(self.points)}pts)"
