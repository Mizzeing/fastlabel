# FastLabel - AI 辅助标注平台

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

**FastLabel** 是一个轻量级 AI 辅助图像标注平台，围绕「人工标注 → 模型训练 → 自动标注 → 人工修正」闭环设计。从简单的 BBox 标注起步，后续可接入 YOLO、SAM 等模型实现自动标注和主动学习。

---

## 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [架构设计](#架构设计)
- [核心模块](#核心模块)
- [开发指南](#开发指南)
- [快捷键](#快捷键)

---

## 功能概览

### 已完成

| 功能 | 描述 |
|------|------|
| 项目管理 | 新建/打开/关闭/删除项目，自动持久化 |
| 图片导入 | 支持 JPG/PNG/BMP/TIFF/WEBP 格式，自动去重，记录来源路径 |
| BBox 标注 | 绘制、选择、移动、调整大小 |
| 多选 | Ctrl+点击多选，批量操作 |
| 批量改标签 | 多选后右键一次修改所有选中标注的类别 |
| 类别管理 | 添加/编辑/删除类别，颜色和快捷键配置 |
| YOLO 导出 | 导出 YOLO 格式标注 + data.yaml |
| Undo/Redo | 完整的撤销/重做支持 |
| YOLO 集成 | 加载 YOLO 模型进行自动标注（.pt 文件） |
| 置信度阈值 | 滑块调节，实时过滤低分预测 |
| 自动标注 | 单张/批量自动标注 |
| 接受/拒绝 | Enter 接受 / Del 拒绝预测结果 |
| 模型路径持久化 | 加载的模型路径自动保存到项目配置 |
| 类别映射 | 配置模型输出索引到项目类别的映射，避免标错类 |
| 导入 YOLO 标签 | 从已有的 YOLO txt 标注目录导入标注到项目 |
| 图片去重导入 | 同名图片自动加源目录前缀，防止覆盖 |
| 图片来源追溯 | 记录每张图片的原始导入路径 |
| 记住导入目录 | 下次导入自动从上次目录打开 |
| 图片删除 | 右键图片列表删除图片及关联标注 |
| 统一管理面板 | 项目管理和模型管理上下合一，无需切换标签页 |
| **一键训练** | 导出标注 → 自动分割训练/验证集 → 启动 YOLO 训练 |
| **增量训练** | 从已有检查点继续训练，快速迭代 |
| **训练参数配置** | 预设方案（快速/标准/精度）、架构、轮数、批次、尺寸、设备 |
| **实时进度** | Epoch 进度条、Loss、mAP50、mAP50-95、学习率、时间 |
| **训练日志** | 实时文本日志输出 |
| **自动类别映射** | 新模型自动匹配项目类别顺序 |
| **训练历史** | 记录最近 20 次训练到 config.yaml |
| **可折叠管理面板** | 项目/模型/训练三区可独立折叠收纳，节省左侧空间 |
| **样式分离** | 前端样式从 Python 代码迁移到独立 `.qss` 文件，易于维护 |

### 后续阶段规划

- **第四阶段**: Active Learning、SAM 分割、插件系统

---

## 快速开始

### 环境要求

- Python 3.9+
- pip / conda

### 安装

```bash
# 克隆仓库
git clone <your-repo-url>
cd fastlabel

# 创建 conda 环境
conda create -n fastlabel python=3.9
conda activate fastlabel

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 快速上手

1. **新建项目**: 点击左侧「新建」或 `Ctrl+N`
2. **导入图片**: 点击「导入」或 `Ctrl+I`（自动记住上次导入目录）
3. **开始标注**: 按 `W` 进入绘制模式，拖拽画框；再按 `W` 退出
4. **切换类别**: 选择标注列表下方的类别下拉框
5. **导出**: 点击菜单 `文件 → 导出 YOLO` 或 `Ctrl+E`

**AI 辅助标注**:
1. 加载 YOLO 模型（支持 `.pt` / `.engine` / `.onnx`）
2. 点击 **「📋 类别映射」** 配置模型输出索引对应的项目类别
3. 点击 **「🎯 自动标注当前图片」** — 蓝色虚线框为预测结果
4. `Enter` 接受 / `Del` 拒绝

**模型训练**:
1. 标注至少 1 张图片后，在左侧面板下方 **「🏋️ 训练管理」** 配置参数
2. 选择预设方案（快速/标准/精度优先）或自定义
3. 点击 **「🚀 开始训练」**，训练在后台线程执行，UI 不卡顿
4. 实时监控 Epoch 进度、Loss、mAP 指标
5. 训练完成后模型自动保存到 `projects/<项目名>/models/best.pt`
6. 勾选 **「训练完成后自动加载模型」** 可直接用新模型推理
7. 支持 **增量训练**：勾选后选择已有 `.pt` 文件继续训练

**导入已有标注**:
- `文件 → 导入 YOLO 标签` — 从已有的 YOLO txt 标注目录导入

---

## 项目结构

```
fastlabel/
│
├── main.py                     # 入口文件
├── requirements.txt            # 依赖
├── README.md                   # 本文件
│
├── backend/                    # 后端核心逻辑
│   ├── annotation/             # 标注模块
│   │   ├── shape.py            # Shape 基类
│   │   ├── bbox.py             # BBox 矩形框
│   │   ├── command.py          # Command 模式 (Undo/Redo)
│   │   └── manager.py          # 标注管理器
│   │
│   ├── project/                # 项目管理
│   │   ├── project.py          # 项目模型 + SQLite 数据库
│   │   ├── config.py           # YAML 配置管理
│   │   └── manager.py          # 项目管理器
│   │
│   ├── dataset/                # 数据集管理
│   │   ├── image_loader.py     # 图片加载/缓存
│   │   ├── label_loader.py     # YOLO 标签读写
│   │   └── manager.py          # 数据集管理器
│   │
│   ├── inference/              # 🆕 推理模块 (第二阶段)
│   │   ├── base.py             # BasePredictor 抽象基类
│   │   ├── yolo_predictor.py   # YOLO 预测器实现
│   │   └── manager.py          # 推理管理器
    │   │
    ├── train/                  # 🆕 训练模块 (第三阶段)
    │   ├── __init__.py         # 入口
    │   ├── config.py           # TrainingConfig 训练超参数
    │   └── trainer.py          # YOLOTrainer 训练核心
│   │
│   ├── export/                 # 导出模块
│   │   └── yolo.py             # YOLO 格式导出
│   │
│   └── utils/
│       └── misc.py             # 工具函数和常量
│
├── frontend/                   # 前端 PyQt5 图形界面
│   ├── main_window.py          # 主窗口 (组装所有组件)
│   ├── styles/                 # 独立样式文件 (.qss)
│   │   ├── __init__.py         # load_styles() 加载器
│   │   ├── base.qss            # 全局基础：背景、菜单栏、状态栏
│   │   ├── components.qss      # 通用控件：按钮、下拉框、滑块等
│   │   ├── dialogs.qss         # 对话框：消息框、文件对话框
│   │   ├── docks.qss           # 面板：项目管理、模型、训练等
│   │   └── canvas.qss          # 画布工具栏
│   └── widgets/
│       ├── canvas.py           # 核心画布组件 (+ 预测框绘制)
│       ├── image_view.py       # 图像查看器 (含工具条)
│       ├── collapsible_section.py  # 可折叠收纳面板组件
│       ├── project_dock.py     # 项目管理面板（统一左侧）
│       ├── label_dock.py       # 标注列表面板
│       ├── property_dock.py    # 属性编辑面板
│       ├── class_dialog.py     # 类别管理对话框
│       ├── class_mapping_dialog.py  # 模型类别映射对话框
│       ├── model_dock.py       # 模型管理面板
│       └── train_dock.py       # 训练管理面板
│
├── projects/                   # 项目数据存放目录
├── models/                     # 模型存放目录
│   └── mostpt/                 # 常用预训练模型
└── docs/                       # 文档
```

---

## 架构设计

### 设计理念

FastLabel 按照 **AI 辅助标注平台** 而非简单画框工具来设计，核心是「人在回路」(Human-in-the-loop) 闭环：

```
导入图片
    │
    ▼
人工标注少量样本
    │
    ▼
一键训练轻量模型  ←────┐
    │                  │
    ▼                  │
模型自动标注剩余图片    │
    │                  │
    ▼                  │
人工快速修正预测结果    │
    │                  │
    ▼                  │
加入训练集继续训练 ─────┘
    │
    ▼
模型越来越准确
```

### 三层架构

```
┌─────────────────────────────────┐
│         Frontend (PyQt5)        │  ← MainWindow, Canvas, DockWidgets
├─────────────────────────────────┤
│        Backend 核心逻辑          │  ← Annotation, Project, Dataset
├─────────────────────────────────┤
│         Data Layer (SQLite)     │  ← project.db, config.yaml, labels/
└─────────────────────────────────┘
```

### 类层次设计

所有标注对象继承自 `Shape` 基类：

```
Shape (ABC)
  ├── BBox              矩形框 (当前实现)
  ├── Polygon           多边形 (规划)
  ├── BrushMask         画笔蒙版 (规划)
  ├── KeyPoint          关键点 (规划)
  └── RotatedBox        旋转框 (规划)
```

---

## 核心模块

### Backend 模块

#### `backend.annotation.shape` — Shape 基类
所有标注对象的抽象基类，定义了 `to_dict()`、`copy()`、`scale()` 等接口。

#### `backend.annotation.bbox` — BBox 矩形框
归一化坐标的矩形框标注，支持 IoU 计算、点包含检测。

#### `backend.annotation.command` — Command 模式
实现完整的 Undo/Redo 机制：
- `AddCommand` / `DeleteCommand` / `MoveCommand` / `ResizeCommand` / `ChangeClassCommand`
- `CommandManager` 管理命令栈（上限 100 步）

#### `backend.annotation.manager` — AnnotationManager
管理标注列表、选中状态，集成 CommandManager 提供 Undo/Redo。

#### `backend.project.project` — Project
SQLite 数据库持久化，管理四张表：`images`、`classes`、`annotations`。

#### `backend.project.config` — ProjectConfig
YAML 配置文件管理，支持类别、显示、导出等配置。

#### `backend.dataset.manager` — DatasetManager
协调 Project、ImageLoader、LabelLoader 之间的关系，提供统一的数据访问接口。

#### `backend.export.yolo` — YOLOExporter
导出 YOLO 格式（class_id cx cy w h score）+ data.yaml。

### Frontend 模块

#### `frontend.widgets.canvas` — Canvas 核心画布
- 图像渲染、缩放、平移
- 三种交互模式：选择、绘制、平移
- BBox 绘制、选择、拖拽移动、手柄调整大小
- 缩放手柄（9 个控制点）
- 右键上下文菜单
- 选区框选（拖拽选中）

#### `frontend.widgets.image_view` — ImageView
封装 Canvas，提供顶部的模式工具栏和缩放控件。

#### `frontend.widgets.project_dock` — ProjectDock
左侧面板，显示项目树和当前项目的图片列表。

#### `frontend.widgets.label_dock` — LabelDock
右侧面板，显示当前图片的所有标注列表，支持右键修改类别。

#### `frontend.widgets.property_dock` — PropertyDock
选中标注的属性编辑器，支持精确修改位置和类别。

#### `frontend.widgets.class_dialog` — ClassDialog
类别管理对话框，添加/编辑/删除类别，支持颜色选择和快捷键绑定。

---

## 开发指南

### 添加新标注类型

继承 `Shape` 基类：

```python
from backend.annotation.shape import Shape

class Polygon(Shape):
    points: List[tuple] = []  # 归一化坐标列表

    def to_dict(self) -> dict:
        return {'points': self.points, ...}

    def copy(self) -> 'Polygon':
        return Polygon(points=self.points.copy(), ...)

    def contains_point(self, px, py) -> bool:
        # 点包含检测
        ...
```

然后在 Canvas 中添加对应的绘制逻辑。

### 集成新模型

实现统一预测接口：

```python
class MyModel:
    def predict(self, image: np.ndarray) -> list:
        # 返回 [{'bbox': [x,y,w,h], 'class_id': int, 'score': float}, ...]
        pass
```

### 自定义快捷键

在 `backend/utils/misc.py` 中修改 `DEFAULT_SHORTCUTS`。

---

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `W` | 切换绘制↔选择模式（再按退出绘制） |
| `S` | 回到选择模式 |
| `H` | 平移模式 |
| `A` / `D` | 上一张 / 下一张 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Shift+Z` | 重做 |
| `Delete` / `Backspace` | 删除选中标注/拒绝预测 |
| `Enter` | 接受选中预测结果 |
| `Escape` | 取消绘制 / 取消选中 |
| `Ctrl+T` | 聚焦训练面板 |
| `Ctrl+N` | 新建项目 |
| `Ctrl+O` | 打开项目 |
| `Ctrl+I` | 导入图片 |
| `Ctrl+E` | 导出 YOLO |
| `Ctrl+=` / `Ctrl+-` | 放大 / 缩小 |
| `双击` | 适应窗口 |
| `滑轮` | 缩放 |
| `Ctrl+点击` | 多选/切换选中 |
| `右键 → 修改类别` | 单个/批量改标签 |

---

## 项目数据格式

### 目录结构

```
projects/<项目名>/
├── images/           # 图片文件
├── labels/           # YOLO 标注 (导出时生成)
├── masks/            # 分割蒙版 (规划)
├── models/           # 模型文件（训练输出 + 预训练权重）
├── cache/            # 缓存
├── exports/          # 导出文件
├── config.yaml       # 项目配置
└── project.db        # SQLite 数据库
```

### 图片导入

- 同名图片自动加 **源目录前缀** 存储（如 `0522D11_Image--01.jpg`）
- 数据库记录 `source_path` 字段，追溯每张图片的原始来源路径
- 导入对话框自动记住上次使用的目录

### YOLO 标签格式

每张图片对应一个 `.txt` 文件：

```
<class_id> <cx> <cy> <width> <height> <score>
```

所有值归一化到 [0, 1]。

---

## License

MIT
