"""写真筛选参考对象的调试入口。

服务层在 `peach.photo_filter_references`，这里只给本机调试与后续界面接线前用：
`create` 新建对象并建向量，`list` 查看，`rebuild` 用已存副本重跑构建，`delete` 连照片副本
一起删。写操作必须显式 `--apply` 并先落一份账本备份；不传时只做只读检查。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from peach import config
from peach.migrations import sqlite_backup
from peach.photo_filter_references import ReferenceStore
from peach.repository import LedgerDatabase
from peach.scripting import BACKUP_REQUIRED


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


def _create(args: argparse.Namespace) -> int:
    _require_apply(args)
    reference = _store(args).create(args.name, args.photo)
    print(f"id={reference.id} status={reference.status} faces={reference.valid_face_count} "
          f"provider={reference.provider}")
    if reference.failure_reason:
        print(reference.failure_reason)
    return 0


def _list(args: argparse.Namespace) -> int:
    for reference in _store(args).list():
        print(f"{reference.id}\t{reference.status}\t{reference.valid_face_count}\t"
              f"{reference.name}\t{reference.failure_reason}")
    return 0


def _rebuild(args: argparse.Namespace) -> int:
    _require_apply(args)
    reference = _store(args).rebuild(args.id)
    print(f"id={reference.id} status={reference.status} faces={reference.valid_face_count} "
          f"provider={reference.provider}")
    return 0


def _delete(args: argparse.Namespace) -> int:
    _require_apply(args)
    return 0 if _store(args).delete(args.id) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", type=Path, default=config.DATABASE_PATH)
    common.add_argument("--reference-root", type=Path,
                        default=config.PHOTO_FILTER_REFERENCE_ROOT)
    common.add_argument("--model-root", type=Path, default=config.PHOTO_FILTER_MODEL_ROOT)
    write = argparse.ArgumentParser(add_help=False)
    write.add_argument("--apply", action="store_true", help="write to the ledger")
    write.add_argument("--backup", type=Path, help=BACKUP_REQUIRED)

    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", parents=[common, write])
    create.add_argument("--name", required=True)
    create.add_argument("--photo", type=Path, nargs="+", required=True)
    create.set_defaults(handler=_create)

    listing = commands.add_parser("list", parents=[common])
    listing.set_defaults(handler=_list)

    rebuild = commands.add_parser("rebuild", parents=[common, write])
    rebuild.add_argument("--id", type=int, required=True)
    rebuild.set_defaults(handler=_rebuild)

    delete = commands.add_parser("delete", parents=[common, write])
    delete.add_argument("--id", type=int, required=True)
    delete.set_defaults(handler=_delete)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
