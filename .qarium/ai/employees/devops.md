# DevOps

## Config

| Key            | Value            | Description                                 |
|----------------|------------------|---------------------------------------------|
| ci_provider    | github-actions   | CI provider                                 |
| trigger_branch | 0.0.x            | Default branch for triggers                 |
| diff_range     | HEAD~5           | Git diff range for auto-analysis in feature |

## Rules

### Workflow Registry

| Workflow    | File               | Trigger                    | Purpose                        |
|-------------|--------------------|----------------------------|--------------------------------|
| Lint        | lint.yml           | push/PR to 0.0.x           | Ruff lint + format check       |
| Tests       | tests.yml          | push/PR to 0.0.x           | Pytest via reusable workflow   |
| Docs        | docs.yml           | push to 0.0.x              | MkDocs deploy to GitHub Pages  |
| Strictacode | strictacode.yml    | push/PR to 0.0.x           | Code quality analysis          |

### Conventions

## Lessons

| Problem | Why | How to prevent |
|---------|-----|----------------|
