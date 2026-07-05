# FastLabel — AI-Assisted Image Annotation Platform

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![中文](https://img.shields.io/badge/语言-中文-red.svg)](README.zh.md)

**FastLabel** is a lightweight AI-assisted image annotation platform built around a human-in-the-loop workflow: **manual annotation → model training → auto-annotation → manual correction**. It integrates YOLO models for semi-automated labeling and on-device training, helping you bootstrap annotation projects quickly.

---

## Features

### ✅ Completed

| Feature | Description |
|---------|-------------|
| Project Management | Create / open / close / delete projects with auto-persistence |
| Image Import | Supports JPG/PNG/BMP/TIFF/WEBP; auto-deduplication; records source paths |
| BBox Annotation | Draw, select, move, resize bounding boxes |
| **Polygon Annotation** | Click-to-draw polygons; vertex editing (insert/delete/drag) |
| Multi-Select | Ctrl+Click for batch operations |
| Batch Label Editing | Right-click to change labels on multiple selected annotations at once |
| Class Management | Add / edit / delete classes with color picker and shortcut binding |
| YOLO Export | Export YOLO detection & segmentation format with `data.yaml` |
| Undo/Redo | Full Undo/Redo support via Command pattern |
| YOLO Integration | Load YOLO detection/segmentation models (`.pt`, `.engine`, `.onnx`) for auto-annotation |
| Confidence Threshold | Slider for real-time low-score prediction filtering |
| **IoU Threshold** | Slider to control NMS overlap for duplicate detection |
| Auto-Annotation | Single-image or batch auto-annotation |
| Accept / Reject | `Enter` to accept / `Del` to reject predictions |
| Model Path Persistence | Loaded model path auto-saved to project config |
| Class Mapping | Configure model output index → project class mapping to prevent mislabeling |
| Import YOLO Labels | Import existing YOLO `.txt` annotations from a directory |
| Image Dedup Import | Same-name images auto-prefixed with source directory name |
| Image Source Traceability | Each image records its original import path in the database |
| Remember Import Dir | Import dialog remembers the last-used directory |
| Image Deletion | Right-click to delete images and their associated annotations |
| Unified Management Panel | Project management, model management, and training in one panel — no tab switching |
| **One-Click Training** | Export annotations → auto-split train/val sets → launch YOLO training |
| **Training Model Filter** | Auto-restrict to segmentation models (`-seg`) when polygon annotations exist |
| **Segmentation Training** | Polygons exported directly; bbox-only labels get auto-generated 4-point rectangles |
| **Model Auto-Cache** | Models downloaded from Hub cached in `mostpt/` for cross-project reuse |
| **Resume Training** | Continue from an existing checkpoint for rapid iteration |
| **Training Config Presets** | Quick / Standard / Precision presets; configurable architecture, epochs, batch size, image size, device |
| **Real-Time Progress** | Epoch progress bar, Loss, mAP50, mAP50-95, learning rate, elapsed time |
| **Training Logs** | Real-time text log output during training |
| **Auto Class Mapping** | New models auto-matched to project class order |
| **Training History** | Last 20 training runs recorded in `config.yaml` |
| **Collapsible Panels** | Project / Model / Training sections independently collapsible |
| **Style Separation** | UI styles extracted to standalone `.qss` files for easy maintenance |

### 🚧 Future Phases

- Active Learning & Curriculum sampling
- SAM (Segment Anything Model) integration
- Rotated bounding boxes (OBB)
- Plugin system

---

## Quick Start

### Prerequisites

- Python 3.9+
- pip / conda

### Installation

```bash
# Clone the repository
git clone https://github.com/Mizzeing/fastlabel.git
cd fastlabel

# Create conda environment (recommended)
conda create -n fastlabel python=3.9
conda activate fastlabel

# Install dependencies
pip install -r requirements.txt
```

### Running

```bash
python main.py
```

### Quick Tutorial

1. **New Project**: Click "New" or press `Ctrl+N`
2. **Import Images**: Click "Import" or press `Ctrl+I` (remembers the last directory)
3. **Start Annotating**: Press `W` to enter BBox draw mode, drag to draw boxes
4. **Polygon Annotation**: Press `P` to enter polygon mode, click to place vertices, double-click or click the first vertex to close
5. **Switch Classes**: Select from the class dropdown below the annotation list
6. **Export**: `File → Export YOLO` or `Ctrl+E`

**AI-Assisted Annotation**:
1. Load a YOLO model (`.pt` / `.engine` / `.onnx`)
2. Click **"📋 Class Mapping"** to configure model output → project class mapping
3. Click **"🎯 Auto-Annotate Current Image"** — blue dashed boxes are predictions
4. `Enter` to accept / `Del` to reject
5. Segmentation models (e.g. `yolov8n-seg.pt`) automatically produce polygon predictions

**Model Training**:
1. After annotating at least 1 image, configure parameters in the **"🏋️ Training"** section
2. Choose a preset (Quick / Standard / Precision) or customize
3. Click **"🚀 Start Training"** — training runs in a background thread, UI stays responsive
4. Monitor epoch progress, Loss, mAP in real time
5. Trained model saved to `projects/<project-name>/models/best.pt`
6. Check **"Auto-load model after training"** to use the new model immediately
7. **Resume Training**: Check the box and select a checkpoint `.pt` file

**Import Existing Labels**:
- `File → Import YOLO Labels` — import from an existing YOLO `.txt` label directory

---

## Project Structure

```
fastlabel/
│
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
├── README.md                   # This file
│
├── backend/                    # Backend core logic
│   ├── annotation/             # Annotation module
│   │   ├── shape.py            # Shape base class (ABC)
│   │   ├── bbox.py             # BBox rectangle
│   │   ├── polygon.py          # Polygon (segmentation)
│   │   ├── command.py          # Command pattern (Undo/Redo)
│   │   └── manager.py          # Annotation manager
│   │
│   ├── project/                # Project management
│   │   ├── project.py          # Project model + SQLite database
│   │   ├── config.py           # YAML config management
│   │   └── manager.py          # Project manager
│   │
│   ├── dataset/                # Dataset management
│   │   ├── image_loader.py     # Image loading/caching
│   │   ├── label_loader.py     # YOLO label read/write
│   │   └── manager.py          # Dataset manager
│   │
│   ├── inference/              # Inference module
│   │   ├── base.py             # BasePredictor abstract class
│   │   ├── yolo_predictor.py   # YOLO predictor implementation
│   │   └── manager.py          # Inference manager
│   │
│   ├── train/                  # Training module
│   │   ├── __init__.py         # Entry point
│   │   ├── config.py           # TrainingConfig hyperparameters
│   │   └── trainer.py          # YOLOTrainer core
│   │
│   ├── export/                 # Export module
│   │   └── yolo.py             # YOLO format export
│   │
│   └── utils/
│       └── misc.py             # Utility functions and constants
│
├── frontend/                   # PyQt5 UI
│   ├── main_window.py          # Main window (assembles all components)
│   ├── styles/                 # Standalone style files (.qss)
│   │   ├── __init__.py         # load_styles() loader
│   │   ├── base.qss            # Global base: backgrounds, menus, status bar
│   │   ├── components.qss      # Common widgets: buttons, dropdowns, sliders
│   │   ├── dialogs.qss         # Dialogs: message boxes, file dialogs
│   │   ├── docks.qss           # Panels: project, model, training
│   │   └── canvas.qss          # Canvas toolbar
│   └── widgets/
│       ├── canvas.py           # Core canvas component (annotation drawing)
│       ├── image_view.py       # Image viewer (with toolbar)
│       ├── collapsible_section.py  # Collapsible panel component
│       ├── project_dock.py     # Project management panel
│       ├── label_dock.py       # Annotation list panel
│       ├── property_dock.py    # Property editor panel
│       ├── class_dialog.py     # Class management dialog
│       ├── class_mapping_dialog.py  # Model class mapping dialog
│       ├── model_dock.py       # Model management panel
│       └── train_dock.py       # Training management panel
│
├── mostpt/                     # Pretrained model cache directory
├── projects/                   # Project data (gitignored)
├── models/                     # Model storage (gitignored)
└── docs/                       # Documentation
    ├── architecture.md
    ├── backend-api.md
    ├── development-plan.md
    ├── frontend-guide.md
    └── quick-ref.md
```

---

## Architecture

### Design Philosophy

FastLabel is designed as an **AI-assisted annotation platform** rather than a simple drawing tool, centered on a **human-in-the-loop** workflow:

```
Import Images
    │
    ▼
Manual Annotation (small batch)
    │
    ▼
One-Click Training ←──────────┐
    │                          │
    ▼                          │
Auto-Annotate Remaining Images │
    │                          │
    ▼                          │
Quick Manual Correction        │
    │                          │
    ▼                          │
Add to Training Set, Retrain ──┘
    │
    ▼
Model Improves Over Time
```

### Three-Layer Architecture

```
┌─────────────────────────────────┐
│         Frontend (PyQt5)        │  ← MainWindow, Canvas, DockWidgets
├─────────────────────────────────┤
│         Backend (Core Logic)    │  ← Annotation, Project, Dataset
├─────────────────────────────────┤
│         Data Layer (SQLite)     │  ← project.db, config.yaml, labels/
└─────────────────────────────────┘
```

### Class Hierarchy

All annotation types inherit from the `Shape` base class:

```
Shape (ABC)
  ├── BBox              Bounding box (implemented)
  ├── Polygon           Polygon segmentation ✅ (implemented)
  ├── BrushMask         Brush mask (planned)
  ├── KeyPoint          Keypoint (planned)
  └── RotatedBox        Rotated box (planned)
```

---

## Core Modules

### Backend

#### `backend.annotation.shape` — Shape Base Class
Abstract base class for all annotation types, defining `to_dict()`, `copy()`, `scale()`, etc.

#### `backend.annotation.bbox` — BBox
Normalized-coordinate bounding box with IoU calculation and point containment.

#### `backend.annotation.polygon` — Polygon
Normalized-coordinate polygon for segmentation masks.

#### `backend.annotation.command` — Command Pattern
Full Undo/Redo via `AddCommand` / `DeleteCommand` / `MoveCommand` / `ResizeCommand` / `ChangeClassCommand`, managed by `CommandManager` (100-step stack).

#### `backend.annotation.manager` — AnnotationManager
Manages annotation list, selection state, integrates CommandManager for Undo/Redo.

#### `backend.project.project` — Project
SQLite persistence with 3 tables: `images`, `classes`, `annotations`.

#### `backend.dataset.manager` — DatasetManager
Coordinates Project, ImageLoader, and LabelLoader; provides a unified data access interface.

#### `backend.export.yolo` — YOLOExporter
Exports YOLO format (`class_id cx cy w h score`) + `data.yaml`.

### Frontend

#### `frontend.widgets.canvas` — Core Canvas
- Image rendering, zoom, pan
- Three interaction modes: Select, Draw, Pan
- BBox drawing / selection / drag-move / resize handles
- 9-point resize handles
- Right-click context menu
- Selection rectangle (rubber-band select)
- Polygon drawing with vertex editing

#### `frontend.widgets.image_view` — ImageView
Wraps Canvas with a mode toolbar and zoom controls.

#### `frontend.widgets.project_dock` — ProjectDock
Left panel showing project tree and image list for the current project.

#### `frontend.widgets.label_dock` — LabelDock
Right panel showing annotation list for the current image; supports right-click for batch label changes.

#### `frontend.widgets.property_dock` — PropertyDock
Property editor for selected annotations; supports precise position and class modification.

#### `frontend.widgets.class_dialog` — ClassDialog
Class management dialog with add / edit / delete, color picker, and shortcut binding.

---

## Development Guide

### Adding a New Annotation Type

Extend the `Shape` base class:

```python
from backend.annotation.shape import Shape

class Polygon(Shape):
    points: list = []          # Normalized coordinate list

    def to_dict(self) -> dict:
        return {'points': self.points, ...}

    def copy(self) -> 'Polygon':
        return Polygon(points=self.points.copy(), ...)

    def contains_point(self, px, py) -> bool:
        # Point-in-polygon test
        ...
```

Then add the corresponding drawing logic in Canvas.

### Integrating a New Model

Implement the unified prediction interface:

```python
class MyModel:
    def predict(self, image: np.ndarray) -> list:
        # Return [{'bbox': [x,y,w,h], 'class_id': int, 'score': float}, ...]
        pass
```

### Customizing Shortcuts

Edit `DEFAULT_SHORTCUTS` in `backend/utils/misc.py`.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `W` | Toggle BBox draw / select mode |
| `P` | Toggle polygon draw / select mode |
| `S` | Return to select mode |
| `H` | Pan mode |
| `A` / `D` | Previous / next image |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Delete` / `Backspace` / `Ctrl+D` | Delete selected / reject predictions |
| `Enter` | Accept selected predictions |
| `Escape` | Cancel drawing / deselect |
| `Ctrl+T` | Focus training panel |
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+I` | Import images |
| `Ctrl+E` | Export YOLO |
| `Ctrl+=` / `Ctrl+-` | Zoom in / out |
| `Double-click` | Fit to window |
| `Scroll wheel` | Zoom |
| `Ctrl+Click` | Multi-select / toggle selection |
| `Right-click → Change Class` | Change label (single or batch) |

---

## Data Format

### Project Directory Layout

```
projects/<project-name>/
├── images/           # Image files
├── labels/           # YOLO annotations (generated on export)
├── masks/            # Segmentation masks (planned)
├── models/           # Model files (training output + pretrained weights)
├── cache/            # Cache
├── exports/          # Export files
├── config.yaml       # Project configuration
└── project.db        # SQLite database
```

### Image Import

- **Deduplication**: same-name images auto-prefixed with source directory name (e.g. `0522D11_Image--01.jpg`)
- **Source Tracking**: the `source_path` field in the database records the original import path for each image
- **Directory Memory**: the import dialog auto-remembers the last-used directory

### YOLO Label Format

Each image has a corresponding `.txt` file, supporting two formats:

**Detection format**: `<class_id> <cx> <cy> <width> <height> [score]`

**Segmentation format**: `<class_id> <x1> <y1> <x2> <y2> ... <xn> <yn> [score]`

All coordinates are normalized to [0, 1]. Format is auto-detected on import.

---

## Why FastLabel?

- **Offline-first**: No cloud dependency — everything runs locally
- **Integrated training loop**: Annotate, train, and iterate without leaving the app
- **Lightweight**: Built with PyQt5 and YOLO — no heavy frameworks required
- **Extensible**: Clean Shape class hierarchy makes it easy to add new annotation types
- **Human-in-the-loop**: Designed from day 1 for the annotation → train → auto-annotate → correct workflow

---

## License

MIT
