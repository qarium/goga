from __future__ import annotations

import logging
from pathlib import Path

import copier

from .project_name import resolve_scaffold_name
from .template_ref import parse_template_ref

logger = logging.getLogger(__name__)


class Scaffold:
    """Wrap the copier template engine for a single scaffolding target.

    Owns the goga hard conventions for the copier state file as construction
    state: ``dst_path`` (the target directory) and ``answers_file`` (the copier
    state file path, passed programmatically to both copier operations and
    overriding any ``answers_file`` declared in the template ``copier.yml``).

    The copier interactive survey is never used — answers are supplied
    programmatically with ``defaults=True`` on both operations. copier
    exceptions are caught (broad ``Exception``) and translated to a nonzero
    exit; they never propagate to the CLI.
    """

    def __init__(
        self,
        dst_path: str = ".",
        answers_file: str = ".goga/scaffold.yml",
    ) -> None:
        self.dst_path = dst_path
        self.answers_file = answers_file

    def generate(
        self,
        template_input: str,
        ref_override: str | None,
    ) -> int:
        """Primary project generation from a copier template.

        Parses ``template_input`` (with ``ref_override`` precedence over any URL
        fragment), resolves the project name, and invokes ``copier.run_copy`` at
        ``dst_path`` with the assembled answers data and the goga state-file
        convention. Returns ``0`` on success, ``1`` on any copier error.

        Args:
            template_input: raw template source — a git URL, optionally carrying
                a ref fragment (``url.git#ref``).
            ref_override: explicit git ref from ``--ref``; when not ``None`` it
                takes precedence over the URL fragment.

        Returns:
            ``0`` on success, ``1`` on error.
        """
        template_url, vcs_ref = parse_template_ref(template_input, ref_override)
        project_name = resolve_scaffold_name()
        data = {"project_name": project_name}
        try:
            copier.run_copy(
                template_url,
                self.dst_path,
                data,
                answers_file=self.answers_file,
                vcs_ref=vcs_ref,
                defaults=True,
            )
        except Exception as exc:
            logger.error(
                "scaffold generate failed", extra={"error": str(exc)}
            )
            return 1
        return 0

    def upgrade(self, ref_override: str | None = None) -> int:
        """Migrate a previously scaffolded project to a newer template version.

        Invokes ``copier.run_update`` at ``dst_path`` with the shared
        ``answers_file`` (written by :meth:`generate`), ``vcs_ref=ref_override``,
        ``overwrite=True`` (required by copier), and ``defaults=True``. The
        template source is read from the state file — no template argument.

        Args:
            ref_override: explicit git ref from ``--ref`` overriding the
                migration target ref; ``None`` uses the ref recorded in the
                state file.

        Returns:
            ``0`` on success, ``1`` on error or when the state file is missing.
        """
        if not Path(self.answers_file).is_file():
            logger.error(
                "missing scaffold state file", extra={"path": self.answers_file}
            )
            return 1
        try:
            copier.run_update(
                self.dst_path,
                answers_file=self.answers_file,
                vcs_ref=ref_override,
                overwrite=True,
                defaults=True,
            )
        except Exception as exc:
            logger.error(
                "scaffold upgrade failed", extra={"error": str(exc)}
            )
            return 1
        return 0
