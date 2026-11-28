"""AI 猜文件名的数据层：猜测留痕、复核状态与作品挂接。

三张新表见 `migrations/0061_ai_filename_guess.sql`。本模块只负责写入与查询，不做 API
调用、提示词、三层路由、自动入库触发或界面；那些属于后续工单。

一条留痕固定包含 `GUESS_FIELDS` 的十项：作品、文件名快照、服务商预设名、model、提示词
版本、原始返回、解析结果、confidence、路由结果与时间。原始返回和解析结果按文本存放，
字典或列表由这里序列化为 JSON。复核状态与自动入库标记挂在作品一侧的
`ai_filename_guess_asset`，不改 `asset` 表结构。
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .repository import LedgerDatabase

#: 功能默认值与定稿规格一致；版本号随提示词单独演进，不跟应用版本走。
DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-flash"
PROMPT_VERSION = "filename-guess-v2"

#: 猜测留痕的十个字段，按数据库列顺序排列，不含自增 `id`。
GUESS_FIELDS = (
    "asset_id", "filename", "provider", "model", "prompt_version",
    "raw_response", "parsed_result", "confidence", "route", "created_at",
)

#: 复核状态取英文 id（ADR-0162）；界面译文由复核队列页负责。
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_MODIFIED_ACCEPTED = "modified_accepted"
STATUS_REJECTED = "rejected"
STATUS_ROLLED_BACK = "rolled_back"
REVIEW_STATUSES = (
    STATUS_PENDING, STATUS_ACCEPTED, STATUS_MODIFIED_ACCEPTED,
    STATUS_REJECTED, STATUS_ROLLED_BACK,
)

_GUESS_COLUMNS = "id," + ",".join(GUESS_FIELDS)
_REVIEW_COLUMNS = "id,guess_id,status,note,updated_at"
_STATE_COLUMNS = "asset_id,auto_ingest,review_id,updated_at"
_UNSET = object()


def _now(moment: datetime | None = None) -> str:
    moment = moment or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: object) -> str:
    """原始返回、解析结果与路由结果落库前的文本形态；结构化值序列化成 JSON。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required(name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


@dataclass(frozen=True)
class GuessRecord:
    id: int
    asset_id: int
    filename: str
    provider: str
    model: str
    prompt_version: str
    raw_response: str
    parsed_result: str
    confidence: float | None
    route: str
    created_at: str

    def trace(self) -> dict[str, object]:
        """十项留痕内容（不含自增 `id`）。"""
        return {name: getattr(self, name) for name in GUESS_FIELDS}


@dataclass(frozen=True)
class ReviewRecord:
    id: int
    guess_id: int
    status: str
    note: str
    updated_at: str


@dataclass(frozen=True)
class AssetGuessState:
    asset_id: int
    auto_ingest: bool
    review_id: int | None
    updated_at: str


class FilenameGuessStore:
    """AI 猜文件名留痕与复核状态的服务层。

    `ledger` 收 `LedgerDatabase` 或账本路径；写走它的写事务，读走只读连接。
    """

    def __init__(self, ledger: LedgerDatabase | Path | str) -> None:
        self.ledger = (ledger if isinstance(ledger, LedgerDatabase)
                       else LedgerDatabase(Path(ledger)))

    def record(self, asset_id: int, filename: str, *, provider: str = DEFAULT_PROVIDER,
               model: str = DEFAULT_MODEL, prompt_version: str = PROMPT_VERSION,
               raw_response: object = "", parsed_result: object = "",
               confidence: float | None = None, route: object = "",
               created_at: datetime | None = None,
               review_status: str = STATUS_PENDING) -> GuessRecord:
        """写一条猜测留痕，同时建立一条待复核状态。"""
        if review_status not in REVIEW_STATUSES:
            raise ValueError(f"unknown review status: {review_status}")
        moment = _now(created_at)
        values = (
            int(asset_id),
            _required("filename", filename),
            _required("provider", provider),
            _required("model", model),
            _required("prompt_version", prompt_version),
            _text(raw_response),
            _text(parsed_result),
            None if confidence is None else float(confidence),
            _text(route),
            moment,
        )
        with self.ledger.write_transaction() as connection:
            cursor = connection.execute(
                f"INSERT INTO ai_filename_guess({','.join(GUESS_FIELDS)}) "
                f"VALUES({','.join('?' for _ in GUESS_FIELDS)})", values)
            guess_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO ai_filename_guess_review(guess_id,status,note,updated_at) "
                "VALUES(?,?,?,?)", (guess_id, review_status, "", moment))
        return GuessRecord(guess_id, *values)

    def get(self, guess_id: int) -> GuessRecord | None:
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_GUESS_COLUMNS} FROM ai_filename_guess WHERE id=?",
                (guess_id,)).fetchone()
        return _guess(row)

    def for_asset(self, asset_id: int) -> list[GuessRecord]:
        """按作品查询留痕，新的在前；同一时间戳按 id 倒序。"""
        with self.ledger.read_connection() as connection:
            rows = connection.execute(
                f"SELECT {_GUESS_COLUMNS} FROM ai_filename_guess WHERE asset_id=? "
                "ORDER BY created_at DESC, id DESC", (asset_id,)).fetchall()
        return [_guess(row) for row in rows if row is not None]

    def review(self, guess_id: int) -> ReviewRecord | None:
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_REVIEW_COLUMNS} FROM ai_filename_guess_review WHERE guess_id=?",
                (guess_id,)).fetchone()
        return _review(row)

    def reviews_for_asset(self, asset_id: int) -> list[ReviewRecord]:
        with self.ledger.read_connection() as connection:
            rows = connection.execute(
                f"SELECT {', '.join('r.' + name for name in _REVIEW_COLUMNS.split(','))} "
                "FROM ai_filename_guess_review r "
                "JOIN ai_filename_guess g ON g.id=r.guess_id "
                "WHERE g.asset_id=? ORDER BY r.id", (asset_id,)).fetchall()
        return [_review(row) for row in rows if row is not None]

    def set_review(self, guess_id: int, status: str, *, note: str | None = None,
                   updated_at: datetime | None = None) -> ReviewRecord:
        """更新或补建复核状态；`note=None` 保留原备注。"""
        if status not in REVIEW_STATUSES:
            raise ValueError(f"unknown review status: {status}")
        moment = _now(updated_at)
        with self.ledger.write_transaction() as connection:
            if connection.execute(
                    "SELECT 1 FROM ai_filename_guess WHERE id=?", (guess_id,)).fetchone() is None:
                raise KeyError(f"guess does not exist: {guess_id}")
            current = connection.execute(
                "SELECT note FROM ai_filename_guess_review WHERE guess_id=?",
                (guess_id,)).fetchone()
            kept_note = current["note"] if note is None and current is not None else (note or "")
            connection.execute(
                "INSERT INTO ai_filename_guess_review(guess_id,status,note,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(guess_id) DO UPDATE SET "
                "status=excluded.status,note=excluded.note,updated_at=excluded.updated_at",
                (guess_id, status, kept_note, moment))
            row = connection.execute(
                f"SELECT {_REVIEW_COLUMNS} FROM ai_filename_guess_review WHERE guess_id=?",
                (guess_id,)).fetchone()
        return _review(row)

    def asset_state(self, asset_id: int) -> AssetGuessState | None:
        with self.ledger.read_connection() as connection:
            row = connection.execute(
                f"SELECT {_STATE_COLUMNS} FROM ai_filename_guess_asset WHERE asset_id=?",
                (asset_id,)).fetchone()
        return _state(row)

    def set_asset_state(self, asset_id: int, *, auto_ingest: bool | None = None,
                        review_id: int | None | object = _UNSET,
                        updated_at: datetime | None = None) -> AssetGuessState:
        """写入作品的自动入库标记和/或复核状态引用；未给的字段保留原值。"""
        if auto_ingest is None and review_id is _UNSET:
            raise ValueError("nothing to update")
        moment = _now(updated_at)
        with self.ledger.write_transaction() as connection:
            if review_id is not _UNSET and review_id is not None and connection.execute(
                    "SELECT 1 FROM ai_filename_guess_review WHERE id=?",
                    (review_id,)).fetchone() is None:
                raise KeyError(f"review does not exist: {review_id}")
            existing = connection.execute(
                f"SELECT {_STATE_COLUMNS} FROM ai_filename_guess_asset WHERE asset_id=?",
                (asset_id,)).fetchone()
            flag = (int(bool(auto_ingest)) if auto_ingest is not None
                    else int(existing["auto_ingest"]) if existing is not None else 0)
            reference = (review_id if review_id is not _UNSET
                         else existing["review_id"] if existing is not None else None)
            connection.execute(
                "INSERT INTO ai_filename_guess_asset(asset_id,auto_ingest,review_id,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET "
                "auto_ingest=excluded.auto_ingest,review_id=excluded.review_id,"
                "updated_at=excluded.updated_at",
                (asset_id, flag, reference, moment))
            row = connection.execute(
                f"SELECT {_STATE_COLUMNS} FROM ai_filename_guess_asset WHERE asset_id=?",
                (asset_id,)).fetchone()
        return _state(row)

    def mark_auto_ingest(self, asset_id: int, enabled: bool = True) -> AssetGuessState:
        return self.set_asset_state(asset_id, auto_ingest=enabled)

    def attach_review_to_asset(self, asset_id: int, guess_id: int) -> AssetGuessState:
        """把某条猜测的复核状态挂到作品上，没有复核行时先补一条待复核。"""
        review = self.review(guess_id)
        if review is None:
            review = self.set_review(guess_id, STATUS_PENDING)
        return self.set_asset_state(asset_id, review_id=review.id)


def _guess(row: sqlite3.Row | None) -> GuessRecord | None:
    if row is None:
        return None
    return GuessRecord(
        id=row["id"],
        asset_id=row["asset_id"],
        filename=row["filename"],
        provider=row["provider"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        raw_response=row["raw_response"],
        parsed_result=row["parsed_result"],
        confidence=row["confidence"],
        route=row["route"],
        created_at=row["created_at"],
    )


def _review(row: sqlite3.Row | None) -> ReviewRecord | None:
    if row is None:
        return None
    return ReviewRecord(
        id=row["id"],
        guess_id=row["guess_id"],
        status=row["status"],
        note=row["note"],
        updated_at=row["updated_at"],
    )


def _state(row: sqlite3.Row | None) -> AssetGuessState | None:
    if row is None:
        return None
    return AssetGuessState(
        asset_id=row["asset_id"],
        auto_ingest=bool(row["auto_ingest"]),
        review_id=row["review_id"],
        updated_at=row["updated_at"],
    )
