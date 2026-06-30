"""ProjectConfig - 项目配置管理"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


DEFAULT_CONFIG = {
    'project': {
        'name': '未命名项目',
        'description': '',
        'version': '0.1.0',
        'created_at': '',
        'updated_at': '',
    },
    'classes': [
        {'id': 0, 'name': 'person', 'color': '#FF0000', 'shortcut': '1'},
        {'id': 1, 'name': 'car', 'color': '#00FF00', 'shortcut': '2'},
        {'id': 2, 'name': 'dog', 'color': '#0000FF', 'shortcut': '3'},
        {'id': 3, 'name': 'cat', 'color': '#FFFF00', 'shortcut': '4'},
    ],
    'annotation': {
        'mode': 'bbox',
        'auto_save': True,
        'auto_save_interval': 60,
    },
    'display': {
        'show_scores': True,
        'show_labels': True,
        'min_score': 0.25,
        'bbox_color': '#00FF00',
        'selected_color': '#FF0000',
    },
    'export': {
        'format': 'yolo',
        'auto_export': False,
    },
}


class ProjectConfig:
    """项目配置管理"""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f) or {}
            # 合并默认值，确保所有键存在
            self._merge_defaults()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

    def _merge_defaults(self):
        """递归合并默认配置"""
        def _merge(target, default):
            for key, value in default.items():
                if key not in target:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    _merge(target[key], value)
        _merge(self._data, DEFAULT_CONFIG)

    @property
    def classes(self) -> list:
        return self._data.get('classes', [])

    @classes.setter
    def classes(self, classes: list):
        self._data['classes'] = classes
        self.save()

    def get_class_by_id(self, class_id: int) -> Optional[dict]:
        for c in self.classes:
            if c['id'] == class_id:
                return c
        return None

    def get_class_by_name(self, name: str) -> Optional[dict]:
        for c in self.classes:
            if c['name'] == name:
                return c
        return None

    def add_class(self, name: str, color: str = '#FFFFFF', shortcut: str = ''):
        """添加类别（自动去重，如果名称已存在则返回 False）"""
        if self.get_class_by_name(name):
            return False
        classes = self.classes
        max_id = max([c['id'] for c in classes], default=-1)
        classes.append({
            'id': max_id + 1,
            'name': name,
            'color': color,
            'shortcut': shortcut,
        })
        self.classes = classes
        return True

    def remove_class(self, class_id: int):
        classes = [c for c in self.classes if c['id'] != class_id]
        self.classes = classes

    def update_class(self, class_id: int, **kwargs):
        for c in self.classes:
            if c['id'] == class_id:
                c.update(kwargs)
                break
        self.save()

    def __getitem__(self, key):
        return self._data.get(key, {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()
