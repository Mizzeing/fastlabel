"""YOLOExporter - YOLO 格式导出模块"""

from pathlib import Path
from typing import List, Dict, Optional
from ..project.project import Project


class YOLOExporter:
    """YOLO 格式标注导出器

    将数据库中的标注导出为 YOLO 格式的 txt 文件。
    同时生成 data.yaml 类别配置文件。
    """

    def __init__(self, project: Project):
        self.project = project

    def export_all(self):
        """导出全部标注到 labels 目录"""
        labels_dir = self.project.path / 'labels'
        labels_dir.mkdir(parents=True, exist_ok=True)

        images = self.project.get_all_images()
        for img in images:
            self._export_image(img['id'], labels_dir)

        # 生成 data.yaml
        self._export_data_yaml()

    def export_image(self, image_id: int):
        """导出单张图片的标注"""
        labels_dir = self.project.path / 'labels'
        labels_dir.mkdir(parents=True, exist_ok=True)
        img = self.project.get_image(image_id)
        if img:
            self._export_image(image_id, labels_dir)

    def _export_image(self, image_id: int, labels_dir: Path):
        """导出单张图片的 YOLO 标注"""
        img = self.project.get_image(image_id)
        if not img:
            return

        annotations = self.project.get_annotations(image_id)
        if not annotations:
            return

        # 用实际文件的 stem（含前缀）保证标签文件名唯一
        img_path = Path(img['path'])
        label_path = labels_dir / f"{img_path.stem}.txt"
        with open(label_path, 'w') as f:
            for ann in annotations:
                # 数据库存储的是左上角坐标
                cx = ann['x'] + ann['width'] / 2
                cy = ann['y'] + ann['height'] / 2
                f.write(f"{ann['class_id']} {cx:.6f} {cy:.6f} "
                        f"{ann['width']:.6f} {ann['height']:.6f} {ann['score']:.4f}\n")

    def _export_data_yaml(self):
        """生成 YOLO data.yaml 配置文件"""
        classes = self.project.get_classes()

        data = {
            'path': str(self.project.path.absolute()),
            'train': 'images',
            'val': 'images',
            'nc': len(classes),
            'names': [c['name'] for c in classes],
        }

        import yaml
        yaml_path = self.project.path / 'exports' / 'data.yaml'
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    @staticmethod
    def annotations_to_yolo(annotations: List[Dict]) -> str:
        """将标注列表转换为 YOLO 格式字符串"""
        lines = []
        for ann in annotations:
            cx = ann['x'] + ann['w'] / 2
            cy = ann['y'] + ann['h'] / 2
            score = ann.get('score', 1.0)
            lines.append(f"{ann['class_id']} {cx:.6f} {cy:.6f} "
                         f"{ann['w']:.6f} {ann['h']:.6f} {score:.4f}")
        return '\n'.join(lines)
