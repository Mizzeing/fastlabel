# Frontend 开发指南

## 组件层次

```
MainWindow
├── ProjectDock (左侧)
├── ImageView (中央)
│   ├── 工具条 (模式切换 + 缩放控制)
│   └── Canvas (核心画布)
├── LabelDock (右侧)
├── PropertyDock (右侧，tab 在 LabelDock 下面)
└── 菜单栏 + 状态栏
```

## Canvas 详解

### 交互模式

Canvas 有三种模式，通过 `Mode` 常量定义：

| 模式 | 快捷键 | 光标 | 功能 |
|------|--------|------|------|
| SELECT | `S` | 箭头/移动 | 选择、拖拽、调整大小、框选 |
| DRAW | `W` | 十字 | 拖拽画矩形框 |
| PAN | `H` | 抓手 | 平移视图 |

### 绘制流程

```
1. 进入 DRAW 模式
2. mousePressEvent: 记录 _draw_start
3. mouseMoveEvent: 更新 _draw_current，实时显示矩形
4. mouseReleaseEvent:
   a. canvas_to_image() 得到图像坐标
   b. clamp 到图片边界
   c. 排除过小矩形 (<5px)
   d. image_to_normalized() 得到归一化坐标
   e. 创建 BBox，通过 annotation_added 信号发出
```

### 拖拽移动流程

```
1. SELECT 模式下，鼠标点击选中标注内部
2. mousePressEvent: 记录 _drag_img_start（图像坐标）
3. mouseMoveEvent:
   a. 计算当前图像坐标与起始坐标的差值
   b. 差值归一化后加到 BBox 位置
   c. 更新 _drag_img_start = 当前位置
4. mouseReleaseEvent: 结束拖拽
```

### 缩放手柄

选中 BBox 显示 9 个控制点：

```
[0]──────[5]──────[1]
 │                 │
[7]    [4]    [8]  │
 │                 │
[2]──────[6]──────[3]
```

- 0=左上, 1=右上, 2=左下, 3=右下（角点，对角缩放）
- 4=中心（移动）
- 5=上中, 6=下中, 7=左中, 8=右中（单边缩放）

### 滚轮缩放

以鼠标位置为中心进行缩放，需要修正偏移量使鼠标下的图像点不变：

```
img_before = canvas_to_image(mouse_pos)
scale *= factor
img_after = canvas_to_image(mouse_pos)
offset += (img_after - img_before) * scale
```

### 坐标转换函数

| 函数 | 转换 |
|------|------|
| `image_to_canvas(img_x, img_y)` | 图像坐标 → 画布像素坐标 |
| `canvas_to_image(canvas_x, canvas_y)` | 画布像素坐标 → 图像坐标 |
| `normalized_to_image(nx, ny)` | 归一化坐标 → 图像坐标 |
| `image_to_normalized(ix, iy)` | 图像坐标 → 归一化坐标 |

## MainWindow 信号连接

```
Canvas.annotation_added ──────────────────→ MainWindow._on_annotation_added
Canvas.annotation_selected ───────────────→ MainWindow._on_annotation_selected
Canvas.annotation_changed ────────────────→ MainWindow._on_annotation_changed
Canvas.mode_changed ─────────────────────→ MainWindow._on_mode_changed
Canvas.status_message ───────────────────→ MainWindow._on_status_message

LabelDock.annotation_selected ────────────→ MainWindow._on_label_selected
LabelDock.annotation_deleted ─────────────→ MainWindow._on_label_deleted
LabelDock.annotation_class_changed ───────→ MainWindow._on_label_class_changed

PropertyDock.property_changed ────────────→ MainWindow._on_annotation_changed

ProjectDock.image_selected ───────────────→ MainWindow._on_image_selected
ProjectDock.project_opened ───────────────→ MainWindow._on_project_opened

AnnotationManager.on_change ──────────────→ MainWindow._on_annotations_updated
AnnotationManager.on_select_change ───────→ MainWindow._on_selection_updated
```

## 添加新 DockWidget

1. 在 `frontend/widgets/` 下创建新文件
2. 定义信号和界面
3. 在 `MainWindow._setup_ui()` 中添加：
```python
self._my_dock = MyDock()
self.addDockWidget(Qt.RightDockWidgetArea, self._my_dock)
```
4. 在 `_connect_signals()` 中连接信号

## 样式指南

FastLabel 使用暗色主题，基于以下颜色方案：

| 用途 | 颜色值 |
|------|--------|
| 窗口背景 | #1e1e1e |
| 面板背景 | #252526 |
| 控件背景 | #2d2d2d |
| 边框 | #3d3d3d |
| 普通文字 | #cccccc |
| 次要文字 | #888888 |
| 高亮/选中 | #0d6efd |
| 悬停 | #4d4d4d |
