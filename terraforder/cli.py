from __future__ import annotations

import argparse
import codecs
import difflib
import os
import shutil
import sys
from pathlib import Path

from .config import ConfigError, load_order
from .parser import ParseError
from .sorter import sort_source

EXTENSIONS = (".tf", ".tfvars")


def discover(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            for root, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                files.extend(Path(root, name) for name in sorted(names) if name.endswith(EXTENSIONS))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"{path}: no such file or directory")
    return files


def _emit(text: str) -> None:
    # Write bytes so CRLF content isn't doubled to CR CR LF by Windows text-mode stdout.
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(text)
        return
    sys.stdout.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _error(message: str) -> None:
    print(f"terraforder: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="terraforder",
        description="Sort top-level Terraform blocks alphabetically, grouped by block type.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories (searched recursively for *.tf and *.tfvars)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-w", "--write", action="store_true", help="rewrite files in place")
    mode.add_argument(
        "--dry-run",
        "--check",
        dest="dry_run",
        action="store_true",
        help="print a diff of the changes without writing; exit 1 if any file is unsorted",
    )
    parser.add_argument("--backup", action="store_true", help="with --write, save each original as FILE.bak")
    parser.add_argument("--config", type=Path, help="TOML config file (default: ./.terraforder.toml if present)")
    parser.add_argument("-v", "--verbose", action="store_true", help="report each file and its resulting block order")
    args = parser.parse_args(argv)

    if args.backup and not args.write:
        parser.error("--backup requires --write")

    try:
        order = load_order(args.config)
        files = discover(args.paths)
    except (ConfigError, FileNotFoundError) as e:
        _error(str(e))
        return 2

    if not args.write and not args.dry_run and len(files) != 1:
        if not files:
            _error("no Terraform files found")
            return 2
        parser.error("use --write or --dry-run when processing more than one file")

    status = 0
    for path in files:
        try:
            data = path.read_bytes()
            bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b""
            original = data[len(bom) :].decode("utf-8")
            result, items = sort_source(original, order)
        except ParseError as e:
            _error(f"{path}:{e}")
            status = 2
            continue
        except (OSError, UnicodeDecodeError) as e:
            _error(f"{path}: {e}")
            status = 2
            continue

        changed = result != original
        if args.write:
            if changed:
                if args.backup:
                    shutil.copy2(path, path.with_name(path.name + ".bak"))
                path.write_bytes(bom + result.encode("utf-8"))
        elif args.dry_run:
            if changed:
                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    result.splitlines(keepends=True),
                    f"a/{path.as_posix()}",
                    f"b/{path.as_posix()}",
                )
                _emit("".join(diff))
                status = max(status, 1)
        else:
            _emit(result)

        if args.verbose:
            print(f"{'reordered' if changed else 'unchanged'}: {path}", file=sys.stderr)
            for item in items:
                print(f"  {item.address}", file=sys.stderr)

    return status
