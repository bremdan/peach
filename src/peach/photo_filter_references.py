"""写真筛选的参考对象数据层与筛选任务基础读写。

三张新表见 `migrations/0060_photo_filter.sql`：参考对象、筛选任务、筛选结果。本模块只负责
参考对象的增删查建与筛选任务的基本读写，不实现图集打分，也不做界面。

参考照片的处理只有一条规则：用户给的原图只读复制到 Peach 数据目录下的本功能专用子目录
（每对象一个 `storage_subdir`），绝不修改源文件。对象的向量、有效脸数与状态随行存放；
删除对象时连同照片副本与向量一并删除，向量就是行上的 blob，行没了向量也就不在了。

向量构建在 `photo_filter_vector`，本模块只负责调用与落库。
"""
from __future__ import annotations

import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .photo_filter_vector import (
    EMBEDDING_DIM,
    InsightFaceDetector,
    build_reference_vector,
)
from .repository import LedgerDatabase

#: 参考对象状态。
REFERENCE_READY = "ready"
REFERENCE_FAILED = "failed"
REFERENCE_STATUSES = (REFERENCE_READY, REFERENCE_FAILED)

#: 筛选任务状态。
TASK_PENDING = "pending"
TASK_RUNNING = "running"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"
TASK_CANCELLED = "cancelled"
TASK_STATUSES = (TASK_PENDING, TASK_RUNNING, TASK_COMPLETED, TASK_FAILED, TASK_CANCELLED)

#: 阈值默认值来自定稿规格。
DEFAULT_HIT_THRESHOLD = 0.50
DEFAULT_TASTE_THRESHOLD = 0.30

_REFERENCE_COLUMNS = (
    "id,name,created_at,updated_at,embedding,valid_face_count,status,"
    "failure_reason,storage_subdir,provider")
_TASK_COLUMNS = (
    "id,created_at,updated_at,root_path,status,processed_count,total_count,"
    "hit_threshold,taste_threshold")


def _now(moment: datetime | None = None) -> str:
    moment = moment or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def embedding_bytes(vector) -> bytes:
    """512 维向量按 float32 小端存成 blob。"""
    import numpy

    array = numpy.asarray(vector, dtype="<f4").reshape(-1)
    if array.size != EMBEDDING_DIM:
        raise ValueError(f"embedding dimension must be {EMBEDDING_DIM}, got {array.size}")
    return array.tobytes()


def embedding_from_blob(blob: bytes | None):
    """blob 还原成 float32 一维数组；没有向量时返回 None。"""
    if blob is None:
        return None
    import numpy

    return numpy.frombuffer(blob, dtype="<f4").copy()


@dataclass(frozen=True)
class Reference:
    id: int
    name: str
    created_at: str
    updated_at: str
    embedding: bytes | None
    valid_face_count: int
    status: str
    failure_reason: str
    storage_subdir: str
    provider: str

    @property
    def ready(self) -> bool:
        return self.status == REFERENCE_READY

    def vector(self):
        return embedding_from_blob(self.embedding)


@dataclass(frozen=True)
class FilterTask:
    id: int
    created_at: str
    updated_at: str
    root_path: str
    status: str
    processed_count: int
    total_count: int
    hit_threshold: float
    taste_threshold: float


