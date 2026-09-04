# goga hooks

Inspect the hooks registered by the installed tool packages.

## Synopsis

```bash
goga hooks [--tool NAME]...
```

## Description

`goga hooks` assembles the run registry once — it imports every installed `goga_tool_*` package and runs its `register_hooks` callback — and prints the registrations as a tree: tool, then domain, then action. It states the **fact of registration**, never whether a hook ran in a particular command. See [Hooks — the registration contract](hooks.md) for the registration contract.

## The tree

```text
$ goga hooks
mkdocs
  statuses
    register_statuses  published
    register_statuses  sync
scriba
  statuses
    register_statuses  published
  rejected statuses/register_statuses "dup": repeated name on the same address
```

- One tool line per tool with registrations — the tool identity, the package name with the `goga_tool_` prefix dropped and underscores turned into hyphens. There is no root line: the tools are the top level.
- Under a tool, one domain line per distinct domain of its subscriptions, ordered alphabetically.
- Under a domain, one line per subscription — the action name and the hook name.
- Every refused registration prints with its reason.
- An empty registry prints nothing and exits `0`.

## The slice

`-t`/`--tool` narrows the tree to the named tools. The option is repeatable; the name is the tool identity — without the `goga_tool_` prefix — as the tool line of the tree shows it. A requested tool without registrations keeps its entry with an empty list; an unknown name is not an error.

```bash
goga hooks --tool my-tool
goga hooks -t my-tool -t other-tool
```

## Behavior

- The registry assembles once at the start of the command; it is never cached between runs — package edits apply from the next run, without reinstall.
- A broken package import fails the command with a clean error naming the package (stderr, exit `1`, no traceback).
- Commands that use no hooks never build the registry and never enumerate the packages; only this command and the hook checkpoints do.

## Exit Codes

| Code | Meaning                              |
|------|--------------------------------------|
| `0`  | Success — an empty registry included |
| `1`  | Error — a broken package import      |

## Examples

List every registered hook of the environment:

```bash
goga hooks
```

Inspect one tool only:

```bash
goga hooks --tool mkdocs
```
