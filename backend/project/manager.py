"""ProjectManager - 项目管理器

管理项目的创建、打开、最近项目等。
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from .project import Project


class ProjectManager:
    """项目管理器 - 单例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._current_project: Optional[Project] = None
        self._base_dir = self._find_base_dir()

    @staticmethod
    def _find_base_dir() -> Path:
        """找到项目根目录下的 projects 文件夹"""
        # 优先使用当前工作目录下的 projects
        cwd_projects = Path.cwd() / 'projects'
        if cwd_projects.exists():
            return cwd_projects
        cwd_projects.mkdir(parents=True, exist_ok=True)
        return cwd_projects

    @property
    def current_project(self) -> Optional[Project]:
        return self._current_project

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ── 项目操作 ──

    def create_project(self, name: str, description: str = '') -> Project:
        """创建新项目"""
        project_dir = self._base_dir / name
        if project_dir.exists():
            raise FileExistsError(f"项目 '{name}' 已存在")

        project_dir.mkdir(parents=True)
        project = Project(project_dir)
        project.config.set('project', {
            'name': name,
            'description': description,
            'version': '0.1.0',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        })
        project.sync_classes_from_config()
        self._current_project = project
        return project

    def open_project(self, name_or_path: str) -> Project:
        """打开已有项目"""
        path = Path(name_or_path)
        if not path.exists():
            path = self._base_dir / name_or_path

        if not path.exists():
            raise FileNotFoundError(f"项目不存在: {name_or_path}")

        config_file = path / 'config.yaml'
        if not config_file.exists():
            raise FileNotFoundError(f"不是有效的项目目录: {path}")

        project = Project(path)
        project.sync_classes_from_config()
        self._current_project = project
        return project

    def close_project(self):
        """关闭当前项目"""
        if self._current_project:
            self._current_project.close()
            self._current_project = None

    def list_projects(self) -> List[Dict]:
        """列出所有可用项目"""
        projects = []
        if not self._base_dir.exists():
            return projects

        for item in sorted(self._base_dir.iterdir()):
            if item.is_dir() and (item / 'config.yaml').exists():
                try:
                    cfg_path = item / 'config.yaml'
                    import yaml
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = yaml.safe_load(f) or {}
                    proj_info = cfg.get('project', {})
                    images_dir = item / 'images'
                    image_count = len(list(images_dir.glob('*'))) if images_dir.exists() else 0
                    projects.append({
                        'name': proj_info.get('name', item.name),
                        'description': proj_info.get('description', ''),
                        'path': str(item),
                        'created_at': proj_info.get('created_at', ''),
                        'updated_at': proj_info.get('updated_at', ''),
                        'image_count': image_count,
                    })
                except Exception:
                    continue
        return projects

    def delete_project(self, name: str):
        """删除项目"""
        import shutil
        path = self._base_dir / name
        if path.exists():
            shutil.rmtree(path)
        if self._current_project and self._current_project.name == name:
            self._current_project = None
