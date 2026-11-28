"""写真筛选的数据层与参考向量构建。

真实的 InsightFace 推理需要 buffalo_l 模型，不在仓库里；这里用确定性替身驱动同一套
编排（白边、女性过滤、质量门、单图取最大、均值归一化、有效脸下限），并把 CRUD 全链路
跑在临时账本与临时目录上。模型目录解析与错误指引直接测真实函数。
"""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from peach import photo_filter_references as references
from peach import photo_filter_vector as vector
from peach.photo_filter_vector import DetectedFace
from peach.repository import LedgerDatabase
from support.ledger import fresh_ledger


def write_image(path: Path, *, width: int = 100, height: int = 80) -> Path:
    import cv2
    import numpy

    image = numpy.full((height, width, 3), 128, dtype=numpy.uint8)
    assert cv2.imwrite(str(path), image)
    return path


def face(*, female: bool = True, size: float = 120.0, fill: float = 1.0) -> DetectedFace:
    import numpy

    return DetectedFace(bbox=(0.0, 0.0, size, size), female=female,
                        embedding=numpy.full(vector.EMBEDDING_DIM, fill, dtype=numpy.float32))


class FakeDetector:
    provider = "CPUExecutionProvider"

    def __init__(self, per_image):
        self.per_image = list(per_image)
        self.calls = 0
        self.shapes = []

    def detect(self, image):
        self.shapes.append(image.shape)
        index = self.calls
        self.calls += 1
        return self.per_image[index] if index < len(self.per_image) else []


class BorderAndSelectionTests(unittest.TestCase):
    def test_white_border_is_fifteen_percent_of_the_short_side(self):
        import numpy

        image = numpy.full((80, 100, 3), 10, dtype=numpy.uint8)
        bordered = vector.add_white_border(image)
        border = round(80 * 0.15)
        self.assertEqual(bordered.shape, (80 + 2 * border, 100 + 2 * border, 3))
        self.assertTrue((bordered[:border] == 255).all())
        self.assertTrue((bordered[border:border + 80, border:border + 100] == 10).all())

    def test_only_large_enough_female_faces_with_vectors_are_eligible(self):
        male = face(female=False, size=400)
        tiny = face(size=50)
        no_vector = DetectedFace(bbox=(0, 0, 300, 300), female=True, embedding=None)
        medium = face(size=90, fill=2.0)
        large = face(size=150, fill=3.0)
        chosen = vector.main_face([male, tiny, no_vector, medium, large])
        self.assertIs(chosen, large)
        self.assertIsNone(vector.main_face([male, tiny, no_vector]))

    def test_object_vector_is_the_normalized_mean(self):
        import numpy

        result = vector.mean_normalized([
            numpy.full(vector.EMBEDDING_DIM, 1.0),
            numpy.full(vector.EMBEDDING_DIM, 3.0),
        ])
        self.assertEqual(result.shape, (vector.EMBEDDING_DIM,))
        self.assertAlmostEqual(float(numpy.linalg.norm(result)), 1.0, places=5)
        self.assertAlmostEqual(float(result[0]), 1.0 / numpy.sqrt(vector.EMBEDDING_DIM), places=5)


class BuildPipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def images(self, count: int):
        return [write_image(self.root / f"{index}.png") for index in range(count)]

    def test_build_reads_bordered_images_and_collects_one_face_per_photo(self):
        paths = self.images(3)
        detector = FakeDetector([[face()], [face()], [face()]])
        build = vector.build_reference_vector(paths, detector)
        self.assertTrue(build.ok)
        self.assertEqual(build.valid_face_count, 3)
        self.assertEqual(build.provider, "CPUExecutionProvider")
        border = round(80 * 0.15)
        self.assertEqual(detector.shapes[0], (80 + 2 * border, 100 + 2 * border, 3))

    def test_two_valid_faces_fail_with_a_clear_reason_and_no_vector(self):
        paths = self.images(3)
        detector = FakeDetector([[face()], [face()], []])
        build = vector.build_reference_vector(paths, detector)
        self.assertFalse(build.ok)
        self.assertIsNone(build.embedding)
        self.assertEqual(build.valid_face_count, 2)
        self.assertEqual(build.failure_reason, "有效脸不足（2 张，需 ≥3）")

    def test_male_and_small_faces_do_not_count_as_valid(self):
        paths = self.images(3)
        detector = FakeDetector([[face(female=False, size=400)], [face(size=20)], [face(size=200)]])
        build = vector.build_reference_vector(paths, detector)
        self.assertFalse(build.ok)
        self.assertEqual(build.failure_reason, "有效脸不足（1 张，需 ≥3）")


