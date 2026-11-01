# Loading a workflow-file with rendering

## Domain

The single loading chain that turns a workflow-file path into a parsed
`WorkflowDocument` under an active profile: read, default-peek,
activation, profile resolution, whole-file rendering, parsing. Target
audience: consumers that load workflow-files — the pipeline run
coordination and card (goga/pipeline, through `resolve_workflow`) and
the build path (goga/build, through `resolve_build_workflow`).

## The chain

```python
from goga.pipeline.workflow import load_workflow

loaded = load_workflow(
    workflow_path,
    cli_profile=profile_flag,  # --profile value, or None
    env_profile=goga_profile,  # GOGA_PROFILE value, or None
    home_profiles=decoded_bundle,  # decode_home_profiles(...) result
)
document = loaded.document  # WorkflowDocument
profile = loaded.profile  # ResolvedProfile | None
```

Steps performed by the chain:

1. Reads the file text (a missing file raises OSError — callers guard
   existence).
2. Peeks a literal top-level `profile:` value from the RAW text. The
   default must be authorable as a plain line: `profile: default`. A
   value that materializes only through template rendering does not
   participate in activation.
3. Resolves the effective profile name (CLI > environment > workflow
   default).
4. Loads the profile when a name resolved — project lookup first
   (`<cwd>/.goga/profiles/`), then the home bundle mapping. Missing or
   malformed → strict pre-run failure.
5. Renders the WHOLE file as a Jinja template with the profile content
   as the context. No activation → empty context; a file without
   template syntax renders to itself.
6. Parses the rendered text through the standard grammar and structural
   validation — unchanged rules; rendering never bypasses validation.
7. Returns the document and the profile that was active during the
   render.

## What the consumer owns

- The channel values: the CLI flag value and the `GOGA_PROFILE` value
  arrive as parameters — the chain reads no environment.
- The home bundle: decode `GOGA_HOME_PROFILES` (goga/docker) before the
  call and pass the mapping.
- The workflow path: composition, containment guards, and existence
  checks belong to the caller.

## Failure modes (all pre-run, all strict)

- Missing profile (name resolved, file absent in both locations) —
  names the profile and both lookup locations.
- Malformed profile file (invalid YAML, non-mapping) — names the
  profile and path.
- Jinja syntax error — names the workflow file and the line.
- Rendered workflow failing structural validation — the standard
  structural errors, unchanged.

## Interplay with skip merges

A skip merge (goga/pipeline) rebuilds the document in memory; the
`profile` and `build` fields survive the rebuild verbatim, exactly as
the memory configuration does.
