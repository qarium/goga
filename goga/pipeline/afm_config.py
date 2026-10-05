"""In-container authorship of the afm configuration file."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..agents import resolve_wrapper_path

_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")
_PROMPTS_DIR = "/home/goga/pipeline/prompts"


def write_afm_config(agent: str | None) -> Path:
    """Write the whole afm configuration file at the fixed in-container home path.

    Args:
        agent: The effective pipeline agent as amended by the config delivery
            (e.g. "codex"); ``None`` omits the whole ``client`` block.

    Returns:
        The fixed in-container path of the written file
        (``/home/goga/.afm/config.yaml``), independent of ``AFM_DIR``. The
        content serializes the optional ``client`` block first (the
        ``client.command`` default for stages without a per-stage ``command:``
        override), then the four static launcher fields — ``theme: goga``,
        ``open_browser: false``, ``proxy.enabled: false``, and ``prompts_dir:
        /home/goga/pipeline/prompts`` — never configurable through the project
        configuration or the CLI.

    Raises:
        OSError: When the home directory is unwritable — propagates unchanged
            (the caller returns before any run event fires; no partial file is
            left behind).
    """
    wrapper = resolve_wrapper_path(agent) if agent is not None else None

    content: dict[str, object] = {}
    if wrapper is not None:
        content["client"] = {"command": wrapper}

    content.update(
        {
            "theme": "goga",
            "open_browser": False,
            "proxy": {"enabled": False},
            "prompts_dir": _PROMPTS_DIR,
        }
    )

    _AFM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AFM_CONFIG_PATH.write_text(yaml.safe_dump(content, default_flow_style=False, sort_keys=False))
    return _AFM_CONFIG_PATH
