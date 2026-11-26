"""写真筛选的 HTTP 编排：参数校验、上传暂存、后台任务与投影。

本模块不实现向量构建、聚簇或分层，只把请求转给第 2、3 步的服务层：

- 参考对象走 `photo_filter_references.ReferenceStore`；
- 图集打分走 `photo_filter_scoring.PhotoFilterScorer`；
- 分层名与加注来自 `photo_filter_words`，这里只把账本里的那一行映射成界面用的稳定分层码。

浏览器一次上传 5–15 张参考照片：每张先落到暂存目录，建向量时再由服务层只读复制进
Peach 数据目录。暂存目录在成功建对象后清掉；源文件全程不修改。

打分任务在后台线程里跑，进度与取消都写 `photo_filter_task`：页面轮询任务投影，取消
只把状态改成 `cancelled`，打分循环在下一集之前读到它就停。
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import uuid
from dataclasses import replace
from pathlib import Path

from . import photo_filter_words as words
from . import settings_file
from .config import TOOLS_DIR
from .photo_filter_references import (
    DEFAULT_HIT_THRESHOLD,
    DEFAULT_TASTE_THRESHOLD,
    TASK_CANCELLED,
    TASK_PENDING,
    TASK_RUNNING,
    ReferenceStore,
)
from .photo_filter_scoring import PhotoFilterScorer
from .photo_filter_vector import PhotoFilterModelUnavailable, resolve_model_dir

LOGGER = logging.getLogger(__name__)

#: 新建参考对象要的照片数，与页面上的说明一致。
MIN_REFERENCE_PHOTOS = 5
MAX_REFERENCE_PHOTOS = 15
#: 单张参考照片的上限，挡住误传的整段视频或磁盘镜像。
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
#: 认作照片的扩展名，与打分服务扫描图集的口径一致。
PHOTO_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
#: 暂存目录名：随机十六进制，页面递回来的 token 必须完整匹配。
_TOKEN = re.compile(r"^[0-9a-f]{32}$")
#: 文件名里不能出现的字符，按 Windows 的最严口径取。
_UNSAFE_FILENAME = re.compile('[\\/:*?"<>|]+|[\x00-\x1f]+')
#: 正在跑的任务线程；用于测试等待与避免同一任务重复开线程。
_THREADS: dict[int, threading.Thread] = {}
_THREADS_LOCK = threading.Lock()


def _model_root() -> Path:
    """当前生效的 buffalo_l 根路径：设置优先，留空回落数据目录下的工具目录。"""
    raw = settings_file.active().photo_filter.model_root.strip()
    return Path(raw).expanduser() if raw else TOOLS_DIR / "insightface"


def _store(contract) -> ReferenceStore:
    return ReferenceStore(
        contract.database,
        reference_root=contract.photo_filter_reference_root,
        model_root=_model_root(),
        detector_factory=getattr(contract, "photo_filter_detector_factory", None),
    )


def _scorer(contract) -> PhotoFilterScorer:
    return PhotoFilterScorer(
        _store(contract),
        representative_root=contract.photo_filter_results_root,
        detector_factory=getattr(contract, "photo_filter_detector_factory", None),
    )


# ---- 参考对象 -------------------------------------------------------------

def reference_payload(reference) -> dict:
    return {
        "id": reference.id,
        "name": reference.name,
        "valid_face_count": reference.valid_face_count,
        "status": reference.status,
        "failure_reason": reference.failure_reason,
        "provider": reference.provider,
        "created_at": reference.created_at,
        "updated_at": reference.updated_at,
    }


def list_references(contract) -> dict:
    return {"references": [reference_payload(item) for item in _store(contract).list()]}


def create_reference(contract, body) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("reference name must not be empty")
    folder = upload_dir(contract, str(body.get("upload_token") or ""))
    photos = sorted(path for path in folder.iterdir() if path.is_file())
    if not MIN_REFERENCE_PHOTOS <= len(photos) <= MAX_REFERENCE_PHOTOS:
        raise ValueError(
            f"reference needs {MIN_REFERENCE_PHOTOS}-{MAX_REFERENCE_PHOTOS} photos, got {len(photos)}")
    reference = _store(contract).create(name, photos)
    shutil.rmtree(folder, ignore_errors=True)
    return reference_payload(reference)


def rebuild_reference(contract, reference_id: int) -> dict:
    return reference_payload(_store(contract).rebuild(reference_id))


def delete_reference(contract, reference_id: int) -> dict:
    return {"ok": _store(contract).delete(reference_id)}


# ---- 参考照片上传 ---------------------------------------------------------

def create_upload(contract) -> dict:
    token = uuid.uuid4().hex
    folder = contract.photo_filter_upload_root / token
    folder.mkdir(parents=True, exist_ok=False)
    return {"token": token}


def upload_dir(contract, token: str) -> Path:
    if not _TOKEN.fullmatch(token or ""):
        raise ValueError("upload token is invalid")
    folder = contract.photo_filter_upload_root / token
    if not folder.is_dir():
        raise KeyError(f"upload session does not exist: {token}")
    return folder


def store_upload(contract, token: str, filename: str, payload: bytes) -> dict:
    folder = upload_dir(contract, token)
    if not payload:
        raise ValueError("uploaded photo is empty")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("uploaded photo is too large")
    name = _UNSAFE_FILENAME.sub("-", os.path.basename(filename or "photo")).strip(".-")[-160:]
    suffix = Path(name).suffix.lower()
    if suffix not in PHOTO_SUFFIXES:
        raise ValueError("uploaded photo type is not supported")
    if not Path(name).stem:
        name = f"photo{suffix}"
    target = folder / name
    index = 1
    while target.exists():
        target = folder / f"{Path(name).stem}-{index}{suffix}"
        index += 1
    temporary = folder / f".{uuid.uuid4().hex}.part"
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    return {"name": target.name}


def delete_upload(contract, token: str) -> dict:
    folder = upload_dir(contract, token)
    shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


# ---- 本机设置 -------------------------------------------------------------

def _runtime_status() -> dict:
    try:
        import insightface  # noqa: F401  确认运行环境完整
        import onnxruntime
    except ModuleNotFoundError:
        return {"runtime_available": False, "cuda_available": False}
    providers = set(onnxruntime.get_available_providers())
    return {
        "runtime_available": True,
        "cuda_available": "CUDAExecutionProvider" in providers,
    }


def settings_payload() -> dict:
    raw = settings_file.active().photo_filter.model_root.strip()
    root = Path(raw).expanduser() if raw else TOOLS_DIR / "insightface"
    ready = False
    try:
        resolved = str(resolve_model_dir(root))
        ready = True
    except PhotoFilterModelUnavailable:
        resolved = str(root)
    return {
        "model_root": raw,
        "model_root_resolved": resolved,
        "model_ready": ready,
        **_runtime_status(),
    }


def write_settings(body) -> dict:
    value = body.get("model_root")
    if not isinstance(value, str):
        raise ValueError("model_root must be a string")
    config = settings_file.load_config()
    updated = replace(config, photo_filter=replace(config.photo_filter, model_root=value.strip()))
    settings_file.write(updated, force=True)
    settings_file.reset_cache()
    return settings_payload()


# ---- 筛选任务 -------------------------------------------------------------

def _threshold(value, default: float) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValueError("threshold must be a number")
    number = float(value)
    if not 0.0 < number <= 1.0:
        raise ValueError("threshold must be within (0, 1]")
    return number


def task_payload(task) -> dict:
    return {
        "id": task.id,
        "root_path": task.root_path,
        "status": task.status,
        "processed_count": task.processed_count,
        "total_count": task.total_count,
        "hit_threshold": task.hit_threshold,
        "taste_threshold": task.taste_threshold,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _tier_of(label: str) -> tuple[str, bool]:
    """把账本里的分层名映射成稳定分层码；加注单独给出，界面按当前语言渲染。"""
    for code, text in (
        ("hit", words.TIER_HIT),
        ("suspected", words.TIER_SUSPECTED),
        ("taste", words.TIER_TASTE),
        ("miss", words.TIER_MISS),
        ("insufficient", words.TIER_INSUFFICIENT),
    ):
        if label == text or label.startswith(text):
            return code, words.PROTAGONIST_SPREAD in label
    return "miss", words.PROTAGONIST_SPREAD in label


def _start_scoring(contract, task_id: int) -> None:
    def run() -> None:
        try:
            _scorer(contract).score_task(task_id)
        except Exception:  # noqa: BLE001  后台异常必须落进日志，任务本身已由服务层标失败
            LOGGER.exception("photo filter task %s failed", task_id)
        finally:
            with _THREADS_LOCK:
                _THREADS.pop(task_id, None)

    thread = threading.Thread(target=run, name=f"photo-filter-{task_id}", daemon=True)
    with _THREADS_LOCK:
        _THREADS[task_id] = thread
    thread.start()


def wait_for_task(task_id: int, timeout: float | None = None) -> None:
    """测试用：等这一轮打分线程结束。"""
    with _THREADS_LOCK:
        thread = _THREADS.get(task_id)
    if thread is not None:
        thread.join(timeout)


def create_task(contract, body) -> dict:
    root = str(body.get("root_path") or "").strip()
    if not root:
        raise ValueError("filter task root path must not be empty")
    if not Path(root).is_dir():
        raise ValueError(f"filter task root does not exist: {root}")
    hit = _threshold(body.get("hit_threshold"), DEFAULT_HIT_THRESHOLD)
    taste = _threshold(body.get("taste_threshold"), DEFAULT_TASTE_THRESHOLD)
    task = _store(contract).create_task(root, hit_threshold=hit, taste_threshold=taste)
    _start_scoring(contract, task.id)
    return task_payload(task)


def list_tasks(contract) -> dict:
    store = _store(contract)
    counts: dict[int, int] = {}
    with store.ledger.read_connection() as connection:
        for row in connection.execute(
                "SELECT task_id, count(*) FROM photo_filter_result GROUP BY task_id"):
            counts[row[0]] = row[1]
    return {"tasks": [{**task_payload(task), "result_count": counts.get(task.id, 0)}
                      for task in store.list_tasks()]}


def cancel_task(contract, task_id: int) -> dict:
    store = _store(contract)
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(f"filter task does not exist: {task_id}")
    if task.status in (TASK_PENDING, TASK_RUNNING):
        task = store.update_task(task_id, status=TASK_CANCELLED)
    return task_payload(task)


def task_detail(contract, task_id: int) -> dict:
    store = _store(contract)
    task = store.get_task(task_id)
    if task is None:
        raise KeyError(f"filter task does not exist: {task_id}")
    names = {reference.id: reference.name for reference in store.list()}
    with store.ledger.read_connection() as connection:
        rows = connection.execute(
            "SELECT id,album_path,score,top_reference_id,valid_image_count,total_image_count,"
            "protagonist_cluster_ratio,tier_label,representative_face_path "
            "FROM photo_filter_result WHERE task_id=? ORDER BY score DESC, id",
            (task_id,)).fetchall()
    results = []
    for row in rows:
        tier, spread = _tier_of(row["tier_label"])
        results.append({
            "id": row["id"],
            "album_path": row["album_path"],
            "score": row["score"],
            "top_reference_id": row["top_reference_id"],
            "top_reference_name": names.get(row["top_reference_id"], ""),
            "valid_image_count": row["valid_image_count"],
            "total_image_count": row["total_image_count"],
            "protagonist_cluster_ratio": row["protagonist_cluster_ratio"],
            "tier": tier,
            "tier_label": row["tier_label"],
            "protagonist_spread": spread,
            "face_url": (f"/photo-filter-face?result={row['id']}"
                         if row["representative_face_path"] else ""),
        })
    return {"task": task_payload(task), "results": results}


def result_album(contract, result_id: int) -> str:
    store = _store(contract)
    with store.ledger.read_connection() as connection:
        row = connection.execute(
            "SELECT album_path FROM photo_filter_result WHERE id=?", (result_id,)).fetchone()
    if row is None:
        raise KeyError(f"photo filter result does not exist: {result_id}")
    return row["album_path"]
