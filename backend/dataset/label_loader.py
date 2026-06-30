"""LabelLoader - YOLO 格式标签加载与保存"""

from pathlib import Path
from typing import List, Dict, Optional
import os


class LabelLoader:
    """YOLO 格式标签加载器

    YOLO 格式说明:
    - 每张图片对应一个 .txt 文件
    - 每行: class_id x_center y_center width height
    - 所有坐标均为归一化值 (0~1)
    """

    @staticmethod
    def load_yolo(label_path: str) -> List[Dict]:
        """加载 YOLO 格式标签文件

        返回:
            [{'class_id': int, 'x': float, 'y': float, 'w': float, 'h': float}, ...]
        注意: x,y 是归一化后的左上角坐标（从 center 转换而来）
        """
        annotations = []
        if not os.path.exists(label_path):
            return annotations

        with open(label_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    cx = float(parts[1])
                    cy = float(parts[2])
                    w = float(parts[3])
                    h = float(parts[4])
                    # 中心坐标 -> 左上角坐标
                    x = cx - w / 2
                    y = cy - h / 2
                    annotations.append({
                        'class_id': class_id,
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h,
                        'score': float(parts[5]) if len(parts) > 5 else 1.0,
                    })
        return annotations

    @staticmethod
    def save_yolo(label_path: str, annotations: List[Dict],
                  classes: List[Dict] = None):
        """保存 YOLO 格式标签文件

        annotations 中的 x,y 是左上角坐标，会转换为中心坐标保存。
        """
        Path(label_path).parent.mkdir(parents=True, exist_ok=True)

        with open(label_path, 'w') as f:
            for ann in annotations:
                cx = ann['x'] + ann['w'] / 2
                cy = ann['y'] + ann['h'] / 2
                score = ann.get('score', 1.0)
                f.write(f"{ann['class_id']} {cx:.6f} {cy:.6f} "
                        f"{ann['w']:.6f} {ann['h']:.6f} {score:.4f}\n")

    @staticmethod
    def get_label_path(image_path: str, label_dir: str) -> str:
        """根据图片路径获取对应的标签路径"""
        img_name = Path(image_path).stem
        return str(Path(label_dir) / f"{img_name}.txt")

    @staticmethod
    def get_label_path_from_image(image_path: str, label_dir: str) -> str:
        """从图片路径推导标签路径"""
        return LabelLoader.get_label_path(image_path, label_dir)
