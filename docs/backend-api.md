# Backend API 文档

## `backend.annotation.shape` — Shape 基类

### Shape
所有标注对象的抽象基类。

**属性:**
| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| class_id | int | 0 | 类别 ID |
| label | str | "" | 类别名称 |
| score | float | 1.0 | 置信度分数 |
| visible | bool | True | 是否可见 |
| locked | bool | False | 是否锁定 |
| selected | bool | False | 是否选中 |
| annotation_id | str | uuid8位 | 唯一标识 |

**方法:**
| 方法 | 说明 |
|------|------|
| `to_dict()` | 序列化为字典 |
| `copy()` | 深拷贝 |
| `scale(sx, sy)` | 缩放坐标 |
| `get_short_repr()` | 获取简短描述 |

---

## `backend.annotation.bbox` — BBox 矩形框

### BBox(Shape)
矩形框标注，使用归一化坐标。

**属性（额外）:**
| 属性 | 类型 | 说明 |
|------|------|------|
| x | float | 左上角 X (归一化) |
| y | float | 左上角 Y (归一化) |
| w | float | 宽度 (归一化) |
| h | float | 高度 (归一化) |

**方法:**
| 方法 | 说明 |
|------|------|
| `get_center()` | 获取中心坐标 |
| `contains_point(px, py)` | 判断点是否在框内 |
| `iou(other)` | 计算与另一个 BBox 的 IoU |
| `area()` | 计算面积 |
| `from_dict(data)` | 从字典创建 BBox (类方法) |

---

## `backend.annotation.command` — Command 模式

### Command (ABC)
命令基类。

| 方法 | 说明 |
|------|------|
| `execute()` | 执行命令 |
| `undo()` | 撤销命令 |

### AddCommand(Command)
添加标注命令。

| 参数 | 类型 | 说明 |
|------|------|------|
| annotations | list | 标注列表引用 |
| shape | Shape | 要添加的标注 |

### DeleteCommand(Command)
删除标注命令。

### MoveCommand(Command)
移动标注命令。

| 参数 | 类型 | 说明 |
|------|------|------|
| shape | Shape | 要移动的标注 |
| dx | float | X 方向偏移 |
| dy | float | Y 方向偏移 |

### ResizeCommand(Command)
调整大小命令（存储旧位置和新位置）。

### ChangeClassCommand(Command)
修改类别命令（存储旧类别和新类别）。

### CommandManager
命令管理器。

| 方法 | 说明 |
|------|------|
| `execute(command)` | 执行命令 |
| `undo()` | 撤销，返回是否成功 |
| `redo()` | 重做，返回是否成功 |
| `can_undo()` | 是否可以撤销 |
| `can_redo()` | 是否可以重做 |
| `clear()` | 清空所有历史 |

---

## `backend.annotation.manager` — AnnotationManager

### AnnotationManager
标注管理器，集成 CommandManager，支持多选。

**属性:**
| 属性 | 说明 |
|------|------|
| annotations | 当前图片的标注列表 |
| selected | 主选中项（多选时返回最后点击的） |
| selected_shapes | 所有选中的标注列表 |
| selection_count | 选中数量 |
| predictions | 模型预测结果列表 |

**方法:**
| 方法 | 说明 |
|------|------|
| `add(shape)` | 添加标注（含 Undo） |
| `delete(shape=None)` | 删除标注（含 Undo） |
| `delete_selected()` | 删除所有选中的标注 |
| `move(shape, dx, dy)` | 移动标注（含 Undo） |
| `resize(shape, ...)` | 调整大小（含 Undo） |
| `change_class(shape, id, label)` | 修改单个类别（含 Undo） |
| `change_class_selected(id, label)` | 批量修改所有选中标注类别 |
| `select(shape)` | 单选（清除之前选中） |
| `toggle_select(shape)` | 切换选中（Ctrl+点击时用） |
| `select_at(px, py, toggle=False)` | 选中指定坐标处的标注 |
| `clear_selection()` | 取消选中 |
| `undo()` / `redo()` | 撤销/重做 |
| `clear()` | 清空所有标注和历史 |
| `set_annotations(list)` | 直接设置标注列表 |
| `set_predictions(list)` | 设置预测结果 |
| `accept_prediction(shape)` | 接受单个预测 |
| `reject_prediction(shape)` | 拒绝单个预测 |
| `accept_all_predictions(min_score)` | 全部接受 |
| `reject_all_predictions(min_score)` | 全部拒绝 |

