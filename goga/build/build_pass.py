from __future__ import annotations

from ..ralphex import run_ralphex
from .ralphex_config import write_ralphex_config
from .run_settings import RunSettings


def run_build_pass(  # noqa: PLR0913, PLR0917 — the signature carries the CODEMANIFEST pass ladder inputs
    plan: str,
    settings: RunSettings,
    options: dict[str, str | int | bool],
    wrapper_path: str,
    dry_run: bool,
    additional_wrapper_path: str | None = None,
) -> int:
    """Execute one ralphex pass: write the pass config, delegate the launch.

    Args:
        plan: Path to the plan file (markdown), passed verbatim to ralphex.
        settings: Resolved run plan (`RunSettings`) — carried to the config
            routine; the pass interprets nothing on it.
        options: Resolved ralphex options of the pass (composed by
            `compose_pass_options`; carries exactly one pass-mode bare flag),
            forwarded verbatim.
        wrapper_path: Executor wrapper of the current pass (tasks wrapper or
            review wrapper), written into `.ralphex/config`.
        dry_run: When True, print instead of launching (the pass config is
            still written — a harmless dry-run side effect matching the
            established behavior).
        additional_wrapper_path: The additional role wrapper path, forwarded
            to the config routine — the external-review surface under the
            full and short strategies. This is the LAST config write before
            the launch, so the surviving on-disk config carries the external
            review surface ralphex actually reads.

    Returns:
        The exit code returned by ralphex, propagated without transformation.
        The launch carries no env layer — the launched process inherits the
        container environment; the env layers of the roles travel through the
        generated wrappers.
    """
    write_ralphex_config(settings, wrapper_path, additional_wrapper_path)

    return run_ralphex(plan, options, dry_run)
