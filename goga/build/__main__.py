from __future__ import annotations

import argparse
import logging
import sys

import yaml

from ..config import load_project_config
from ..config.hooks import ConfigHooks
from ..docker import ensure_in_docker
from .build import build

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the goga build command as a standalone entry point.

    Returns:
        0 on success; 1 on a configuration failure, which returns before any
        ralphex launch or ``.ralphex/`` state write; otherwise the exit code
        ``build`` returned.
    """
    ensure_in_docker()

    parser = argparse.ArgumentParser(prog="goga.build", description="Run goga build inside Docker")
    parser.add_argument("plan", help="Path to the build plan file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-manifest-check", action="store_true")
    parser.add_argument("--skip-review", dest="skip_review", action="store_true", default=None)
    parser.add_argument("--no-skip-review", dest="skip_review", action="store_false")
    parser.add_argument("--session-timeout", type=str, default=None)
    parser.add_argument("--idle-timeout", type=str, default=None)
    parser.add_argument("--wait", type=str, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--review-patience", type=int, default=None)
    parser.add_argument("--base-ref", type=str, default=None)
    args = parser.parse_args()

    # Steps 2-4 — the in-container configuration load-and-amend. The authored
    # load and the config-amendment delivery each own a clean-error boundary:
    # both return 1 before any ralphex launch, so nothing is partially
    # applied. Every downstream step consumes the effective configuration of
    # the overlay — the run parameters this domain owns (build.agent,
    # build.env, build.review.env) are read from it alone.
    try:
        authored = load_project_config()
    except (FileNotFoundError, OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        logger.error("project configuration load failed", extra={"reason": str(exc)})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        overlay = ConfigHooks().amend_config(config=authored)
    except (ValueError, ImportError) as exc:
        logger.error("config amendment delivery failed", extra={"reason": str(exc)})
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in overlay.summary_lines:
        print(line, file=sys.stderr)

    cli_options = {
        "dry_run": args.dry_run,
        "skip_manifest_check": args.skip_manifest_check,
        "skip_review": args.skip_review,
        "base_ref": args.base_ref,
        "review_patience": args.review_patience,
        "session_timeout": args.session_timeout,
        "idle_timeout": args.idle_timeout,
        "wait": args.wait,
        "max_iterations": args.max_iterations,
    }

    return build(args.plan, overlay.config, cli_options)


if __name__ == "__main__":
    raise SystemExit(main())
