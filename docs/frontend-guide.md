# Frontend 开发指南

## 组件层次

```
MainWindow
├── ProjectDock + ModelDock (左侧，Tab切换)
├── ImageView (中央)
│   ├── 工具条 (模式切换 + 缩放控制)
│   └── Canvas (核心画布)
├── LabelDock + PropertyDock (右侧，Tab切换)
└── 菜单栏 + 状态栏
```

## Canvas 详解

### 交互模式

Canvas 有三种模式，通过 `Mode` 常量定义：

| 模式 | 快捷键 | 光标 | 功能 |
|------|--------|------|------|
| SELECT | `S` | 箭头/移动 | 选择、拖拽、多选、空白→平移 |
| DRAW | `W` | 十字 | 拖拽画矩形框 |
| DRAW_POLYGON | `P` | 十字 | 点击加顶点，双击闭合多边形 |
| PAN | `H` | 抓手 | 平移视图 |

### 多选操作

| 操作 | 效果 |
|------|------|
| 点击框 | 单选（取消之前选中） |
| Ctrl+点击 | 切换该框选中状态（多选） |
| 点击空白 | 取消全部选中 + 平移 |
| 右键 → 修改类别 | 单个/批量改所有选中标注的类别 |

### 多边形绘制流程

```
1. 进入 DRAW_POLYGON 模式 (P 键)
2. mousePressEvent: 添加顶点到 _poly_points
3. mouseMoveEvent: 更新 _poly_hover_pos，显示临时线
4. 双击 / 点击起点: 闭合多边形
   a. 将画布坐标转为归一化坐标
   b. 创建 Polygon，通过 annotation_added 信号发出
5. Escape: 撤销上一个顶点
6. 右键: 撤销上一个顶点
```

### 多边形编辑

- 拖拽顶点: 移动该顶点
- 点击边中点: 在该位置插入新顶点
- 拖拽内部: 移动整个多边形

### 绘制流程 (BBox)

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
Canvas.annotation_toggled ────────────────→ MainWindow._on_annotation_toggled   ← Ctrl+点击多选
Canvas.annotation_changed ────────────────→ MainWindow._on_annotation_changed
Canvas.annotation_class_changed ──────────→ MainWindow._on_label_class_changed
Canvas.annotation_accept_requested ───────→ MainWindow._on_accept_prediction
Canvas.annotation_reject_requested ───────→ MainWindow._on_reject_prediction
Canvas.mode_changed ─────────────────────→ MainWindow._on_mode_changed
Canvas.mode_changed ─────────────────────→ ImageView.sync_mode_buttons          ← 同步工具栏按钮
Canvas.status_message ───────────────────→ MainWindow._on_status_message

LabelDock.annotation_selected ────────────→ MainWindow._on_label_selected
LabelDock.annotation_deleted ─────────────→ MainWindow._on_label_deleted
LabelDock.annotation_class_changed ───────→ MainWindow._on_label_class_changed

PropertyDock.property_changed ────────────→ MainWindow._on_annotation_changed

ProjectDock.image_selected ───────────────→ MainWindow._on_image_selected
ProjectDock.project_opened ───────────────→ MainWindow._on_project_opened
ProjectDock.project_closed ───────────────→ MainWindow 关闭清理

ModelDock.load_model_requested ───────────→ MainWindow._on_load_model
ModelDock.unload_model_requested ─────────→ MainWindow._on_unload_model
ModelDock.auto_label_requested ───────────→ MainWindow._on_auto_label
ModelDock.batch_label_requested ──────────→ MainWindow._on_batch_label
ModelDock.accept_all_requested ───────────→ MainWindow._on_accept_all
ModelDock.reject_all_requested ───────────→ MainWindow._on_reject_all
ModelDock.conf_threshold_changed ─────────→ MainWindow._on_conf_threshold
ModelDock.iou_threshold_changed ──────────→ MainWindow._on_iou_threshold

AnnotationManager.on_change ──────────────→ MainWindow._on_annotations_updated
AnnotationManager.on_select_change ───────→ MainWindow._on_selection_updated
AnnotationManager.on_predictions_change ──→ MainWindow._on_predictions_updated
```

## ModelDock 面板

模型管理面板，用于加载 YOLO 模型、自动标注、接受/拒绝预测。

### 功能
- 选择并加载 .pt 模型文件（路径自动持久化到 config.yaml）
- 卸载模型释放显存
- 置信度阈值滑块 (0.05~0.95)
- IoU 阈值滑块 (0.10~0.90)，控制 NMS 去重力度
- 自动标注当前图片
- 批量标注所有未标注图片
- 全部接受 / 全部拒绝（不按阈值过滤）

### 信号
```
load_model_requested(path)      → MainWindow._on_load_model
unload_model_requested()        → MainWindow._on_unload_model
auto_label_requested()          → MainWindow._on_auto_label
batch_label_requested()         → MainWindow._on_batch_label
accept_all_requested(0.0)        → MainWindow._on_accept_all（接受全部，不按阈值过滤）
reject_all_requested(0.0)        → MainWindow._on_reject_all（拒绝全部）
conf_threshold_changed(value)   → MainWindow._on_conf_threshold
iou_threshold_changed(value)    → MainWindow._on_iou_threshold
```

### 预测工作流
```
用户点「自动标注」 → YOLO 预测 → 蓝色虚线框显示
→ 用户按 Enter 接受 / Del 拒绝
→ 接受的预测转为正式标注（score=1.0）
→ 自动保存到项目数据库
```

## TrainDock 面板

训练管理面板（位于左侧面板最下方），用于 YOLO 模型训练。

### 功能
- 数据集统计概览（图片数/已标注数/类别数）
- 训练参数配置：预设方案（快速/标准/精度优先）或自定义
- 架构选择（yolov8n/s/m/l/x, yolo11n/s/m/l/x）
- 增量训练：从已有检查点继续训练
- 高级参数：优化器、学习率、早停耐心、数据增强、训练集比例
- 开始/停止训练
- 实时进度条 + 指标展示（Loss, mAP50, mAP50-95, LR, 时间）
- 训练日志实时输出
- 训练完成后自动加载模型

### 信号
```
training_started()              → MainWindow 更新 UI
training_finished(success)      → MainWindow 自动配置类别映射
load_model_requested(path)      → MainWindow._on_load_model
```

### 训练工作流
```
用户点「🚀 开始训练」
  → 主线程导出标注数据（SQLite 安全）
  → QThread 后台运行 YOLO 训练
  → 每轮回调更新 UI 进度
  → 训练完成 → 模型保存到 projects/<name>/models/best.pt
  → 自动配置类别映射
  → 可选：自动加载模型到推理引擎
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
