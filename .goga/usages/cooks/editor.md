# Multi-Line Text Entry with an External Editor

## Library

**External editor** — the user's editor resolved git-style: `$VISUAL` → `$EDITOR` → the
system default `vi`. No new Python dependency; the editor is an external process.

**IMPORTANT** — no editor fields exist in the project or home configuration; the
environment chain plus the default is the whole resolution.

## Purpose

Interactive entering and editing of a multi-line text (a topic todo) with full editing
capabilities — erasing any line, moving the cursor — which a prompt cycle cannot offer.
Use this practice for every interactive moment that collects or edits a multi-line text.
The practice replaces the former prompt-cycle entry (the lone `.` line and Ctrl+D
terminators are abolished).

## Entry Protocol

1. Resolve the editor: `$VISUAL` first, then `$EDITOR`, otherwise `vi`.
2. Create a temporary file outside the topic directory — empty for a fresh text, or
   prefilled with the existing content when an existing text is edited.
3. Print the hint to the terminal **before** launching the editor — an empty file means
   cancellation. No hint comments inside the file itself.
4. Launch the editor on the temporary file. Saving and exiting the editor completes the
   entry.
5. Read the file back after the editor exits.

## Cancellation

An empty or unchanged file means the entry did not happen — execution continues as
without the entry. When an existing target file is edited, cancellation leaves it
untouched. The emptiness check runs on the saved content; a text of only blank lines
cancels the entry the same way.

## Errors

- A non-TTY when the entry is requested is a clean error raised **before any mutation**
  (except where a command explicitly documents a silent skip of the flag instead).
- A non-zero editor exit code and Ctrl+C are clean errors without mutations.
- A missing editor binary surfaces as a clean error, not a traceback.

## Writing the Result

The saved text is written to the target file as entered plus a single trailing newline,
encoded UTF-8. Empty lines inside the text stay as entered. The temporary file is
removed after the session (its exact placement and cleanup details belong to the
implementation).

## Testing

Mock `$EDITOR` with a script that writes into the file (or leaves it, or clears it, or
exits non-zero) to model every outcome: save, cancellation, failure. Mock the TTY
detection for the non-interactive error. A real editor is never launched in tests.

## Launch Mechanism

The editor process is launched through the editor facility of the click
library (already a project dependency): the facility resolves the
editor git-style ($VISUAL, then $EDITOR, then the system default vi),
creates and reads back the temporary file, and maps a failed editor run
to a clean error. The hint before the launch, the cancellation check
(blank or unchanged saved content), and the non-TTY detection belong to
the calling code.

```python
import sys

import click


def enter_text(initial: str | None = None) -> str | None:
    if not sys.stdin.isatty():
        raise click.ClickException("the entry needs an interactive terminal")
    click.echo("Enter the text. An empty or unchanged file cancels the entry.")
    start = initial or ""
    if start and not start.endswith("\n"):   # the click facility prefills
        start += "\n"                        # with a trailing newline
    saved = click.edit(text=start)
    if saved is None or not saved.strip() or saved == start:
        return None
    return saved
```

The equality check compares against the **normalized prefill**, not the raw
`initial`: the click facility appends a missing trailing newline when it
writes the temporary file, so an unchanged save of a text without one comes
back as `initial + "\n"` — comparing to the raw value would treat the
unchanged save as a change.

In tests mock the editor with a script that writes into the file (or
leaves it, or clears it, or exits non-zero) via the `$EDITOR`
environment variable, and mock the TTY detection for the
non-interactive error. A real editor is never launched in tests.
