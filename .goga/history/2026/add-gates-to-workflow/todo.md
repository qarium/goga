# Add gates to workflow

Reed doc for understand DSL syntax in AFM flow file: https://akopichin.github.io/afm/verify/

## Workflow file example

```yaml
gates:
  patience: 1 # review_patience
  max_iterations: 5 # max_failures
  fresh_correction: false

stages:
   stage:
     prompt: |
       Example prompt
     gates:
       - script: pytest ./
          timeout: 30m # 1h by default
       - agent: codex
          prompt: |
            Example review prompt
```