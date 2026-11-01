# Contributor Profiles

## Problem

Each contributor in the repository may have different subscriptions to different LLMs, and they may work on different agent harnesses. Today this can only be solved by maintaining separate workflows, which is a bad path: there is no single configuration point for extending the process.

## Desired capability

- Create **profiles** (per-contributor definitions, e.g. LLM subscription, agent harness).
- Reference and pin profile data inside workflows.
- Support specifying **env variables on a stage** in a workflow; this requires generating a wrapper for invoking the sh script.

## Open idea

The workflow yml file could start supporting template syntax (e.g. profile interpolation). Other options are welcome.
