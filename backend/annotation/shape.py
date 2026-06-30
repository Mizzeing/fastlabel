"""标注形状基类 - 所有标注对象的抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import uuid


@dataclass
class Shape(ABC):
    """标注形状基类

    所有标注对象（BBox, Polygon, BrushMask 等）都继承自此类。
    """
    class_id: int = 0
    label: str = ""
    score: float = 1.0
    visible: bool = True
    locked: bool = False
    selected: bool = False
    annotation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @abstractmethod
    def to_dict(self) -> dict:
        """序列化为字典"""
        pass

    @abstractmethod
    def copy(self) -> 'Shape':
        """深拷贝"""
        pass

    @abstractmethod
    def scale(self, sx: float, sy: float):
        """缩放坐标"""
        pass

    def get_short_repr(self) -> str:
        return f"{self.label}({self.annotation_id})"
