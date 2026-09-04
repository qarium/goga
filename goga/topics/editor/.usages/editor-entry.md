# topics/editor — the editor entry session

How to collect or edit a multi-line text through the user's external
editor with the `goga.topics.editor` facade. For consumers that need
interactive text entry in the topics domain: the topics orchestrations.

The session is the only interactive moment — the caller decides when it
happens. Cancellation is a normal outcome, not an error: the caller
continues as without the entry.

## Entering a fresh text

    from goga.topics.editor import edit_text

    text = edit_text()
    if text is None:
        ...  # cancelled — continue as without the entry

- The editor resolves $VISUAL, then $EDITOR, then vi.
- An empty saved file (or only blank lines) cancels the entry.
- The saved text comes back as entered — the caller owns any write.

## Editing an existing text

    text = edit_text(initial="Fix retries.\n\nIgnore the cap.")

- The session starts from the existing content; saving without changes
  cancels the entry — the existing text is the caller's to keep.

## Errors

- A missing interactive terminal, a failed editor run, or an
  interrupted session raise a clean error before any mutation — the
  caller's state is untouched.
- In tests never launch a real editor: mock the editor with a script
  that writes into the file, leaves it, clears it, or exits non-zero.
