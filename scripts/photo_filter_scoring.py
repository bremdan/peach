"""写真筛选打分任务的调试入口。

服务层在 `peach.photo_filter_scoring`，这里只给本机调试与后续界面接线前用：
`run` 建任务或跑既有任务并逐集打分，`cancel` 把任务标成已取消，`task` 与 `results`
只读查看。写操作必须显式 `--apply` 并先落一份账本备份；不传时只做只读检查。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from peach import config
from peach.migrations import sqlite_backup
from peach.photo_filter_references import (
    TASK_CANCELLED,
    ReferenceStore,
)
from peach.photo_filter_scoring import PhotoFilterScorer
from peach.repository import LedgerDatabase
from peach.scripting import BACKUP_REQUIRED


def _representative_root() -> Path:
    return config.GENERATED_DIR / "photo-filter" / "representatives"


def _store(args: argparse.Namespace) -> ReferenceStore:
    return ReferenceStore(
        LedgerDatabase(args.db),
        reference_root=args.reference_root,
        model_root=args.model_root,
    )


def _require_apply(args: argparse.Namespace) -> None:
    if not args.apply:
        raise SystemExit("--apply is required for writes")
    if not args.backup:
        raise SystemExit(BACKUP_REQUIRED)
    sqlite_backup(args.db, args.backup)


def _run(args: argparse.Namespace) -> int:
    _require_apply(args)
    store = _store(args)
    if args.task_id is not None:
        task_id = args.task_id
    else:
        task = store.create_task(
            args.root,
            hit_threshold=args.hit_threshold,
            taste_threshold=args.taste_threshold,
        )
        task_id = task.id
    scorer = PhotoFilterScorer(
        store, representative_root=args.representative_root)

    def report(task, result):
        print(f"[{task.processed_count}/{task.total_count}] {result.tier_label}\t"
              f"score={result.score:.4f}\t{result.album_path}", flush=True)

    run = scorer.score_task(task_id, progress=report)
    state = "cancelled" if run.cancelled else "completed"
    print(f"task={run.task_id} status={state} "
          f"processed={run.processed_count} total={run.total_count}")
    return 0


def _cancel(args: argparse.Namespace) -> int:
    _require_apply(args)
    _store(args).update_task(args.task_id, status=TASK_CANCELLED)
    print(f"task={args.task_id} status={TASK_CANCELLED}")
    return 0


def _task(args: argparse.Namespace) -> int:
    task = _store(args).get_task(args.task_id)
    if task is None:
        print(f"task {args.task_id} not found", file=sys.stderr)
        return 1
    print(f"id={task.id} status={task.status} "
          f"processed={task.processed_count}/{task.total_count} "
          f"hit={task.hit_threshold:.2f} taste={task.taste_threshold:.2f} "
          f"root={task.root_path}")
    return 0


def _results(args: argparse.Namespace) -> int:
    with _store(args).ledger.read_connection() as connection:
        rows = connection.execute(
            "SELECT album_path,score,top_reference_id,valid_image_count,"
            "total_image_count,protagonist_cluster_ratio,tier_label,"
            "representative_face_path FROM photo_filter_result "
            "WHERE task_id=? ORDER BY score DESC, album_path",
            (args.task_id,)).fetchall()
    for row in rows:
        print("\t".join(str(row[name]) for name in row.keys()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", type=Path, default=config.DATABASE_PATH)
    common.add_argument("--reference-root", type=Path,
                        default=config.PHOTO_FILTER_REFERENCE_ROOT)
    common.add_argument("--representative-root", type=Path,
                        default=_representative_root())
    common.add_argument("--model-root", type=Path, default=config.PHOTO_FILTER_MODEL_ROOT)
    write = argparse.ArgumentParser(add_help=False)
    write.add_argument("--apply", action="store_true", help="write to the ledger")
    write.add_argument("--backup", type=Path, help=BACKUP_REQUIRED)

    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", parents=[common, write])
    target = run.add_mutually_exclusive_group(required=True)
    target.add_argument("--root", help="album root for a new task")
    target.add_argument("--task-id", type=int, help="run an existing task")
    run.add_argument("--hit-threshold", type=float, default=0.50)
    run.add_argument("--taste-threshold", type=float, default=0.30)
    run.set_defaults(handler=_run)

    cancel = commands.add_parser("cancel", parents=[common, write])
    cancel.add_argument("--task-id", type=int, required=True)
    cancel.set_defaults(handler=_cancel)

    task = commands.add_parser("task", parents=[common])
    task.add_argument("--task-id", type=int, required=True)
    task.set_defaults(handler=_task)

    results = commands.add_parser("results", parents=[common])
    results.add_argument("--task-id", type=int, required=True)
    results.set_defaults(handler=_results)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
