# commands — the hooks command

How to inspect the hooks registered by the installed tool packages. For
goga users; the command reads the registry and prints it.

## The tree

    goga hooks

One tool line per tool with registrations; under a tool, one domain line
per domain; under a domain, the actions the tool subscribed to. A refused
registration prints its reason. A tool without registrations prints its
line alone. No root line.

## The slice

    goga hooks --tool my-tool
    goga hooks -t my-tool -t other-tool

The repeatable option narrows the tree to the named tools — the name
without the goga_tool_ prefix, as the tool line of the tree shows it.
A requested tool without registrations shows its empty entry.

## Behavior

- The command assembles the registry once at start; a broken package
  import fails the command with the package name.
- The view states the fact of registration, not whether a hook ran in a
  particular command.
- An empty result prints nothing and exits 0.
