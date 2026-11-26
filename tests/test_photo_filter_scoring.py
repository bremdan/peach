"""写真筛选的打分：抽样、聚簇、五层边界、主角加注与任务全链路。

真实 InsightFace 推理需要 buffalo_l 模型，不在仓库里；这里用一张图中心像素当标记的
确定性检测器驱动同一条管线（读图、加白边、取最大合格女性脸），聚簇与分层则直接用构造
向量验证边界。任务全链路跑在临时账本、临时图集与临时代表图目录上。
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import numpy

from peach import photo_filter_references as references
from peach import photo_filter_scoring as scoring
from peach import photo_filter_vector as vector
from peach import photo_filter_words as words
from peach.photo_filter_vector import DetectedFace
from peach.repository import LedgerDatabase
from support.ledger import fresh_ledger


def basis(index: int):
    value = numpy.zeros(vector.EMBEDDING_DIM, dtype=numpy.float32)
    value[index] = 1.0
    return value


def blend(weight: float, first: int, second: int):
    """和 `basis(first)` 的余弦正好是 `weight` 的单位向量。"""
    value = weight * basis(first) + numpy.sqrt(1 - weight * weight) * basis(second)
    return value.astype(numpy.float32)


def write_marked_image(path: Path, marker: int) -> Path:
    import cv2

    image = numpy.full((80, 100, 3), 128, dtype=numpy.uint8)
    image[40, 50] = (marker, 0, 0)
    assert cv2.imwrite(str(path), image)
    return path


class MarkerDetector:
    """按图片中心像素选向量，走真实的读图与加白边链路。"""

    provider = "CPUExecutionProvider"

    def __init__(self, mapping):
        self.mapping = mapping

    def detect(self, image):
        height, width = image.shape[:2]
        pixel = tuple(int(value) for value in image[height // 2, width // 2])
        embedding = self.mapping.get(pixel)
        if embedding is None:
            return []
        return [DetectedFace(bbox=(20.0, 10.0, 110.0, 100.0),
                             female=True, embedding=embedding)]


class SamplingTests(unittest.TestCase):
    def test_oversized_album_is_evenly_sampled_keeping_order(self):
        images = [Path(f"{index:04d}.jpg") for index in range(250)]
        picked = scoring.sample_images(images)
        self.assertEqual(len(picked), 100)
        self.assertIs(picked[0], images[0])
        self.assertIs(picked[-1], images[-1])
        self.assertEqual(len({path.name for path in picked}), 100)
        positions = [images.index(path) for path in picked]
        self.assertEqual(positions, sorted(positions))

    def test_album_at_the_limit_is_returned_in_full(self):
        images = [Path(f"{index}.jpg") for index in range(100)]
        self.assertEqual(scoring.sample_images(images), images)


class ClusterTests(unittest.TestCase):
    def test_greedy_clustering_joins_similar_vectors_and_splits_others(self):
        first = basis(0)
        near = blend(0.9, 0, 1)
        other = basis(2)
        clusters = scoring.cluster_face_indices([first, near, other])
        self.assertEqual([sorted(members) for members in clusters], [[0, 1], [2]])
        self.assertEqual(scoring.protagonist_cluster(clusters), [0, 1])

    def test_largest_cluster_wins_and_ties_go_to_the_earlier_one(self):
        self.assertEqual(scoring.protagonist_cluster([[0], [1, 2]]), [1, 2])
        self.assertEqual(scoring.protagonist_cluster([[0, 1], [2, 3]]), [0, 1])


class TierTests(unittest.TestCase):
    def tier(self, valid: int, score: float) -> str:
        return scoring.tier_for(valid, score, hit_threshold=0.50, taste_threshold=0.30)

    def test_five_tiers_and_their_boundaries(self):
        self.assertEqual(self.tier(5, 0.50), words.TIER_HIT)
        self.assertEqual(self.tier(5, 0.4999), words.TIER_TASTE)
        self.assertEqual(self.tier(5, 0.30), words.TIER_TASTE)
        self.assertEqual(self.tier(5, 0.2999), words.TIER_MISS)
        self.assertEqual(self.tier(4, 0.50), words.TIER_SUSPECTED)
        self.assertEqual(self.tier(4, 0.4999), words.TIER_INSUFFICIENT)
        self.assertEqual(self.tier(4, 0.30), words.TIER_INSUFFICIENT)

    def test_low_protagonist_ratio_only_annotates_when_faces_exist(self):
        label = scoring.tier_label(5, 0.8, 0.4,
                                   hit_threshold=0.50, taste_threshold=0.30)
        self.assertTrue(label.startswith(words.TIER_HIT))
        self.assertIn(words.PROTAGONIST_SPREAD, label)
        self.assertEqual(
            scoring.tier_label(5, 0.8, 0.5, hit_threshold=0.50, taste_threshold=0.30),
            words.TIER_HIT)
        self.assertEqual(
            scoring.tier_label(0, 0.0, 0.0, hit_threshold=0.50, taste_threshold=0.30),
            words.TIER_INSUFFICIENT)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def test_direct_subfolders_are_albums_and_images_are_recursive(self):
        (self.root / "b" / "deep").mkdir(parents=True)
        (self.root / "a").mkdir()
        (self.root / "c").mkdir()
        write_marked_image(self.root / "a" / "y.jpg", 10)
        write_marked_image(self.root / "b" / "deep" / "x.PNG", 10)
        (self.root / "b" / "z.webp").write_bytes(b"not decoded here")
        (self.root / "loose.png").write_bytes(b"root file is not an album image")
        (self.root / "c" / "notes.txt").write_text("no images")

        self.assertEqual([path.name for path in scoring.discover_albums(self.root)],
                         ["a", "b", "c"])
        self.assertEqual([path.name for path in scoring.album_images(self.root / "a")], ["y.jpg"])
        self.assertEqual([path.name for path in scoring.album_images(self.root / "b")],
                         ["x.PNG", "z.webp"])


class ScoringChainTests(unittest.TestCase):
    MARKERS = {
        (10, 0, 0): basis(0),
        (20, 0, 0): basis(1),
        (30, 0, 0): basis(2),
        (40, 0, 0): blend(0.4, 0, 3),
        (50, 0, 0): blend(0.1, 0, 4),
        (60, 0, 0): basis(5),
        (70, 0, 0): basis(6),
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.ledger = LedgerDatabase(fresh_ledger(self.root))
        self.reference_root = self.root / "references"
        self.representative_root = self.root / "representatives"
        self.albums = self.root / "albums"
        self.albums.mkdir()
        self.store = references.ReferenceStore(
            self.ledger, reference_root=self.reference_root,
            detector_factory=lambda: MarkerDetector(self.MARKERS))
        self.scorer = scoring.PhotoFilterScorer(
            self.store, representative_root=self.representative_root)
        self.references = {}
        for name, marker in (("甲", 10), ("乙", 20), ("丙", 30)):
            sources = [write_marked_image(self.root / f"{name}-{index}.png", marker)
                       for index in range(3)]
            self.references[name] = self.store.create(name, sources)

    def make_album(self, name: str, markers):
        folder = self.albums / name
        folder.mkdir()
        for index, marker in enumerate(markers, 1):
            write_marked_image(folder / f"{index:02d}.png", marker)
        return folder

    def build_albums(self):
        self.make_album("hit", [10] * 5)
        self.make_album("taste", [40] * 5)
        self.make_album("miss", [50] * 5)
        self.make_album("suspect", [10] * 3)
        self.make_album("insufficient", [50] * 3)
        self.make_album("spread", [10, 10, 60, 60, 70])
        (self.albums / "empty").mkdir()

    def snapshot(self):
        digest = {}
        for path in sorted(self.albums.rglob("*")):
            if path.is_file():
                stat = path.stat()
                digest[str(path.relative_to(self.albums))] = (
                    stat.st_size, stat.st_mtime_ns,
                    hashlib.sha256(path.read_bytes()).hexdigest())
        return digest

    def rows(self, task_id: int):
        with self.ledger.read_connection() as connection:
            return {Path(row["album_path"]).name: dict(row) for row in connection.execute(
                "SELECT * FROM photo_filter_result WHERE task_id=?", (task_id,))}

    def test_whole_task_scores_tiers_and_writes_results(self):
        self.build_albums()
        before = self.snapshot()
        task = self.store.create_task(str(self.albums))
        run = self.scorer.score_task(task.id)

        self.assertFalse(run.cancelled)
        self.assertEqual((run.processed_count, run.total_count), (7, 7))
        stored = self.store.get_task(task.id)
        self.assertEqual(stored.status, references.TASK_COMPLETED)

        rows = self.rows(task.id)
        self.assertEqual(set(rows), {"hit", "taste", "miss", "suspect",
                                     "insufficient", "spread", "empty"})
        hit = rows["hit"]
        self.assertEqual(hit["tier_label"], words.TIER_HIT)
        self.assertAlmostEqual(hit["score"], 1.0, places=4)
        self.assertEqual(hit["top_reference_id"], self.references["甲"].id)
        self.assertEqual((hit["valid_image_count"], hit["total_image_count"]), (5, 5))
        self.assertAlmostEqual(hit["protagonist_cluster_ratio"], 1.0, places=5)
        self.assertTrue(Path(hit["representative_face_path"]).is_file())
        self.assertTrue(Path(hit["representative_face_path"]).is_relative_to(
            self.representative_root / str(task.id)))

        taste = rows["taste"]
        self.assertEqual(taste["tier_label"], words.TIER_TASTE)
        self.assertAlmostEqual(taste["score"], 0.4, places=4)
        miss = rows["miss"]
        self.assertEqual(miss["tier_label"], words.TIER_MISS)
        self.assertAlmostEqual(miss["score"], 0.1, places=4)

        suspect = rows["suspect"]
        self.assertEqual(suspect["tier_label"], words.TIER_SUSPECTED)
        self.assertEqual(suspect["valid_image_count"], 3)
        self.assertAlmostEqual(suspect["score"], 1.0, places=4)
        insufficient = rows["insufficient"]
        self.assertEqual(insufficient["tier_label"], words.TIER_INSUFFICIENT)
        self.assertEqual(insufficient["valid_image_count"], 3)

        spread = rows["spread"]
        self.assertTrue(spread["tier_label"].startswith(words.TIER_HIT))
        self.assertIn(words.PROTAGONIST_SPREAD, spread["tier_label"])
        self.assertAlmostEqual(spread["protagonist_cluster_ratio"], 0.4, places=5)

        empty = rows["empty"]
        self.assertEqual(empty["tier_label"], words.TIER_INSUFFICIENT)
        self.assertEqual((empty["valid_image_count"], empty["total_image_count"]), (0, 0))
        self.assertIsNone(empty["top_reference_id"])
        self.assertEqual(empty["representative_face_path"], "")

        self.assertEqual(self.snapshot(), before)

    def test_cancelling_between_albums_stops_the_run(self):
        self.build_albums()
        task = self.store.create_task(str(self.albums))
        seen = []

        def cancel_after_first(updated, result):
            seen.append(Path(result.album_path).name)
            if len(seen) == 1:
                self.store.update_task(task.id, status=references.TASK_CANCELLED)

        run = self.scorer.score_task(task.id, progress=cancel_after_first)
        self.assertTrue(run.cancelled)
        self.assertEqual(run.processed_count, 1)
        self.assertEqual(seen, ["empty"])
        stored = self.store.get_task(task.id)
        self.assertEqual(stored.status, references.TASK_CANCELLED)
        self.assertEqual(stored.processed_count, 1)
        self.assertEqual(len(self.rows(task.id)), 1)

    def test_missing_references_are_reported(self):
        self.build_albums()
        (self.root / "other").mkdir()
        empty_store = references.ReferenceStore(
            LedgerDatabase(fresh_ledger(self.root / "other")),
            reference_root=self.root / "other-references",
            detector_factory=lambda: MarkerDetector(self.MARKERS))
        task = empty_store.create_task(str(self.albums))
        scorer = scoring.PhotoFilterScorer(
            empty_store, representative_root=self.root / "other-representatives")
        with self.assertRaises(ValueError):
            scorer.score_task(task.id)


if __name__ == "__main__":
    unittest.main()
