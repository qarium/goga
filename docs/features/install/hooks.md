# Install — Hooks

The install domain exposes **no hook actions** of its own — it invokes a tool-package **lifecycle callback** instead.

## The post-install hook

A tool package **may** expose an `install(user: str | None = None)` callable in its facade. `goga install` calls it after a successful pip, passing the initiating user (`SUDO_USER` when goga itself runs under sudo, else the current OS user) only when the parameter is declared keyword-capable; otherwise the hook is called with no arguments.

- A missing or non-callable `install` is skipped quietly.
- A failing hook exits 1 — the tool name and hook message go to stderr, the pip package stays, activation does not run, and a bulk install stops at the first failing hook.
- The hook still runs under `--no-connect` (the flag skips activation only).
- In local mode, the `:<tool-name>` suffix of `--local` names the tool whose hook runs; without it no hook runs (a warning is logged).

The invocation surface is covered in [CLI — post-install hooks](cli.md#post-install-hooks). The domain hook actions (a tool's `register_hooks` subscriptions) are the [Hooks](../hooks/hooks.md) platform — fired at domain checkpoints, not at install time.
