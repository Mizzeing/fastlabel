"""Project - 单个项目的数据模型和管理"""

import sqlite3
import json
import time
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .config import ProjectConfig

DEBUG = False

def _log(*args):
    if DEBUG:
        print('[Project]', *args, file=sys.stderr)


class Project:
    """项目类 - 管理单个项目的所有数据和资源"""

    def __init__(self, project_path: Path):
        self.path = Path(project_path)
        self.name = self.path.name
        self.config = ProjectConfig(self.path / 'config.yaml')
        self.db_path = self.path / 'project.db'
        self._conn: Optional[sqlite3.Connection] = None
        self._init_dirs()
        self._init_db()

    def _init_dirs(self):
        """创建项目目录结构"""
        dirs = ['images', 'labels', 'masks', 'models', 'cache', 'exports']
        for d in dirs:
            (self.path / d).mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """初始化 SQLite 数据库"""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        # 使用 TRUNCATE journal 模式（比 WAL 更可靠，避免跨会话数据丢失）
        self._conn.execute("PRAGMA journal_mode=TRUNCATE")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate_if_needed()

    def _create_tables(self):
        cursor = self._conn.cursor()

        # 图片表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                source_path TEXT NOT NULL DEFAULT '',
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                file_size INTEGER NOT NULL DEFAULT 0,
                num_annotations INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 类别表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#FFFFFF',
                shortcut_key TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # 标注表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                annotation_id TEXT NOT NULL UNIQUE,
                image_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                x REAL NOT NULL DEFAULT 0.0,
                y REAL NOT NULL DEFAULT 0.0,
                width REAL NOT NULL DEFAULT 0.0,
                height REAL NOT NULL DEFAULT 0.0,
                score REAL NOT NULL DEFAULT 1.0,
                status TEXT NOT NULL DEFAULT 'manual',
                type TEXT NOT NULL DEFAULT 'bbox',
                points TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        """)

        self._conn.commit()

    def _migrate_if_needed(self):
        """数据库迁移：为旧数据库添加新列"""
        cols = [row['name'] for row in
                self._conn.execute("PRAGMA table_info(images)").fetchall()]
        if 'source_path' not in cols:
            self._conn.execute(
                "ALTER TABLE images ADD COLUMN source_path TEXT NOT NULL DEFAULT ''")
            self._conn.commit()

        # annotations 表迁移
        ann_cols = [row['name'] for row in
                     self._conn.execute("PRAGMA table_info(annotations)").fetchall()]
        if 'type' not in ann_cols:
            self._conn.execute(
                "ALTER TABLE annotations ADD COLUMN type TEXT NOT NULL DEFAULT 'bbox'")
            self._conn.commit()
        if 'points' not in ann_cols:
            self._conn.execute(
                "ALTER TABLE annotations ADD COLUMN points TEXT NOT NULL DEFAULT ''")
            self._conn.commit()

    # ── 连接管理 ──

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── 类别管理 ──

    def get_classes(self) -> List[Dict]:
        cursor = self._conn.execute(
            "SELECT * FROM classes ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]

    def sync_classes_from_config(self):
        """将 config.yaml 中的类别同步到数据库

        以 config.yaml 为唯一来源，通过差量计算确保增删改都正确同步。
        - 自动去重同名类别（防止 config.yaml 损坏时项目打不开）
        - 新增的类别 → INSERT
        - 已存在的类别 → UPDATE
        - 被删除的类别 → 自动移除其标注，再删除
        """
        cursor = self._conn.cursor()
        now = datetime.now().isoformat()

        # 去重：同名类别只保留第一个（config.yaml 可能因旧 bug 产生重复）
        seen_names = set()
        deduped = []
        for cls in self.config.classes:
            if cls['name'] not in seen_names:
                seen_names.add(cls['name'])
                deduped.append(cls)
        if len(deduped) != len(self.config.classes):
            self.config.classes = deduped  # 回写修正

        # 获取数据库中已有的类别 ID
        existing = {
            row['id'] for row in
            cursor.execute("SELECT id FROM classes").fetchall()
        }
        config_ids = {cls['id'] for cls in deduped}

        # 删除已经不在配置中的类别（连带删除其标注）
        for cid in existing - config_ids:
            cursor.execute("DELETE FROM annotations WHERE class_id = ?", (cid,))
            cursor.execute("DELETE FROM classes WHERE id = ?", (cid,))

        # 插入或更新配置中的类别
        # 注意: 不能用 INSERT OR REPLACE, 因为 REPLACE = DELETE+INSERT,
        # 会触发 ON DELETE CASCADE 导致关联标注被删除
        for cls in deduped:
            cursor.execute("""
                INSERT INTO classes (id, name, color, shortcut_key, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    color = excluded.color,
                    shortcut_key = excluded.shortcut_key
            """, (cls['id'], cls['name'], cls['color'],
                  cls.get('shortcut', ''), now))

        self._conn.commit()

    def add_class(self, name: str, color: str = '#FFFFFF', shortcut: str = '') -> bool:
        """添加类别，返回是否成功（False 表示名称已存在）"""
        if not self.config.add_class(name, color, shortcut):
            return False
        self.sync_classes_from_config()
        return True

    def remove_class(self, class_id: int):
        self.config.remove_class(class_id)
        self.sync_classes_from_config()

    # ── 图片管理 ──

    def add_image(self, path: str, filename: str, width: int, height: int,
                  file_size: int = 0, source_path: str = '') -> int:
        now = datetime.now().isoformat()
        cursor = self._conn.execute("""
            INSERT OR IGNORE INTO images
                (path, filename, width, height, file_size, source_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (path, filename, width, height, file_size, source_path, now, now))
        self._conn.commit()
        return cursor.lastrowid or self.get_image_id_by_path(path)

    def get_image_id_by_path(self, path: str) -> Optional[int]:
        cursor = self._conn.execute(
            "SELECT id FROM images WHERE path = ?", (path,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def get_image(self, image_id: int) -> Optional[Dict]:
        cursor = self._conn.execute(
            "SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_images(self) -> List[Dict]:
        cursor = self._conn.execute(
            "SELECT * FROM images ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]

    def get_image_count(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) as cnt FROM images")
        return cursor.fetchone()['cnt']

    def get_annotated_count(self) -> int:
        cursor = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM images WHERE num_annotations > 0")
        return cursor.fetchone()['cnt']

    def update_image_status(self, image_id: int, status: str):
        now = datetime.now().isoformat()
        self._conn.execute("""
            UPDATE images SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now, image_id))
        self._conn.commit()

    def remove_image(self, image_id: int):
        self._conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        self._conn.commit()

    # ── 标注管理 ──

    def get_annotations(self, image_id: int) -> List[Dict]:
        cursor = self._conn.execute("""
            SELECT a.*, c.name as label
            FROM annotations a
            LEFT JOIN classes c ON a.class_id = c.id
            WHERE a.image_id = ?
            ORDER BY a.id
        """, (image_id,))
        results = [dict(row) for row in cursor.fetchall()]
        _log(f'get_annotations(db={self.db_path}, image_id={image_id}): {len(results)} 条记录')
        for r in results:
            _log(f'  id={r["id"]}, type={r["type"]}, points={repr(r.get("points","")[:60])}')
        return results

    def save_annotation(self, image_id: int, annotation_id: str,
                        class_id: int, x: float, y: float,
                        width: float, height: float, score: float = 1.0,
                        status: str = 'manual', ann_type: str = 'bbox',
                        points: str = ''):
        now = datetime.now().isoformat()
        self._conn.execute("""
            INSERT OR REPLACE INTO annotations
                (annotation_id, image_id, class_id, x, y, width, height,
                 score, status, type, points, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT created_at FROM annotations WHERE annotation_id = ?), ?),
                    ?)
        """, (annotation_id, image_id, class_id, x, y, width, height, score,
              status, ann_type, points, annotation_id, now, now))
        # 更新标注计数
        count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM annotations WHERE image_id = ?",
            (image_id,)).fetchone()['cnt']
        self._conn.execute(
            "UPDATE images SET num_annotations = ?, updated_at = ? WHERE id = ?",
            (count, now, image_id))
        _log(f'  COMMIT 前, num_annotations={count}')
        self._conn.commit()
        _log(f'  COMMIT 完成')

    def delete_annotation(self, annotation_id: str):
        # 先获取 image_id
        cursor = self._conn.execute(
            "SELECT image_id FROM annotations WHERE annotation_id = ?",
            (annotation_id,))
        row = cursor.fetchone()
        if row:
            image_id = row['image_id']
            self._conn.execute(
                "DELETE FROM annotations WHERE annotation_id = ?",
                (annotation_id,))
            # 更新计数
            count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM annotations WHERE image_id = ?",
                (image_id,)).fetchone()['cnt']
            now = datetime.now().isoformat()
            self._conn.execute(
                "UPDATE images SET num_annotations = ?, updated_at = ? WHERE id = ?",
                (count, now, image_id))
            self._conn.commit()

    def delete_annotations_by_image(self, image_id: int):
        self._conn.execute(
            "DELETE FROM annotations WHERE image_id = ?", (image_id,))
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE images SET num_annotations = 0, updated_at = ? WHERE id = ?",
            (now, image_id))
        self._conn.commit()

    def save_all_annotations(self, image_id: int, annotations: List[Dict]):
        """批量保存标注（先清空再写入）"""
        _log(f'save_all_annotations(db={self.db_path}, image_id={image_id}): {len(annotations)} 条')
        try:
            self._conn.execute(
                "DELETE FROM annotations WHERE image_id = ?", (image_id,))
            _log(f'  DELETE 完成')
            now = datetime.now().isoformat()
            for i, ann in enumerate(annotations):
                ann_type = ann.get('type', 'bbox')
                points_json = ''
                if ann_type == 'polygon':
                    pts = ann.get('points', [])
                    import json
                    points_json = json.dumps(pts)

                x = ann.get('x', 0.0)
                y = ann.get('y', 0.0)
                w = ann.get('w', ann.get('width', 0.0))
                h = ann.get('h', ann.get('height', 0.0))

                _log(f'  INSERT[{i}]: id={ann["annotation_id"]}, type={ann_type}, '
                     f'class_id={ann["class_id"]}, points_len={len(points_json)}')
                self._conn.execute("""
                    INSERT INTO annotations
                        (annotation_id, image_id, class_id, x, y, width, height,
                         score, status, type, points, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ann['annotation_id'], image_id, ann['class_id'],
                    x, y, w, h,
                    ann.get('score', 1.0), ann.get('status', 'manual'),
                    ann_type, points_json, now, now
                ))
            count = len(annotations)
            self._conn.execute(
                "UPDATE images SET num_annotations = ?, updated_at = ?, status = ? WHERE id = ?",
                (count, now, 'annotated' if count > 0 else 'pending', image_id))
            self._conn.commit()
            # 立即验证数据是否写入
            verify = self._conn.execute("SELECT COUNT(*) as c FROM annotations WHERE image_id = ?", (image_id,)).fetchone()
            _log(f'  COMMIT 完成, {count} 条标注已保存 (验证: {verify["c"]} 条)')
        except Exception as e:
            self._conn.rollback()
            _log(f'  保存失败, 事务回滚: {e}')
            import traceback
            traceback.print_exc()
            raise

    # ── 导入/导出项目信息 ──

    def has_polygon_annotations(self) -> bool:
        """检查项目中是否有 polygon 类型的标注"""
        try:
            cursor = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM annotations WHERE type = 'polygon'")
            return cursor.fetchone()['cnt'] > 0
        except Exception:
            return False

    def get_stats(self) -> Dict:
        total = self.get_image_count()
        annotated = self.get_annotated_count()
        ann_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM annotations").fetchone()['cnt']
        class_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM classes").fetchone()['cnt']
        return {
            'total_images': total,
            'annotated_images': annotated,
            'total_annotations': ann_count,
            'class_count': class_count,
            'progress': (annotated / total * 100) if total > 0 else 0,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
