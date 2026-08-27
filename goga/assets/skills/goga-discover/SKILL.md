---
name: goga-discover
description: Interview the user relentlessly about a decision until every branch of the design tree is resolved, then record the result as a short ADR.
---

# Goga discover

Interview the user relentlessly until you reach a shared understanding on a decision worth recording. Map this as a **design tree**: every decision branches into the decisions that hang off it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled — the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round: number each question and give your recommended answer. Then wait for the user's answers before the next round.

Each question should be formatted like so:

```
❓ **Q1** - **<question title>**: <question body, might be multiple paragraphs, including multiple choices>

➡️ <your recommended answer>
```

Each round the user answers reshapes the tree — settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it — don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report — ask the rest of the frontier now. The _decisions_ are the user's — put each to them and wait.

The interview is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not write the ADR until the user confirms you have reached a shared understanding.

Once confirmed, write the ADR to `.goga/history/<year>/<topic>/adr.md` (`<topic>` is a slug name, lowercase kebab-case; `<year>` is the current year in `YYYY` format, 4 digits, zero-padded; create the directory lazily if needed), following `adr-template.md` from the current skill directory.

## Research

### Initialization

Load these skills via the **Skill tool** before starting the interview.

- **`goga-cell`** — DSL specification: cell and CODEMANIFEST structure, directives, and syntax.
- **`goga-lang-disp`** — language implementation rules: naming, signatures, and location for the target language (routes to the per-language skill).

These skills are loaded **read-only**: use them solely to understand and discuss the existing project architecture — to read `goga schema` output and existing CODEMANIFEST and usage files. They do not license you to produce contracts, signatures, or cell layouts.

### Project structure

To understand the architectural diagram of the project, use:
```bash
goga schema
```

To understand the json of diagram, use `goga schema --help`.

## Context structure

Keep a working context in your context window — do not write it to disk. The structure:

```yaml
terms:    # glossary: term -> definition, captured during the interview
  <term>: "<short, crisp definition>"
decided:  # what has been settled in this session, not to be re-litigated
  - "<short statement of the decision>"
```

Append to it as the interview progresses — never overwrite, only add. After each round, update `terms` with new or sharpened definitions, and `decided` with anything the user has confirmed.

### Active term work

Challenge terms as you go. Specifically:

- **Fuzzy term surfaced?** Don't let it pass. Pin it down with a concrete definition before moving on — propose one and put it to the user.
- **Overloaded word?** If one term is doing two or three jobs across questions, name the conflict explicitly, propose split definitions, and ask the user to choose.
- **User uses a term informally?** Capture the formal version in `terms` and use it consistently from then on.
- **Term already in `terms`?** Use that exact definition in subsequent questions — don't re-coin, don't paraphrase, don't drift.

### Why

The ADR's "why" only makes sense if the vocabulary it uses is sharp.

## Constraints

- To understand the project, read only the architectural diagram, CODEMANIFEST and usage files.
- Never design cells or CODEMANIFEST contracts — even when the user's constraints sound architectural. That is outside this skill's scope.
- Do not propose or discuss: type signatures, method/property lists, `location` values, Entities vs Routines, cell boundaries, Imports/Usages wiring, or CODEMANIFEST structure. If a question drifts there, do not answer it — record the open point in the ADR as an unresolved question and move on.
- Interview outputs are decision records about the problem, its terms, and its constraints — not contracts.
