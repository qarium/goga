# Packaging directory trees with tarfile

## Library

**tarfile** — Python standard library for reading and writing tar archives.
No installation and no `pyproject.toml` entry — it is stdlib.

## Creating a `.tar.gz` in-process

Open with `tarfile.open(path, "w:gz")` — write mode with gzip compression.
The destination file is created/truncated at open time, so an unwritable
destination raises `OSError` before any data is written.

```python
import tarfile

with tarfile.open(archive_path, "w:gz") as tar:
    tar.add(source_dir, arcname="goga-runtime-build-main")
```

On a mid-packaging failure nothing partial is kept — close and unlink the
archive file, then let the error propagate:

```python
opened = False
try:
    with tarfile.open(archive_path, "w:gz") as tar:
        opened = True
        tar.add(source_dir, arcname=wrapper_root)
except BaseException:
    if opened:
        archive_path.unlink(missing_ok=True)
    raise
```

Remove only a partial archive the block itself created: a failure before
the destination is opened (e.g. an unwritable pre-existing file under an
explicit destination) must leave any pre-existing file at the destination
untouched.

## Adding a directory tree under a wrapper root

- `tar.add(name, arcname=...)` — `arcname` sets the archive-internal name of
  the tree root: pass the wrapper directory name as `arcname` and the whole
  tree lands under one root directory inside the archive
- `recursive=True` (the default) adds the full tree; per-directory member
  order is `sorted(os.listdir(...))` — the order is deterministic, but file
  metadata (mtime, uid/gid, mode) is stored as encountered, so archive bytes
  are not reproducible
- `dereference` defaults to `False`: symlinks are archived as symlinks (the
  target path is stored, not followed); other special file types are stored
  as-is — no content transformation happens

## Built-in guards

- Self-archiving guard: `add` skips the archive file itself when it is
  encountered inside the tree being archived — an archive written into the
  source directory does not recursively include itself
- The `filter` callable of `add` is the exclusion/sanitization hook — leave
  it unused to keep "full recursive contents, as encountered" semantics
- The extraction-filter default change (Python 3.14, PEP 706) concerns
  `extract`/`extractall` only; `add` takes no named filters and its behavior
  is stable across versions
