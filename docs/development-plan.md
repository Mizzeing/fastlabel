# FastLabel 开发计划

## ✅ 第一阶段：MVP（已完成）

### 目标
实现核心标注功能，能够完整走通「创建项目 → 导入图片 → 标注 → 导出」流程。

### 已完成功能
- [x] 项目管理（新建/打开/关闭）
- [x] 图片导入（支持多种格式）
- [x] 图片浏览（前后切换）
- [x] BBox 标注（绘制/选择/拖拽/缩放）
- [x] 类别管理（添加/编辑/删除/颜色/快捷键）
- [x] YOLO 格式导出
- [x] Undo/Redo（Command 模式）
- [x] 快捷键（全键盘操作）
- [x] SQLite 持久化存储

### 完成文件
```
共 20 个文件，~3000 行代码

backend/
├── annotation/
│   ├── shape.py          (Shape 基类，~50 行)
│   ├── bbox.py           (BBox 实现，~100 行)
│   └── polygon.py        (Polygon 多边形，~80 行)
│   ├── command.py        (Command 模式，~160 行)
│   └── manager.py        (标注管理器，~130 行)
├── project/
│   ├── config.py         (YAML 配置，~110 行)
│   ├── project.py        (项目+数据库，~230 行)
│   └── manager.py        (项目管理器，~130 行)
├── dataset/
│   ├── image_loader.py   (图片加载，~90 行)
│   ├── label_loader.py   (标签读写，~80 行)
│   └── manager.py        (数据集管理，~160 行)
├── export/
│   └── yolo.py           (YOLO 导出，~80 行)
└── utils/
    └── misc.py           (工具函数，~80 行)

frontend/
├── main_window.py         (主窗口，~430 行)
└── widgets/
    ├── canvas.py          (核心画布，~520 行)
    ├── image_view.py      (图像查看器，~170 行)
    ├── project_dock.py    (项目管理面板，~230 行)
    ├── label_dock.py      (标注列表面板，~200 行)
    ├── property_dock.py   (属性编辑面板，~200 行)
    └── class_dialog.py    (类别管理对话框，~270 行)

main.py                     (入口文件，~50 行)
```

---

## ✅ 第二阶段：AI 辅助标注（已完成）

### 目标
集成轻量目标检测模型，实现自动标注和置信度过滤。

### 已完成功能
- [x] 集成 YOLOv8/v11 推理（通过 Ultralytics）
- [x] 自动标注当前图片（模型预测 → 蓝色虚线框 → Enter 接受）
- [x] 批量自动标注所有未标注图片
- [x] 置信度阈值过滤（滑块调节 0.05~0.95）
- [x] 一键接受/拒绝预测结果（全部或单个）
- [x] BasePredictor 统一模型接口
- [x] InferenceManager 推理管理器
- [x] ModelDock 模型管理面板
- [x] 预测框与标注框视觉区分（蓝色虚线 vs 实线）

### 已完成模块
- `backend/inference/` — 推理模块
- `backend/inference/base.py` — BasePredictor 抽象基类
- `backend/inference/yolo_predictor.py` — YOLO 预测器实现
- `backend/inference/manager.py` — 推理管理器
- `frontend/widgets/model_dock.py` — 模型面板

---

## ✅ 附加功能（第二阶段后追加）

### 多选 + 批量改标签 (Ctrl+Click)
- [x] AnnotationManager 多选支持（`_selection` 列表，`toggle_select()`）
- [x] Canvas Ctrl+点击切换选中
- [x] 多选框全部高亮显示
- [x] 右键「修改类别」批量应用到所有选中标注
- [x] LabelDock 多选高亮
- [x] 属性面板 signal 阻塞修复（防止恢复 combo 时自动改标签）
- [x] 选择模式下空白区域平移（取代选区框）
- [x] W 键在 DRAW/SELECT 之间切换

### 已知问题 / 待修复
- [ ] 预测框的手柄不能拖拽调整大小（只有标注框可以）
- [ ] 模型类别和项目类别的自动映射偶有 ID 不一致
- [ ] Canvas 绘制大量标注时可能卡顿（后续可切 QGraphicsView）

---

## 🚧 第三阶段：训练闭环

### 目标
实现从标注到训练的完整闭环，支持增量训练。

### 待开发功能
- [ ] 从已标注数据生成训练集
- [ ] 一键启动训练
- [ ] 训练进度监控
- [ ] 训练完成后自动加载最新模型
- [ ] 增量训练（持续迭代）
- [ ] TrainDock 训练面板

### 涉及模块
- `backend/training/` — 训练模块
- `backend/training/trainer.py` — 训练器
- `backend/training/dataset_builder.py` — 数据集构建
- `backend/training/exporter.py` — 模型导出
- `frontend/widgets/train_dock.py` — 训练面板

---

## 🚧 第四阶段：高级功能

### 目标
引入主动学习、SAM 分割、插件系统等高级功能。

### 已完成功能
- [x] 多边形标注（Polygon）—— 点击绘制、顶点编辑、插入/删除顶点
- [x] 实例分割标注—— YOLO 分割模型自动提取多边形
- [x] YOLO 分割格式导入/导出—— 自动识别检测/分割格式

### 待开发功能
- [ ] Active Learning（不确定性采样）
- [ ] SAM 辅助分割（自动/交互式）
- [ ] 旋转框标注
- [ ] 多模型管理与版本控制
- [ ] 插件系统
- [ ] 多语言界面

---

## 技术债务与改进

- [ ] Canvas 渲染性能优化（QGraphicsView 替代 QWidget 绘制）
- [ ] 大图片缩略图/金字塔加载
- [ ] 批量操作（批量删除、批量修改类别）
- [ ] 撤销/重做合并（连续移动合并为一个操作）
- [ ] 自动保存定时器
- [ ] 更完善的异常处理
- [ ] 单元测试
- [ ] 国际化 (i18n)

## 性能目标

| 场景 | 目标 |
|------|------|
| 单图片加载 | < 200ms（4K 以下） |
| 标注切换 | 实时（< 16ms） |
| 缩放/平移 | 60fps |
| 内存占用 | < 500MB |
| 支持图片格式 | JPG/PNG/BMP/TIFF/WEBP |
