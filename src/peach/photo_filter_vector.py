"""写真筛选的参考向量构建。

每位参考对象用若干张照片在本地建一张「向量身份证」：InsightFace buffalo_l（SCRFD 检测 +
ArcFace 512 维向量），逐人建向量、绝不把多位对象的脸混在一起平均。这里只做计算，不碰
账本；调用方（`photo_filter_references`）负责把结果存进 `photo_filter_reference`。

参数来自真机试点定版，写死不暴露成设置：

- 检测前给图片加白边，边宽是短边的 15%。紧特写不加边时大量漏检。
- 只留女性脸，用 buffalo_l 自带的 genderage 属性判定。
- 人脸框短边 ≥ 80px 才计入。
- 每张图只取面积最大的那张合格女性脸。
- 全部有效脸的向量取均值并归一化，得到对象级的一个向量。
- 有效脸少于 3 张直接失败，不生成向量、不拿不足样本硬凑。

模型与推理全部在本机完成：模型目录由设置提供（`photo_filter.model_root`），缺失时抛出
带路径与文件清单的明确错误；构造检测器时只传本地目录，InsightFace 不会走取模型的网络
分支。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .photo_filter_words import INSUFFICIENT_FACES

#: 对象向量的维度，与 ArcFace buffalo_l 一致。
EMBEDDING_DIM = 512
#: 送检前白边宽度占图片短边的比例。
BORDER_RATIO = 0.15
#: 人脸框短边下限（像素）。
MIN_FACE_SHORT_SIDE = 80
#: 建成一个对象向量所需的最少有效脸数。
MIN_VALID_FACES = 3
#: buffalo_l 必需的三个模型文件：SCRFD 检测、ArcFace 识别、性别年龄。
REQUIRED_MODEL_FILES = ("det_10g.onnx", "w600k_r50.onnx", "genderage.onnx")
#: 模型目录候选：设置可以直接指向 buffalo_l，也可以指向它的父目录。
MODEL_DIR_CANDIDATES = ("", "buffalo_l", "models/buffalo_l")
#: 推理时送进 SCRFD 的尺寸，沿用 InsightFace 示例的常见值。
DETECT_SIZE = (640, 640)


class PhotoFilterModelUnavailable(RuntimeError):
    """模型目录缺失或 InsightFace 运行环境不可用。"""


@dataclass(frozen=True)
class DetectedFace:
    """一张检出的人脸：原图坐标框、是否女性、以及 512 维向量。"""

    bbox: tuple[float, float, float, float]
    female: bool
    embedding: object | None

    @property
    def short_side(self) -> float:
        return min(self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0]) * max(0.0, self.bbox[3] - self.bbox[1])


@dataclass(frozen=True)
class VectorBuild:
    """一次对象级构建的结果；失败时 `embedding` 为 None、`failure_reason` 写给用户看。"""

    embedding: object | None
    valid_face_count: int
    provider: str
    failure_reason: str = ""

    @property
    def ok(self) -> bool:
        return self.embedding is not None


class FaceDetector(Protocol):
    """检测器接口。生产实现是 `InsightFaceDetector`，测试可注入轻量替身。"""

    provider: str

    def detect(self, image) -> list[DetectedFace]:
        """返回一张 BGR 图里的全部人脸（已带向量）。"""


def add_white_border(image):
    """在四周加白边；边宽 = 图片短边的 15%。"""
    import numpy

    height, width = image.shape[:2]
    border = max(1, int(round(min(height, width) * BORDER_RATIO)))
    if image.ndim == 2:
        shape = (height + 2 * border, width + 2 * border)
    else:
        shape = (height + 2 * border, width + 2 * border, image.shape[2])
    bordered = numpy.full(shape, 255, dtype=image.dtype)
    bordered[border:border + height, border:border + width] = image
    return bordered


def eligible_faces(faces: list[DetectedFace]) -> list[DetectedFace]:
    """合格女性脸：女性、框短边够大、且有可用的向量。"""
    return [face for face in faces
            if face.female and face.short_side >= MIN_FACE_SHORT_SIDE
            and face.embedding is not None]


def main_face(faces: list[DetectedFace]) -> DetectedFace | None:
    """单图主角：合格女性脸里面积最大的那一张；没有就返回 None。"""
    eligible = eligible_faces(faces)
    return max(eligible, key=lambda face: face.area) if eligible else None


def mean_normalized(embeddings) -> object:
    """全体向量取均值并归一化，返回 float32 的一维数组。"""
    import numpy

    stack = numpy.asarray([numpy.asarray(item, dtype=numpy.float64).reshape(-1)
                           for item in embeddings], dtype=numpy.float64)
    if stack.ndim != 2 or stack.shape[1] != EMBEDDING_DIM:
        raise ValueError(f"embedding dimension must be {EMBEDDING_DIM}, got {stack.shape}")
    mean = stack.mean(axis=0)
    norm = float(numpy.linalg.norm(mean))
    if norm == 0:
        raise ValueError("object embedding is a zero vector and cannot be normalized")
    return (mean / norm).astype(numpy.float32)


def read_bgr(path: Path | str):
    """读取 BGR 图片；中文路径可用，解码失败时抛 `ValueError`。"""
    import cv2
    import numpy

    try:
        payload = Path(path).read_bytes()
    except OSError as error:
        raise ValueError(f"reference photo is unreadable: {path}") from error
    image = cv2.imdecode(numpy.frombuffer(payload, numpy.uint8), cv2.IMREAD_COLOR)
    if image is None or not image.size:
        raise ValueError(f"reference photo cannot be decoded: {path}")
    return image


def build_reference_vector(photo_paths, detector: FaceDetector) -> VectorBuild:
    """按定版参数从照片集合建一个对象向量。"""
    embeddings = []
    for path in photo_paths:
        image = add_white_border(read_bgr(path))
        face = main_face(detector.detect(image))
        if face is not None:
            embeddings.append(face.embedding)
    provider = str(getattr(detector, "provider", "") or "")
    if len(embeddings) < MIN_VALID_FACES:
        return VectorBuild(
            None, len(embeddings), provider,
            INSUFFICIENT_FACES.format(count=len(embeddings), needed=MIN_VALID_FACES))
    return VectorBuild(mean_normalized(embeddings), len(embeddings), provider)


def resolve_model_dir(model_root: Path | str) -> Path:
    """在设置给的目录下找到 buffalo_l 并核对必需文件；找不到就带指引报错。"""
    root = Path(model_root).expanduser()
    for relative in MODEL_DIR_CANDIDATES:
        candidate = root / relative if relative else root
        if candidate.is_dir() and all((candidate / name).is_file()
                                       for name in REQUIRED_MODEL_FILES):
            return candidate
    required = ", ".join(REQUIRED_MODEL_FILES)
    raise PhotoFilterModelUnavailable(
        f"InsightFace buffalo_l model directory not found: {root}. "
        f"Point [photo_filter] model_root at a buffalo_l folder containing {required}; "
        "the model files are not shipped with the repository."
    )


class InsightFaceDetector:
    """生产检测器：InsightFace buffalo_l，优先 CUDA，回退 CPU。"""

    def __init__(self, model_root: Path | str) -> None:
        try:
            import insightface
            import onnxruntime
        except ModuleNotFoundError as error:
            raise PhotoFilterModelUnavailable(
                "Photo filtering requires InsightFace and onnxruntime; install the "
                "project's photo-filter extra and retry."
            ) from error
        self.model_dir = resolve_model_dir(model_root)
        available = set(onnxruntime.get_available_providers())
        chosen = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                  if "CUDAExecutionProvider" in available else ["CPUExecutionProvider"])
        self._app = insightface.app.FaceAnalysis(
            name=str(self.model_dir),
            root=str(Path(model_root).expanduser()),
            allowed_modules=["detection", "recognition", "genderage"],
            providers=chosen,
        )
        self._app.prepare(ctx_id=0 if chosen[0] == "CUDAExecutionProvider" else -1,
                          det_size=DETECT_SIZE)
        self.provider = self._actual_provider(chosen[0])

    def _actual_provider(self, fallback: str) -> str:
        model = self._app.models.get("detection")
        for attribute in ("main_session", "session"):
            session = getattr(model, attribute, None)
            getters = getattr(session, "get_providers", None)
            if callable(getters):
                names = getters()
                if names:
                    return str(names[0])
        return fallback

    def detect(self, image) -> list[DetectedFace]:
        faces = []
        for face in self._app.get(image):
            bbox = tuple(float(value) for value in face.bbox[:4])
            embedding = getattr(face, "embedding", None)
            faces.append(DetectedFace(
                bbox=bbox,
                female=getattr(face, "sex", None) == "F",
                embedding=embedding,
            ))
        return faces
