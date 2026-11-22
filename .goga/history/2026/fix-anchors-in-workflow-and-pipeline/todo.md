There's currently an issue with supporting YAML links in workflows and pipeline files. It was necessary to ensure that declaring starting points wouldn't cause parsing issues.

```yaml
.anchor: &anchor
  prompt: ...

stages:
  <<: &anchor
```