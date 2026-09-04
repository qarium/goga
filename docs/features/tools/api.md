# Tools — API

The facade of the domain package **`goga.commands.tool`** — the dynamic invocation of an installed tool package.

The signatures below are the CODEMANIFEST contract of the cell.

```python
tool(name: str, args: list[str])
build_injections(main: Callable) -> dict[str, object]
```

- `tool` — resolve the `goga_tool_<name>` package installed in the running interpreter, import it, and call its `main` facade with `args`. The call is transparent: the tool's output and exit behavior pass through unchanged; a missing package or a broken import surfaces as a clean CLI error.
- `build_injections` — inspect a tool's `main` callable and build the opt-in injection values for the parameters it declares (the keyword-capable `ast` parameter receives the project AST). A `main` that declares no injections receives an empty mapping and the AST is never built.

A tool package's own facade API — `main(argv)`, `install(user)`, `register_hooks(hooks)` — is authored by the tool; the contract of each callback is covered in [Hooks](hooks.md).

## Example

```python
from goga.commands.tool import tool

tool("mkdocs", ["--help"])
```
