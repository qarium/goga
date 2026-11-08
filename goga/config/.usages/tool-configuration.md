# config — reading tool configuration

How to read a tool config file through the `goga.config` facade. For
consumers that need a tool's own configuration: the tool dispatcher's
config injection, tool packages reading their sibling files,
higher-level orchestration.

`load_tool_config` takes the tool identity and a file name — verbatim,
with extension — and returns the raw parsed content as-is, or `None`
when the file is absent. The path standard is fixed on both sides:
`.goga/tools/<tool>/<filename>`.

## Reading a tool config

    from goga.config import load_tool_config

    data = load_tool_config("coverage", "config.yml")     # mapping, string, list — as parsed
    data = load_tool_config("coverage", "overrides.yml")  # None when absent

- Absence is the normal state of a tool config — `None`, never an
  error.
- The file name is flat and verbatim: non-empty, no separators, no
  `.` or `..` — anything else is a clean error naming the file name.
- The returned value is the raw parse — no models, no validation, no
  merging with the project or home layers, no caching.
- Interpreting the content is the consuming tool's responsibility.
- Tests may pass a `root` directory override to read a prepared tree.

## The standard

The onboarding engine is the single writer: it buffers verbatim file
names and writes them under the same path. Reading follows the write
side exactly — no suffix rules, no fallbacks.

## Environment references (!ENV)

Tool config files resolve `!ENV NAME` scalars the same way the project
configuration does — at load time, to the variable's string value.

    # .goga/tools/coverage/config.yml
    fail_under: !ENV COVERAGE_THRESHOLD

- Unset variable → the empty string `""`; the interpreting tool applies
  its own semantics to it.
- Resolution is a string, never a number or bool — a tool expecting an
  int must parse it itself.
- Malformed use fails the read with the yaml library's own error naming
  the file position.
