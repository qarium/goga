"""The external-editor entry session of the topics-domain editor cell.

The entity declared in the cell CODEMANIFEST with
``location: entry.py``: the interactive collection and editing of a
multi-line text through the editor resolved by the ``editor``
practice. The session is the single interactive surface of the topics
domain — every orchestration moment, the decision when an entry
happens, belongs to the caller. It is environment access, not topic
logic.
"""

from __future__ import annotations

import sys

import click

_HINT = "Enter the text. An empty or unchanged file cancels the entry."


def edit_text(initial: str | None = None) -> str | None:
    """Collect or edit a multi-line text in the external editor.

    Args:
        initial: The text the session starts from — the existing content
            when an entry edits; None or an empty string starts from an
            empty entry.

    Returns:
        The saved text as entered, or None when the entry was cancelled.

    Algorithm:
        1. No interactive terminal -> a clean error, before anything
           else
        2. Print the hint to the terminal — an empty saved file cancels
           the entry — before the editor starts
        3. Run the editor session over a temporary file — empty for a
           fresh entry, carrying ``initial`` plus a missing trailing
           newline (the editor facility of the click library appends
           one to its prefill) otherwise
        4. A failed editor run or an interrupted session -> a clean
           error, nothing mutated
        5. The saved content blank or equal to the prefilled text ->
           cancellation: return None
        6. Return the saved text as entered

    Requirements:
        The session touches nothing but its temporary file — no project
        state is read or mutated.

        The hint precedes the editor start.

        The text is returned as entered — no normalization, no trailing
        newline added.

    Constraints:
        Do not place hint comments inside the file itself.

        Do not validate the content — every non-blank text is accepted.

        Do not write the result anywhere — the write belongs to the
        caller.

    Raises:
        click.ClickException: No interactive terminal is attached, or
            the editor run failed — the caller's state is untouched.
    """
    if not sys.stdin.isatty():
        raise click.ClickException("the entry needs an interactive terminal")

    click.echo(_HINT)

    start = initial or ""

    if start and not start.endswith("\n"):
        start += "\n"

    saved = click.edit(text=start)

    if saved is None or not saved.strip() or saved == start:
        return None

    return saved
