"""写真筛选的打分：逐集扫描、集内聚簇、与参考对象比对、分层并落库。

输入是一个根目录，根目录下每个子文件夹和每个 `.zip` 文件各算一个图集；文件夹图集内部的
图片递归读取，ZIP 图集按条目名扁平读取、不整包解压落盘。两者都只认
jpg/jpeg/png/webp/bmp，嵌套 ZIP 跳过。单张图的处理与参考向量构建共用
`photo_filter_vector`：加白边 15% → 只留女性脸 → 质量门 ≥80px → 取面积最大的那张脸。
每张图因此只贡献一个向量。

集内把全部向量按余弦相似度 ≥0.45 贪心聚簇，最大簇（同大小取更早出现的）是主角簇。
主角簇均值向量归一化后，与每个就绪参考对象的向量算余弦，最高分就是该集得分，同时记下
「最像参考」。得分按任务自带的阈值分层；有效图少于 5 张时高分单独落到「疑似命中·待
确认」，低分落到「信号不足」，不会埋进末尾。

代表图取主角簇里与「最像参考」向量最相似的那张脸，从原图裁出脸部区域写进 Peach 数据
目录；源目录全程只读，不复制整图、不改不删任何文件。

任务运行状态与进度写回 `photo_filter_task`；处理下一集之前重读任务状态，发现已被标成
`cancelled` 就停下，留给后续界面接入。
"""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import photo_filter_words as words
from .photo_filter_references import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_RUNNING,
    ReferenceStore,
)
from .photo_filter_vector import (
    BORDER_RATIO,
    add_white_border,
    decode_bgr,
    main_face,
    mean_normalized,
    read_bgr,
)

#: 每集最多处理的图片数；超量按文件名排序后均匀抽样。
MAX_ALBUM_IMAGES = 100
#: 认作图片的扩展名。
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
#: 集内聚簇的余弦相似度下限。
CLUSTER_SIMILARITY = 0.45
#: 少于这么多有效图时，高分只算「疑似命中·待确认」。
MIN_VALID_IMAGES = 5
#: 主角簇占比低于这个值时加注「主角不集中」。
PROTAGONIST_SPREAD_RATIO = 0.5


