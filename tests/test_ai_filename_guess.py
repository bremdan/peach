"""AI 猜文件名的数据层：十项留痕、复核状态与作品挂接。"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from peach.ai_filename_guess import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    GUESS_FIELDS,
    PROMPT_VERSION,
    REVIEW_STATUSES,
    STATUS_ACCEPTED,
    STATUS_MODIFIED_ACCEPTED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_ROLLED_BACK,
    FilenameGuessStore,
)
from peach.repository import LedgerDatabase
from support.ledger import fresh_ledger


def insert_asset(path: Path, asset_id: int = 1) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "INSERT INTO asset(id,location,path,name,medium,size) VALUES(?,?,?,?,?,?)",
            (asset_id, "local", f"R:\\media\\{asset_id}.mp4", f"{asset_id}.mp4", "video", 1))


class GuessTraceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.db = fresh_ledger(self.root)
        self.store = FilenameGuessStore(LedgerDatabase(self.db))
        insert_asset(self.db)

    def test_record_writes_the_ten_trace_fields_and_queries_by_asset(self):
        moment = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
        guess = self.store.record(
            1, "unknown-file.mp4",
            provider="deepseek", model="deepseek-flash",
            raw_response={"choices": [{"message": {"content": "ABC-123 作品名"}}]},
            parsed_result={"code": "ABC-123", "title": "作品名"},
            confidence=0.91, route={"tier": "review"}, created_at=moment)

        self.assertEqual(guess.trace(), {
            "asset_id": 1,
            "filename": "unknown-file.mp4",
            "provider": "deepseek",
            "model": "deepseek-flash",
            "prompt_version": "filename-guess-v2",
            "raw_response": json.dumps(
                {"choices": [{"message": {"content": "ABC-123 作品名"}}]},
                ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "parsed_result": json.dumps(
                {"code": "ABC-123", "title": "作品名"},
                ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "confidence": 0.91,
            "route": '{"tier":"review"}',
            "created_at": "2026-11-27T12:00:00Z",
        })
        self.assertEqual(set(guess.trace()), set(GUESS_FIELDS))
        self.assertEqual(len(GUESS_FIELDS), 10)
        self.assertEqual(self.store.get(guess.id), guess)
        self.assertEqual(self.store.for_asset(1), [guess])
        self.assertEqual(self.store.for_asset(2), [])
        self.assertIsNone(self.store.get(999))

    def test_defaults_are_the_finalised_spec_values(self):
        guess = self.store.record(1, "sample.mp4")
        self.assertEqual(guess.provider, DEFAULT_PROVIDER)
        self.assertEqual(guess.model, DEFAULT_MODEL)
        self.assertEqual(guess.prompt_version, PROMPT_VERSION)
        self.assertEqual(guess.provider, "deepseek")
        self.assertEqual(guess.model, "deepseek-flash")
        self.assertEqual(guess.prompt_version, "filename-guess-v2")
        self.assertIsNone(guess.confidence)
        self.assertEqual((guess.raw_response, guess.parsed_result, guess.route), ("", "", ""))

    def test_asset_query_returns_newest_first(self):
        base = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
        older = self.store.record(1, "older.mp4", created_at=base)
        newer = self.store.record(1, "newer.mp4", created_at=base + timedelta(seconds=1))
        same_time = self.store.record(1, "same.mp4", created_at=base + timedelta(seconds=1))
        self.assertEqual([item.id for item in self.store.for_asset(1)],
                         [same_time.id, newer.id, older.id])

    def test_empty_required_values_and_unknown_statuses_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record(1, " ")
        with self.assertRaises(ValueError):
            self.store.record(1, "x.mp4", provider="")
        with self.assertRaises(ValueError):
            self.store.record(1, "x.mp4", review_status="done")
        with self.assertRaises(ValueError):
            self.store.record(1, "x.mp4", created_at=datetime(2026, 11, 27, 12, 0))

    def test_review_statuses_round_trip_and_note_is_kept_when_omitted(self):
        guess = self.store.record(1, "x.mp4")
        pending = self.store.review(guess.id)
        self.assertEqual((pending.status, pending.note), (STATUS_PENDING, ""))

        for status in REVIEW_STATUSES:
            updated = self.store.set_review(guess.id, status, note="复核备注")
            self.assertEqual(updated.status, status)
            self.assertEqual(updated.note, "复核备注")
        self.assertEqual(self.store.set_review(guess.id, STATUS_REJECTED).note, "复核备注")
        self.assertEqual(self.store.set_review(guess.id, STATUS_REJECTED, note="").note, "")
        with self.assertRaises(ValueError):
            self.store.set_review(guess.id, "done")
        with self.assertRaises(KeyError):
            self.store.set_review(999, STATUS_ACCEPTED)

    def test_asset_state_holds_auto_ingest_and_a_review_reference_without_changing_asset(self):
        guess = self.store.record(1, "x.mp4")
        self.store.set_review(guess.id, STATUS_MODIFIED_ACCEPTED)
        review = self.store.review(guess.id)
        self.assertIsNone(self.store.asset_state(1))

        state = self.store.mark_auto_ingest(1)
        self.assertTrue(state.auto_ingest)
        self.assertIsNone(state.review_id)
        state = self.store.set_asset_state(1, review_id=review.id)
        self.assertTrue(state.auto_ingest)
        self.assertEqual(state.review_id, review.id)
        state = self.store.mark_auto_ingest(1, False)
        self.assertFalse(state.auto_ingest)
        self.assertEqual(state.review_id, review.id)
        self.assertEqual([item.id for item in self.store.reviews_for_asset(1)], [review.id])
        with self.assertRaises(ValueError):
            self.store.set_asset_state(1)
        with self.assertRaises(KeyError):
            self.store.set_asset_state(1, review_id=999)

    def test_attach_review_creates_pending_when_the_row_is_missing(self):
        guess = self.store.record(1, "x.mp4")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("DELETE FROM ai_filename_guess_review WHERE guess_id=?", (guess.id,))
        state = self.store.attach_review_to_asset(1, guess.id)
        review = self.store.review(guess.id)
        self.assertEqual(review.status, STATUS_PENDING)
        self.assertEqual(state.review_id, review.id)

    def test_deleting_an_asset_removes_guesses_reviews_and_state(self):
        guess = self.store.record(1, "x.mp4")
        review = self.store.review(guess.id)
        self.store.set_asset_state(1, auto_ingest=True, review_id=review.id)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("DELETE FROM asset WHERE id=1")
        self.assertIsNone(self.store.get(guess.id))
        self.assertIsNone(self.store.review(guess.id))
        self.assertIsNone(self.store.asset_state(1))

    def test_deleting_a_guess_clears_the_asset_review_reference(self):
        guess = self.store.record(1, "x.mp4")
        review = self.store.review(guess.id)
        self.store.set_asset_state(1, review_id=review.id)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("DELETE FROM ai_filename_guess WHERE id=?", (guess.id,))
        self.assertIsNone(self.store.asset_state(1).review_id)
        self.assertIsNone(self.store.review(guess.id))

    def test_review_status_check_rejects_unknown_values_at_the_database(self):
        guess = self.store.record(1, "x.mp4")
        with closing(sqlite3.connect(self.db)) as connection, connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE ai_filename_guess_review SET status='done' WHERE guess_id=?",
                    (guess.id,))


class MigrationSchemaTests(unittest.TestCase):
    def test_tables_expose_the_documented_columns_and_trigger_coverage(self):
        with tempfile.TemporaryDirectory() as holder:
            db = fresh_ledger(Path(holder))
            with closing(sqlite3.connect(db)) as connection:
                columns = {table: [row[1] for row in connection.execute(
                    f"PRAGMA table_info({table})")] for table in (
                        "ai_filename_guess", "ai_filename_guess_review",
                        "ai_filename_guess_asset")}
                triggers = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type='trigger'")}
                revisions = {row[0] for row in connection.execute(
                    "SELECT tbl FROM ledger_revision")}
        self.assertEqual(columns["ai_filename_guess"], ["id", *GUESS_FIELDS])
        self.assertEqual(columns["ai_filename_guess_review"],
                         ["id", "guess_id", "status", "note", "updated_at"])
        self.assertEqual(columns["ai_filename_guess_asset"],
                         ["asset_id", "auto_ingest", "review_id", "updated_at"])
        for table in columns:
            self.assertIn(table, revisions)
            for event in ("insert", "update", "delete"):
                self.assertIn(f"rev_{table}_{event}", triggers)
        self.assertIn("ai_filename_guess_asset_delete_guesses", triggers)
        self.assertIn("ai_filename_guess_delete_reviews", triggers)
        self.assertIn("ai_filename_guess_review_clear_asset", triggers)


class StatusConstantsTests(unittest.TestCase):
    def test_status_ids_are_the_five_documented_review_states(self):
        self.assertEqual(REVIEW_STATUSES, (
            STATUS_PENDING, STATUS_ACCEPTED, STATUS_MODIFIED_ACCEPTED,
            STATUS_REJECTED, STATUS_ROLLED_BACK))
        self.assertEqual(REVIEW_STATUSES, (
            "pending", "accepted", "modified_accepted", "rejected", "rolled_back"))