class ModelDirectoryTests(unittest.TestCase):
    def test_missing_model_directory_names_the_files_and_setting(self):
        with tempfile.TemporaryDirectory() as holder:
            with self.assertRaises(vector.PhotoFilterModelUnavailable) as caught:
                vector.resolve_model_dir(Path(holder))
        message = str(caught.exception)
        self.assertIn("buffalo_l", message)
        self.assertIn("det_10g.onnx", message)
        self.assertIn("model_root", message)

    def test_model_directory_can_be_the_buffalo_folder_or_its_parent(self):
        with tempfile.TemporaryDirectory() as holder:
            root = Path(holder)
            folder = root / "models" / "buffalo_l"
            folder.mkdir(parents=True)
            for name in vector.REQUIRED_MODEL_FILES:
                (folder / name).write_bytes(b"")
            self.assertEqual(vector.resolve_model_dir(root), folder)
            self.assertEqual(vector.resolve_model_dir(folder), folder)


class ReferenceStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.db = fresh_ledger(self.root)
        self.ledger = LedgerDatabase(self.db)
        self.reference_root = self.root / "references"
        self.sources = [write_image(self.root / f"source-{index}.png") for index in range(3)]

    def store(self, detector):
        return references.ReferenceStore(
            self.ledger, reference_root=self.reference_root,
            detector_factory=lambda: detector)

    def test_create_builds_ready_reference_and_copies_photos_without_touching_sources(self):
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in self.sources]
        store = self.store(FakeDetector([[face()], [face()], [face()]]))
        reference = store.create("参考一", self.sources)
        self.assertEqual(reference.status, references.REFERENCE_READY)
        self.assertEqual(reference.valid_face_count, 3)
        self.assertEqual(reference.provider, "CPUExecutionProvider")
        self.assertTrue(reference.ready)
        self.assertEqual(reference.vector().shape, (vector.EMBEDDING_DIM,))
        self.assertAlmostEqual(float((reference.vector() ** 2).sum()) ** 0.5, 1.0, places=5)

        copies = store.photo_paths(reference.id)
        self.assertEqual(len(copies), 3)
        self.assertTrue(all(path.parent.name == reference.storage_subdir for path in copies))
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in self.sources], before)
        self.assertEqual([item.id for item in store.list()], [reference.id])
        self.assertEqual(store.get(reference.id).name, "参考一")

    def test_insufficient_faces_keep_the_reference_without_a_vector(self):
        store = self.store(FakeDetector([[face()], [face()], []]))
        reference = store.create("样本不足", self.sources)
        self.assertEqual(reference.status, references.REFERENCE_FAILED)
        self.assertEqual(reference.valid_face_count, 2)
        self.assertIsNone(reference.embedding)
        self.assertIsNone(reference.vector())
        self.assertEqual(reference.failure_reason, "有效脸不足（2 张，需 ≥3）")
        self.assertEqual(len(store.photo_paths(reference.id)), 3)

    def test_rebuild_uses_saved_copies_after_sources_are_gone(self):
        first = self.store(FakeDetector([[face()], [], []]))
        reference = first.create("重建", self.sources)
        self.assertEqual(reference.status, references.REFERENCE_FAILED)
        for path in self.sources:
            path.unlink()

        second_detector = FakeDetector([[face()], [face()], [face()]])
        rebuilt = self.store(second_detector).rebuild(reference.id)
        self.assertEqual(rebuilt.status, references.REFERENCE_READY)
        self.assertEqual(rebuilt.valid_face_count, 3)
        self.assertEqual(second_detector.calls, 3)

    def test_delete_removes_the_vector_and_photo_copies(self):
        store = self.store(FakeDetector([[face()], [face()], [face()]]))
        reference = store.create("待删", self.sources)
        folder = self.reference_root / reference.storage_subdir
        self.assertTrue(folder.is_dir())
        self.assertTrue(store.delete(reference.id))
        self.assertFalse(folder.exists())
        self.assertIsNone(store.get(reference.id))
        self.assertEqual(store.list(), [])
        self.assertFalse(store.delete(reference.id))

    def test_deleting_a_reference_clears_it_from_existing_results(self):
        store = self.store(FakeDetector([[face()], [face()], [face()]]))
        reference = store.create("被引用", self.sources)
        task = store.create_task(r"D:\albums")
        with self.ledger.write_transaction() as connection:
            connection.execute(
                "INSERT INTO photo_filter_result(created_at,task_id,album_path,score,"
                "top_reference_id,tier_label) VALUES('now',?,?,?,?,?)",
                (task.id, r"D:\albums\a", 0.9, reference.id, "hit"))
        store.delete(reference.id)
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                "SELECT top_reference_id FROM photo_filter_result").fetchone()
        self.assertIsNone(row["top_reference_id"])


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.ledger = LedgerDatabase(fresh_ledger(self.root))
        self.store = references.ReferenceStore(
            self.ledger, reference_root=self.root / "references",
            detector_factory=lambda: FakeDetector([]))

    def test_task_defaults_and_basic_read_write(self):
        task = self.store.create_task(r"D:\albums")
        self.assertEqual(task.status, references.TASK_PENDING)
        self.assertEqual(task.processed_count, 0)
        self.assertEqual(task.total_count, 0)
        self.assertAlmostEqual(task.hit_threshold, 0.50)
        self.assertAlmostEqual(task.taste_threshold, 0.30)

        updated = self.store.update_task(
            task.id, status=references.TASK_RUNNING, processed_count=2, total_count=5)
        self.assertEqual(updated.status, references.TASK_RUNNING)
        self.assertEqual((updated.processed_count, updated.total_count), (2, 5))
        self.assertEqual([item.id for item in self.store.list_tasks()], [task.id])
        self.assertEqual(self.store.get_task(task.id).root_path, r"D:\albums")

    def test_unknown_status_and_empty_root_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.create_task(" ")
        task = self.store.create_task(r"D:\albums")
        with self.assertRaises(ValueError):
            self.store.update_task(task.id, status="done")

    def test_task_delete_removes_its_results(self):
        task = self.store.create_task(r"D:\albums")
        with self.ledger.write_transaction() as connection:
            connection.execute(
                "INSERT INTO photo_filter_result(created_at,task_id,album_path,score,tier_label) "
                "VALUES('now',?,?,?,?)", (task.id, r"D:\albums\a", 0.9, "hit"))
            connection.execute("DELETE FROM photo_filter_task WHERE id=?", (task.id,))
        with self.ledger.read_connection() as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM photo_filter_result").fetchone()[0], 0)


