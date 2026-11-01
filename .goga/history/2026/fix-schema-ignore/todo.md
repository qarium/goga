Why does goga schema fail?

In short: the team builds an AST without an ignore list and therefore goes down to .venv/, where the swax and resq pip packages appeared on October 22nd with their
CODEMANIFEST — their contracts are validated against the goga root and fail due to 160 rules.

Chain:

1. goga/schema/schema.py:185 ​​— schema() calls AST(".") without ignore. The traversal in AST.load() (goga/ast/ast.py:98) recursively enters .venv/.
2. On October 22nd at 6:12 PM, swax 1.0.0 ("tool for test plan generation based on AI") and resq 1.0.0 were installed in the project venv — they are not in pyproject,
installed manually. Both are Goga-managed projects; their wheels carry CODEMANIFESTs directly inside site-packages/swax/** and site-packages/resq/**.
3. Rules resolve paths from the cwd (the root of the Goga repository), not from the manifest location:
- ImportHasValidFromPath (goga/ast/rules/document/imports/rules.py:159) — swax/config does not exist at the root of Goga;
- UsageFilepathExists — .goga/usages/cooks/pyyaml.md, anthropic.md, openai.md, etc. are not in this repo;
- EmbeddedTypeHasLowLevel — 7 errors on embedded resq types (Requests, Session, Response, etc.).
Total: 153 DocumentRuleErrors + 7 ASTRuleErrors = 160.
4. schema() throws a ValueError if errors is non-empty (schema.py:189).

Why does goga lint work? It reads lint.ignore from .goga/config.yml (which contains .venv/, build/, example/) and passes it to AST(".",
ignore=...) (goga/commands/lint/lint.py:51). However, schema, contract, and tool ignore are not passed—the comment in ast.py:89–91 explicitly states this
"backward compatible for schema/review/contract."

Hypothesis check: AST('.', ignore=['.venv']) → 0 errors, tree = single root cell goga. In other words, all 160 errors are exclusively from
venv, the project itself is clean.
