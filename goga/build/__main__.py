from __future__ import annotations

import argparse

from ..config import load_config
from ..docker import ensure_in_docker
from .build import build


def main() -> int:
    """Run the goga build command as a standalone entry point.

    Parses CLI arguments, loads project configuration, and invokes the build pipeline.

    Returns:
        0 on success, 1 on failure.
    """
    ensure_in_docker()
    parser = argparse.ArgumentParser(prog="goga.build", description="Run goga build inside Docker")
    parser.add_argument("plan", help="Path to the build plan file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--worktree", action="store_true")
    parser.add_argument("--skip-finalize", action="store_true")
    parser.add_argument("--skip-manifest-check", action="store_true")
    parser.add_argument("--session-timeout", type=str, default=None)
    parser.add_argument("--idle-timeout", type=str, default=None)
    parser.add_argument("--wait", type=str, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--review-patience", type=int, default=None)
    args = parser.parse_args()

    config = load_config()

    cli_options = {
        "worktree": args.worktree,
        "skip_finalize": args.skip_finalize,
        "skip_manifest_check": args.skip_manifest_check,
        "session_timeout": args.session_timeout,
        "idle_timeout": args.idle_timeout,
        "wait": args.wait,
        "max_iterations": args.max_iterations,
        "review_patience": args.review_patience,
        "dry_run": args.dry_run,
    }

    return build(args.plan, config, cli_options)


if __name__ == "__main__":
    raise SystemExit(main())
