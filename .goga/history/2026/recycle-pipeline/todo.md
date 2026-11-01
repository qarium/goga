We need to support a repeating pipeline cycle. In the AFM flow file, it looks like this:

```
repeat:
  max_cycles: 3 # total passes including the first; 0 (default) = unlimited
  keep_runs: 2 # successful runs to retain; 0 = retain all (default: 2)
```

But it could just be short: `repeat: true`.

Add `repeat: true` to the pipeline metadata, next to the name and description, and repeat in the workflow settings file.

Additionally, let's simplify the description of assistants in the workflow.

Now

```
assistants:
  - name: architector
    agent: claude
    ...
```

It should become
```
assistants:
  architector:
    agent: claude
```

In stages too.