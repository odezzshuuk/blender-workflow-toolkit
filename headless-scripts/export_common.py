"""Shared CLI and filesystem helpers for standalone Blender exporters."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
import re
import sys
from typing import Literal, TypeAlias, TypeVar

ConflictPolicy: TypeAlias = Literal["overwrite", "number", "stop"]
Args = TypeVar("Args", bound="ExportArgs")


class ExportArgs(argparse.Namespace):
    blend_file: Path
    output_dir: Path | None
    selected_only: bool


class ExportError(Exception):
    """An expected file or Blender operation failure reported without a traceback."""


def blender_args(argv: Sequence[str] | None) -> Sequence[str]:
    if argv is not None:
        return argv

    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def add_export_arguments(
    parser: argparse.ArgumentParser, output_suffix: str, *, prompt: bool = False,
    selection_help: str = "Use the selection saved in the file",
) -> None:

    # Define the common source, destination, selection, and collision options.
    parser.add_argument("blend_file", type=Path, help="Source .blend file")
    parser.add_argument("output_dir", type=Path, nargs="?",
                        help=f"Default: <blend stem>{output_suffix}")
    parser.add_argument("--selected-only", action="store_true", help=selection_help)
    parser.add_argument(
        "--on-exists", choices=("overwrite", "number", "stop"),
        default=None if prompt else "stop",
        help=("Handle every filename conflict automatically; prompt when omitted" if prompt else
              "Handle filename conflicts (default: stop without overwriting)"),
    )


def safe_name(name: str, fallback: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or fallback


def overwrite_path(filepath: Path) -> Path:
    if filepath.is_dir():
        raise IsADirectoryError(filepath)

    return filepath


def numbered_path(
    output_dir: Path, name: str, extension: str, occupied: Callable[[Path], bool],
) -> Path:

    # Choose the first available filename under the caller’s collision rules.
    filepath = output_dir / f"{name}.{extension}"
    suffix = 1
    while occupied(filepath):
        filepath = output_dir / f"{name}_{suffix}.{extension}"
        suffix += 1
    return filepath


def run_export(
    args: Args, export: Callable[[Args], None], output_suffix: str, label: str,
) -> int:
    try:
        args.blend_file = args.blend_file.expanduser().resolve()

        if not args.blend_file.is_file() or args.blend_file.suffix.lower() != ".blend":
            print(f"Expected an existing .blend file: {args.blend_file}", file=sys.stderr)
            return 2

        # Resolve the destination before handing the batch to its exporter.
        args.output_dir = (
            args.output_dir or args.blend_file.with_name(args.blend_file.stem + output_suffix)
        ).expanduser().resolve()
        export(args)
    except (OSError, ExportError) as error:
        print(f"{label} stopped: {' '.join(str(error).split())}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n{label} interrupted; completed files kept.")
        return 130
    return 0
