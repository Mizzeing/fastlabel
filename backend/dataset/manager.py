"""DatasetManager - 数据集管理器

统一管理图片、标签、类别的加载与同步。
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Callable
from .image_loader import ImageLoader
from .label_loader import LabelLoader
from ..project.project import Project

def _log(*args):
    print("[DatasetManager]", *args, file=sys.stderr)
from ..annotation.bbox import BBox
from ..annotation.polygon import Polygon
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

    @staticmethod
    def _unique_image_name(src_path: Path, dest_dir: Path) -> str:
        """生成唯一的图片文件名，避免同名文件冲突

        策略：用 {源目录名}_{原文件名} 作为唯一标识，
        如果还有冲突则追加数字后缀。
        """
        stem = src_path.stem
        suffix = src_path.suffix
        # 用源文件所在目录名做前缀，保留导入时的目录结构
        parent_name = src_path.parent.name
        name = f"{parent_name}_{stem}{suffix}"

        if not (dest_dir / name).exists():
            return name

        # 万一加了前缀还冲突，追加计数器
        for i in range(1, 999):
            name = f"{parent_name}_{stem}_{i}{suffix}"
            if not (dest_dir / name).exists():
                return name

        # 极限情况：用路径的 hash 保证唯一
        import hashlib
        h = hashlib.md5(str(src_path.absolute()).encode()).hexdigest()[:8]
        return f"{parent_name}_{stem}_{h}{suffix}"

    def import_images(self, file_paths: List[str],
                      import_yolo_labels: bool = True) -> int:
        """导入图片到项目，返回导入数量

        参数:
            file_paths: 要导入的图片路径列表
            import_yolo_labels: 是否自动导入同目录下的 YOLO txt 标签文件
        """
        if self._project is None:
            return 0

        import shutil
        count = 0
        for src in file_paths:
            src_path = Path(src)
            if not src_path.exists() or not ImageLoader.is_supported(src_path.name):
                continue

            images_dir = self._project.path / 'images'
            images_dir.mkdir(parents=True, exist_ok=True)

            # 生成唯一文件名
            unique_name = self._unique_image_name(src_path, images_dir)
            dest = images_dir / unique_name

            if dest.exists():
                continue  # 极少情况：hash 碰撞

            shutil.copy2(str(src_path), str(dest))

            # 获取图片尺寸
            w, h = self._image_loader.get_image_size(str(dest))

            # 添加到数据库（记录来源路径方便追溯）
            self._project.add_image(
                path=str(dest),
                filename=src_path.name,
                width=w,
                height=h,
                file_size=dest.stat().st_size,
                source_path=str(src_path),
            )

            # 自动导入同目录下的 YOLO 标签
            if import_yolo_labels:
                lbl_path = src_path.with_suffix('.txt')
                if lbl_path.exists():
                    records = LabelLoader.load_yolo(str(lbl_path))
                    if records:
                        image_id = self._project.get_image_id_by_path(str(dest))
                        if image_id:
                            self._import_yolo_records(image_id, records)

            count += 1

        self.refresh()
        if self._image_list and self._current_index == -1:
            self._current_index = 0
        return count

    def _import_yolo_records(self, image_id: int, records: List[Dict]):
        """将 YOLO label records 导入为项目标注"""
        import uuid
        img = self._project.get_image(image_id)
        if not img:
            return

        classes = self._project.get_classes()
        if not classes:
            return

        # 按 class_id 排序，YOLO class_id → 项目类别（按位置匹配）
        classes_sorted = sorted(classes, key=lambda x: x['id'])
        from ..annotation.bbox import BBox
        from ..annotation.polygon import Polygon

        shapes = []
        for r in records:
            yolo_cid = r['class_id']
            if yolo_cid >= len(classes_sorted):
                continue
            proj_class = classes_sorted[yolo_cid]

            if r.get('type') == 'polygon':
                polygon = Polygon(
                    annotation_id=str(uuid.uuid4()),
                    class_id=proj_class['id'],
                    label=proj_class['name'],
                    points=[(float(x), float(y)) for x, y in r.get('points', [])],
                    score=r.get('score', 1.0),
                )
                shapes.append(polygon)
            else:
                bbox = BBox(
                    annotation_id=str(uuid.uuid4()),
                    class_id=proj_class['id'],
                    label=proj_class['name'],
                    x=r['x'], y=r['y'], w=r['w'], h=r['h'],
                    score=r.get('score', 1.0),
                )
                shapes.append(bbox)

        if shapes:
            self._project.save_all_annotations(image_id,
                [s.to_dict() for s in shapes])

    # ── 标注同步 ──

    def load_annotations(self, image_id: int) -> List[Shape]:
        """加载图片的所有标注为 Shape 对象"""
        if self._project is None:
            return []

        records = self._project.get_annotations(image_id)
        _log(f"load_annotations(image_id={image_id}): {len(records)} 条 DB 记录")
        shapes = []
        for r in records:
            ann_type = r.get('type', 'bbox')
            _log(f"  DB记录 type={ann_type}, class_id={r['class_id']}, "
                 f"points={repr(r.get('points', '')[:60])}, "
                 f"x={r['x']}, y={r['y']}, w={r['width']}, h={r['height']}, "
                 f"label={r.get('label', '')}")
            if ann_type == 'polygon':
                points_str = r.get('points', '')
                if points_str:
                    import json
                    try:
                        pts = json.loads(points_str)
                    except (json.JSONDecodeError, TypeError) as e:
                        _log(f"  JSON解析失败: {e}")
                        pts = []
                else:
                    pts = []
                try:
                    converted = [(float(p[0]), float(p[1])) for p in pts]
                except (IndexError, TypeError) as e:
                    _log(f"  点解析失败: {e}, pts={pts}")
                    converted = []
                shape = Polygon(
                    annotation_id=r['annotation_id'],
                    class_id=r['class_id'],
                    label=r.get('label', ''),
                    points=converted,
                    score=r['score'],
                )
                _log(f"  -> Polygon: {len(converted)} 点, isinstance={isinstance(shape, Polygon)}")
            else:
                shape = BBox(
                    annotation_id=r['annotation_id'],
                    class_id=r['class_id'],
                    label=r.get('label', ''),
                    x=r['x'],
                    y=r['y'],
                    w=r['width'],
                    h=r['height'],
                    score=r['score'],
                )
            shapes.append(shape)
        _log(f"load_annotations 返回 {len(shapes)} 个 Shape 对象")
        return shapes

    def save_annotations(self, image_id: int, shapes: List[Shape]):
        """保存标注到数据库"""
        if self._project is None:
            _log("save_annotations: project is None")
            return

        dicts = []
        for s in shapes:
            if isinstance(s, (BBox, Polygon)):
                d = s.to_dict()
                dicts.append(d)
                _log(f"save_annotations: {type(s).__name__} -> type={d.get('type','?')}, "
                     f"points={repr(d.get('points', ''))[:60] if 'points' in d else 'N/A'}")
        _log(f"save_annotations: 保存 {len(dicts)} 个标注到 image_id={image_id}")
        self._project.save_all_annotations(image_id, dicts)

    def export_yolo(self, image_id: Optional[int] = None):
        """导出 YOLO 格式标签到 labels 目录"""
        if self._project is None:
            return

        from ..export.yolo import YOLOExporter
        exporter = YOLOExporter(self._project)
        exporter.export_all()

    # ── YOLO 标签导入 ──

    def import_yolo_labels(self, label_dir: str, image_dir: Optional[str] = None,
                           class_mapping: Optional[Dict[int, str]] = None) -> int:
        """从 YOLO 格式标签目录导入标注到项目

        label_dir 中的 .txt 文件通过文件名与项目中的图片匹配。
        如果某个 label 对应图片已存在标注，不会重复导入。

        参数:
            label_dir: YOLO txt 标签目录
            image_dir: （可选）图片源目录，用于从 data.yaml 解析类别映射
            class_mapping: （可选）{class_id: class_name} 覆盖类别映射

        返回:
            成功导入标注的图片数量
        """
        if self._project is None:
            return 0

        # 解析类别映射
        mapping = self._resolve_class_mapping(label_dir, image_dir, class_mapping)

        label_path = Path(label_dir)
        if not label_path.exists():
            return 0

        # 建立双向索引：原始文件名stem + 实际文件名stem → 项目图片
        # 兼容两种命名方式：
        #   - 原始名: Image--01 → 匹配源目录中的 Image--01.txt
        #   - 带前缀: 0522D11_Image--01 → 匹配 labels/raw_train 中的 0522D11_Image--01.txt
        images = self._project.get_all_images()
        img_by_stem = {}
        for img in images:
            # 原始文件名（如 Image--01）
            orig_stem = Path(img['filename']).stem
            if orig_stem not in img_by_stem:
                img_by_stem[orig_stem] = img
            # 实际存储的文件名（如 0522D11_Image--01，含前缀）
            actual_stem = Path(img['path']).stem
            if actual_stem not in img_by_stem:
                img_by_stem[actual_stem] = img

        # 从 label 目录反向查找：txt 文件名 stem → 项目图片
        count = 0
        from ..annotation.bbox import BBox
        for txt_file in sorted(label_path.glob("*.txt")):
            stem = txt_file.stem
            img = img_by_stem.get(stem)
            if img is None:
                continue

            # 检查是否已有标注
            existing = self._project.get_annotations(img['id'])
            if existing:
                continue

            # 读取 YOLO 标签
            records = LabelLoader.load_yolo(str(txt_file))
            if not records:
                continue

            # 解析图片原始尺寸（YOLO 坐标是归一化的，需要宽高来创建 BBox）
            img_meta = self._project.get_image(img['id'])
            img_w = img_meta.get('width', 0)
            img_h = img_meta.get('height', 0)
            if not img_w or not img_h:
                continue

            import uuid
            from ..annotation.polygon import Polygon

            shapes = []
            for r in records:
                yolo_cid = r['class_id']
                # 查找对应的项目 class_id
                label_name = mapping.get(yolo_cid, f"class_{yolo_cid}")
                proj_class = self._project.config.get_class_by_name(label_name)
                if proj_class is None:
                    continue  # 跳过未知类别

                if r.get('type') == 'polygon':
                    polygon = Polygon(
                        annotation_id=str(uuid.uuid4()),
                        class_id=proj_class['id'],
                        label=label_name,
                        points=[(float(x), float(y)) for x, y in r.get('points', [])],
                        score=r.get('score', 1.0),
                    )
                    shapes.append(polygon)
                else:
                    bbox = BBox(
                        annotation_id=str(uuid.uuid4()),
                        class_id=proj_class['id'],
                        label=label_name,
                        x=r['x'], y=r['y'], w=r['w'], h=r['h'],
                        score=r.get('score', 1.0),
                    )
                    shapes.append(bbox)

            if shapes:
                self._project.save_all_annotations(img['id'],
                    [s.to_dict() for s in shapes])
                count += 1

        return count

    def _resolve_class_mapping(self, label_dir: str, image_dir: Optional[str],
                               class_mapping: Optional[Dict[int, str]]) -> Dict[int, str]:
        """解析 YOLO class_id → 类别名称 的映射

        优先级:
        1. 用户显式传入的 class_mapping
        2. label_dir / image_dir 中的 data.yaml
        3. 项目已注册的类别（按 id 顺序匹配）
        """
        if class_mapping:
            return class_mapping

        # 尝试读 data.yaml
        for search_dir in [label_dir, image_dir] if image_dir else [label_dir]:
            if search_dir:
                yaml_path = Path(search_dir) / 'data.yaml'
                if yaml_path.exists():
                    try:
                        import yaml
                        with open(yaml_path) as f:
                            cfg = yaml.safe_load(f) or {}
                        names = cfg.get('names', [])
                        if names:
                            return {i: name for i, name in enumerate(names)}
                    except Exception:
                        pass

        # 用项目已有类别，按 id 顺序映射（假设 YOLO class_id 0→第1个类别, 1→第2个...）
        if self._project:
            classes = self._project.get_classes()
            return {i: c['name'] for i, c in enumerate(sorted(classes, key=lambda x: x['id']))}

        return {}

    # ── 统计 ──

    def get_stats(self) -> Dict:
        if self._project is None:
            return {}
        return self._project.get_stats()
