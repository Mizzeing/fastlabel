"""Command 模式实现 Undo/Redo

每个操作封装为一个 Command 对象，支持 execute/undo。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from .shape import Shape
from .bbox import BBox


class Command(ABC):
    """命令基类"""

    @abstractmethod
    def execute(self):
        pass

    @abstractmethod
    def undo(self):
        pass

    def __str__(self):
        return self.__class__.__name__


class AddCommand(Command):
    """添加标注"""

    def __init__(self, annotations: list, shape: Shape):
        self.annotations = annotations
        self.shape = shape

    def execute(self):
        self.annotations.append(self.shape)

    def undo(self):
        self.annotations.remove(self.shape)

    def __str__(self):
        return f"Add({self.shape.get_short_repr()})"


class DeleteCommand(Command):
    """删除标注"""

    def __init__(self, annotations: list, shape: Shape):
        self.annotations = annotations
        self.shape = shape

    def execute(self):
        if self.shape in self.annotations:
            self.annotations.remove(self.shape)

    def undo(self):
        if self.shape not in self.annotations:
            self.annotations.append(self.shape)

    def __str__(self):
        return f"Delete({self.shape.get_short_repr()})"


class MoveCommand(Command):
    """移动标注"""

    def __init__(self, shape: Shape, dx: float, dy: float):
        self.shape = shape
        self.dx = dx
        self.dy = dy
        self.executed = False

    def execute(self):
        self.shape.x += self.dx
        self.shape.y += self.dy
        self.executed = True

    def undo(self):
        self.shape.x -= self.dx
        self.shape.y -= self.dy

    def __str__(self):
        return f"Move({self.shape.get_short_repr()}, dx={self.dx:.3f}, dy={self.dy:.3f})"


class ResizeCommand(Command):
    """调整标注大小"""

    def __init__(self, shape: BBox, old_x: float, old_y: float,
                 old_w: float, old_h: float, new_x: float, new_y: float,
                 new_w: float, new_h: float):
        self.shape = shape
        self.old = (old_x, old_y, old_w, old_h)
        self.new = (new_x, new_y, new_w, new_h)

    def execute(self):
        self.shape.x, self.shape.y, self.shape.w, self.shape.h = self.new

    def undo(self):
        self.shape.x, self.shape.y, self.shape.w, self.shape.h = self.old

    def __str__(self):
        return f"Resize({self.shape.get_short_repr()})"


class ChangeClassCommand(Command):
    """修改标注类别"""

    def __init__(self, shape: Shape, old_class_id: int, old_label: str,
                 new_class_id: int, new_label: str):
        self.shape = shape
        self.old_class_id = old_class_id
        self.old_label = old_label
        self.new_class_id = new_class_id
        self.new_label = new_label

    def execute(self):
        self.shape.class_id = self.new_class_id
        self.shape.label = self.new_label

    def undo(self):
        self.shape.class_id = self.old_class_id
        self.shape.label = self.old_label

    def __str__(self):
        return f"ChangeClass({self.shape.get_short_repr()})"


class CommandManager:
    """命令管理器 - 管理 Undo/Redo 栈"""

    def __init__(self, max_history: int = 100):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self.max_history = max_history
        self._on_change: Optional[Callable] = None

    def set_on_change(self, callback: Optional[Callable]):
        self._on_change = callback

    def execute(self, command: Command):
        """执行命令并压入 Undo 栈"""
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> bool:
        """撤销上一个操作，返回是否成功"""
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify()
        return True

    def redo(self) -> bool:
        """重做上一个撤销的操作，返回是否成功"""
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        self._notify()
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify()

    def _notify(self):
        if self._on_change:
            self._on_change()
