"""写真筛选的 HTTP 薄封装：参考对象、上传、设置读取、任务与代表脸。

真实 InsightsFace 推理不在测试里跑；确定性替身让参考向量与图集打分走同一条服务层
编排。所有读写落在临时账本与临时目录，验证路由只做参数校验与转发，不改服务层语义。
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy

from support.ledger import fresh_ledger


def write_image(path: Path) -> Path:
    import cv2

    image = numpy.full((80, 100, 3), 128, dtype=numpy.uint8)
    image[40, 50] = (200, 0, 0)
    assert cv2.imwrite(str(path), image)
    return path


class StaticDetector:
    provider = "CPUExecutionProvider"

    def detect(self, image):
        from peach.photo_filter_vector import DetectedFace, EMBEDDING_DIM

        return [DetectedFace(bbox=(20.0, 10.0, 110.0, 100.0), female=True,
                             embedding=numpy.ones(EMBEDDING_DIM, dtype=numpy.float32))]


@unittest.skipUnless(__import__("importlib").util.find_spec("fastapi"), "FastAPI 尚未安装")
class PhotoFilterRouteTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from peach.api import create_app
        from peach.config import PeachSettings

        self.folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.database = fresh_ledger(self.folder)
        self.app = create_app(PeachSettings(
            db_path=self.database, configured=True, token="secret",
            photo_filter_reference_root=self.folder / "references",
            photo_filter_results_root=self.folder / "results",
            photo_filter_upload_root=self.folder / "uploads"))
        self.contract = self.app.state.web_contract
        self.contract.photo_filter_detector_factory = StaticDetector
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def post(self, path, **kwargs):
        return self.client.post(f"{path}?t=secret", **kwargs)

    def get(self, path):
        joiner = "&" if "?" in path else "?"
        return self.client.get(f"{path}{joiner}t=secret")

    def upload_photos(self, count: int) -> str:
        token = self.post("/api/photo-filter/uploads").json()["token"]
        for index in range(count):
            source = write_image(self.folder / f"upload-{index}.png")
            response = self.post(
                f"/api/photo-filter/uploads/{token}",
                content=source.read_bytes(),
                headers={"X-Peach-Filename": source.name})
            self.assertEqual(response.status_code, 200, response.text)
        return token

    def create_reference(self, name="参考一", count=5):
        token = self.upload_photos(count)
        return self.post("/api/photo-filter/references",
                         json={"name": name, "upload_token": token})

    def test_references_start_empty_and_a_full_upload_builds_a_vector(self):
        self.assertEqual(self.get("/api/photo-filter/references").json(), {"references": []})
        created = self.create_reference()
        self.assertEqual(created.status_code, 200, created.text)
        reference = created.json()
        self.assertEqual(reference["status"], "ready")
        self.assertEqual(reference["valid_face_count"], 5)
        listed = self.get("/api/photo-filter/references").json()["references"]
        self.assertEqual([item["name"] for item in listed], ["参考一"])
        self.assertEqual(listed[0]["valid_face_count"], 5)

    def test_too_few_photos_are_rejected_before_a_vector_is_built(self):
        response = self.create_reference(count=4)
        self.assertEqual(response.status_code, 400)
        self.assertIn("5-15", response.json()["error"])
        self.assertEqual(self.get("/api/photo-filter/references").json()["references"], [])

    def test_rebuild_and_delete_reference(self):
        reference = self.create_reference().json()
        rebuilt = self.post(f"/api/photo-filter/references/{reference['id']}/rebuild")
        self.assertEqual(rebuilt.status_code, 200, rebuilt.text)
        self.assertEqual(rebuilt.json()["status"], "ready")
        deleted = self.client.delete(
            f"/api/photo-filter/references/{reference['id']}?t=secret")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["ok"])
        self.assertEqual(self.get("/api/photo-filter/references").json()["references"], [])

    def test_task_scores_albums_and_serves_the_representative_face(self):
        self.create_reference()
        root = self.folder / "albums"
        for album in ("album-a", "album-b"):
            folder = root / album
            folder.mkdir(parents=True)
            for index in range(6):
                write_image(folder / f"{index}.png")
        created = self.post("/api/photo-filter/tasks",
                            json={"root_path": str(root), "hit_threshold": 0.5,
                                  "taste_threshold": 0.3})
        self.assertEqual(created.status_code, 200, created.text)
        task = created.json()
        from peach import photo_filter_api
        photo_filter_api.wait_for_task(task["id"], timeout=20)

        detail = self.get(f"/api/photo-filter/tasks/{task['id']}").json()
        self.assertEqual(detail["task"]["status"], "completed")
        self.assertEqual(detail["task"]["processed_count"], 2)
        self.assertEqual(detail["task"]["total_count"], 2)
        self.assertEqual(len(detail["results"]), 2)
        first = detail["results"][0]
        self.assertEqual(first["tier"], "hit")
        self.assertAlmostEqual(first["score"], 1.0, places=5)
        self.assertEqual(first["top_reference_name"], "参考一")
        self.assertTrue(first["face_url"].startswith("/photo-filter-face?result="))

        face = self.get(first["face_url"])
        self.assertEqual(face.status_code, 200)
        self.assertEqual(face.headers["content-type"], "image/jpeg")

        listed = self.get("/api/photo-filter/tasks").json()["tasks"]
        self.assertEqual(listed[0]["result_count"], 2)

        revealed = self.post("/api/photo-filter/reveal", json={"result_id": first["id"]})
        self.assertEqual(revealed.status_code, 200, revealed.text)
        self.assertTrue(revealed.json()["ok"])

    def test_zip_albums_expose_distinct_names_and_failures(self):
        self.create_reference()
        root = self.folder / "zip-albums"
        folder = root / "same"
        folder.mkdir(parents=True)
        for index in range(6):
            write_image(folder / f"{index}.png")
        with zipfile.ZipFile(root / "same.zip", "w") as archive:
            for index in range(6):
                archive.write(folder / f"{index}.png", f"nested/{index}.png")
        broken = root / "broken.zip"
        with zipfile.ZipFile(broken, "w") as archive:
            archive.writestr("01.png", b"truncated later")
        payload = broken.read_bytes()
        broken.write_bytes(payload[:max(1, len(payload) // 2)])

        created = self.post("/api/photo-filter/tasks", json={
            "root_path": str(root), "hit_threshold": 0.5, "taste_threshold": 0.3})
        self.assertEqual(created.status_code, 200, created.text)
        task = created.json()
        from peach import photo_filter_api
        photo_filter_api.wait_for_task(task["id"], timeout=20)

        detail = self.get(f"/api/photo-filter/tasks/{task['id']}").json()
        self.assertEqual(detail["task"]["status"], "completed")
        self.assertEqual((detail["task"]["processed_count"], detail["task"]["total_count"]), (3, 3))
        results = {result["album_name"]: result for result in detail["results"]}
        self.assertEqual(set(results), {"same", "same (zip)", "broken"})
        self.assertEqual(results["same"]["tier"], "hit")
        self.assertEqual(results["same (zip)"]["tier"], "hit")
        self.assertAlmostEqual(results["same (zip)"]["score"], 1.0, places=5)
        self.assertEqual(results["broken"]["tier"], "failed")
        self.assertTrue(results["broken"]["failure_reason"])

    def test_cancel_marks_a_pending_task(self):
        from peach.photo_filter_references import ReferenceStore

        store = ReferenceStore(self.contract.database,
                               reference_root=self.contract.photo_filter_reference_root,
                               detector_factory=StaticDetector)
        task = store.create_task(str(self.folder))
        cancelled = self.post(f"/api/photo-filter/tasks/{task.id}/cancel")
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "cancelled")

    def test_missing_task_and_result_are_404(self):
        self.assertEqual(self.get("/api/photo-filter/tasks/999").status_code, 404)
        self.assertEqual(
            self.post("/api/photo-filter/reveal", json={"result_id": 999}).status_code, 404)

    def test_settings_payload_reports_a_missing_model_directory(self):
        out = self.get("/api/photo-filter/settings").json()
        self.assertIn("model_root", out)
        self.assertIn("model_ready", out)
        self.assertIn("cuda_available", out)
        self.assertFalse(out["model_ready"])


if __name__ == "__main__":
    unittest.main()
