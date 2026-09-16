# topics — entering the todo of a topic

How to collect or edit the todo.md of a topic in one call with the
`goga.topics` facade. For consumers that continue work on a topic: the
switch and ensure orchestrations, the command layer.

`enter_topic_todo` opens the external editor with the topic's todo.md —
the existing content when the file exists, an empty entry otherwise —
and writes the saved text without a commit.

    from goga.topics import enter_topic_todo

    written = enter_topic_todo("feature-foo")           # current year
    written = enter_topic_todo("Feature/Foo_Bar", year="2025")

- Saved text -> todo.md overwritten as entered plus a trailing
  newline, UTF-8 — no commit. The written content is the final
  amended text when a tool package subscribes an amendment hook —
  the saved text passes through the todo-entry amendment before the
  write.
- Cancelled entry (empty or unchanged file) -> False, the file stays
  untouched.
- The topic directory must exist — creation belongs to the caller.
- A missing interactive terminal is a clean error before anything.
