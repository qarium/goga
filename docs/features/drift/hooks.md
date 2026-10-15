# Drift — Hooks

The drift domain exposes **no hook actions of its own** — the comparison is a pure pass over the two assembled views with no extension points. Tool packages cannot amend or veto the report.

The declared view is not hook-free, though: it is produced by [`goga schema`](../schema/cli.md), whose [checkpoints](../schema/hooks.md) — the per-cell amendment and the whole-tree validation gate — run inside every drift comparison. Both are hard actions: a failing or vetoing hook stops the command as an execution failure (exit code `2`), the reason on stderr, nothing on stdout — a declared view that could not be built is not a discrepancy.

The platform mechanism behind hook actions in general is covered in [Hooks](../hooks/index.md).
