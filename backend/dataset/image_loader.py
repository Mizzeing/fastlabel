"""ImageLoader - 图片加载与缓存"""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from PIL import Image
import numpy as np


class ImageLoader:
    """图片加载器 - 支持多种格式，带缓存"""

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    def __init__(self, cache_size: int = 50):
        self._cache: Dict[str, Tuple[np.ndarray, int, int]] = {}
        self._cache_keys: List[str] = []
        self._cache_size = cache_size

    def load_image(self, path: str) -> Tuple[np.ndarray, int, int]:
        """加载图片，返回 (图像数据, 宽度, 高度)

        结果会缓存，避免重复加载。
        """
        if path in self._cache:
            img, w, h = self._cache[path]
            return img.copy(), w, h

        pil_img = Image.open(path)
        img = np.array(pil_img.convert('RGB'))
        h, w = img.shape[:2]

        self._add_to_cache(path, img, w, h)
        return img.copy(), w, h

    def load_pil(self, path: str) -> Image.Image:
        """以 PIL Image 形式加载"""
        return Image.open(path).convert('RGB')

    def get_image_size(self, path: str) -> Tuple[int, int]:
        """获取图片尺寸，不加载像素数据"""
        if path in self._cache:
            _, w, h = self._cache[path]
            return w, h
        with Image.open(path) as img:
            w, h = img.size
        return w, h

    def _add_to_cache(self, path: str, img: np.ndarray, w: int, h: int):
        if len(self._cache_keys) >= self._cache_size:
            oldest = self._cache_keys.pop(0)
            self._cache.pop(oldest, None)
        self._cache[path] = (img, w, h)
        self._cache_keys.append(path)

    def clear_cache(self):
        self._cache.clear()
        self._cache_keys.clear()

    @staticmethod
    def list_images(directory: str) -> List[str]:
        """列出目录中所有支持的图片文件"""
        images = []
        path = Path(directory)
        if not path.exists():
            return images
        for f in sorted(path.iterdir()):
            if f.suffix.lower() in ImageLoader.SUPPORTED_FORMATS:
                images.append(str(f))
        return images

    @staticmethod
    def is_supported(filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in ImageLoader.SUPPORTED_FORMATS
