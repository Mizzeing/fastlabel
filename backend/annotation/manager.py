"""AnnotationManager - 标注管理器

管理当前图片的所有标注对象，集成 Undo/Redo 和选择逻辑。
"""

from typing import List, Optional, Callable
from .shape import Shape
from .bbox import BBox
from .command import (
    CommandManager, AddCommand, DeleteCommand,
    MoveCommand, ResizeCommand, ChangeClassCommand,
)


class AnnotationManager:
    """标注管理器"""

    def __init__(self):
        self._annotations: List[Shape] = []
        self._predictions: List[Shape] = []   # 模型预测结果（待确认）
        self._selected: Optional[Shape] = None
        self._command_manager = CommandManager()
        self._command_manager.set_on_change(self._on_command_change)
        self._on_change: Optional[Callable] = None
        self._on_select_change: Optional[Callable] = None
        self._on_predictions_change: Optional[Callable] = None

    # ── 事件回调 ──

    def set_on_change(self, callback: Optional[Callable]):
        self._on_change = callback

    def set_on_select_change(self, callback: Optional[Callable]):
        self._on_select_change = callback

    def set_on_predictions_change(self, callback: Optional[Callable]):
        self._on_predictions_change = callback

    def _notify_change(self):
        if self._on_change:
            self._on_change()

    def _notify_predictions(self):
        if self._on_predictions_change:
            self._on_predictions_change()

    def _on_command_change(self):
        self._notify_change()

    # ── 标注管理 ──

    @property
    def annotations(self) -> List[Shape]:
        return self._annotations

    @property
    def selected(self) -> Optional[Shape]:
        return self._selected

    def add(self, shape: Shape):
        """添加标注（含 Undo）"""
        self._command_manager.execute(AddCommand(self._annotations, shape))
        self.select(shape)

    def delete(self, shape: Optional[Shape] = None):
        """删除标注（含 Undo）"""
        shape = shape or self._selected
        if shape is None:
            return
        if shape not in self._annotations:
            return
        if self._selected == shape:
            self._selected = None
            if self._on_select_change:
                self._on_select_change()
        self._command_manager.execute(DeleteCommand(self._annotations, shape))

    def delete_selected(self):
        self.delete(self._selected)

    def move(self, shape: Shape, dx: float, dy: float):
        """移动标注（含 Undo）"""
        self._command_manager.execute(MoveCommand(shape, dx, dy))

    def resize(self, shape: BBox, old_x: float, old_y: float,
               old_w: float, old_h: float, new_x: float, new_y: float,
               new_w: float, new_h: float):
        """调整标注大小（含 Undo）"""
        self._command_manager.execute(ResizeCommand(
            shape, old_x, old_y, old_w, old_h, new_x, new_y, new_w, new_h))

    def change_class(self, shape: Shape, new_class_id: int, new_label: str):
        """修改类别（含 Undo）"""
        self._command_manager.execute(ChangeClassCommand(
            shape, shape.class_id, shape.label, new_class_id, new_label))

    # ── 选择 ──

    def select(self, shape: Optional[Shape]):
        if self._selected != shape:
            if self._selected:
                self._selected.selected = False
            self._selected = shape
            if shape:
                shape.selected = True
            if self._on_select_change:
                self._on_select_change()
            self._notify_change()

    def select_at(self, px: float, py: float) -> Optional[Shape]:
        """选择指定像素坐标处的标注"""
        # 从上层（后添加的）开始查找
        for shape in reversed(self._annotations):
            if hasattr(shape, 'contains_point') and shape.contains_point(px, py):
                self.select(shape)
                return shape
        self.select(None)
        return None

    def clear_selection(self):
        self.select(None)

    # ── Undo/Redo ──

    def undo(self) -> bool:
        return self._command_manager.undo()

    def redo(self) -> bool:
        return self._command_manager.redo()

    def can_undo(self) -> bool:
        return self._command_manager.can_undo()

    def can_redo(self) -> bool:
        return self._command_manager.can_redo()

    # ── 批量操作 ──

    def clear(self):
        self._annotations.clear()
        self._selected = None
        self._command_manager.clear()
        self._notify_change()
        if self._on_select_change:
            self._on_select_change()

    def set_annotations(self, annotations: List[Shape]):
        """直接设置标注列表（加载时使用，不清除历史）"""
        self._annotations = annotations
        self._selected = None
        self._command_manager.clear()
        self._notify_change()
        if self._on_select_change:
            self._on_select_change()

    def get_selected_index(self) -> int:
        if self._selected is None:
            return -1
        try:
            return self._annotations.index(self._selected)
        except ValueError:
            return -1

    # ══════════════════════════════════════
    # 预测管理（AI 辅助标注）
    # ══════════════════════════════════════

    @property
    def predictions(self) -> List[Shape]:
        return self._predictions

    def set_predictions(self, predictions: List[Shape]):
        """设置预测结果列表"""
        self._predictions = predictions
        self._notify_predictions()
        self._notify_change()

    def accept_prediction(self, shape: Shape) -> bool:
        """接受单个预测结果，加入标注列表"""
        if shape not in self._predictions:
            return False
        self._predictions.remove(shape)
        shape.score = 1.0
        self._command_manager.execute(AddCommand(self._annotations, shape))
        self.select(shape)
        self._notify_predictions()
        return True

    def reject_prediction(self, shape: Shape) -> bool:
        """拒绝单个预测结果"""
        if shape not in self._predictions:
            return False
        self._predictions.remove(shape)
        self._notify_predictions()
        self._notify_change()
        return True

    def accept_all_predictions(self, min_score: float = 0.0) -> int:
        """接受所有符合条件的预测

        Args:
            min_score: 最低置信度阈值

        Returns:
            接受的预测数量
        """
        accepted = []
        for pred in list(self._predictions):
            if pred.score >= min_score:
                self._predictions.remove(pred)
                pred.score = 1.0
                self._annotations.append(pred)
                accepted.append(pred)
        if accepted:
            self._command_manager.clear()
            self.select(accepted[-1])
            self._notify_predictions()
            self._notify_change()
        return len(accepted)

    def reject_all_predictions(self, min_score: float = 0.0) -> int:
        """拒绝所有符合条件的预测"""
        count = 0
        for pred in list(self._predictions):
            if pred.score >= min_score:
                self._predictions.remove(pred)
                count += 1
        if count:
            self._notify_predictions()
            self._notify_change()
        return count

    def clear_predictions(self):
        """清空所有预测"""
        self._predictions.clear()
        self._notify_predictions()
        self._notify_change()
