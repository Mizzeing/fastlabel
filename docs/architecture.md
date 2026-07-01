# FastLabel 架构文档

## 整体架构

FastLabel 采用前后端分离的三层架构：

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (PyQt5)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ MainWindow│ │  Canvas  │ │ DockWidget│ │  Dialogs  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │            │            │              │        │
├───────┴────────────┴────────────┴──────────────┴────────┤
│                    Backend 核心逻辑                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Annotation│ │ Project  │ │ Dataset  │ │  Export   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │            │            │              │        │
├───────┴────────────┴────────────┴──────────────┴────────┤
│                   Data Layer                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ SQLite   │ │ YAML cfg │ │  Label   │                │
│  │ project.db│ │config.yaml│ │*.txt文件 │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────┘
```

## 设计原则

### 1. 面向接口编程
所有标注对象继承 `Shape` 基类，新增类型只需实现基类接口。
所有模型通过统一 `Predict()` 接口调用，UI 不关心具体模型。

### 2. Command 模式
用 Command 模式封装所有标注操作：
```
AddCommand / DeleteCommand / MoveCommand / ResizeCommand
    ↓
CommandManager (栈管理，上限 100 步)
    ↓
undo() / redo()
```

### 3. 归一化坐标
所有标注坐标归一化到 [0, 1] 范围，独立于图像尺寸。
- 归一化 ↔ 图像坐标：通过 `image_size` 转换
- 图像坐标 ↔ 画布坐标：通过 `scale` 和 `offset` 转换

### 4. 信号-槽解耦
前端组件之间通过 PyQt5 信号-槽机制解耦：
```
Canvas.annotation_added → MainWindow → AnnotationManager
LabelDock.annotation_selected → MainWindow → Canvas.update()
```

## 数据流

### 标注流程
```
用户拖动画框
    ↓
Canvas._finish_draw()
    ↓
signal: annotation_added(bbox)
    ↓
MainWindow._on_annotation_added()
    ↓
AnnotationManager.add(bbox)  ← 自动执行 AddCommand
    ↓
更新 Canvas + LabelDock 显示
    ↓
切换图片时 → Project.save_all_annotations() → SQLite
```

### 图片导航流程
```
用户按 A/D 或双击图片列表
    ↓
MainWindow._on_prev_image() / _on_next_image()
    ↓
_save_current_annotations()  →  SQLite 持久化
    ↓
_load_image(new_image_id)
    ↓
DatasetManager.image_loader().load_image()  →  图像数据
DatasetManager.load_annotations()  →  Shape 列表
    ↓
AnnotationManager.set_annotations()  →  更新内存
    ↓
Canvas + LabelDock + PropertyDock 同步更新
```

## 坐标系统

共有三套坐标系统：

| 坐标系 | 范围 | 用途 |
|--------|------|------|
| 归一化坐标 | [0, 1] × [0, 1] | 数据库存储、YOLO 格式 |
| 图像坐标 | [0, W] × [0, H] | 图像处理、命中检测 |
| 画布坐标 | 窗口像素 | 绘制、鼠标交互 |

转换路径：
```
归一化坐标 <──> 图像坐标 <──> 画布坐标
      ×W,×H         ×scale+offset
```

## 模块依赖关系

```
main.py
  └── MainWindow
        ├── ProjectDock ──→ ProjectManager ──→ Project ──→ SQLite
        ├── ImageView
        │     └── Canvas ──→ AnnotationManager ──→ Shape/BBox
        ├── LabelDock ──→ AnnotationManager
        ├── PropertyDock ──→ AnnotationManager
        ├── ClassDialog ──→ Project.config
        ├── DatasetManager
        │     ├── ImageLoader
        │     └── LabelLoader
        └── TrainDock ──→ YOLOTrainer ──→ Project (export dataset)
                            └── ultralytics YOLO (training engine)
```

## 命令模式详解

```
CommandManager (命令栈)
│
├── _undo_stack: List[Command]   ← 可撤销的命令
├── _redo_stack: List[Command]   ← 可重做的命令
│
├── execute(cmd)  → 执行并压入 undo 栈，清空 redo 栈
├── undo()        → 弹出 undo 栈顶，执行 undo，压入 redo 栈
└── redo()        → 弹出 redo 栈顶，执行 execute，压入 undo 栈

每个 Command:
├── execute()     → 执行操作
└── undo()        → 撤销操作（反向操作）
```