class ReferenceStore:
    """参考对象与筛选任务的服务层。

    `detector_factory` 留给出测试注入替身；生产路径构造 `InsightFaceDetector(model_root)`。
    `ledger` 收 `LedgerDatabase` 或账本路径，写走它的写事务。
    """

    def __init__(self, ledger: LedgerDatabase | Path | str, *,
                 reference_root: Path | str, model_root: Path | str | None = None,
                 detector_factory=None) -> None:
        self.ledger = (ledger if isinstance(ledger, LedgerDatabase)
                       else LedgerDatabase(Path(ledger)))
        self.reference_root = Path(reference_root)
        if model_root is None:
            from .config import PHOTO_FILTER_MODEL_ROOT
            model_root = PHOTO_FILTER_MODEL_ROOT
        self.model_root = Path(model_root)
        self.detector_factory = detector_factory

    # ---- 参考对象 ---------------------------------------------------------

    def create(self, name: str, photo_paths) -> Reference:
        """新建参考对象：复制照片、构建向量、落库。"""
        name = (name or "").strip()
        if not name:
            raise ValueError("reference name must not be empty")
        sources = [Path(path) for path in photo_paths]
        if not sources:
            raise ValueError("at least one reference photo is required")
        for source in sources:
            if not source.is_file():
                raise FileNotFoundError(f"reference photo does not exist: {source}")

        # 先确认模型可用，避免构建失败后在磁盘上留下半份副本。
        detector = self._detector()
        storage_subdir = uuid.uuid4().hex
        target = self.reference_root / storage_subdir
        target.mkdir(parents=True, exist_ok=False)
        copies = []
        try:
            for index, source in enumerate(sources, 1):
                suffix = source.suffix.lower() or ".jpg"
                destination = target / f"photo-{index:02d}{suffix}"
                shutil.copyfile(source, destination)
                copies.append(destination)
            build = build_reference_vector(copies, detector)
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

        timestamp = _now()
        ready = build.ok
        with self.ledger.write_transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO photo_filter_reference(name,created_at,updated_at,embedding,"
                "valid_face_count,status,failure_reason,storage_subdir,provider) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (name, timestamp, timestamp,
                 embedding_bytes(build.embedding) if ready else None,
                 build.valid_face_count,
                 REFERENCE_READY if ready else REFERENCE_FAILED,
                 build.failure_reason, storage_subdir, build.provider))
            reference_id = cursor.lastrowid
        return self.get(reference_id)

    def get(self, reference_id: int) -> Reference | None:
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_REFERENCE_COLUMNS} FROM photo_filter_reference WHERE id=?",
                (reference_id,)).fetchone()
        return _reference(row)

    def list(self) -> list[Reference]:
        with self.ledger.read_connection() as connection:
            rows = connection.execute(
                f"SELECT {_REFERENCE_COLUMNS} FROM photo_filter_reference ORDER BY id").fetchall()
        return [_reference(row) for row in rows]

    def rebuild(self, reference_id: int) -> Reference:
        """用已存的参考照片副本重跑向量构建。"""
        reference = self.get(reference_id)
        if reference is None:
            raise KeyError(f"reference does not exist: {reference_id}")
        target = self.reference_root / reference.storage_subdir
        copies = sorted(target.glob("photo-*"))
        if not copies:
            raise FileNotFoundError(f"reference photo copies are missing: {target}")
        build = build_reference_vector(copies, self._detector())
        ready = build.ok
        with self.ledger.write_transaction() as connection:
            connection.execute(
                "UPDATE photo_filter_reference SET updated_at=?, embedding=?, "
                "valid_face_count=?, status=?, failure_reason=?, provider=? WHERE id=?",
                (_now(), embedding_bytes(build.embedding) if ready else None,
                 build.valid_face_count,
                 REFERENCE_READY if ready else REFERENCE_FAILED,
                 build.failure_reason, build.provider, reference_id))
        return self.get(reference_id)

    def delete(self, reference_id: int) -> bool:
        """删除对象：行（含向量）与参考照片副本一起删。"""
        reference = self.get(reference_id)
        if reference is None:
            return False
        with self.ledger.write_transaction() as connection:
            connection.execute(
                "DELETE FROM photo_filter_reference WHERE id=?", (reference_id,))
        shutil.rmtree(self.reference_root / reference.storage_subdir, ignore_errors=True)
        return True

    def photo_paths(self, reference_id: int) -> list[Path]:
        """对象已存副本的路径，按复制顺序。"""
        reference = self.get(reference_id)
        if reference is None:
            raise KeyError(f"reference does not exist: {reference_id}")
        return sorted((self.reference_root / reference.storage_subdir).glob("photo-*"))

    # ---- 筛选任务 ---------------------------------------------------------

    def create_task(self, root_path: str, *,
                    hit_threshold: float = DEFAULT_HIT_THRESHOLD,
                    taste_threshold: float = DEFAULT_TASTE_THRESHOLD) -> FilterTask:
        root_path = (root_path or "").strip()
        if not root_path:
            raise ValueError("filter task root path must not be empty")
        timestamp = _now()
        with self.ledger.write_transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO photo_filter_task(created_at,updated_at,root_path,status,"
                "processed_count,total_count,hit_threshold,taste_threshold) "
                "VALUES(?,?,?,?,0,0,?,?)",
                (timestamp, timestamp, root_path, TASK_PENDING,
                 float(hit_threshold), float(taste_threshold)))
            task_id = cursor.lastrowid
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> FilterTask | None:
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_TASK_COLUMNS} FROM photo_filter_task WHERE id=?",
                (task_id,)).fetchone()
        return _task(row)

    def list_tasks(self) -> list[FilterTask]:
        with self.ledger.read_connection() as connection:
            rows = connection.execute(
                f"SELECT {_TASK_COLUMNS} FROM photo_filter_task ORDER BY id").fetchall()
        return [_task(row) for row in rows]

    def update_task(self, task_id: int, *, status: str | None = None,
                    processed_count: int | None = None,
                    total_count: int | None = None) -> FilterTask:
        changes = {}
        if status is not None:
            if status not in TASK_STATUSES:
                raise ValueError(f"unknown filter task status: {status}")
            changes["status"] = status
        if processed_count is not None:
            changes["processed_count"] = int(processed_count)
        if total_count is not None:
            changes["total_count"] = int(total_count)
        if not changes:
            return self.get_task(task_id)
        changes["updated_at"] = _now()
        assignments = ",".join(f"{column}=?" for column in changes)
        with self.ledger.write_transaction() as connection:
            cursor = connection.execute(
                f"UPDATE photo_filter_task SET {assignments} WHERE id=?",
                (*changes.values(), task_id))
            if cursor.rowcount == 0:
                raise KeyError(f"filter task does not exist: {task_id}")
        return self.get_task(task_id)

    # ---- 内部 ------------------------------------------------------------

    def detector(self):
        """供打分服务复用同一套检测器构造：生产是 InsightFace，测试可注入替身。"""
        return self._detector()

    def _detector(self):
        if self.detector_factory is not None:
            return self.detector_factory()
        return InsightFaceDetector(self.model_root)


def _reference(row: sqlite3.Row | None) -> Reference | None:
    if row is None:
        return None
    return Reference(
        id=row["id"], name=row["name"], created_at=row["created_at"],
        updated_at=row["updated_at"], embedding=row["embedding"],
        valid_face_count=row["valid_face_count"], status=row["status"],
        failure_reason=row["failure_reason"], storage_subdir=row["storage_subdir"],
        provider=row["provider"])


def _task(row: sqlite3.Row | None) -> FilterTask | None:
    if row is None:
        return None
    return FilterTask(
        id=row["id"], created_at=row["created_at"], updated_at=row["updated_at"],
        root_path=row["root_path"], status=row["status"],
        processed_count=row["processed_count"], total_count=row["total_count"],
        hit_threshold=row["hit_threshold"], taste_threshold=row["taste_threshold"])
