"""Canvas - 核心画布组件

负责图像渲染、标注绘制、交互操作的核心组件。

## 职责
- 图像渲染与缩放/平移
- 标注形状（BBox）的绘制与选中高亮
- 鼠标交互：绘制、选择、移动、调整大小
- 上下文菜单

## 坐标系统
- 图像坐标: 原始像素坐标 (0, 0) ~ (img_w, img_h)
- 画布坐标: 经过缩放和平移后的显示坐标
- 归一化坐标: 0~1 之间的相对坐标（用于存储）
"""

from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction,
)
from PyQt5.QtCore import (
    Qt, QPoint, QPointF, QRectF, QSizeF,
    pyqtSignal, QTimer,
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap,
    QImage, QFont, QCursor, QPainterPath,
    QTransform, QPolygonF,
)
import numpy as np
import math
from typing import Optional, List, Tuple, Callable, Dict

from backend.annotation.shape import Shape
from backend.annotation.bbox import BBox
from backend.annotation.polygon import Polygon
from backend.utils.misc import get_class_color, hex_to_rgb


# ── 交互模式 ──

class Mode:
    """交互模式常量"""
    SELECT = 'select'       # 选择/编辑
    DRAW = 'draw'           # 绘制新 BBox
    DRAW_POLYGON = 'draw_polygon'  # 绘制多边形
    PAN = 'pan'             # 平移视图
    ZOOM = 'zoom'           # 缩放


# ── 选择手柄 ──

HANDLE_SIZE = 8
HANDLE_HALF = HANDLE_SIZE // 2


