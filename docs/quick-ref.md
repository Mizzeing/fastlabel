# FastLabel 快速参考

## 启动
```bash
cd /home/quxin/A_Project/A_项目/fastlabel
QT_QPA_PLATFORM=xcb python main.py
# 或直接 python main.py（如果 wayland 没问题）
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

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 主程序入口 | `main.py` |
| 主窗口 | `frontend/main_window.py` |
| 画布 | `frontend/widgets/canvas.py` |
| 项目面板 | `frontend/widgets/project_dock.py` |
| 模型面板 | `frontend/widgets/model_dock.py` |
| 类别映射对话框 | `frontend/widgets/class_mapping_dialog.py` |
| 项目管理 | `backend/project/` |
| 数据集管理 | `backend/dataset/` |
| 推理模块 | `backend/inference/` |
| 项目数据 | `projects/<项目名>/` |
| LED 数据 | `/home/quxin/A_Project/A_项目/施浪/LED缺陷/project/` |

## 最新改动
- 导入图片自动前缀去重（0522D11_Image--01.jpg）
- 导入 YOLO 标签（文件菜单）
- 图片来源追溯（source_path 字段）
- 记住上次导入目录
- 左右面板统一为上下布局
- 类别映射（模型索引→项目类别）
- W 键 toggle 修复
- 右键删除图片
