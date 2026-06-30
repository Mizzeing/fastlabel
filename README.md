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

### 第一阶段 (MVP) ✅ 已完成

| 功能 | 描述 |
|------|------|
| 项目管理 | 新建/打开/关闭/删除项目，自动持久化 |
| 图片导入 | 支持 JPG/PNG/BMP/TIFF/WEBP 格式 |
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

### 后续阶段规划

- **第三阶段**: 训练闭环（一键训练、增量训练）
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
2. **导入图片**: 点击「导入」或 `Ctrl+I`
3. **开始标注**: 按 `W` 进入绘制模式，拖拽画框
4. **切换类别**: 选择标注列表下方的类别下拉框
5. **导出**: 点击菜单 `文件 → 导出 YOLO` 或 `Ctrl+E`
6. **AI 辅助标注**:
   - 下载 YOLO 模型（如 `yolov8n.pt`）放到 `models/` 目录
   - 底部模型面板点击「选择模型 → 加载模型」
   - 点击「🎯 自动标注当前图片」
   - 蓝色虚线框为预测结果，`Enter` 接受，`Del` 拒绝

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
│   ├── export/                 # 导出模块
│   │   └── yolo.py             # YOLO 格式导出
│   │
│   └── utils/
│       └── misc.py             # 工具函数和常量
│
├── frontend/                   # 前端 PyQt5 图形界面
│   ├── main_window.py          # 主窗口 (组装所有组件)
│   └── widgets/
│       ├── canvas.py           # 核心画布组件 (+ 预测框绘制)
│       ├── image_view.py       # 图像查看器 (含工具条)
│       ├── project_dock.py     # 项目管理面板
│       ├── label_dock.py       # 标注列表面板
│       ├── property_dock.py    # 属性编辑面板
│       ├── class_dialog.py     # 类别管理对话框
│       └── model_dock.py       # 🆕 模型管理面板
│
├── projects/                   # 项目数据存放目录
├── models/                     # 模型存放目录
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
| `W` | 切换绘制/选择模式 |
| `S` | 回到选择模式 |
| `H` | 平移模式 |
| `A` / `D` | 上一张 / 下一张 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Shift+Z` | 重做 |
| `Delete` / `Backspace` | 删除选中标注/拒绝预测 |
| `Enter` | 接受选中预测结果 |
| `Escape` | 取消绘制 / 取消选中 |
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
├── models/           # 模型文件 (规划)
├── cache/            # 缓存
├── exports/          # 导出文件
├── config.yaml       # 项目配置
└── project.db        # SQLite 数据库
```

### YOLO 标签格式

每张图片对应一个 `.txt` 文件：

```
<class_id> <cx> <cy> <width> <height> <score>
```

所有值归一化到 [0, 1]。

---

## License

MIT