class AlbumReadError(RuntimeError):
    """一个 ZIP 图集读不出来；只标记该集失败，不中断整个任务。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ZipImage:
    """ZIP 里的一个图片条目；只读取当前条目，不整包解压落盘。"""

    archive: Path
    entry: str

    @property
    def name(self) -> str:
        return PurePosixPath(self.entry.replace("\\", "/")).name

    @property
    def label(self) -> str:
        return f"{self.archive.name}:{self.entry}"

    def read_bytes(self) -> bytes:
        try:
            with zipfile.ZipFile(self.archive) as bundle:
                return bundle.read(self.entry)
        except Exception as error:
            raise AlbumReadError(_zip_reason(self.archive, error)) from error


@dataclass(frozen=True)
class FaceSample:
    """一张有效图的主脸：来源（文件或 ZIP 条目）、白边图里的框、512 维向量。"""

    path: Path | ZipImage
    bbox: tuple[float, float, float, float]
    embedding: object


@dataclass(frozen=True)
class AlbumResult:
    """一个图集的打分结果，字段与 `photo_filter_result` 一一对应。"""

    album_path: str
    score: float
    top_reference_id: int | None
    valid_image_count: int
    total_image_count: int
    protagonist_cluster_ratio: float
    tier_label: str
    representative_face_path: str
    album_name: str = ""
    failure_reason: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.failure_reason)


@dataclass(frozen=True)
class ScoreRun:
    """一次任务执行的收尾状态。`cancelled` 为真时任务保持「已取消」。"""

    task_id: int
    processed_count: int
    total_count: int
    cancelled: bool
    results: tuple[AlbumResult, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_zip_path(path: Path) -> bool:
    return path.suffix.lower() == ".zip" and not path.is_dir()


def _zip_stem(path: Path) -> str:
    return path.name[:-4] if path.name.casefold().endswith(".zip") else path.name


def _zip_reason(archive: Path, error: Exception) -> str:
    name = Path(archive).name
    if isinstance(error, zipfile.BadZipFile):
        return words.ALBUM_CORRUPT.format(name=name)
    message = str(error).casefold()
    if "password" in message or "encrypted" in message:
        return words.ALBUM_ENCRYPTED.format(name=name)
    if isinstance(error, NotImplementedError):
        return words.ALBUM_UNSUPPORTED_COMPRESSION.format(name=name)
    return words.ALBUM_UNREADABLE.format(name=name, error=error)


def discover_albums(root: Path | str) -> list[Path]:
    """根目录下的直接子文件夹和 `.zip` 文件，按名字排序；根目录散图不算图集。"""
    base = Path(root)
    albums = [path for path in base.iterdir()
              if path.is_dir() or (path.is_file() and _is_zip_path(path))]
    return sorted(albums, key=lambda path: (path.name.casefold(), path.name))


def album_display_names(albums) -> dict[Path, str]:
    """图集的展示名：文件夹用目录名，ZIP 去后缀；与文件夹同名时加 ` (zip)`。"""
    paths = [Path(album) for album in albums]
    folder_names = {path.name.casefold() for path in paths if not _is_zip_path(path)}
    names: dict[Path, str] = {}
    taken: set[str] = set()
    for path in paths:
        base = _zip_stem(path) if _is_zip_path(path) else path.name
        if _is_zip_path(path) and base.casefold() in folder_names:
            base = f"{base} (zip)"
        name = base
        index = 2
        while name.casefold() in taken:
            name = f"{base} ({index})"
            index += 1
        taken.add(name.casefold())
        names[path] = name
    return names


def zip_album_images(archive: Path | str) -> list[ZipImage]:
    """流式列出 ZIP 内的图片条目；嵌套 ZIP 与非图片条目跳过。"""
    path = Path(archive)
    try:
        with zipfile.ZipFile(path) as bundle:
            infos = [info for info in bundle.infolist()
                     if not info.is_dir()
                     and PurePosixPath(info.filename.replace("\\", "/")).suffix.lower()
                     in IMAGE_EXTENSIONS]
    except Exception as error:
        raise AlbumReadError(_zip_reason(path, error)) from error
    if any(info.flag_bits & 0x1 for info in infos):
        raise AlbumReadError(words.ALBUM_ENCRYPTED.format(name=path.name))
    infos.sort(key=lambda info: (
        PurePosixPath(info.filename.replace("\\", "/")).name.casefold(), info.filename))
    return [ZipImage(path, info.filename) for info in infos]


def album_images(album: Path | str) -> list[Path | ZipImage]:
    """列出图集里的图片，按文件名排序；ZIP 图集只读条目名，不解压。"""
    path = Path(album)
    if _is_zip_path(path):
        return zip_album_images(path)
    found = [item for item in path.rglob("*")
             if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS]
    return sorted(found, key=lambda item: (item.name.casefold(), str(item)))


def sample_images(images, limit: int = MAX_ALBUM_IMAGES) -> list[Path]:
    """超过上限时均匀抽样：保留首尾、按原顺序取等距的 `limit` 张。"""
    ordered = list(images)
    if limit <= 0:
        return []
    if len(ordered) <= limit:
        return ordered
    if limit == 1:
        return [ordered[0]]
    step = (len(ordered) - 1) / (limit - 1)
    return [ordered[round(index * step)] for index in range(limit)]


def _unit(vector):
    import numpy

    array = numpy.asarray(vector, dtype=numpy.float64).reshape(-1)
    norm = float(numpy.linalg.norm(array))
    if norm == 0:
        raise ValueError("photo filter embedding is a zero vector")
    return array / norm


def cosine(left, right) -> float:
    """两个向量的余弦相似度；任意一边是零向量时返回 0。"""
    import numpy

    a = numpy.asarray(left, dtype=numpy.float64).reshape(-1)
    b = numpy.asarray(right, dtype=numpy.float64).reshape(-1)
    na = float(numpy.linalg.norm(a))
    nb = float(numpy.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(numpy.dot(a, b) / (na * nb))


def cluster_face_indices(embeddings, *, threshold: float = CLUSTER_SIMILARITY) -> list[list[int]]:
    """贪心聚簇：每个向量并入质心最相似且达到阈值的簇，否则另起一簇。"""
    import numpy

    clusters: list[list[int]] = []
    centroids: list[object] = []
    for index, embedding in enumerate(embeddings):
        vector = _unit(embedding)
        if centroids:
            similarities = [float(numpy.dot(vector, centroid)) for centroid in centroids]
            best = max(range(len(similarities)), key=similarities.__getitem__)
            if similarities[best] >= threshold:
                clusters[best].append(index)
                centroids[best] = _unit(numpy.mean(
                    [numpy.asarray(embeddings[i], dtype=numpy.float64).reshape(-1)
                     for i in clusters[best]], axis=0))
                continue
        clusters.append([index])
        centroids.append(vector)
    return clusters


def protagonist_cluster(clusters: list[list[int]]) -> list[int]:
    """最大簇为主角簇；大小相同取先出现的那一簇。"""
    return max(clusters, key=lambda members: (len(members), -members[0]))


def tier_for(valid_image_count: int, score: float, *,
             hit_threshold: float, taste_threshold: float) -> str:
    """按有效图数与得分分层，返回基础分层名（不含加注）。"""
    if valid_image_count >= MIN_VALID_IMAGES:
        if score >= hit_threshold:
            return words.TIER_HIT
        if score >= taste_threshold:
            return words.TIER_TASTE
        return words.TIER_MISS
    if score >= hit_threshold:
        return words.TIER_SUSPECTED
    return words.TIER_INSUFFICIENT


def tier_label(valid_image_count: int, score: float, ratio: float, *,
               hit_threshold: float, taste_threshold: float) -> str:
    """分层名；主角簇占比不足一半时附上「主角不集中」加注，分数不变。"""
    label = tier_for(valid_image_count, score,
                     hit_threshold=hit_threshold, taste_threshold=taste_threshold)
    if valid_image_count > 0 and ratio < PROTAGONIST_SPREAD_RATIO:
        return f"{label}；{words.PROTAGONIST_SPREAD}"
    return label


def _border_size(image) -> int:
    height, width = image.shape[:2]
    return max(1, int(round(min(height, width) * BORDER_RATIO)))


def _read_source(source: Path | str | ZipImage):
    if isinstance(source, ZipImage):
        return decode_bgr(source.read_bytes(), source.label)
    return read_bgr(source)


def examine_image(source: Path | str | ZipImage, detector) -> FaceSample | None:
    """读一张图、走定版管线，返回主脸样本；读不出或没有合格女性脸时返回 None。"""
    try:
        image = _read_source(source)
    except ValueError:
        return None
    face = main_face(detector.detect(add_white_border(image)))
    if face is None:
        return None
    origin = source if isinstance(source, ZipImage) else Path(source)
    return FaceSample(path=origin, bbox=face.bbox, embedding=face.embedding)


def save_face_crop(source: Path | str | ZipImage, bbox, destination: Path | str) -> Path:
    """按白边图坐标从原图裁出脸部区域，写到 `destination`，返回写入的路径。"""
    import cv2
    import numpy

    image = _read_source(source)
    height, width = image.shape[:2]
    border = _border_size(image)
    x1, y1, x2, y2 = bbox
    left = max(0, min(width, int(round(x1 - border))))
    top = max(0, min(height, int(round(y1 - border))))
    right = max(0, min(width, int(round(x2 - border))))
    bottom = max(0, min(height, int(round(y2 - border))))
    if right <= left or bottom <= top:
        raise ValueError("face box falls outside the source image")
    crop = image[top:bottom, left:right]
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    ok, buffer = cv2.imencode(".jpg", numpy.ascontiguousarray(crop))
    if not ok:
        raise ValueError("face crop cannot be encoded as JPEG")
    target.write_bytes(buffer.tobytes())
    return target


def _representative_path(root: Path, task_id: int, album: Path) -> Path:
    digest = hashlib.sha1(str(album).encode("utf-8")).hexdigest()[:16]
    return root / str(task_id) / f"{digest}.jpg"


def failed_album_result(album: Path | str, album_name: str, reason: str) -> AlbumResult:
    """读取失败的图集：不出分，只留下失败标记与原因。"""
    return AlbumResult(
        album_path=str(album),
        score=0.0,
        top_reference_id=None,
        valid_image_count=0,
        total_image_count=0,
        protagonist_cluster_ratio=0.0,
        tier_label=f"{words.TIER_READ_FAILED}：{reason}",
        representative_face_path="",
        album_name=album_name,
        failure_reason=reason,
    )


def score_album(album: Path | str, images, detector, references, *,
                hit_threshold: float, taste_threshold: float,
                representative_root: Path | str, task_id: int,
                album_name: str | None = None) -> AlbumResult:
    """对单个图集跑完整流程并返回结果；`references` 是 `(id, 归一化向量)`。"""
    album_path = Path(album)
    name = album_name or (_zip_stem(album_path) if _is_zip_path(album_path)
                          else album_path.name)
    try:
        return _score_album(
            album_path, name, images, detector, references,
            hit_threshold=hit_threshold, taste_threshold=taste_threshold,
            representative_root=representative_root, task_id=task_id)
    except AlbumReadError as error:
        return failed_album_result(album_path, name, error.reason)


def _score_album(album_path: Path, album_name: str, images, detector, references, *,
                 hit_threshold: float, taste_threshold: float,
                 representative_root: Path | str, task_id: int) -> AlbumResult:
    all_images = list(images)
    sampled = sample_images(all_images)
    faces: list[FaceSample] = []
    for path in sampled:
        sample = examine_image(path, detector)
        if sample is not None:
            faces.append(sample)

    total = len(all_images)
    valid = len(faces)
    if not faces:
        label = tier_label(0, 0.0, 0.0,
                           hit_threshold=hit_threshold, taste_threshold=taste_threshold)
        return AlbumResult(str(album_path), 0.0, None, 0, total, 0.0, label, "",
                           album_name=album_name)

    clusters = cluster_face_indices([face.embedding for face in faces])
    protagonist = protagonist_cluster(clusters)
    ratio = len(protagonist) / valid
    mean_vector = mean_normalized([faces[index].embedding for index in protagonist])

    scored = [(cosine(mean_vector, vector), reference_id)
              for reference_id, vector in references]
    score, top_reference_id = max(scored, key=lambda item: (item[0], -item[1]))
    top_vector = next(vector for reference_id, vector in references
                      if reference_id == top_reference_id)

    best_index = max(protagonist, key=lambda index: cosine(faces[index].embedding, top_vector))
    destination = _representative_path(Path(representative_root), task_id, album_path)
    crop = save_face_crop(faces[best_index].path, faces[best_index].bbox, destination)

    label = tier_label(valid, score, ratio,
                       hit_threshold=hit_threshold, taste_threshold=taste_threshold)
    return AlbumResult(
        album_path=str(album_path),
        score=score,
        top_reference_id=top_reference_id,
        valid_image_count=valid,
        total_image_count=total,
        protagonist_cluster_ratio=ratio,
        tier_label=label,
        representative_face_path=str(crop),
        album_name=album_name,
    )


class PhotoFilterScorer:
    """把参考对象、检测器与任务表串起来的打分服务。

    `store` 是第 2 步的 `ReferenceStore`，任务的读写与参考向量都从它取；
    `detector_factory` 留给出测试注入替身，默认复用参考对象那套检测器。
    """

    def __init__(self, store: ReferenceStore, *,
                 representative_root: Path | str,
                 detector_factory=None) -> None:
        self.store = store
        self.representative_root = Path(representative_root)
        self.detector_factory = detector_factory

    def _detector(self):
        if self.detector_factory is not None:
            return self.detector_factory()
        return self.store.detector()

    def _references(self) -> list[tuple[int, object]]:
        return [(reference.id, reference.vector())
                for reference in self.store.list()
                if reference.ready and reference.embedding is not None]

    def _clear_results(self, task_id: int) -> None:
        with self.store.ledger.write_transaction() as connection:
            connection.execute(
                "DELETE FROM photo_filter_result WHERE task_id=?", (task_id,))

    def _insert_result(self, task_id: int, result: AlbumResult) -> None:
        with self.store.ledger.write_transaction() as connection:
            connection.execute(
                "INSERT INTO photo_filter_result(created_at,task_id,album_path,score,"
                "top_reference_id,valid_image_count,total_image_count,"
                "protagonist_cluster_ratio,tier_label,representative_face_path) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_now(), task_id, result.album_path, result.score,
                 result.top_reference_id, result.valid_image_count,
                 result.total_image_count, result.protagonist_cluster_ratio,
                 result.tier_label, result.representative_face_path))

    def score_task(self, task_id: int, *, progress=None) -> ScoreRun:
        """跑完一个任务；每处理一集更新进度，发现已取消就停。"""
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"filter task does not exist: {task_id}")
        references = self._references()
        if not references:
            raise ValueError("no ready photo filter reference to score against")
        root = Path(task.root_path)
        if not root.is_dir():
            raise FileNotFoundError(f"filter task root does not exist: {root}")

        detector = self._detector()
        albums = discover_albums(root)
        album_names = album_display_names(albums)
        self._clear_results(task_id)
        self.store.update_task(task_id, status=TASK_RUNNING,
                               processed_count=0, total_count=len(albums))

        results: list[AlbumResult] = []
        cancelled = False
        try:
            for index, album in enumerate(albums, 1):
                current = self.store.get_task(task_id)
                if current is None or current.status == TASK_CANCELLED:
                    cancelled = True
                    break
                name = album_names[album]
                try:
                    result = score_album(
                        album, album_images(album), detector, references,
                        hit_threshold=task.hit_threshold,
                        taste_threshold=task.taste_threshold,
                        representative_root=self.representative_root,
                        task_id=task_id, album_name=name)
                except AlbumReadError as error:
                    result = failed_album_result(album, name, error.reason)
                self._insert_result(task_id, result)
                results.append(result)
                updated = self.store.update_task(task_id, processed_count=index)
                if progress is not None:
                    progress(updated, result)
            final = self.store.get_task(task_id)
            if final is not None and final.status != TASK_CANCELLED:
                self.store.update_task(task_id, status=TASK_COMPLETED,
                                       processed_count=len(results),
                                       total_count=len(albums))
            else:
                cancelled = True
        except Exception:
            self.store.update_task(task_id, status=TASK_FAILED)
            raise
        return ScoreRun(task_id, len(results), len(albums), cancelled, tuple(results))
