# FastLabel 快速参考

## 启动
```bash
cd /home/quxin/Projects/fastlabel
python main.py
```

## 使用流程

### 用 FastLabel 标注新数据
1. **新建项目** → 添加类别
2. **导入图片**（Ctrl+I）→ 自动去重命名
3. **标注**：W 键切换绘制模式，拖拽画框
4. **导出**（Ctrl+E）→ YOLO 格式

### 用已有标注数据（LED 缺陷）
1. **新建项目** → 添加 MLED / Corrosion / Fracture 三个类别
2. **导入图片** → 选 `Datasets/0522D11/*.jpg` + `Datasets/0522D12/*.jpg`
3. **文件 → 导入 YOLO 标签** → 选 `labels/raw_train/` 或 `labels/raw_val/`

### AI 自动标注
1. **加载模型** → 点击模型面板 📂 选 .pt 文件
2. **类别映射** → 配置模型输出索引对应的项目类别
3. **自动标注** → 单张或批量
4. **Enter 接受 / Del 拒绝**

### 训练模型
1. **标注图片** → 至少 1 张
2. **训练参数** → 左侧下方「🏋️ 训练管理」面板配置
3. **开始训练** → 后台线程执行，实时看进度
4. **完成** → 模型存入 `projects/<项目名>/models/best.pt`
5. **增量训练** → 勾选增量训练，选已有检查点继续

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 主程序入口 | `main.py` |
| 主窗口 | `frontend/main_window.py` |
| 画布 | `frontend/widgets/canvas.py` |
| 项目面板 | `frontend/widgets/project_dock.py` |
| 模型面板 | `frontend/widgets/model_dock.py` |
| 训练面板 | `frontend/widgets/train_dock.py` |
| 类别映射对话框 | `frontend/widgets/class_mapping_dialog.py` |
| 项目管理 | `backend/project/` |
| 数据集管理 | `backend/dataset/` |
| 推理模块 | `backend/inference/` |
| 训练模块 | `backend/train/` |
| 项目数据 | `projects/<项目名>/` |
| 预训练模型 | `mostpt/` |
| LED 数据 | `/home/quxin/A_Project/A_项目/施浪/LED缺陷/project/` |

## 最新改动
- 文件对话框恢复系统默认样式（palette 系统色）
- 文件对话框默认到项目目录并记住上次浏览位置
- 训练闭环（一键训练 + 增量训练）
- TrainDock 训练管理面板（预设方案、实时进度、日志）
- 训练数据导出（5 列 YOLO 格式，类别 ID 自动 0-index）
- CPU/GPU 自动检测，CPU 模式禁用 AMP 降低 workers
- 模型本地路径搜索（mostpt/ 目录优先）
- 训练完成自动加载模型 + 自动类别映射
- 导入图片自动前缀去重（0522D11_Image--01.jpg）
- 导入 YOLO 标签（文件菜单）
- 图片来源追溯（source_path 字段）
- 记住上次导入目录
- 左右面板统一为上下布局
- 类别映射（模型索引→项目类别）
- W 键 toggle 修复
- 右键删除图片

### 最新改动
- 修复新建项目崩溃：`_create_tables()` 补全 `classes` 和 `annotations` 表创建
- 多边形标注（Polygon）：逐点绘制、顶点编辑、插入/删除顶点
- YOLO 分割模型推理支持（自动提取 mask 多边形点）
- 新快捷键：P 切换多边形绘制模式
- 工具栏新增多边形按钮
- YOLO 导入/导出自动识别分割格式

### 本次更新
- **训练模型自动过滤**：项目有 polygon 标注时只显示分割模型（`-seg`），纯 bbox 显示全部
- **分割模型训练导出**：支持 YOLO seg 格式（6+列含多边形坐标），纯 bbox 自动生成 4 点
- **模型缓存到 mostpt/**：从 Hub 下载的模型自动缓存到 `mostpt/` 目录，跨项目复用
- **Ctrl+D 删除**：新增 `Ctrl+D` 快捷键删除选中标注
- **框/多边形拖拽修复**：修复坐标归一化 bug，现在可以正常拖拽移动了
