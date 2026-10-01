"""In-container authorship of the afm configuration file."""

from __future__ import annotations

from pathlib import Path

import yaml

from ..agents import resolve_wrapper_path

_AFM_CONFIG_PATH = Path("/home/goga/.afm/config.yaml")
_PROMPTS_DIR = "/home/goga/pipeline/prompts"


def write_afm_config(agent: str | None) -> Path:
    """Write the whole afm configuration file at the fixed in-container home path.

    Called by the run coordination before the afm launch: the effective pipeline
    agent (``None`` when nothing resolved) becomes the ``client.command`` default
    every stage without a per-stage ``command:`` override launches through. The
    four static launcher-side fields are constants — never configurable through
    the project configuration or the CLI:

    - ``theme: goga`` — the dashboard theme applied by afm.
    - ``open_browser: false`` — the dashboard is reached via the host-printed
      URL; afm must not attempt an in-container browser launch.
    - ``proxy.enabled: false`` — goga manages the outbound proxy through the
      container env-file, so afm's own internal proxy provider stays off.
    - ``prompts_dir: /home/goga/pipeline/prompts`` — where afm reads the four
      agent prompt files the run coordination materializes. The directory itself
      is neither created nor managed here.

    The insertion order fixes the serialized field order: ``client`` (when
    present), then the four static fields. The path is the fixed in-container
    home path — independent of the afm state directory variable (``AFM_DIR``).

    Args:
        agent: The effective pipeline agent as amended by the config delivery
            (e.g. "codex"); ``None`` omits the whole ``client`` block so
            per-stage workflow agents or the binary's own defaults cover the
            absent global default.

    Returns:
        The fixed in-container path of the written file
        (``/home/goga/.afm/config.yaml``).

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
