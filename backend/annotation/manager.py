"""AnnotationManager - 标注管理器

管理当前图片的所有标注对象，集成 Undo/Redo、单选/多选选择逻辑。
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
        self._selection: List[Shape] = []     # 当前选中的标注列表（支持多选）
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

    def _notify_select(self):
        if self._on_select_change:
            self._on_select_change()

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
        """主选中项（多选时返回最后点击的那个）"""
        return self._selection[-1] if self._selection else None

    @property
    def selected_shapes(self) -> List[Shape]:
        """所有选中的标注"""
        return list(self._selection)

    @property
    def selection_count(self) -> int:
        return len(self._selection)

    def is_selected(self, shape: Shape) -> bool:
        return shape in self._selection

    def add(self, shape: Shape):
        """添加标注（含 Undo）"""
        self._command_manager.execute(AddCommand(self._annotations, shape))
        self.select(shape)

    def delete(self, shape: Optional[Shape] = None):
        """删除标注（含 Undo）"""
        shape = shape or self.selected
        if shape is None:
            return
        if shape not in self._annotations:
            return
        self._remove_from_selection(shape)
        self._command_manager.execute(DeleteCommand(self._annotations, shape))

    def delete_selected(self):
        """删除所有选中的标注"""
        for s in list(self._selection):
            if s in self._annotations:
                self._command_manager.execute(DeleteCommand(self._annotations, s))
        self._selection.clear()
        self._notify_select()
        self._notify_change()

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
        """修改单个标注类别（含 Undo）"""
        self._command_manager.execute(ChangeClassCommand(
            shape, shape.class_id, shape.label, new_class_id, new_label))

    def change_class_selected(self, new_class_id: int, new_label: str):
        """批量修改所有选中标注的类别"""
        if not self._selection:
            return
        for shape in self._selection:
            self._command_manager.execute(ChangeClassCommand(
                shape, shape.class_id, shape.label, new_class_id, new_label))

    # ── 选择 ──

    def _remove_from_selection(self, shape: Shape):
        """从选中列表移除（不通知）"""
        if shape in self._selection:
            self._selection.remove(shape)
            shape.selected = False

    def _clear_selection_internal(self):
        """清空选中列表并重置状态（不通知）"""
        for s in self._selection:
            s.selected = False
        self._selection.clear()

    def select(self, shape: Optional[Shape]):
        """单选：替换当前选中"""
        self._clear_selection_internal()
        if shape:
            self._selection.append(shape)
            shape.selected = True
        self._notify_select()
        self._notify_change()

    def toggle_select(self, shape: Shape):
        """切换选中状态（Ctrl+点击）"""
        if shape in self._selection:
            if len(self._selection) > 1:
                # 多选时移除
                self._remove_from_selection(shape)
            else:
                # 最后一个不移除（改为单选该对象）
                return  # 保持选中
        else:
            self._selection.append(shape)
            shape.selected = True
        self._notify_select()
        self._notify_change()

    def select_at(self, px: float, py: float, toggle: bool = False) -> Optional[Shape]:
        """选择指定像素坐标处的标注

        Args:
            px, py: 像素坐标
            toggle: 是否切换选中（Ctrl+点击时为 True）
        """
        for shape in reversed(self._annotations):
            if hasattr(shape, 'contains_point') and shape.contains_point(px, py):
                if toggle:
                    self.toggle_select(shape)
                else:
                    self.select(shape)
                return shape
        if not toggle:
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
        self._clear_selection_internal()
        self._command_manager.clear()
        self._notify_change()
        self._notify_select()

    def set_annotations(self, annotations: List[Shape]):
        """直接设置标注列表（加载时使用，不清除历史）"""
        self._annotations = annotations
        self._clear_selection_internal()
        self._command_manager.clear()
        self._notify_change()
        self._notify_select()

    def get_selected_index(self) -> int:
        if not self._selection:
            return -1
        try:
            return self._annotations.index(self._selection[-1])
        except ValueError:
            return -1

    # ══════════════════════════════════════
    # 预测管理（AI 辅助标注）
    # ══════════════════════════════════════

    @property
    def predictions(self) -> List[Shape]:
        return self._predictions

    def set_predictions(self, predictions: List[Shape]):
        self._predictions = predictions
        self._notify_predictions()
        self._notify_change()

    def accept_prediction(self, shape: Shape) -> bool:
        if shape not in self._predictions:
            return False
        self._predictions.remove(shape)
        shape.score = 1.0
        self._command_manager.execute(AddCommand(self._annotations, shape))
        self.select(shape)
        self._notify_predictions()
        return True

    def reject_prediction(self, shape: Shape) -> bool:
        if shape not in self._predictions:
            return False
        self._predictions.remove(shape)
        self._notify_predictions()
        self._notify_change()
        return True

    def accept_all_predictions(self, min_score: float = 0.0) -> int:
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
        self._predictions.clear()
        self._notify_predictions()
        self._notify_change()
