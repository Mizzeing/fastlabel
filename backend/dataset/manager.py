"""DatasetManager - 数据集管理器

统一管理图片、标签、类别的加载与同步。
"""

from pathlib import Path
from typing import List, Optional, Dict, Callable
from .image_loader import ImageLoader
from .label_loader import LabelLoader
from ..project.project import Project
from ..annotation.bbox import BBox
from ..annotation.shape import Shape


class DatasetManager:
    """数据集管理器

    协调 Project、ImageLoader、LabelLoader 之间的关系。
    """

    def __init__(self, project: Project = None):
        self._project = project
        self._image_loader = ImageLoader()
        self._on_images_changed: Optional[Callable] = None
        self._image_list: List[Dict] = []
        self._current_index: int = -1

    def set_project(self, project: Project):
        self._project = project
        self.refresh()

    @property
    def current_project(self) -> Optional[Project]:
        return self._project

    # ── 图片管理 ──

    def refresh(self):
        """刷新图片列表"""
        if self._project is None:
            self._image_list = []
            self._current_index = -1
            return

        self._image_list = self._project.get_all_images()
        if self._current_index >= len(self._image_list):
            self._current_index = max(0, len(self._image_list) - 1) if self._image_list else -1

    @property
    def image_count(self) -> int:
        return len(self._image_list)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_image(self) -> Optional[Dict]:
        if 0 <= self._current_index < len(self._image_list):
            return self._image_list[self._current_index]
        return None

    def get_image(self, index: int) -> Optional[Dict]:
        if 0 <= index < len(self._image_list):
            return self._image_list[index]
        return None

    def set_current_index(self, index: int):
        if 0 <= index < len(self._image_list):
            self._current_index = index

    def goto_first(self):
        self.set_current_index(0)

    def goto_last(self):
        self.set_current_index(len(self._image_list) - 1)

    def goto_prev(self) -> bool:
        if self._current_index > 0:
            self._current_index -= 1
            return True
        return False

    def goto_next(self) -> bool:
        if self._current_index < len(self._image_list) - 1:
            self._current_index += 1
            return True
        return False

    def image_loader(self) -> ImageLoader:
        return self._image_loader

    def import_images(self, file_paths: List[str]) -> int:
        """导入图片到项目，返回导入数量"""
        if self._project is None:
            return 0

        import shutil
        count = 0
        for src in file_paths:
            src_path = Path(src)
            if not src_path.exists() or not ImageLoader.is_supported(src_path.name):
                continue

            # 复制到项目 images 目录
            dest = self._project.path / 'images' / src_path.name
            if dest.exists():
                continue  # 跳过重复

            shutil.copy2(str(src_path), str(dest))

            # 获取图片尺寸
            w, h = self._image_loader.get_image_size(str(dest))

            # 添加到数据库
            self._project.add_image(
                path=str(dest),
                filename=src_path.name,
                width=w,
                height=h,
                file_size=dest.stat().st_size,
            )
            count += 1

        self.refresh()
        if self._image_list and self._current_index == -1:
            self._current_index = 0
        return count

    # ── 标注同步 ──

    def load_annotations(self, image_id: int) -> List[Shape]:
        """加载图片的所有标注为 Shape 对象"""
        if self._project is None:
            return []

        records = self._project.get_annotations(image_id)
        shapes = []
        for r in records:
            bbox = BBox(
                annotation_id=r['annotation_id'],
                class_id=r['class_id'],
                label=r.get('label', ''),
                x=r['x'],
                y=r['y'],
                w=r['width'],
                h=r['height'],
                score=r['score'],
            )
            shapes.append(bbox)
        return shapes

    def save_annotations(self, image_id: int, shapes: List[Shape]):
        """保存标注到数据库"""
        if self._project is None:
            return

        dicts = []
        for s in shapes:
            if isinstance(s, BBox):
                dicts.append(s.to_dict())
        self._project.save_all_annotations(image_id, dicts)

    def export_yolo(self, image_id: Optional[int] = None):
        """导出 YOLO 格式标签到 labels 目录"""
        if self._project is None:
            return

        from ..export.yolo import YOLOExporter
        exporter = YOLOExporter(self._project)
        exporter.export_all()

    # ── 统计 ──

    def get_stats(self) -> Dict:
        if self._project is None:
            return {}
        return self._project.get_stats()