class MigrationSchemaTests(unittest.TestCase):
    def test_photo_filter_tables_exist_with_the_documented_semantics(self):
        with tempfile.TemporaryDirectory() as holder:
            db = fresh_ledger(Path(holder))
            with closing(sqlite3.connect(db)) as connection:
                columns = {table: [row[1] for row in connection.execute(
                    f"PRAGMA table_info({table})")] for table in (
                        "photo_filter_reference", "photo_filter_task", "photo_filter_result")}
                triggers = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'")}
                revisions = {row[0] for row in connection.execute(
                    "SELECT tbl FROM ledger_revision")}
        self.assertEqual(columns["photo_filter_reference"][:3], ["id", "name", "created_at"])
        self.assertIn("embedding", columns["photo_filter_reference"])
        self.assertIn("valid_face_count", columns["photo_filter_reference"])
        self.assertIn("failure_reason", columns["photo_filter_reference"])
        self.assertIn("storage_subdir", columns["photo_filter_reference"])
        self.assertEqual(
            columns["photo_filter_task"][2:],
            ["updated_at", "root_path", "status", "processed_count", "total_count",
             "hit_threshold", "taste_threshold"])
        for column in ("task_id", "album_path", "score", "top_reference_id",
                       "valid_image_count", "total_image_count", "protagonist_cluster_ratio",
                       "tier_label", "representative_face_path"):
            self.assertIn(column, columns["photo_filter_result"])
        for table in columns:
            self.assertIn(table, revisions)
            for event in ("insert", "update", "delete"):
                self.assertIn(f"rev_{table}_{event}", triggers)


if __name__ == "__main__":
    unittest.main()
