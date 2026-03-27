"""CLI entrypoint for the Trax foundation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trax.storage.bootstrap import bootstrap_local_storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trax",
        description="Local-first AI debugging CLI foundation.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the Trax foundation version and exit.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return int(exc.code)

    if args.version:
        from trax import __version__

        print(__version__)
        return 0

    try:
        bootstrap = bootstrap_local_storage()
    except PermissionError as exc:
        print(f"Unable to initialize local Trax storage: {exc}", file=sys.stderr)
        return 1

    _ = _format_bootstrap_state(bootstrap.app_dir, bootstrap.db_path, bootstrap.artifacts_dir)
    return 0


def _format_bootstrap_state(app_dir: Path, db_path: Path, artifacts_dir: Path) -> str:
    """Keep a minimal formatter ready for future diagnostic commands."""
    return (
        f"app_dir={app_dir}\n"
        f"db_path={db_path}\n"
        f"artifacts_dir={artifacts_dir}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
