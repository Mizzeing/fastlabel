"""LabelLoader - YOLO 格式标签加载与保存

支持：
- YOLO 检测格式: class_id x_center y_center width height [score]
- YOLO 分割格式: class_id x1 y1 x2 y2 ... xn yn [score]
"""

from pathlib import Path
from typing import List, Dict, Optional
import os


class LabelLoader:
    """YOLO 格式标签加载器"""

    @staticmethod
    def load_yolo(label_path: str) -> List[Dict]:
        """加载 YOLO 格式标签文件

        自动检测格式：
        - 检测格式（5 列）→ 返回 BBox 格式
        - 分割格式（6+ 列且列数为奇数）→ 返回分割格式

        Returns:
            BBox 格式:
                [{'class_id': int, 'x': float, 'y': float, 'w': float, 'h': float, ...}]
            分割格式:
                [{'class_id': int, 'type': 'polygon', 'points': [(x1,y1),...], ...}]
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
                if len(parts) < 5:
                    continue

                class_id = int(parts[0])
                values = [float(v) for v in parts[1:]]

                # 检测格式（5 列: class_id cx cy w h [score]）
                if len(values) in (4, 5):
                    cx, cy, w, h = values[0], values[1], values[2], values[3]
                    score = values[4] if len(values) > 4 else 1.0
                    x = cx - w / 2
                    y = cy - h / 2
                    annotations.append({
                        'class_id': class_id,
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h,
                        'score': score,
                    })
                # 分割格式（6+ 列: class_id x1 y1 x2 y2 ... xn yn [score]）
                elif len(values) >= 6 and len(values) % 2 == 0:
                    score = values[-1] if len(values) % 2 == 1 else 1.0
                    coords = values[:-1] if len(values) % 2 == 1 else values
                    points = [(coords[i], coords[i + 1])
                              for i in range(0, len(coords), 2)]
                    annotations.append({
                        'class_id': class_id,
                        'type': 'polygon',
                        'points': points,
                        'score': score,
                    })

        return annotations

    @staticmethod
    def save_yolo(label_path: str, annotations: List[Dict],
                  classes: List[Dict] = None):
        """保存 YOLO 格式标签文件

        支持 BBox 和 Polygon 格式自动判断。
        BBox 保存为检测格式: class_id cx cy w h score
        Polygon 保存为分割格式: class_id x1 y1 x2 y2 ... xn yn score
        """
        Path(label_path).parent.mkdir(parents=True, exist_ok=True)

        with open(label_path, 'w') as f:
            for ann in annotations:
                score = ann.get('score', 1.0)
                # Polygon 格式
                if ann.get('type') == 'polygon' or 'points' in ann:
                    pts = ann.get('points', [])
                    coords = ' '.join(f"{p[0]:.6f} {p[1]:.6f}" for p in pts)
                    f.write(f"{ann['class_id']} {coords} {score:.4f}\n")
                else:
                    # BBox 格式
                    cx = ann['x'] + ann['w'] / 2
                    cy = ann['y'] + ann['h'] / 2
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