---

## `backend.project.project` — Project

### Project
项目类，管理 SQLite 数据库和目录结构。

**构造参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| project_path | Path | 项目目录路径 |

**方法:**
| 方法 | 说明 |
|------|------|
| `get_classes()` | 获取所有类别 |
| `sync_classes_from_config()` | 从 YAML 同步类别到数据库 |
| `add_image(path, filename, w, h, file_size)` | 添加图片，返回 image_id |
| `get_image(image_id)` | 获取图片信息 |
| `get_all_images()` | 获取所有图片 |
| `get_image_count()` | 获取图片总数 |
| `get_annotated_count()` | 获取已标注图片数 |
| `get_annotations(image_id)` | 获取图片的所有标注 |
| `save_all_annotations(image_id, list)` | 批量保存标注 |
| `save_annotation(...)` | 保存单个标注 |
| `delete_annotation(annotation_id)` | 删除标注 |
| `get_stats()` | 获取统计信息 |
| `close()` | 关闭数据库连接 |

---

## `backend.dataset.manager` — DatasetManager

### DatasetManager
数据集管理器。

**方法:**
| 方法 | 说明 |
|------|------|
| `set_project(project)` | 设置当前项目 |
| `refresh()` | 刷新图片列表 |
| `import_images(file_paths)` | 导入图片到项目 |
| `load_annotations(image_id)` | 加载标注为 Shape 列表 |
| `save_annotations(image_id, shapes)` | 保存标注到数据库 |
| `get_image(index)` | 获取指定索引的图片 |
| `goto_prev()` | 上一张，返回 bool |
| `goto_next()` | 下一张，返回 bool |
| `export_yolo()` | 导出 YOLO 格式 |

---

## `backend.export.yolo` — YOLOExporter

### YOLOExporter
YOLO 格式导出器。

| 方法 | 说明 |
|------|------|
| `export_all()` | 导出所有标注 + data.yaml |
| `export_image(image_id)` | 导出单张图片的标注 |
| `annotations_to_yolo(list)` | 静态方法，将标注列表转为 YOLO 字符串 |

---

## `backend.inference` — 推理模块

### BasePredictor (ABC)
预测器抽象基类，所有模型预测器实现统一接口。

| 方法 | 说明 |
|------|------|
| `load(model_path)` | 加载模型权重 |
| `predict(image, conf_threshold)` | 预测单张图片，返回 List[PredictionResult] |
| `unload()` | 卸载模型，释放显存 |
| `is_loaded()` | 模型是否已加载 |
| `name` | 模型名称（属性） |
| `model_type` | 模型类型（属性） |

### PredictionResult
预测结果数据结构。

| 属性 | 类型 | 说明 |
|------|------|------|
| class_id | int | 类别 ID |
| label | str | 类别名称 |
| x, y | float | 归一化左上角坐标 |
| w, h | float | 归一化宽高 |
| score | float | 置信度 |

### InferenceManager
推理管理器。

| 方法 | 说明 |
|------|------|
| `load_model(path, type='yolo')` | 加载模型 |
| `unload_model()` | 卸载模型 |
| `predict(image, conf_threshold)` | 预测 |
| `predict_and_filter(image)` | 预测+过滤 |
| `conf_threshold` | 置信度阈值（属性） |
| `is_loaded` | 模型是否已加载（属性） |