class Canvas(QWidget):
    """核心画布组件"""

    # 信号
    mode_changed = pyqtSignal(str)            # 模式切换
    annotation_added = pyqtSignal(object)      # 添加标注
    annotation_selected = pyqtSignal(object)   # 选中标注
    annotation_changed = pyqtSignal()          # 标注变更
    annotation_class_changed = pyqtSignal(object, int, str)  # 修改类别
    annotation_accept_requested = pyqtSignal(object)  # 接受预测
    annotation_reject_requested = pyqtSignal(object)  # 拒绝预测
    annotation_toggled = pyqtSignal(object)           # 切换选中(Ctrl+点击)
    image_changed = pyqtSignal()               # 图片切换
    status_message = pyqtSignal(str)           # 状态栏消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # ── 图像数据 ──
        self._pixmap: Optional[QPixmap] = None
        self._image_size: Tuple[int, int] = (0, 0)  # (w, h)

        # ── 视图变换 ──
        self._scale: float = 1.0          # 缩放因子
        self._offset: QPointF = QPointF(0, 0)  # 平移偏移
        self._zoom_center: QPointF = QPointF(0, 0)

        # ── 标注数据（来自 AnnotationManager 的引用） ──
        self._annotations: List[Shape] = []
        self._predictions: List[Shape] = []   # 模型预测框（待确认）
        self._selected: Optional[Shape] = None
        self._on_request_delete: Optional[Callable] = None
        self._on_request_accept: Optional[Callable] = None  # 接受预测
        self._classes: List[Dict] = []           # 可用类别列表，用于右键菜单

        # ── 交互状态 ──
        self._mode: str = Mode.SELECT
        self._drawing: bool = False       # 是否正在绘制
        self._draw_start: QPointF = QPointF(0, 0)
        self._draw_current: QPointF = QPointF(0, 0)
        self._drag_start: QPointF = QPointF(0, 0)
        self._dragging: bool = False
        self._resizing: bool = False
        self._resize_handle: int = -1     # 手柄索引
        self._panning: bool = False
        self._pan_start: QPointF = QPointF(0, 0)
        self._pan_offset_start: QPointF = QPointF(0, 0)

        # ── 多边形绘制状态 ──
        self._poly_points: List[QPointF] = []  # 正在绘制的多边形顶点（画布坐标）
        self._poly_hover_pos: Optional[QPointF] = None  # 鼠标悬停位置（用于绘制中连线）
        self._poly_closing: bool = False  # 是否正在闭合检测中

        # ── 多边形编辑状态 ──
        self._editing_polygon: bool = False  # 是否正在编辑多边形
        self._edit_vertex_idx: int = -1     # 正在拖拽的顶点索引
        self._edit_insert_idx: int = -1     # 插入顶点位置的索引

        # ── 拖动手柄前的保存状态 ──
        self._resize_old_bbox: Optional[tuple] = None

        # ── 选中包围盒 ──
        self._select_rect: Optional[QRectF] = None
        self._selecting: bool = False

        # ── 显示设置 ──
        self._show_labels: bool = True
        self._show_scores: bool = True

        # ── 光标管理 ──
        self._update_cursor()

    # ── 绑定数据 ──

    def set_annotations_ref(self, annotations_ref: list):
        """设置标注列表引用（指向 AnnotationManager._annotations）"""
        self._annotations = annotations_ref

    def set_selected_ref(self, selected_ref):
        """设置选中的标注引用"""
        self._selected = None

    def set_on_request_delete(self, callback: Callable):
        self._on_request_delete = callback

    def set_on_request_accept(self, callback: Callable):
        self._on_request_accept = callback

    def set_predictions(self, predictions: List[Shape]):
        self._predictions = predictions
        self.update()

    def set_classes(self, classes: List[Dict]):
        """设置可用类别列表（供右键菜单修改类别用）"""
        self._classes = classes

    def update_annotations(self, annotations: List[Shape], selected: Optional[Shape] = None):
        """更新标注数据并重绘（由外部调用）"""
        self._annotations = annotations
        self._selected = selected
        self.update()

    # ── 图片加载 ──

    def load_image(self, image_array: np.ndarray):
        """加载 numpy 格式的图像并显示"""
        if image_array is None or image_array.size == 0:
            return

        h, w = image_array.shape[:2]
        self._image_size = (w, h)

        if image_array.dtype != np.uint8:
            image_array = image_array.astype(np.uint8)

        if image_array.shape[2] == 3:
            from PyQt5.QtGui import QImage
            qimg = QImage(image_array.data, w, h, 3 * w,
                          QImage.Format_RGB888)
            self._pixmap = QPixmap.fromImage(qimg)
        else:
            qimg = QImage(image_array.data, w, h, image_array.strides[0],
                          QImage.Format_RGB888)
            self._pixmap = QPixmap.fromImage(qimg)

        # 初始化适配窗口
        self._fit_to_widget()
        self.image_changed.emit()
        self.update()

    def _fit_to_widget(self):
        """缩放图片适配窗口大小"""
        if self._pixmap is None:
            return
        w, h = self._image_size
        if w == 0 or h == 0:
            return

        margin = 20
        ww = self.width() - margin * 2
        wh = self.height() - margin * 2

        if ww <= 0 or wh <= 0:
            return

        scale_x = ww / w
        scale_y = wh / h
        self._scale = min(scale_x, scale_y)

        # 居中
        img_w = w * self._scale
        img_h = h * self._scale
        self._offset = QPointF(
            (self.width() - img_w) / 2,
            (self.height() - img_h) / 2
        )

    # ── 坐标转换 ──

    def image_to_canvas(self, img_x: float, img_y: float) -> QPointF:
        """图像坐标 -> 画布坐标"""
        return QPointF(
            img_x * self._scale + self._offset.x(),
            img_y * self._scale + self._offset.y(),
        )

    def canvas_to_image(self, canvas_x: float, canvas_y: float) -> QPointF:
        """画布坐标 -> 图像坐标"""
        return QPointF(
            (canvas_x - self._offset.x()) / self._scale,
            (canvas_y - self._offset.y()) / self._scale,
        )

    def normalized_to_image(self, nx: float, ny: float) -> QPointF:
        """归一化坐标 -> 图像坐标"""
        w, h = self._image_size
        return QPointF(nx * w, ny * h)

    def image_to_normalized(self, ix: float, iy: float) -> QPointF:
        """图像坐标 -> 归一化坐标"""
        w, h = self._image_size
        return QPointF(ix / w if w > 0 else 0, iy / h if h > 0 else 0)

    # ── 交互模式 ──

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        self._mode = mode
        self._drawing = False
        self._dragging = False
        self._resizing = False
        self._selecting = False
        self._poly_points.clear()
        self._poly_hover_pos = None
        self._poly_closing = False
        self._editing_polygon = False
        self._edit_vertex_idx = -1
        self._edit_insert_idx = -1
        self._update_cursor()
        self.mode_changed.emit(mode)
        self.update()

    def _update_cursor(self):
        """根据当前模式设置光标"""
        if self._mode in (Mode.DRAW, Mode.DRAW_POLYGON):
            self.setCursor(QCursor(Qt.CrossCursor))
        elif self._mode == Mode.PAN:
            self.setCursor(QCursor(Qt.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.ArrowCursor))

    @property
    def show_labels(self) -> bool:
        return self._show_labels

    @show_labels.setter
    def show_labels(self, value: bool):
        self._show_labels = value
        self.update()

    @property
    def show_scores(self) -> bool:
        return self._show_scores

    @show_scores.setter
    def show_scores(self, value: bool):
        self._show_scores = value
        self.update()

    # ── 绘制 ──

    def paintEvent(self, event):
        """主绘制函数"""
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            # 背景
            painter.fillRect(self.rect(), QColor(45, 45, 45))

            if self._pixmap is None:
                # 无图片时的提示
                painter.setPen(QColor(180, 180, 180))
                painter.setFont(QFont('Arial', 14))
                painter.drawText(self.rect(), Qt.AlignCenter,
                                 "请打开项目并选择图片\n快捷键: Ctrl+O 打开项目")
                return

            # ── 绘制图像 ──
            painter.setTransform(QTransform().translate(
                self._offset.x(), self._offset.y()).scale(self._scale, self._scale))
            painter.drawPixmap(0, 0, self._pixmap)
            painter.resetTransform()

            # ── 绘制标注 ──
            if self._annotations:
                for shape in self._annotations:
                    if isinstance(shape, BBox):
                        self._draw_bbox(painter, shape, is_selected=shape.selected)
                    elif isinstance(shape, Polygon):
                        self._draw_polygon(painter, shape, is_selected=shape.selected)

            # ── 绘制预测框（虚线蓝色，低于标注层） ──
            if self._predictions:
                for shape in self._predictions:
                    if isinstance(shape, BBox):
                        self._draw_prediction_bbox(painter, shape, is_selected=shape.selected)
                    elif isinstance(shape, Polygon):
                        self._draw_prediction_polygon(painter, shape, is_selected=shape.selected)

            # ── 绘制中的框 ──
            if self._drawing:
                self._draw_drawing_bbox(painter)

            # ── 绘制中的多边形 ──
            if self._poly_points:
                self._draw_drawing_polygon(painter)

            # ── 选区框 ──
            if self._selecting and self._select_rect:
                painter.setPen(QPen(QColor(100, 200, 255), 1, Qt.DashLine))
                painter.setBrush(QBrush(QColor(100, 200, 255, 30)))
                painter.drawRect(self._select_rect)

            # ── 放大信息 ──
            painter.setPen(QColor(200, 200, 200))
            painter.setFont(QFont('Monospace', 10))
            info = f"缩放: {self._scale:.2f}x  |  图片: {self._image_size[0]}x{self._image_size[1]}"
            painter.drawText(10, self.height() - 10, info)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_message.emit(f"绘制出错: {e}")

    def _draw_bbox(self, painter: QPainter, bbox: BBox, is_selected: bool = False):
        """绘制单个 BBox"""
        # 归一化 -> 图像坐标
        img_x = bbox.x * self._image_size[0]
        img_y = bbox.y * self._image_size[1]
        img_w = bbox.w * self._image_size[0]
        img_h = bbox.h * self._image_size[1]

        # 图像坐标 -> 画布坐标
        p1 = self.image_to_canvas(img_x, img_y)
        p2 = self.image_to_canvas(img_x + img_w, img_y + img_h)

        rect = QRectF(p1, p2)
        color = QColor(get_class_color(bbox.class_id))

        # 边框
        pen_width = 2 if not is_selected else 3
        pen = QPen(color, pen_width)
        if is_selected:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
        painter.drawRect(rect)

        # 选中时半透明填充
        if is_selected:
            fill_color = QColor(color.red(), color.green(), color.blue(), 30)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(rect)

        # 标签
        if self._show_labels and bbox.label:
            label_text = bbox.label
            if self._show_scores and bbox.score < 1.0:
                label_text += f" ({bbox.score:.2f})"

            # 标签背景
            font = QFont('Arial', 10)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_w = fm.width(label_text) + 6
            text_h = fm.height() + 2

            label_bg = QRectF(p1.x(), max(0, p1.y() - text_h), text_w, text_h)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(label_bg)

            # 标签文字
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_bg, Qt.AlignCenter, label_text)

            # 恢复画笔
            painter.setPen(pen)

        # 选中时绘制手柄
        if is_selected:
            self._draw_handles(painter, rect)

    def _draw_handles(self, painter: QPainter, rect: QRectF):
        """绘制缩放手柄"""
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QBrush(QColor(0, 120, 215)))

        points = [
            rect.topLeft(), rect.topRight(),
            rect.bottomLeft(), rect.bottomRight(),
            rect.center(),  # 中心移动手柄
        ]
        # 边中点
        points.append(QPointF(rect.center().x(), rect.top()))
        points.append(QPointF(rect.center().x(), rect.bottom()))
        points.append(QPointF(rect.left(), rect.center().y()))
        points.append(QPointF(rect.right(), rect.center().y()))

        for pt in points:
            painter.drawRect(QRectF(
                pt.x() - HANDLE_HALF, pt.y() - HANDLE_HALF,
                HANDLE_SIZE, HANDLE_SIZE
            ))

    def _draw_drawing_bbox(self, painter: QPainter):
        """绘制正在拖画的框"""
        rect = QRectF(self._draw_start, self._draw_current)
        painter.setPen(QPen(QColor(0, 200, 255), 2, Qt.DashLine))
        painter.setBrush(QBrush(QColor(0, 200, 255, 30)))
        painter.drawRect(rect)

    # ── 多边形绘制 ──

    VERTEX_RADIUS = 5
    VERTEX_HIT_RADIUS = 8
    CLOSE_DISTANCE = 12  # 闭合检测距离（画布像素）

    def _draw_polygon(self, painter: QPainter, polygon: Polygon,
                       is_selected: bool = False):
        """绘制单个多边形标注"""
        if len(polygon.points) < 2:
            return

        w, h = self._image_size
        color = QColor(get_class_color(polygon.class_id))

        # 将归一化顶点转为画布坐标
        pts_canvas = []
        for px, py in polygon.points:
            ix, iy = px * w, py * h
            cp = self.image_to_canvas(ix, iy)
            pts_canvas.append(cp)

        # 创建 QPolygonF
        poly_q = QPolygonF([QPointF(p.x(), p.y()) for p in pts_canvas])

        # 填充
        if len(polygon.points) >= 3:
            fill_color = QColor(color.red(), color.green(), color.blue(), 40)
            if is_selected:
                fill_color = QColor(color.red(), color.green(), color.blue(), 60)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly_q)

        # 边线
        pen_width = 2 if not is_selected else 3
        pen = QPen(color, pen_width)
        if is_selected:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if len(polygon.points) >= 2:
            for i in range(len(pts_canvas)):
                p1 = pts_canvas[i]
                p2 = pts_canvas[(i + 1) % len(pts_canvas)]
                painter.drawLine(int(p1.x()), int(p1.y()),
                                 int(p2.x()), int(p2.y()))

        # 标签
        if self._show_labels and polygon.label:
            label_text = polygon.label
            if self._show_scores and polygon.score < 1.0:
                label_text += f" ({polygon.score:.2f})"

            bbox = polygon.get_bbox()
            bx, by = bbox[0] * w, bbox[1] * h
            top_left = self.image_to_canvas(bx, by)

            font = QFont('Arial', 10)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_w = fm.width(label_text) + 6
            text_h = fm.height() + 2

            label_bg = QRectF(top_left.x(), max(0, top_left.y() - text_h),
                              text_w, text_h)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(label_bg)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_bg, Qt.AlignCenter, label_text)

        # 顶点手柄（选中时）
        if is_selected:
            self._draw_polygon_handles(painter, pts_canvas)

    def _draw_polygon_handles(self, painter: QPainter, pts_canvas: List[QPointF]):
        """绘制多边形顶点手柄和插入点"""
        # 顶点手柄
        for pt in pts_canvas:
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(0, 120, 215)))
            painter.drawEllipse(pt, self.VERTEX_RADIUS, self.VERTEX_RADIUS)

        # 边中点插入手柄（至少3个顶点才有边）
        if len(pts_canvas) >= 3:
            painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.DashLine))
            painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
            n = len(pts_canvas)
            for i in range(n):
                p1 = pts_canvas[i]
                p2 = pts_canvas[(i + 1) % n]
                mid = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
                painter.drawEllipse(mid, 3, 3)

    def _draw_drawing_polygon(self, painter: QPainter):
        """绘制正在绘制中的多边形"""
        if not self._poly_points:
            return

        pts = self._poly_points

        # 已固定的边
        if len(pts) >= 2:
            painter.setPen(QPen(QColor(0, 200, 255), 2))
            painter.setBrush(Qt.NoBrush)
            for i in range(len(pts) - 1):
                p1 = pts[i]
                p2 = pts[i + 1]
                painter.drawLine(int(p1.x()), int(p1.y()),
                                 int(p2.x()), int(p2.y()))

        # 最后一个点到鼠标位置的临时线
        if self._poly_hover_pos and len(pts) >= 1:
            painter.setPen(QPen(QColor(0, 200, 255, 150), 2, Qt.DashLine))
            last = pts[-1]
            painter.drawLine(int(last.x()), int(last.y()),
                             int(self._poly_hover_pos.x()),
                             int(self._poly_hover_pos.y()))

        # 闭合指示（鼠标靠近起点）
        if len(pts) >= 3 and self._poly_hover_pos:
            first = pts[0]
            dist = math.hypot(
                self._poly_hover_pos.x() - first.x(),
                self._poly_hover_pos.y() - first.y())
            if dist < self.CLOSE_DISTANCE * 2:
                painter.setPen(QPen(QColor(0, 255, 0), 2, Qt.DashLine))
                last = pts[-1]
                painter.drawLine(int(last.x()), int(last.y()),
                                 int(first.x()), int(first.y()))
                # 提示圆
                painter.setBrush(QBrush(QColor(0, 255, 0, 60)))
                painter.setPen(QPen(QColor(0, 255, 0), 1))
                painter.drawEllipse(first, 12, 12)

        # 顶点
        painter.setPen(QPen(QColor(0, 200, 255), 1))
        painter.setBrush(QBrush(QColor(0, 200, 255)))
        for pt in pts:
            painter.drawEllipse(pt, self.VERTEX_RADIUS, self.VERTEX_RADIUS)

    def _draw_prediction_polygon(self, painter: QPainter, polygon: Polygon,
                                  is_selected: bool = False):
        """绘制预测多边形（虚线蓝色）"""
        if len(polygon.points) < 2:
            return

        w, h = self._image_size
        pts_canvas = []
        for px, py in polygon.points:
            ix, iy = px * w, py * h
            cp = self.image_to_canvas(ix, iy)
            pts_canvas.append(cp)

        poly_q = QPolygonF([QPointF(p.x(), p.y()) for p in pts_canvas])

        # 填充
        if len(polygon.points) >= 3:
            painter.setBrush(QBrush(QColor(0, 100, 255, 20)))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly_q)

        # 边线
        pen_width = 2 if not is_selected else 3
        pen = QPen(QColor(0, 150, 255), pen_width, Qt.DashLine)
        if is_selected:
            pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if len(polygon.points) >= 2:
            for i in range(len(pts_canvas)):
                p1 = pts_canvas[i]
                p2 = pts_canvas[(i + 1) % len(pts_canvas)]
                painter.drawLine(int(p1.x()), int(p1.y()),
                                 int(p2.x()), int(p2.y()))

        # 标签
        label_text = f"{polygon.label} ({polygon.score:.2f})"
        font = QFont('Arial', 10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.width(label_text) + 6
        text_h = fm.height() + 2

        bbox = polygon.get_bbox()
        top_left = self.image_to_canvas(bbox[0] * w, bbox[1] * h)
        label_bg = QRectF(top_left.x(), max(0, top_left.y() - text_h),
                          text_w, text_h)
        painter.setBrush(QBrush(QColor(0, 120, 215, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(label_bg)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(label_bg, Qt.AlignCenter, label_text)

        if is_selected:
            self._draw_polygon_handles(painter, pts_canvas)

    def _draw_prediction_bbox(self, painter: QPainter, bbox: BBox,
                               is_selected: bool = False):
        """绘制预测框（虚线、蓝色、半透明）"""
        img_x = bbox.x * self._image_size[0]
        img_y = bbox.y * self._image_size[1]
        img_w = bbox.w * self._image_size[0]
        img_h = bbox.h * self._image_size[1]

        p1 = self.image_to_canvas(img_x, img_y)
        p2 = self.image_to_canvas(img_x + img_w, img_y + img_h)
        rect = QRectF(p1, p2)

        # 预测框：蓝色虚线
        pen_width = 2 if not is_selected else 3
        pen = QPen(QColor(0, 150, 255), pen_width, Qt.DashLine)
        if is_selected:
            pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(0, 100, 255, 20)))
        painter.drawRect(rect)

        # 标签：显示置信度
        label_text = f"{bbox.label} ({bbox.score:.2f})"
        font = QFont('Arial', 10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.width(label_text) + 6
        text_h = fm.height() + 2

        label_bg = QRectF(p1.x(), max(0, p1.y() - text_h), text_w, text_h)
        painter.setBrush(QBrush(QColor(0, 120, 215, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(label_bg)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(label_bg, Qt.AlignCenter, label_text)

        # 选中时绘制手柄
        if is_selected:
            self._draw_handles(painter, rect)

    # ── 鼠标事件 ──

    def mousePressEvent(self, event):
        self.setFocus()

        if self._pixmap is None:
            return

        pos = event.pos()
        img_pos = self.canvas_to_image(pos.x(), pos.y())
        ctrl = bool(event.modifiers() & Qt.ControlModifier)

        if event.button() == Qt.LeftButton:
            if self._mode == Mode.DRAW:
                self._start_draw(pos)
            elif self._mode == Mode.DRAW_POLYGON:
                self._polygon_add_point(pos)
            elif self._mode == Mode.SELECT:
                try:
                    if self._selected and not ctrl:
                        # 多边形顶点拖拽
                        if isinstance(self._selected, Polygon):
                            vi = self._hit_polygon_vertex(pos, self._selected)
                            if vi >= 0:
                                self._start_polygon_vertex_drag(pos, vi)
                                return
                            # 边中点插入
                            ei = self._hit_polygon_edge(pos, self._selected)
                            if ei >= 0:
                                self._insert_polygon_vertex(self._selected, ei, pos)
                                return
                            if self._selected.contains_point(
                                    img_pos.x() / self._image_size[0] if self._image_size[0] > 0 else 0,
                                    img_pos.y() / self._image_size[1] if self._image_size[1] > 0 else 0):
                                self._start_drag(pos, img_pos)
                                return
                        # BBox 调整大小
                        if isinstance(self._selected, BBox):
                            handle = self._hit_handle(pos)
                            if handle >= 0:
                                self._start_resize(pos, handle)
                                return
                        if hasattr(self._selected, 'contains_point') and \
                           self._selected.contains_point(
                               img_pos.x() / self._image_size[0] if self._image_size[0] > 0 else 0,
                               img_pos.y() / self._image_size[1] if self._image_size[1] > 0 else 0):
                            self._start_drag(pos, img_pos)
                            return

                    # Ctrl+点击 → 切换选中；普通点击 → 单选
                    hit = self._hit_test(pos)
                    if hit:
                        if ctrl:
                            self.annotation_toggled.emit(hit)
                        else:
                            self.annotation_selected.emit(hit)
                    elif not ctrl:
                        # 点击空白：取消选中 + 平移
                        if self._selected:
                            self.annotation_selected.emit(None)
                        self._start_pan(pos)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.status_message.emit(f"鼠标按下出错: {e}")

        elif event.button() == Qt.RightButton:
            if self._mode == Mode.DRAW and self._drawing:
                self._cancel_draw()
            elif self._mode == Mode.DRAW_POLYGON and self._poly_points:
                self._polygon_undo_point()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        img_pos = self.canvas_to_image(pos.x(), pos.y())

        # 状态栏显示坐标
        nx, ny = img_pos.x(), img_pos.y()
        if 0 <= nx <= self._image_size[0] and 0 <= ny <= self._image_size[1]:
            norm = self.image_to_normalized(nx, ny)
            self.status_message.emit(
                f"像素: ({int(nx)}, {int(ny)})  "
                f"归一化: ({norm.x():.4f}, {norm.y():.4f})"
            )

        if self._poly_points:
            self._polygon_update_hover(pos)
        if self._drawing:
            self._update_draw(pos)
        elif self._dragging:
            self._update_drag(pos, img_pos)
        elif self._resizing:
            self._update_resize(pos)
        elif self._editing_polygon:
            self._update_polygon_vertex_drag(pos)
        elif self._panning:
            self._update_pan(pos)
        elif self._selecting:
            self._update_select_rect(pos)
        elif self._mode == Mode.SELECT and self._selected:
            # 光标样式
            if isinstance(self._selected, Polygon):
                vi = self._hit_polygon_vertex(pos, self._selected)
                if vi >= 0:
                    self.setCursor(QCursor(Qt.CrossCursor))
                elif self._hit_polygon_edge(pos, self._selected) >= 0:
                    self.setCursor(QCursor(Qt.PointingHandCursor))
                elif self._selected.contains_point(
                        img_pos.x() / self._image_size[0] if self._image_size[0] > 0 else 0,
                        img_pos.y() / self._image_size[1] if self._image_size[1] > 0 else 0):
                    self.setCursor(QCursor(Qt.SizeAllCursor))
                else:
                    self.setCursor(QCursor(Qt.ArrowCursor))
            elif isinstance(self._selected, BBox):
                handle = self._hit_handle(pos)
                if handle >= 0:
                    self.setCursor(QCursor(Qt.SizeFDiagCursor)
                                   if handle in [0, 3] else
                                   QCursor(Qt.SizeBDiagCursor)
                                   if handle in [1, 2] else
                                   QCursor(Qt.SizeAllCursor))
                elif self._hit_bbox(pos, self._selected):
                    self.setCursor(QCursor(Qt.SizeAllCursor))
                else:
                    self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drawing:
                self._finish_draw()
            elif self._dragging:
                self._finish_drag()
            elif self._resizing:
                self._finish_resize()
            elif self._editing_polygon:
                self._finish_polygon_edit()
            elif self._panning:
                self._panning = False
                self._update_cursor()
            elif self._selecting:
                self._finish_select_rect()
                self._selecting = False

    def mouseDoubleClickEvent(self, event):
        """双击适应窗口或完成多边形"""
        if event.button() == Qt.LeftButton:
            if self._mode == Mode.DRAW_POLYGON and len(self._poly_points) >= 2:
                self._polygon_finish()
                return
            self._fit_to_widget()
            self.update()

    # ── 滚轮缩放 ──

    def wheelEvent(self, event):
        """滚轮缩放"""
        if self._pixmap is None:
            return

        factor = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
        mouse_pos = QPointF(event.pos())

        # 以鼠标位置为中心缩放
        img_before = self.canvas_to_image(mouse_pos.x(), mouse_pos.y())
        self._scale *= factor
        self._scale = max(0.1, min(50.0, self._scale))
        img_after = self.canvas_to_image(mouse_pos.x(), mouse_pos.y())

        # 修正偏移使鼠标位置不变
        delta = img_after - img_before
        self._offset += QPointF(delta.x() * self._scale, delta.y() * self._scale)

        self.update()

    # ── 键盘事件 ──

    def keyPressEvent(self, event):
        try:
            key = event.key()

            if key == Qt.Key_Delete or key == Qt.Key_Backspace or \
               (key == Qt.Key_D and event.modifiers() & Qt.ControlModifier):
                if self._selected:
                    if self._selected in self._predictions:
                        self.annotation_reject_requested.emit(self._selected)
                    elif self._on_request_delete:
                        self._on_request_delete(self._selected)
            elif key == Qt.Key_Return or key == Qt.Key_Enter:
                if self._poly_points:
                    self._polygon_finish()
                elif self._selected and self._selected in self._predictions:
                    self.annotation_accept_requested.emit(self._selected)
            elif key == Qt.Key_Escape:
                if self._drawing:
                    self._cancel_draw()
                if self._poly_points:
                    self._poly_points.clear()
                    self._poly_hover_pos = None
                    self.update()
                self.annotation_selected.emit(None)
            elif key == Qt.Key_W:
                if self._mode == Mode.DRAW:
                    self.set_mode(Mode.SELECT)
                elif self._mode == Mode.SELECT:
                    self.set_mode(Mode.DRAW)
            elif key == Qt.Key_P:
                if self._mode == Mode.DRAW_POLYGON:
                    self.set_mode(Mode.SELECT)
                else:
                    self.set_mode(Mode.DRAW_POLYGON)
            elif key == Qt.Key_S:
                self.set_mode(Mode.SELECT)
            elif key == Qt.Key_H:
                self.set_mode(Mode.PAN)
            elif key == Qt.Key_Plus or key == Qt.Key_Equal:
                self._scale *= 1.2
                self._scale = min(50.0, self._scale)
                self.update()
            elif key == Qt.Key_Minus:
                self._scale /= 1.2
                self._scale = max(0.1, self._scale)
                self.update()

            super().keyPressEvent(event)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_message.emit(f"键盘操作出错: {e}")

    # ── 绘制操作 ──

    def _start_draw(self, pos: QPointF):
        self._drawing = True
        self._draw_start = QPointF(pos)
        self._draw_current = QPointF(pos)

    def _update_draw(self, pos: QPointF):
        self._draw_current = QPointF(pos)
        self.update()

    def _finish_draw(self):
        """完成绘制，创建 BBox"""
        if not self._drawing:
            return

        self._drawing = False

        p1 = self.canvas_to_image(self._draw_start.x(), self._draw_start.y())
        p2 = self.canvas_to_image(self._draw_current.x(), self._draw_current.y())

        x1 = max(0, min(p1.x(), p2.x()))
        y1 = max(0, min(p1.y(), p2.y()))
        x2 = min(self._image_size[0], max(p1.x(), p2.x()))
        y2 = min(self._image_size[1], max(p1.y(), p2.y()))

        w = x2 - x1
        h = y2 - y1
        if w < 5 or h < 5:
            return  # 太小的框忽略

        # 转换为归一化坐标
        norm_p1 = self.image_to_normalized(x1, y1)
        norm_p2 = self.image_to_normalized(x2, y2)
        nw = norm_p2.x() - norm_p1.x()
        nh = norm_p2.y() - norm_p1.y()

        bbox = BBox(
            x=norm_p1.x(),
            y=norm_p1.y(),
            w=nw,
            h=nh,
            label='',
        )
        self.annotation_added.emit(bbox)
        self.update()

    def _cancel_draw(self):
        self._drawing = False
        self.update()

    # ── 拖拽操作 ──

    def _start_drag(self, pos: QPointF, img_pos: QPointF):
        self._dragging = True
        self._drag_start = QPointF(pos)
        self._drag_img_start = QPointF(img_pos)

    def _update_drag(self, pos: QPointF, img_pos: QPointF):
        if not self._dragging or not self._selected:
            return
        if isinstance(self._selected, BBox):
            dx_img = (img_pos.x() - self._drag_img_start.x()) / self._image_size[0]
            dy_img = (img_pos.y() - self._drag_img_start.y()) / self._image_size[1]
            self._selected.x += dx_img
            self._selected.y += dy_img
            self._drag_img_start = QPointF(img_pos)
        elif isinstance(self._selected, Polygon):
            dx_img = (img_pos.x() - self._drag_img_start.x()) / self._image_size[0]
            dy_img = (img_pos.y() - self._drag_img_start.y()) / self._image_size[1]
            self._selected.points = [
                (x + dx_img, y + dy_img) for x, y in self._selected.points
            ]
            self._drag_img_start = QPointF(img_pos)
        self.annotation_changed.emit()
        self.update()

    def _finish_drag(self):
        self._dragging = False

    # ── 调整大小操作 ──

    def _hit_handle(self, pos: QPointF) -> int:
        """检测是否点击到手柄，返回手柄索引"""
        if not isinstance(self._selected, BBox):
            return -1

        bbox = self._selected
        img_x = bbox.x * self._image_size[0]
        img_y = bbox.y * self._image_size[1]
        img_w = bbox.w * self._image_size[0]
        img_h = bbox.h * self._image_size[1]

        p1 = self.image_to_canvas(img_x, img_y)
        p2 = self.image_to_canvas(img_x + img_w, img_y + img_h)

        handles = [
            p1,                         # 0: 左上
            QPointF(p2.x(), p1.y()),    # 1: 右上
            QPointF(p1.x(), p2.y()),    # 2: 左下
            p2,                         # 3: 右下
        ]

        for i, hp in enumerate(handles):
            if abs(pos.x() - hp.x()) < HANDLE_SIZE and \
               abs(pos.y() - hp.y()) < HANDLE_SIZE:
                return i
        return -1

    def _start_resize(self, pos: QPointF, handle: int):
        self._resizing = True
        self._resize_handle = handle
        if isinstance(self._selected, BBox):
            b = self._selected
            self._resize_old_bbox = (b.x, b.y, b.w, b.h)
        self._resize_start = QPointF(pos)

    def _update_resize(self, pos: QPointF):
        if not self._resizing or not isinstance(self._selected, BBox):
            return

        bbox = self._selected
        dx = (pos.x() - self._resize_start.x()) / self._scale / self._image_size[0]
        dy = (pos.y() - self._resize_start.y()) / self._scale / self._image_size[1]

        handle = self._resize_handle
        x, y, w, h = bbox.x, bbox.y, bbox.w, bbox.h

        if handle == 0:  # 左上
            bbox.x = x + dx
            bbox.y = y + dy
            bbox.w = w - dx
            bbox.h = h - dy
        elif handle == 1:  # 右上
            bbox.y = y + dy
            bbox.w = w + dx
            bbox.h = h - dy
        elif handle == 2:  # 左下
            bbox.x = x + dx
            bbox.w = w - dx
            bbox.h = h + dy
        elif handle == 3:  # 右下
            bbox.w = w + dx
            bbox.h = h + dy

        # 确保最小尺寸
        if bbox.w < 0.01:
            bbox.w = 0.01
        if bbox.h < 0.01:
            bbox.h = 0.01

        self._resize_start = QPointF(pos)
        self.annotation_changed.emit()
        self.update()

    def _finish_resize(self):
        self._resizing = False

    # ── 平移操作 ──

    def _start_pan(self, pos: QPointF):
        self._panning = True
        self._pan_start = QPointF(pos)
        self._pan_offset_start = QPointF(self._offset)
        self.setCursor(QCursor(Qt.ClosedHandCursor))

    def _update_pan(self, pos: QPointF):
        if not self._panning:
            return
        delta = pos - self._pan_start
        self._offset = QPointF(
            self._pan_offset_start.x() + delta.x(),
            self._pan_offset_start.y() + delta.y(),
        )
        self.update()

    # ── 选区操作 ──

    def _start_select_rect(self, pos: QPointF):
        self._selecting = True
        self._select_rect = QRectF(pos, QSizeF(0, 0))

    def _update_select_rect(self, pos: QPointF):
        if self._select_rect:
            self._select_rect.setBottomRight(pos)
            self.update()

    def _finish_select_rect(self):
        if self._select_rect is None:
            return

        rect = self._select_rect.normalized()
        if rect.width() < 5 and rect.height() < 5:
            self._select_rect = None
            self.update()
            return

        # 检测选中范围内的标注
        img_p1 = self.canvas_to_image(rect.left(), rect.top())
        img_p2 = self.canvas_to_image(rect.right(), rect.bottom())

        for shape in reversed(self._annotations):
            if isinstance(shape, BBox):
                sx = shape.x * self._image_size[0]
                sy = shape.y * self._image_size[1]
                sw = shape.w * self._image_size[0]
                sh = shape.h * self._image_size[1]

                if (sx >= img_p1.x() and sy >= img_p1.y() and
                        sx + sw <= img_p2.x() and sy + sh <= img_p2.y()):
                    self.annotation_selected.emit(shape)
                    self._select_rect = None
                    self.update()
                    return

        # 没选中任何东西
        self._select_rect = None
        self.annotation_selected.emit(None)
        self.update()

    # ── 命中检测 ──

    def _hit_test(self, pos: QPointF) -> Optional[Shape]:
        """检测画布坐标pos处是否有标注"""
        img_pos = self.canvas_to_image(pos.x(), pos.y())
        px, py = img_pos.x(), img_pos.y()
        # 从上层往下查
        for shape in reversed(self._annotations):
            if isinstance(shape, BBox):
                sx = shape.x * self._image_size[0]
                sy = shape.y * self._image_size[1]
                sw = shape.w * self._image_size[0]
                sh = shape.h * self._image_size[1]
                if sx <= px <= sx + sw and sy <= py <= sy + sh:
                    return shape
            elif isinstance(shape, Polygon):
                if shape.contains_point(px / self._image_size[0] if self._image_size[0] > 0 else 0,
                                        py / self._image_size[1] if self._image_size[1] > 0 else 0):
                    return shape
        return None

    def _hit_bbox(self, pos: QPointF, bbox: BBox) -> bool:
        """检测pos是否在bbox的范围内"""
        img_pos = self.canvas_to_image(pos.x(), pos.y())
        sx = bbox.x * self._image_size[0]
        sy = bbox.y * self._image_size[1]
        sw = bbox.w * self._image_size[0]
        sh = bbox.h * self._image_size[1]
        return sx <= img_pos.x() <= sx + sw and sy <= img_pos.y() <= sy + sh

    # ── 多边形绘制操作 ──

    def _polygon_add_point(self, pos: QPointF):
        """添加多边形顶点"""
        # 检测是否点击在起点上（闭合多边形）
        if len(self._poly_points) >= 2:
            first = self._poly_points[0]
            dist = math.hypot(pos.x() - first.x(), pos.y() - first.y())
            if dist < self.CLOSE_DISTANCE:
                self._polygon_finish(closed_by_proximity=True)
                return

        self._poly_points.append(QPointF(pos))
        self._poly_hover_pos = QPointF(pos)
        self.update()

    def _polygon_update_hover(self, pos: QPointF):
        """更新绘制中多边形的鼠标悬停位置"""
        if self._poly_points:
            self._poly_hover_pos = QPointF(pos)
            self.update()

    def _polygon_undo_point(self):
        """撤销上一个顶点"""
        if self._poly_points:
            self._poly_points.pop()
            self.update()

    def _polygon_finish(self, closed_by_proximity=False):
        """完成多边形绘制（支持闭合和开放线膨胀）

        Args:
            closed_by_proximity: True=用户点击起点闭合, False=双击/Enter完成(开放线)
        """
        if len(self._poly_points) < 2:
            # 点数不够，忽略
            self._poly_points.clear()
            self._poly_hover_pos = None
            self.update()
            return

        pts = self._poly_points

        # 将画布坐标转为归一化坐标
        pts_normalized = []
        for pt in pts:
            img_pt = self.canvas_to_image(pt.x(), pt.y())
            norm = self.image_to_normalized(img_pt.x(), img_pt.y())
            # 裁剪到 [0, 1]
            nx = max(0, min(1, norm.x()))
            ny = max(0, min(1, norm.y()))
            pts_normalized.append((nx, ny))

        if not closed_by_proximity and len(pts_normalized) >= 2:
            # 开放线（双击/Enter）→ 左右膨胀为闭合多边形
            pts_expanded = self._create_thickened_polygon(pts_normalized)
            if pts_expanded and len(pts_expanded) >= 3:
                polygon = Polygon(points=pts_expanded)
                self.annotation_added.emit(polygon)
                self.status_message.emit("已自动膨胀为裂纹多边形")
        elif len(pts_normalized) >= 3:
            # 正常闭合多边形，做面积检测
            xs = [p[0] for p in pts_normalized]
            ys = [p[1] for p in pts_normalized]
            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            if area < 0.001:
                self._poly_points.clear()
                self._poly_hover_pos = None
                self.update()
                return
            polygon = Polygon(points=pts_normalized)
            self.annotation_added.emit(polygon)

        self._poly_points.clear()
        self._poly_hover_pos = None
        self.update()

    # ── 开放线膨胀 ──

    POLYGON_THICKNESS = 0.012  # 默认膨胀厚度（归一化坐标）

    def _create_thickened_polygon(self, pts_norm):
        """将开放线左右膨胀为闭合多边形（用于裂纹标注）

        沿中心线每个点的垂直方向，向两侧偏移生成左右边，形成带状多边形。
        """
        if len(pts_norm) < 2:
            return None
        w, h = self._image_size
        if w == 0 or h == 0:
            return None

        # 转换为图像坐标（像素），膨胀厚度用图像尺寸计算
        img_pts = [(x * w, y * h) for x, y in pts_norm]
        half = self.POLYGON_THICKNESS * min(w, h) / 2.0
        if half < 1:
            half = 2.0  # 最小 2 像素

        left_side = []
        right_side = []

        for i, (px, py) in enumerate(img_pts):
            # 计算方向向量
            if i == 0:
                dx = img_pts[1][0] - px
                dy = img_pts[1][1] - py
            elif i == len(img_pts) - 1:
                dx = px - img_pts[i - 1][0]
                dy = py - img_pts[i - 1][1]
            else:
                # 内部点：用前后两段的方向均值
                dx = img_pts[i + 1][0] - img_pts[i - 1][0]
                dy = img_pts[i + 1][1] - img_pts[i - 1][1]

            length = math.hypot(dx, dy)
            if length < 1:
                left_side.append((px, py))
                right_side.append((px, py))
                continue

            dx /= length
            dy /= length

            # 垂直向量（顺时针旋转 90°）
            perp_x = -dy
            perp_y = dx

            left_side.append((px + perp_x * half, py + perp_y * half))
            right_side.append((px - perp_x * half, py - perp_y * half))

        # 构建闭合多边形：沿左侧 → 从右侧返回（反转）
        poly_img = left_side + right_side[::-1]

        # 转回归一化坐标，裁剪到 [0, 1]
        result = []
        for x, y in poly_img:
            result.append((
                max(0, min(1, x / w)),
                max(0, min(1, y / h)),
            ))
        return result

    # ── 多边形编辑操作 ──

    def _hit_polygon_vertex(self, pos: QPointF, polygon: Polygon) -> int:
        """检测是否点击到多边形顶点，返回顶点索引"""
        w, h = self._image_size
        for i, (px, py) in enumerate(polygon.points):
            ix, iy = px * w, py * h
            cp = self.image_to_canvas(ix, iy)
            dist = math.hypot(pos.x() - cp.x(), pos.y() - cp.y())
            if dist < self.VERTEX_HIT_RADIUS:
                return i
        return -1

    def _hit_polygon_edge(self, pos: QPointF, polygon: Polygon) -> int:
        """检测是否点击到多边形边，返回插入位置索引（边的起点）"""
        if len(polygon.points) < 3:
            return -1
        w, h = self._image_size
        n = len(polygon.points)
        for i in range(n):
            x1, y1 = polygon.points[i]
            x2, y2 = polygon.points[(i + 1) % n]
            p1 = self.image_to_canvas(x1 * w, y1 * h)
            p2 = self.image_to_canvas(x2 * w, y2 * h)
            mid = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2)
            dist = math.hypot(pos.x() - mid.x(), pos.y() - mid.y())
            if dist < self.VERTEX_HIT_RADIUS:
                return (i + 1) % n
        return -1

    def _start_polygon_vertex_drag(self, pos: QPointF, vertex_idx: int):
        """开始拖拽多边形顶点"""
        self._editing_polygon = True
        self._edit_vertex_idx = vertex_idx
        self._drag_start = QPointF(pos)

    def _update_polygon_vertex_drag(self, pos: QPointF):
        """拖拽多边形顶点"""
        if not self._editing_polygon or not isinstance(self._selected, Polygon):
            return
        poly = self._selected
        if self._edit_vertex_idx < 0 or self._edit_vertex_idx >= len(poly.points):
            return

        img_pos = self.canvas_to_image(pos.x(), pos.y())
        norm = self.image_to_normalized(img_pos.x(), img_pos.y())
        nx = max(0, min(1, norm.x()))
        ny = max(0, min(1, norm.y()))

        pts = list(poly.points)
        pts[self._edit_vertex_idx] = (nx, ny)
        poly.points = pts
        self.annotation_changed.emit()
        self.update()

    def _finish_polygon_edit(self):
        """完成多边形编辑"""
        self._editing_polygon = False
        self._edit_vertex_idx = -1
        self._edit_insert_idx = -1

    def _insert_polygon_vertex(self, polygon: Polygon, insert_idx: int, pos: QPointF):
        """在边的中点插入新顶点"""
        img_pos = self.canvas_to_image(pos.x(), pos.y())
        norm = self.image_to_normalized(img_pos.x(), img_pos.y())
        nx = max(0, min(1, norm.x()))
        ny = max(0, min(1, norm.y()))

        pts = list(polygon.points)
        pts.insert(insert_idx, (nx, ny))
        polygon.points = pts
        self.annotation_changed.emit()
        self.update()

    # ── 上下文菜单 ──

    def _show_context_menu(self, pos):
        menu = QMenu(self)

        if self._mode == Mode.SELECT and self._selected:
            # ── 修改类别 ──
            if self._classes:
                class_menu = menu.addMenu("📋 修改类别")
                for c in self._classes:
                    action = class_menu.addAction(f"● {c['name']}")
                    action.setData(c['id'])
                    ann = self._selected
                    action.triggered.connect(
                        lambda checked, cid=c['id'], nm=c['name']:
                        self.annotation_class_changed.emit(ann, cid, nm))
                menu.addSeparator()

            # ── 删除 ──
            delete_action = menu.addAction("🗑 删除标注 (Del)")
            delete_action.triggered.connect(
                lambda: self._on_request_delete(self._selected) if self._on_request_delete else None)
            menu.addSeparator()

        if self._mode == Mode.SELECT:
            mode_menu = menu.addMenu("切换模式")
            mode_menu.addAction("选择 (S)", lambda: self.set_mode(Mode.SELECT))
            mode_menu.addAction("绘制 (W)", lambda: self.set_mode(Mode.DRAW))
            mode_menu.addAction("平移 (H)", lambda: self.set_mode(Mode.PAN))

            fit_action = menu.addAction("适应窗口 (双击)")
            fit_action.triggered.connect(lambda: self._fit_to_widget() or self.update())

            menu.exec_(self.mapToGlobal(pos))
