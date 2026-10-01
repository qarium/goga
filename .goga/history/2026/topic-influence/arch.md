# [ARCHITECTURE_PLAN]

## Topic

**topic-influence — Topics workflow: scriptable stdin todo, one-entry-per-topic board, JSON output.**

Plan path: `.goga/history/2026/topic-influence/arch.md` (the path printed by `goga history path -f arch.md`).

Source task: `.goga/history/2026/topic-influence/task.md` (PRD + ADR synchronized; on conflict the ADR wins).

## Implementation Order

1. **`goga/topics`** (MODIFIED) — designed first: it depends only on unchanged leaf cells (`goga/history`, `goga/topics/git`, `goga/topics/editor`, `goga/topics/hooks`); the CLI cell imports the two new exports (`BoardEntry`, `aggregate_topic_board`) that this cell defines.
2. **`goga/commands/topics`** (MODIFIED) — designed second: it depends on `goga/topics` (extended contract), `goga/config`, `goga/config/hooks`; nothing depends on it below `goga/commands` (group registration unchanged).
3. **Project practices** — `.goga/usages/cooks/click.md` updated with the optional-value option section; `.goga/usages/cooks/beautiful_json.md` connected by path (no edit).

No cell is created anew; both cells are modifications of existing contracts (per the Artifact Resolution of the primary analysis).

## Artifacts

### Cell: `goga/topics` (MODIFIED)

Change summary against the current manifest:
- **Header — Annotations**: ownership paragraph rewritten in current state — two board projections, the todo acquisition ladder, the stdin channel clause (read once at todo-resolution time; a terminal stdin is never read). Imports and Usages keys unchanged.
- **Body — added**: `BoardEntry` (entity), `aggregate_topic_board` (routine) in `board.py`.
- **Body — changed**: `BoardRecord` (audit-view re-title, per-host statuses wording), `collect_topic_board` (signature gains `hosts: tuple[str, ...] | None = None`; algorithm step 9 — the filter; one requirement added), `create_topic` (signature gains `todo_from_stdin: bool = False`; algorithm step 2 — the acquisition ladder; step 3 — the ask condition; three requirements and one constraint added).
- **Body — unchanged (carried verbatim)**: `SwitchCandidate`, `resolve_switch_candidates`, `switch_topic`, `ensure_topic`, `enter_topic_todo`, `check_branch_occupancy`, `publish_topic`, `check_slug_occupancy`, `DeleteTarget`, `resolve_delete_targets`, `delete_topics`.
- **Footer**: `Description` updated to the current state; `Author`/`CreatedAt` unchanged.

**CODEMANIFEST** — complete file content:

```yaml
Imports:
  - Types:
      - normalize_topic_slug
      - resolve_current_branch_name
      - topic_exists
      - ensure_topic_dir
      - resolve_history_root
      - resolve_topic_status
      - resolve_topic_dir
      - resolve_topic_file
      - current_year
      - StatusScale
      - assemble_status_scale
      - collect_history_tree
      - remove_topic_dir
    Usages:
      - topic-paths
      - topic-statuses
    From: goga/history
  - Types:
      - BranchRef
      - list_branch_refs
      - read_ref_tree_paths
      - read_ref_file
      - checkout_local_branch
      - create_branch_from_remote_tracking
      - create_and_switch_branch
      - is_working_tree_clean
      - resolve_ref_commit
      - commit_file_on_base
      - create_branch_at_commit
      - delete_local_branch
      - delete_remote_branch
      - push_branch
      - origin_configured
    Usages:
      - refs-and-switching
      - publishing
      - deleting
    From: goga/topics/git
  - Types:
      - edit_text
    Usages:
      - editor-entry
    From: goga/topics/editor
  - Types:
      - TopicIdentity
      - TopicHooks
      - CreationDraft
      - TodoEntryDraft
    Usages:
      - checkpoints
    From: goga/topics/hooks

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  Use the `click` practice for the interactive moments of the domain:
  the numbered candidate selection, the publication ask, and the
  non-interactive detection with its clean error.
  Use the `editor-entry` practice for the editor session patterns.
  Use the `topic-paths` practice for the consumer patterns of the
  history facade — the topic slug, the topic directory of a year, the
  existence oracle, the topic todo file path, and the current branch.
  Use the `topic-statuses` practice for the status scale patterns of
  the history facade — scale assembly and maximal-status computation.
  Use the `refs-and-switching` practice for the git patterns of the
  topics git cell — the branch inventory, ref tree reading, and file
  reading without checkout.
  Use the `publishing` practice for the quarantined commit building,
  branch planting, publication, and rollback patterns of the topics git
  cell.
  Use the `deleting` practice for the symmetric local-and-origin
  removal and the restore-on-failure patterns of the topics git cell.
  Use the `checkpoints` practice for the lifecycle checkpoint patterns
  of the topics hooks zone — the identity construction, the amendment
  delivery before the content is fixed, and the notification emission
  after the moment.

  This cell owns the topics domain — the work-tracker view of the
  history tree: the cross-branch topic inventory of one year in two
  projections — the per-host records, one per topic and hosting
  branch, as the single source of board facts, and the aggregated
  one-entry-per-topic view computed from them, each entry with its
  own branch, the hosts carrying the topic's history, the own
  branch's statuses, and the todo summary; the switch-identifier
  resolution and switching orchestration with the optional todo
  entry; the creation procedure off an explicit base with its todo
  acquisition ladder — an explicit value, else the declared stdin
  source, else the interactive editor, else a clean error — with the
  preflight and the publication ask that skips itself when the todo
  came from stdin: by default one quarantined todo commit planted as
  the branch without a switch, under the switch flag the checked-out
  branch with its working-copy topic directory; the fast
  creation-and-publication procedure — a committed branch off an
  explicit base without switching, pushed to origin, rolled back
  fully on a failed publication; the combined ensure orchestration
  of the fast process — always from the current HEAD, the topic
  directory ensured on any hosting branch, the todo entry after the
  switch or the creation; the todo entry of an existing topic; and
  the identified-topic deletion — the local branch, the origin twin,
  and the topic directory removed symmetrically with restore on
  failure. The domain opens its lifecycle to tool packages through
  its hooks zone: the creation, publication, switch, todo-entry, and
  deletion checkpoints fire inside the domain routines — a failing
  hook of the soft actions warns and never breaks the operation, and
  every event fact comes from the operation's own data; every todo
  source — value, stdin, editor — passes through the same amendment
  hooks. Topic identity, addressing, and statuses belong to the
  history facade; git access to the topics git cell; the editor
  session to the editor cell; the stdin channel belongs to the
  domain and is read once, at todo-resolution time — a terminal
  stdin is never read. Git infrastructure failures and the fatal
  scale-assembly ImportError surface as click.ClickException.
  Mutations are local-only except the two pushes — publication and
  deletion; no fetch ever happens. Use relative imports.

---

"BoardRecord(topic: str, branch: str, statuses: list[str], current: bool, remote: bool, todo: str | None = None)":
  location: board.py
  annotations: |
    One row of the board audit view — a topic hosted by one branch;
    the per-host records are the single source of the board's facts.

    `topic`: the topic slug
    `branch`: the display name of the hosting branch
    `statuses`: the qualified names of the maximal present statuses of
                this hosting branch, in scale order
    `current`: True when the row hosts the current working branch
    `remote`: True when the hosting ref is remote-tracking
    `todo`: the todo summary of the topic — the first line of todo.md that
            yields a non-empty result after leading # markers are stripped
            and the edges trimmed — or None when the topic has no todo.md

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "topic -> str": |
      The topic slug — the directory name of the topic.
    "branch -> str": |
      The display name of the hosting branch.
    "statuses -> list[str]": |
      The maximal present status names of the topic on this hosting
      branch, in scale order.
    "current -> bool": |
      True when the row hosts the current working branch.
    "remote -> bool": |
      True when the hosting ref is remote-tracking.
    "todo -> str | None": |
      The todo summary of the topic, or None when the topic has no
      todo.md. The summary is computed for display — the file itself is
      never modified; a todo.md whose every line reduces to emptiness
      yields the empty summary.

"collect_topic_board(year: str | None = None, remote: bool = False, hosts: tuple[str, ...] | None = None) -> records: list[BoardRecord]":
  location: board.py
  annotations: |
    Collect the cross-branch topic inventory of one year — one record
    per topic and hosting branch pair: the complete audit view and the
    single source of the board's facts.

    `year`: optional year as four digits; None means the current year
    `remote`: True reads remote-tracking refs instead of local branches
    `hosts`: optional hosting-branch display names — None or empty
             keeps every record; when non-empty, only the records
             whose branch display name exactly equals one of them
             survive, union across values; an unknown name yields the
             empty list, never an error
    `records`: one `BoardRecord` per topic and hosting branch, sorted by
               scale order of the first maximal status, then
               alphabetically by topic

    Apply the `topic-paths` practice for the year and tree-root patterns.
    Apply the `topic-statuses` practice for the scale assembly and
    maximal-status computation.
    Apply the `refs-and-switching` practice for the inventory,
    tree-reading, and file-reading patterns.

    Algorithm:
    1. Resolve the year — `year` when given, otherwise the current year
       via `current_year`
    2. Assemble the status scale via `assemble_status_scale` once
    3. Local mode enumerates local branches via `list_branch_refs` and reads
       the current branch from the working copy via
       `resolve_current_branch_name`; remote mode enumerates the
       remote-tracking `BranchRef` entries of the same inventory only.
       Local mode takes the full inventory of `list_branch_refs` — a topic
       hosted only by a remote-tracking ref keeps its row with the remote
       marker
    4. Read the topic tree of every ref under the root resolved via
       `resolve_history_root` with `read_ref_tree_paths`, without checkout
    5. For every ref, take the topics of the resolved year with their
       artifact paths and compute the maximal statuses — the working copy
       over the directory composed by `resolve_topic_dir` via
       `resolve_topic_status`, every other ref via the `StatusScale`
    6. Read the todo summary of every hosted topic — the working copy from
       todo.md of its directory, every other ref from the todo.md of its
       ref tree via `read_ref_file`; the summary is the first line that
       yields a non-empty result after leading # markers are stripped and
       the edges trimmed — the normalization decides the choice, a line of
       # markers alone never qualifies; None when the file is absent, the
       empty string when no line qualifies; the file is never modified
    7. Collapse a local branch and its remote twin into one row — the local
       branch wins; different branches hosting one slug stay separate rows
    8. Mark the row hosting the current branch
    9. A non-empty `hosts` keeps the records of the named hosting branches
       only — exact display-name equality, union across values; the sort
       order of the survivors stays
    10. Sort by scale order of the first maximal status, then alphabetically
        by topic, and return the records

    Requirements:
    - The current branch is read from the working copy — uncommitted
      progress is visible; remote mode shows it through its remote twin
    - Read-only — no checkout, no worktree, no mutation of any kind
    - A year without topics yields an empty list — not an error
    - A multi-line todo.md yields its first qualifying line; a todo.md
      whose every line reduces to emptiness yields the empty summary
    - The todo summary never affects the sort order
    - An unknown `hosts` name yields the empty list — not an error

    Constraints:
    - Do not render — output shaping belongs to the consumer
    - Do not cross the year boundary — other years are invisible here

"BoardEntry(topic: str, branch: str, hosts: list[str], statuses: list[str], current: bool, remote: bool, todo: str | None = None)":
  location: board.py
  annotations: |
    One entry of the default board — one topic that still has its own
    branch, with every branch carrying the topic's history.

    `topic`: the topic slug
    `branch`: the display name of the topic's own branch — the hosting
              branch whose branch part (the whole name of a local
              branch, the short name of a remote-tracking ref)
              normalizes into the topic slug
    `hosts`: the display names of every branch carrying the topic's
             history, the own branch included, alphabetical
    `statuses`: the qualified names of the maximal present statuses of
                the own branch, in scale order
    `current`: True when the current working branch hosts the topic
    `remote`: True when the own branch is a remote-tracking ref
    `todo`: the todo summary of the topic read from the own branch — or
            None when the topic has no todo.md

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "topic -> str": |
      The topic slug — the directory name of the topic.
    "branch -> str": |
      The display name of the topic's own branch — the hosting branch
      whose branch part (the whole name of a local branch, the short
      name of a remote-tracking ref) normalizes into the topic slug.
    "hosts -> list[str]": |
      The display names of every branch carrying the topic's history,
      the own branch included, alphabetical by display name.
    "statuses -> list[str]": |
      The maximal present status names of the topic on its own branch,
      in scale order.
    "current -> bool": |
      True when the current working branch hosts the topic.
    "remote -> bool": |
      True when the own branch is a remote-tracking ref.
    "todo -> str | None": |
      The todo summary of the topic read from the own branch, or None
      when the topic has no todo.md; a todo.md whose every line reduces
      to emptiness yields the empty summary.

"aggregate_topic_board(records: list[BoardRecord], hosts: tuple[str, ...] | None = None) -> entries: list[BoardEntry]":
  location: board.py
  annotations: |
    Project the per-host records into the default board — exactly one
    entry per topic that still has an own branch.

    `records`: the collected per-host records — the source of facts
    `hosts`: optional hosting-branch display names — None or empty
             keeps every entry; when non-empty, only the entries
             whose hosts list contains one of them survive, union
             across values; the own-branch requirement stands first —
             the filter never resurrects a topic without an own
             branch; an unknown name yields the empty list, never an
             error
    `entries`: one `BoardEntry` per topic with an own branch, sorted by
               scale order of the first maximal status, then
               alphabetically by topic

    Apply the `topic-paths` practice for the slug normalization pattern.

    Algorithm:
    1. Group the records by topic slug
    2. Hosts list of a topic — the branch display names of its records,
       alphabetical; a local branch and its remote twin count as one
       host under the local name — the collapse belongs to the
       collection
    3. Own branch — the topic's records whose branch part — the whole
       display name of a local branch, the short name (the part after
       the first "/") of a remote-tracking ref — normalizes into the
       topic slug via `normalize_topic_slug`; a remote-tracking ref
       qualifies; a topic without an own branch produces no entry —
       its history survives only in merged hosts
    4. Several own branches collide -> the deterministic winner: the
       record hosting the current branch, otherwise a non-remote record
       over a remote-tracking one, otherwise the first in the
       display-name alphabet
    5. The entry carries the winner's statuses, remote marker, and todo
       summary; the current marker is True when any record of the topic
       hosts the current branch
    6. Sort by scale order of the first maximal status, then
       alphabetically by topic
    7. A non-empty `hosts` keeps the entries whose hosts list contains
       any given name — union; None or empty keeps every entry

    Requirements:
    - Read-only over `records` — no mutation, no re-sort of the input;
      no git access happens here — every fact comes from the records
    - Both board views derive from one collection pass — this routine
      computes, it never reads the ref trees
    - A topic without an own branch produces no entry, whatever hosts
      carry it
    - The filter never resurrects a hidden topic — the own-branch
      requirement precedes it
    - An empty `records` yields the empty list

    Constraints:
    - Do not render — output shaping belongs to the consumer
    - Do not cross the year boundary — the records already scope it

"SwitchCandidate(branch: str, topic: str | None, statuses: list[str], current: bool, remote: bool)":
  location: switching.py
  annotations: |
    One candidate of a switch-identifier resolution — a branch that may
    host the requested work.

    `branch`: the display name of the candidate branch
    `topic`: the topic slug the branch hosts, or None for a branch without
             a topic
    `statuses`: the qualified names of the maximal present statuses, in
                scale order
    `current`: True for the current branch
    `remote`: True when the candidate ref is remote-tracking

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "branch -> str": |
      The display name of the candidate branch.
    "topic -> str | None": |
      The topic slug the branch hosts, or None for a branch without a
      topic.
    "statuses -> list[str]": |
      The maximal present status names of the candidate's topic, in scale
      order — empty for a branch without a topic.
    "current -> bool": |
      True for the current branch.
    "remote -> bool": |
      True when the candidate ref is remote-tracking.

"resolve_switch_candidates(identifier: str, year: str | None = None) -> candidates: list[SwitchCandidate]":
  location: switching.py
  annotations: |
    Resolve a switch identifier into its candidate branches.

    `identifier`: the user input — a branch name, a topic slug, or their
                 prefix
    `year`: optional year as four digits; None means the current year
    `candidates`: the matching candidates, exact matches first, then prefix
                  matches

    Apply the `topic-paths` practice for the slug normalization and current
    branch patterns.
    Apply the `refs-and-switching` practice for the inventory and
    tree-reading patterns.

    Algorithm:
    1. Normalize `identifier` into a slug via `normalize_topic_slug`
    2. Collect the branch inventory and the topics of the resolved year
    3. Exact branch name match -> the candidates hosting that name
    4. Exact slug match otherwise -> the branches hosting the slug, local
       branches first
    5. Prefix matches otherwise -> the branches whose name starts with
       the raw `identifier`, and — when the slug is non-empty — the
       branches hosting a topic whose slug starts with it
    6. Collapse the tier to one entry per branch, then return the
       candidates with their statuses

    Requirements:
    - Exact matches always precede prefix matches
    - A branch appears in the result once — a local branch beats its
      remote twin, and a branch hosting several topics of the year
      contributes its first entry only, so an unambiguous identifier never
      reaches a prompt
    - A branch without a topic is a valid candidate
    - Read-only — no mutation before a choice

    Constraints:
    - Do not choose among multiple candidates — selection belongs to the
      caller

"switch_topic(identifier: str, todo: bool = False, year: str | None = None) -> result: str":
  location: switching.py
  annotations: |
    Bring the repository onto the branch hosting the requested work;
    with the todo flag, enter the todo of the switched topic after the
    switch.

    `identifier`: the user input — a branch name, a topic slug, or
                 their prefix
    `todo`: True enters the todo of the switched topic
    `year`: optional year as four digits; None means the current year
    `result`: one line describing the outcome

    Apply the `click` practice for the numbered selection prompt and
    the non-interactive detection.
    Apply the `refs-and-switching` practice for the checkout and
    remote-tracking branch patterns.
    Apply the `checkpoints` practice for the switch notification.

    Algorithm:
    1. `todo` without an interactive terminal -> clean error before any
       switching
    2. Resolve the candidates via `resolve_switch_candidates`; none ->
       clean error with a hint to the board; several -> the numbered
       list with statuses and the number prompt, or the failure with
       the list without interactive input
    3. `todo` and the chosen candidate hosts no topic -> clean error —
       switching creates nothing; nothing fires
    4. Already on the hosting branch -> idempotent success without
       mutation; with `todo` the entry still runs
    5. A mutation is needed -> probe the working tree cleanliness
       first via `is_working_tree_clean`; a dirty tree is a clean
       error; local host -> check out the branch via
       `checkout_local_branch`; remote-only host -> create the local
       branch from the remote-tracking ref via
       `create_branch_from_remote_tracking`
    6. Emit topic_switched over `TopicHooks` — the identity via
       `TopicIdentity`: the hosted slug of the chosen candidate when
       it hosts one, the resolved year, the branch as entered; the
       branch-only identity when it hosts none — and the outcome kind:
       already-on-branch, local-checkout, or created-from-remote
    7. With `todo` -> enter the todo of the topic via
       `enter_topic_todo`, passing the switched branch as the branch
       fact
    8. Return the single result line

    Requirements:
    - Every mutation is local — no network, no fetch, no push
    - Nothing is mutated before the candidate choice is complete
    - The result is exactly one line
    - topic_switched fires on every completed switch, every outcome
      included; the identity degrades to branch-only when the chosen
      candidate hosts no topic
    - `todo` onto a branch hosting no topic keeps the clean
      pre-mutation error and fires nothing
    - The identity facts are the operation's own data — the hosted
      slug of the chosen candidate, the resolved year, and the branch
      name

    Constraints:
    - Do not create a topic for a branch without one
    - Do not commit the todo write
    - Do not manage the stages of the hosting pipeline — continuation
      belongs to the pipeline itself
    - Do not return to the previous branch — the switch is the outcome

"ensure_topic(identifier: str, todo: bool = False, year: str | None = None) -> result: str":
  location: ensuring.py
  annotations: |
    Bring the repository onto the requested work, creating it when
    nothing hosts the identifier; with the todo flag, enter the todo of
    the work after the switch or the creation.

    `identifier`: the user input — a branch name, a topic slug, or
                 their prefix
    `todo`: True enters the todo of the work
    `year`: optional year as four digits; None means the current year
    `result`: one line describing the outcome

    Apply the `click` practice for the interactive moments inherited
    from the switch orchestration.
    Apply the `topic-paths` practice for the slug and topic-directory
    patterns of the creation.
    Apply the `refs-and-switching` practice for the checkout and
    create-and-switch patterns.
    Apply the `checkpoints` practice for the creation amendment and
    the creation notification of the fast creation.

    Algorithm:
    1. `todo` without an interactive terminal -> clean error before any
       action
    2. Resolve the candidates via `resolve_switch_candidates`
    3. No candidate -> the fast creation: normalize `identifier` into a
       slug via `normalize_topic_slug`; an empty slug or an occupancy
       conflict — the oracles `check_branch_occupancy` and
       `check_slug_occupancy` — is a clean error; deliver the creation
       amendment over `TopicHooks` with the identity via
       `TopicIdentity` — the normalized slug, the resolved year, the
       branch name as entered — checked_out True, published False, no
       draft commit message (the path builds no commit), and no draft
       todo (the todo resolves later through the entry); create the
       branch named as entered from the current HEAD and switch to it
       via `create_and_switch_branch`; create the topic directory of
       the year via `ensure_topic_dir`; with `todo` enter the todo of
       the fresh topic via `enter_topic_todo`, passing the branch
       name as the branch fact — the entry starts only after the
       switch; after the creation completes, emit topic_created over
       `TopicHooks` — the identity, checked_out True, published False,
       the final todo when the entry resolved one, and no commit
       facts
    4. Otherwise -> the switch procedure via `switch_topic` without
       the entry — the switch notification fires inside it; with
       `todo`, take the hosted topic of the switched work — the
       resolution candidate of step 2 whose branch is the current
       branch read via `resolve_current_branch_name` (a remote-tracking
       candidate matches by its short name) — and: a hosted topic
       exists -> enter its todo via `enter_topic_todo` with the branch
       fact; the hosting branch hosts no topic -> an empty slug of its
       name is a clean error, otherwise create the topic directory of
       the year via `ensure_topic_dir`, then enter the todo of the
       fresh topic via `enter_topic_todo` with the derived identity —
       the slug normalized from the branch name, the resolved year —
       as the topic input and the branch fact; no creation checkpoint
       fires for the directory creation
    5. Return the single result line

    Requirements:
    - Creation happens only at zero candidates — a resolvable
      identifier never creates anything
    - The creation always starts from the current HEAD — the
      configuration base is never read here
    - With `todo`, no mutation follows the todo write — the creation
      notification alone may follow it
    - Every mutation is local — no network, no fetch, no push
    - The fast creation delivers the creation amendment exactly once,
      immediately before its first mutation, and emits topic_created
      after the creation completes — the identity-only amendment form
      is the norm on this path
    - Directory creation under the todo flag of a topic-less branch
      fires no creation checkpoint — the todo entry alone fires its
      two
    - The todo entries pass the operation's branch fact into the
      entry

    Constraints:
    - Do not ask about publication — the fast process publishes
      nothing
    - Do not manage the stages of the hosting pipeline — continuation
      belongs to the pipeline itself

"create_topic(branch_name: str, base_ref: str, todo: str | None = None, todo_from_stdin: bool = False, publish: bool = False, commit_message: str | None = None, year: str | None = None, switch: bool = False) -> result: str":
  location: creation.py
  annotations: |
    Create fresh work — a branch off an explicit base with the name as
    entered, its topic of the year, and an optional multi-line todo
    resolved through the acquisition ladder.

    `branch_name`: the branch name as entered by the user
    `base_ref`: the base revision the branch starts from — any revision
                string, resolved as git resolves it
    `todo`: the todo text; None or an empty string means no value
    `todo_from_stdin`: True declares stdin as the todo source — the
                       value-less request for the piped content
    `publish`: True takes the publication path without the ask
    `commit_message`: the message template; None applies the built-in
                      default
    `year`: optional year as four digits; None means the current year
    `switch`: True checks out the fresh branch after the creation —
              the topic directory and the todo land in the working
              copy, uncommitted, and the todo is optional; the default
              path quarantines the topic into the branch instead and
              needs the todo
    `result`: one line describing the outcome

    Apply the `click` practice for the publication ask and the
    non-interactive detection.
    Apply the `editor-entry` practice for the editor session.
    Apply the `topic-paths` practice for the slug, existence, directory
    creation, and todo-file path patterns.
    Apply the `refs-and-switching` practice for the checkout pattern.
    Apply the `checkpoints` practice for the creation amendment and
    the creation notification.

    Algorithm:
    1. Preflight, read-only and before any input: normalize
       `branch_name` into a slug via `normalize_topic_slug`; an empty
       slug is an input error; the current branch — read via
       `resolve_current_branch_name` — hosting the same slug is a
       conflict; the occupancy oracles `check_branch_occupancy` and
       `check_slug_occupancy` report a conflict; resolve `base_ref`
       into its commit via `resolve_ref_commit` — every conflict is a
       clean error with a hint to the board
    2. Resolve the todo through the acquisition ladder, in order:
       a. A `todo` value given -> it is the todo; stdin stays unread —
          an explicit value wins over piped content
       b. Otherwise a non-TTY stdin is read fully, exactly once, here:
          bytes that do not decode as UTF-8 are a clean error naming
          the todo option; the content test strips whitespace only to
          decide — at least one non-whitespace character means
          content: `todo_from_stdin` with content -> the content is
          the todo, verbatim, and the came-from-stdin fact is set —
          no editor opens, nothing is asked; `todo_from_stdin`
          without content -> the editor rung; no declaration with
          content -> a clean error naming the todo option — supplied
          stdin content is never silently ignored; no declaration
          without content -> the editor rung
       c. A TTY stdin is never read — an interactive terminal goes
          straight to the editor
       d. Still no todo and an interactive terminal -> the editor
          session via `edit_text`; its cancellation leaves no todo; a
          non-interactive terminal leaves no todo
       e. An unresolved todo meets the path rules: the publication
          path without a todo is a clean error asking for it; the
          no-switch path without a todo is a clean error — git keeps
          no empty directories, so the no-switch work exists only
          through its committed todo file; the switch path tolerates
          the absent todo
    3. The publication ask — an interactive terminal, `publish` not
       set, a todo resolved, and the todo not came from stdin: the
       answer chooses the path; no ask otherwise
    4. Deliver the creation amendment over `TopicHooks`: build the
       identity via `TopicIdentity` — the normalized slug, the
       resolved year, `branch_name` as entered — and deliver
       amend_creation with the path facts — checked_out as `switch`
       dictates, published as the chosen path dictates — the draft
       commit message of the path (the no-switch and the publication
       paths build one; the switch path delivers None) and the draft
       todo when resolved; the amended values of the returned
       `CreationDraft` replace the todo and the commit message carried
       into the mutation steps
    5. The normal path without `switch`: build one quarantined commit
       carrying the todo file todo.md — the path resolved via
       `resolve_topic_file` — with the final todo content and the
       final commit message on the base commit via
       `commit_file_on_base`, capture the returned commit hash, and
       plant the branch named as entered at it; the working copy, the
       index, and HEAD stay untouched — the caller stays on their
       branch; then emit topic_created over `TopicHooks` — the
       identity, checked_out False, published False, the final todo,
       the final commit message, and the captured commit hash
    6. The normal path under `switch`: create the branch at the base
       commit via `create_branch_at_commit` and switch to it via
       `checkout_local_branch` — a failed checkout rolls the planted
       branch back via `delete_local_branch` (the occupancy oracle
       would otherwise block the retry) —, create the topic directory
       of the year via `ensure_topic_dir`, and write the todo file
       todo.md when a todo resolved; the write is the last mutation of
       the path; then emit topic_created — the identity, checked_out
       True, published False, the final todo when written, and no
       commit facts
    7. The publication path: delegate to `publish_topic` with the
       name, the amended todo, the base, the amended template, and the
       year — the publication path fires its checkpoints inside the
       delegated routine; nothing fires here
    8. Return the single result line

    Requirements:
    - Every decision — preflight, todo, ask — precedes the first
      mutation
    - The stdin read happens at todo-resolution time — after the
      preflight, before the editor and the ask — once per creation; a
      TTY stdin is never read
    - The stdin-resolved todo carries the value-form semantics:
      verbatim content with the trailing-newline normalization at the
      write, UTF-8, the same amendment hooks
    - When the todo came from stdin, the publication ask never
      appears — publication happens only under `publish`
    - A failed checkout of the switch path rolls the planted branch
      back — nothing of the path stays behind
    - The todo.md content carries the todo as entered with exactly one
      trailing newline — a todo already ending in one keeps it, a
      bare todo gains it — encoded UTF-8; empty lines inside the
      text stay as entered
    - The no-switch path needs a resolved todo and builds its commit
      with the built-in domain message — `commit_message` stays
      publication-only
    - The topic directory of the switch path exists before the
      todo.md file is written; the todo.md file is written only when
      a todo resolved
    - The branch keeps the name as entered; the topic directory takes
      the slug
    - The caller stays on their branch unless `switch` is set
    - The creation amendment delivers exactly once per creation,
      immediately before the first mutation of the chosen path, with
      the draft content of that path; the identity-only form is valid
    - topic_created fires exactly once per successful creation — from
      this routine on the no-switch and switch paths, from the
      delegated publication routine after its push succeeds; a failed
      creation fires nothing

    Constraints:
    - Do not validate branch-name characters — git owns name validity
    - Do not auto-pick suffixed names on a conflict
    - Do not write artifact files other than the topic todo file
      inside the topic directory
    - Do not cap the stdin volume — the todo is text and the caller
      owns the volume

"enter_topic_todo(topic: str, year: str | None = None, branch: str | None = None) -> written: bool":
  location: creation.py
  annotations: |
    Enter the todo of a topic — the editor session with the topic's
    todo.md and the write of the saved text, without a commit; the
    saved text passes through the todo-entry amendment before the
    write, and the completed entry emits its notification.

    `topic`: topic input — a branch name or an already-normalized slug
    `year`: optional year as four digits; None means the current year
    `branch`: the branch fact of the identity, passed by the calling
              operation; None leaves the identity without a branch
              fact
    `written`: True when the saved text was written; False when the
               entry was cancelled

    Apply the `editor-entry` practice for the editor session pattern.
    Apply the `topic-paths` practice for the todo-file path pattern.
    Apply the `checkpoints` practice for the amendment delivery and
    the notification emission.

    Algorithm:
    1. Resolve the todo.md path of the topic via `resolve_topic_file`;
       an existing file provides the initial text
    2. Open the editor session via `edit_text` with the initial text
    3. A cancelled entry -> False — the file stays untouched, nothing
       is delivered or emitted
    4. A saved text -> deliver the todo-entry amendment over
       `TopicHooks`: the identity via `TopicIdentity` — the normalized
       slug, the resolved year, `branch` — and amend_todo_entry with
       the saved text; the final text of the returned `TodoEntryDraft`
       replaces the text being written
    5. Write todo.md with the final text as entered with exactly one
       trailing newline — a text already ending in one keeps it —
       encoded UTF-8, without a commit -> True
    6. Emit topic_todo_entered — the identity and the final written
       text

    Requirements:
    - The topic directory exists — directory creation belongs to the
      caller
    - The write is the last mutation — nothing mutates after it; the
      notification emission follows the write and mutates nothing
    - The amendment delivers after the save and before the write; the
      write carries the final amended text
    - An entry completing with a saved write emits
      topic_todo_entered; a cancelled entry delivers and emits nothing
    - The identity needs no repository reads — the slug, the year, and
      the branch arrive as inputs

    Constraints:
    - Do not create the topic directory
    - Do not commit the write

"check_branch_occupancy(branch_name: str, slug: str, year: str | None = None) -> conflict: str | None":
  location: creation.py
  annotations: |
    Decide whether the entered branch name and the topic slug are free.

    `branch_name`: branch name as entered — checked against the branch
                   inventory
    `slug`: normalized topic slug — checked against the topic directory of
            the year
    `year`: optional year as four digits; None means the current year
    `conflict`: human-readable reason of the first occupied oracle, or None
                when everything is free

    Apply the `topic-paths` practice for the topic-existence oracle
    contract.
    Apply the `refs-and-switching` practice for the inventory pattern.

    Algorithm:
    1. A local `BranchRef` named `branch_name` exists in the inventory of
       `list_branch_refs` -> return the reason
    2. A remote-tracking `BranchRef` whose short name (the part after the
       first "/") equals `branch_name` exists -> return the reason
    3. The topic directory of `slug` in the year exists via `topic_exists`
       -> return the reason
    4. All three oracles are free -> None

    Requirements:
    - The first occupied oracle wins; remaining oracles are not probed
    - Read-only — no ref or directory is created

    Constraints:
    - Do not resolve remote state over the network — the local inventory
      only

"publish_topic(branch_name: str, todo: str, base_ref: str, commit_message: str | None = None, year: str | None = None) -> result: str":
  location: publishing.py
  annotations: |
    Create fresh work and publish it — a branch off an explicit base
    carrying one commit with the topic todo, pushed to origin, while
    the caller stays on their branch.

    `branch_name`: the branch name as entered by the user
    `todo`: the multi-line todo of the fresh work — written to todo.md
            as entered with exactly one trailing newline; required and
            non-empty, an empty todo is a clean error asking for it
    `base_ref`: the base revision the branch starts from — any revision
                string, resolved as git resolves it
    `commit_message`: the commit message template — the {slug}
                      placeholder is replaced with the topic slug; None
                      applies the built-in default
    `year`: optional year as four digits; None means the current year
    `result`: one line describing the outcome

    Apply the `topic-paths` practice for the slug, current-branch, and
    todo-file path patterns.
    Apply the `refs-and-switching` practice for the occupancy inventory
    and tree-reading patterns.
    Apply the `publishing` practice for the quarantined commit
    building, branch planting, publication, and rollback patterns.
    Apply the `checkpoints` practice for the publication
    notifications.

    Algorithm:
    1. Normalize `branch_name` into a slug via `normalize_topic_slug`
    2. An empty slug, an empty `todo`, or the current branch — read via
       `resolve_current_branch_name` — hosting the same slug -> clean
       error, before any mutation
    3. The occupancy oracles `check_branch_occupancy` and
       `check_slug_occupancy` report a conflict -> clean error with a
       hint to the board
    4. `origin_configured` reads False -> clean error with the reason
    5. Resolve `base_ref` into its commit via `resolve_ref_commit` — an
       unresolvable base is a clean error with the reason, before any
       mutation
    6. Build the publication commit via `commit_file_on_base` — the
       parent commit, the todo.md path resolved via `resolve_topic_file`
       as a repository-root-relative posix string, the final todo
       content, and the applied commit message — and capture the
       returned commit hash
    7. Plant the branch named exactly as entered via
       `create_branch_at_commit`
    8. Publish via `push_branch`; a failed publication deletes the
       branch via `delete_local_branch` and surfaces one clean error
       carrying the reason — nothing fires on the failure
    9. After the successful push, emit over `TopicHooks` with the
       identity via `TopicIdentity` — the normalized slug, the
       resolved year, `branch_name` as entered: topic_created —
       checked_out False, published True, the final todo, the applied
       commit message, the captured commit hash — then
       topic_published — the same final commit message, commit hash,
       and todo
    10. Return the single result line

    Requirements:
    - The working copy, the index, and HEAD stay untouched — the caller
      stays on their branch whatever its state; a dirty tree and a
      detached HEAD do not interfere
    - Every decision is made before the first mutation; the mutation
      sequence is the commit build, the branch plant, and the push
    - The push to origin is the only network operation of the path; no
      fetch ever happens
    - A failed publication rolls back fully — the planted branch is
      deleted and nothing else was ever mutated; a re-run after the
      cause is resolved succeeds
    - The todo.md file carries `todo` as entered with exactly one
      trailing newline — a todo already ending in one keeps it, a
      bare todo gains it — encoded UTF-8; the sole artifact of the
      topic directory
    - The result is exactly one line
    - The creation amendment belongs to the creating orchestration —
      this routine fires the publication checkpoints only; a direct
      call publishes without amend_creation
    - The two publication checkpoints fire only after the push
      succeeds, in the order topic_created then topic_published; a
      failed publication that rolls back fires nothing

    Constraints:
    - Do not validate branch-name characters — git owns name validity
    - Do not auto-pick suffixed names on a conflict
    - Do not write artifact files other than the topic todo file inside
      the topic directory
    - Do not switch the caller's branch — the caller keeps their
      working state

"check_slug_occupancy(slug: str, year: str | None = None) -> conflict: str | None":
  location: creation.py
  annotations: |
    Decide whether the topic slug of the year is already hosted by any
    branch of the inventory — read from the branch trees, without checkout.

    `slug`: the normalized topic slug — checked against the topic directory
            of the year across every branch tree
    `year`: optional year as four digits; None means the current year
    `conflict`: human-readable reason naming the hosting branch, or None
                when no branch hosts the slug

    Apply the `topic-paths` practice for the year and tree-root patterns.
    Apply the `refs-and-switching` practice for the inventory and
    tree-reading patterns.

    Algorithm:
    1. Resolve the year — `year` when given, otherwise the current year via
       `current_year`
    2. Compose the topic directory prefix of the slug under the root
       resolved via `resolve_history_root` — the prefix carries a trailing
       slash, so a sibling slug sharing only the prefix text
       ("feature-foo" of "feature-foo-bar") stays free
    3. Probe every ref of `list_branch_refs` via `read_ref_tree_paths` —
       the first ref whose tree carries paths under the prefix is the
       conflict
    4. No ref hosts the slug -> None

    Requirements:
    - The first occupied ref wins and names the conflict; remaining refs
      are not probed
    - Read-only — no ref or directory is created; no checkout, no worktree
    - One git invocation per ref

    Constraints:
    - Do not resolve remote state over the network — the local inventory
      only
    - Do not probe the working copy — a topic living only on disk is the
      file oracle's domain

"DeleteTarget(topic: str, branch: str | None, remote: str | None, has_dir: bool)":
  location: deletion.py
  annotations: |
    One identified deletion target — a topic with its hosting refs and
    directory.

    `topic`: the topic slug
    `branch`: the hosting local branch name, or None
    `remote`: the hosting origin twin name, or None
    `has_dir`: True when the topic directory of the year exists on
               disk and no merged-work host carries the topic — a
               merged host's tree survives the deletion, so its
               directory stays out of the target

    Apply the `convention` practice for the data-model rules and
    intra-package imports.
  properties:
    "topic -> str": |
      The topic slug.
    "branch -> str | None": |
      The hosting local branch name, or None.
    "remote -> str | None": |
      The hosting origin twin name, or None.
    "has_dir -> bool": |
      True when the topic directory of the year exists on disk and no
      merged-work host carries the topic — a merged host's tree
      survives the deletion, so its directory stays out of the target.

"resolve_delete_targets(identifiers: list[str], year: str | None = None) -> targets: list[DeleteTarget]":
  location: deletion.py
  annotations: |
    Resolve deletion identifiers into targets — every check before any
    removal.

    `identifiers`: the user inputs — branch names, topic slugs, or
                   their prefixes
    `year`: optional year as four digits; None means the current year
    `targets`: one `DeleteTarget` per identified topic, in identifier
               order

    Apply the `topic-paths` practice for the year and tree patterns.
    Apply the `refs-and-switching` practice for the inventory pattern.

    Algorithm:
    1. Resolve the year — `year` when given, otherwise the current year
       via `current_year`; collect the branch inventory via
       `list_branch_refs` and the topics of the year on disk via
       `collect_history_tree` — a topic
       directory no branch hosts is a targetable topic
    2. Each identifier resolves through the tiers: the exact branch
       name, the exact topic slug, the prefixes of both — the first
       non-empty tier wins
    3. No match -> clean error naming the identifier; several matches
       -> clean error listing the candidates — no interactive choice
    4. A hosting ref whose name does not normalize into the topic
       slug — a branch carrying a topic merged from another branch —
       is not part of the target; when no eligible hosting ref
       remains, the identifier is a clean error naming the topic and
       the hosting branch — merged work is removed from the hosting
       branch's tree, not deleted here. A topic carried by both an
       eligible ref and a merged-work host deletes its eligible refs
       but keeps its directory — the merged host's tree survives the
       deletion, so the target covers the refs only. A topic directory
       no branch hosts stays targetable (no refs, directory only)
    5. A local branch and its origin twin form one target; identifiers
       naming one topic collapse into it
    6. The current branch — read via `resolve_current_branch_name` —
       hosting any target -> clean error asking to switch away first
    7. Return the targets

    Requirements:
    - Read-only — nothing is removed, created, or switched
    - All-or-nothing — any unresolved or ambiguous identifier cancels
      the whole call
    - A topic hosted only by refs that are not its own topic branch
      is a clean error naming the hosting branch — merged work is
      out of scope
    - A topic carried by both an eligible ref and a merged-work host
      deletes its eligible refs but keeps its directory — the merged
      host's tree survives the deletion

    Constraints:
    - Do not resolve remote state over the network — the local
      inventory only
    - Do not offer an interactive selection

"delete_topics(targets: list[DeleteTarget], year: str | None = None) -> result: str":
  location: deletion.py
  annotations: |
    Execute the confirmed deletion of the targets — the local branch,
    the origin twin, and the topic directory.

    `targets`: the resolved targets — the caller has confirmed them
    `year`: optional year as four digits; None means the current year
    `result`: one line describing the outcome

    Apply the `deleting` practice for the symmetric removal and the
    restore-on-failure patterns.
    Apply the `checkpoints` practice for the deletion notification.

    Algorithm:
    1. Per target, in order: a local branch exists -> capture its
       commit via `resolve_ref_commit` first, then delete the local
       branch via `delete_local_branch`
    2. An origin twin exists -> delete it on origin via
       `delete_remote_branch`; a failed deletion restores the local
       branch at the captured commit via `create_branch_at_commit` and
       surfaces one clean error — the targets removed before the
       failure stay removed and fired theirs
    3. A target with only an origin twin -> delete it on origin via
       `delete_remote_branch`
    4. A target with a directory -> remove the topic directory via
       `remove_topic_dir`
    5. After the target's full removal, emit topic_deleted over
       `TopicHooks` — the identity via `TopicIdentity`: the target's
       slug and the resolved year, no branch fact — with the removal
       composition: the removed local branch name or None, the
       removed origin twin name or None, and whether the topic
       directory was removed
    6. Return the single result line

    Requirements:
    - The deletion is unconditional — no merge checks; the
      confirmation belongs to the caller
    - The deletion push is a network operation; no fetch ever happens
    - A target fires after its complete removal; targets fully
      removed before a later failure fire theirs; a target whose
      removal fails midway fires nothing
    - No deleted-commit hash is carried — the captured rollback
      commit stays internal

    Constraints:
    - Do not re-resolve the identifiers — the caller passes resolved
      targets
    - Do not touch topics outside `targets`

---

Author: Goga
CreatedAt: 29/08/26
Description: |
  The topics domain — the cross-branch topic inventory of one year in
  two projections (per-host audit records as the source of facts, the
  aggregated one-entry-per-topic view) with todo summaries, the todo
  acquisition ladder of the creation — value, declared stdin, editor,
  clean error — with preflight and the publication ask skipped when
  the todo came from stdin, quarantined without a switch by default,
  checked out under the switch flag, fast creation with publication,
  the ensure orchestration of the fast process, the todo entry of a
  topic, and identified-topic deletion; the lifecycle events of the
  domain fire through its hooks zone.

```

**.usages files**:

**File:** `goga/topics/.usages/creating.md` (UPDATED)

```md
# topics — creating fresh work

How to create a new branch off an explicit base with its topic using
the `goga.topics` facade. For consumers that start new work —
interactive callers and scripted pipelines alike.

`create_topic` takes the branch name as entered and the base revision.
The branch keeps the name verbatim; the topic directory takes the
normalized slug of the year — the two may deliberately differ
(Feature/Foo_Bar branches into the feature-foo-bar topic).

## Creating

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.")  # current year
result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.", year="2025")
result = create_topic("Feature/Foo_Bar", "origin/main", todo="Fix.", switch=True)
print(result)  # one line describing what was created
```

- The base is explicit — any revision git resolves; the branch starts
  at it and, by default, the repository stays on the caller's branch.
- The preflight runs before any input: an empty slug, an occupied
  branch name or slug, or the current branch hosting the same slug is
  a clean error with a hint to the board — creating the existing is an
  error, not an update.
- The todo resolves through an acquisition ladder, in order: an
  explicit `todo` value; else the declared stdin source
  (`todo_from_stdin=True`) when the piped content carries at least one
  non-whitespace character; else the external editor on an interactive
  terminal; else no todo — the path rules decide what a missing todo
  means.
- Stdin rules: a terminal stdin is never read; a non-terminal stdin
  is read fully exactly once, at todo-resolution time. Piped bytes
  that are not UTF-8 are a clean error naming the todo. Piped content
  without any declared source — no `todo` value and no
  `todo_from_stdin` — is a clean error naming the todo: piped content
  is never silently ignored. An empty or whitespace-only stdin counts
  as no content: the editor opens on a terminal, and headless the path
  rules apply.
- The stdin-resolved todo behaves exactly like a value: written as
  entered plus a trailing newline, UTF-8, through the same amendment
  hooks. When the todo came from stdin, the publication ask never
  appears — publication happens only through `publish=True`.
- The default path quarantines the topic into the branch: one commit
  carrying `todo.md` — the text as entered plus a trailing newline,
  UTF-8 — on top of the base, the branch planted at it, the working
  copy untouched. The todo is required on this path — git keeps no
  empty directories, so an unresolved todo is a clean error naming the
  todo source and the switch form; the built-in message applies.
- `switch=True` checks out the fresh branch instead: the topic
  directory appears in the working copy and the resolved todo is
  written as `todo.md` — uncommitted, the last action of the path; the
  todo is optional on this path.
- On an interactive terminal without an explicit publish decision, the
  publication ask runs when a todo was obtained and did not come from
  stdin — the answer chooses between the local path and the
  publication path.
- The written todo.md content and the built commit message are the
  final amended values when a tool package subscribes an amendment
  hook — the creation amendment runs before the first mutation of the
  chosen path.

## Scripted creation with the todo from stdin

```python
from goga.topics import create_topic

result = create_topic("Feature/Foo_Bar", "origin/main", todo_from_stdin=True)
result = create_topic("Feature/Foo_Bar", "origin/main", todo_from_stdin=True, switch=True)
```

- Pipe the multi-line todo into the process and declare
  `todo_from_stdin=True`; the piped content becomes the todo with the
  value-form semantics. No editor opens and nothing is asked — the
  call runs fully non-interactive.
- Works on every creation path — the quarantined default,
  `switch=True`, and `publish=True`.
- An explicit `todo` value wins over piped content; content-free
  stdin falls through to the editor on a terminal and to the path
  rules headless.

## Occupancy

- Occupancy oracles: a local branch ref, a remote-tracking ref, and
  the topic directory of the year — exposed as
  `check_branch_occupancy`; the branch-tree oracle is
  `check_slug_occupancy`.
- No artifact files are written inside the topic directory beyond the
  todo file — artifacts belong to their producers.

```

**File:** `goga/topics/.usages/topic-board.md` (UPDATED)

```md
# topics — the topic board

How to collect the cross-branch topic inventory of one year with the
`goga.topics` facade, in its two projections. For consumers that show
all work of a repository: CLI boards, reviews, overviews, tools.

The board sees one year at a time. The per-host collection is the
single source of facts: one record per topic and hosting branch,
twin-collapsed, complete including topics that no longer have their
own branch. The default view is a projection of those records — one
entry per topic that still has its own branch. Local mode reads the
full branch inventory and the current branch from the working copy —
uncommitted progress is visible. Remote mode lists remote-tracking
refs instead; the current branch shows through its remote twin. No
checkout happens: every ref is read through git plumbing, so the
working copy and .git stay untouched.

## Collecting the per-host records

```python
from goga.topics import collect_topic_board

records = collect_topic_board()  # current year, local — every topic × host row
records = collect_topic_board(year="2025", remote=True)
records = collect_topic_board(hosts=("main", "release/1.3"))  # named hosts only
```

- One `BoardRecord` per topic and hosting branch: the slug, the
  hosting branch display name, that branch's maximal status names in
  scale order, the current and remote markers, and the todo summary —
  the first line of the topic's `todo.md` that yields text after
  leading `#` markers are stripped and the edges trimmed, or None
  when the topic has none. Rows hosted by other branches read their
  summaries from the ref trees without checkout; the current branch's
  row reads the working copy, so an uncommitted todo edit shows at
  once. The file is never modified — the stripping is for display.
- A local branch and its remote twin collapse to one row — the local
  branch wins. Two different branches hosting one slug stay two rows.
- `hosts` keeps the records of the named hosting branches only —
  exact display-name match, several names unite; an unknown name
  yields the empty list, never an error.
- Sorting: scale order of the first maximal status, then topic
  alphabet.
- A year without topics yields an empty list — not an error.
- Strictly read-only.

## Aggregating the one-entry-per-topic view

```python
from goga.topics import aggregate_topic_board

entries = aggregate_topic_board(records)  # one entry per topic with an own branch
entries = aggregate_topic_board(records, hosts=("main",))
for entry in entries:
    print(entry.topic, entry.branch, entry.hosts, entry.statuses, entry.current, entry.todo)
```

- One `BoardEntry` per topic that still has an own branch — a hosting
  branch whose branch part (the whole name of a local branch, the
  short name of a remote-tracking ref) normalizes into the topic
  slug; a remote-tracking ref qualifies, so remote-only topics keep
  their entry. A topic whose history survives only in merged hosts
  produces no entry — its rows live in the per-host records.
- `branch` is the own branch; several colliding own branches resolve
  deterministically — the current branch when it is among them,
  otherwise a local branch over a remote-tracking one, otherwise the
  display-name alphabet.
- `hosts` lists every branch carrying the topic's history, the own
  branch included, alphabetical by display name.
- `statuses` are the own branch's maximal statuses — artifacts that
  exist solely on merged hosts do not advance them.
- `current` marks the topic the current working branch hosts.
- The `hosts` filter keeps the entries whose hosts list contains any
  given name — union, exact match; an own branch is still required,
  the filter never resurrects a hidden topic; an unknown name yields
  the empty list, never an error.
- The entries sort like the records: scale order of the first maximal
  status, then topic alphabet. Strictly read-only over the records —
  no second git read happens; both views derive from one collection
  pass.

```

### Cell: `goga/commands/topics` (MODIFIED)

Change summary against the current manifest:
- **Header — Imports**: the `goga/topics` import gains the types `BoardEntry` and `aggregate_topic_board` (usages list unchanged); config imports unchanged.
- **Header — Usages**: the key `beautiful_json: .goga/usages/cooks/beautiful_json.md` is added.
- **Header — Annotations**: `click` application extended (optional-value todo option with three states mapped in the callback; repeatable host filter); `beautiful_json` line added; the CLI-surface paragraph rewritten (renders two views + JSON; no stdin reading here).
- **Body — added**: `render_topic_host_rows`, `render_board_json` in `render.py`.
- **Body — changed**: `topics` (subcommand surfaces; `board` method — full new contract (`host: tuple[str, ...] | None = None`); `create` method — `todo_from_stdin` parameter, mapping step 5, delegation step 6), `render_topic_board` (input `list[BoardEntry]`, hosts column, four/five-column width rules).
- **Body — unchanged (carried verbatim)**: `switch` and `delete` methods of `topics`.
- **Footer**: `Description` updated; `Author`/`CreatedAt` unchanged.

**CODEMANIFEST** — complete file content:

```yaml
Imports:
  - Types:
      - BoardRecord
      - BoardEntry
      - collect_topic_board
      - aggregate_topic_board
      - switch_topic
      - create_topic
      - resolve_delete_targets
      - delete_topics
    Usages:
      - topic-board
      - switching
      - todo-entry
      - creating
      - publishing
      - deleting
      - registering-hooks
    From: goga/topics
  - Types:
      - load_project_config
      - TopicsConfig
    Usages:
      - project-configuration
    From: goga/config
  - Types:
      - ConfigHooks
      - ConfigOverlay
    Usages:
      - checkpoints
    From: goga/config/hooks

Usages:
  convention: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  beautiful_json: .goga/usages/cooks/beautiful_json.md

Annotations: |
  The `convention` practice is used for:
  - Working with the codebase
  - Organizing the REPL development cycle
  - Debugging and testing
  - Organizing the test infrastructure
  - Understanding the general principles and rules of development and testing in the project

  Use the `click` practice to build the topics command group: the group
  decorator with its own option, the subcommand registration, the
  flags, arguments, and options of each subcommand — the
  optional-value todo option included, its three states mapped in the
  callback — the repeatable host filter, echo, exit-code propagation,
  the confirmation of the delete subcommand, and the clean error
  rendering.

  Use the `creating` and `publishing` practices for the creation and
  publication contracts of the domain, the `switching` practice for
  the switching contract, the `todo-entry` practice for the todo entry
  behind the --todo flags, the `topic-board` practice for the board
  contract, and the `deleting` practice for the deletion contract of
  the domain. Use the `project-configuration` practice for the schema
  of the topics section.

  Use the `beautiful_json` practice for the JSON serialization of the
  board output.

  Use the `registering-hooks` practice for the
  lifecycle events this command group emits and the tool-package hooks
  subscribed to them.

  Use the `checkpoints` practice for the config amendment checkpoint at
  the project-configuration load moment — the command loads the authored
  configuration, delivers the checkpoint, consumes the effective
  configuration of the returned `ConfigOverlay`, and prints the amendment
  summary lines to stderr. A checkpoint failure — ValueError (the
  hard action) or ImportError (a broken tool package facade) — folds
  into the same clean-error wrapper as a failed load; a missing file
  counts as unset and offers no checkpoint.

  The creation inputs resolve their values at this layer: the base —
  a flag beats the topics section — `TopicsConfig` — of the effective
  configuration of the `ConfigOverlay` (the configuration load delivers
  the config amendment checkpoint), which beats the
  current HEAD requested explicitly; no base at all is a clean error
  naming the flag and the configuration line. The commit message
  template — a flag beats the topics section; the built-in default
  lives in the domain. The todo option maps its three states into the
  domain source declaration — a non-empty value is the todo, the
  value-less form declares stdin, an absent option or an empty value
  declares nothing; no resolution happens here. The switch flag
  passes through to the domain. The configuration is read only for
  values no flag provided.

  This cell is the CLI surface of the topics domain: a thin wrapper
  that resolves inputs, delegates every computation to the domain
  routines, renders the board in its two views and its JSON form, and
  confirms the deletion. No inventory walking, no switch resolution,
  no git access, no editor session, no stdin reading live here — the
  value-less todo option maps into the domain's source declaration.
  Domain errors surface as clean CLI errors (stderr, non-zero exit,
  no traceback). Use relative imports.

---

"topics(year: str | None = None)":
  location: topics.py
  annotations: |
    The goga topics command group — a click.Group container for the
    topics subcommands, exported via __all__ and registered in the
    root application group. The group carries the year scope every
    subcommand shares.

    `year`: the --year/-y group option — exactly one year, four digits
            the recognized form; None means the current year; a search
            across years does not exist

    Use the `click` practice for the group decorator, the group option,
    and the subcommand registration.

    Subcommand surfaces:
    - board — a --remote/-r flag, an --info/-i flag, a repeatable
      --host option, a --per-host flag, a --json flag
    - create — a NAME positional, a --todo/-t option with an optional
      value, a --publish/-p flag, a --base-ref option, a --from-current
      flag, a --commit/-c option, a --switch/-s flag
    - switch — an IDENTIFIER positional, a --todo flag
    - delete — IDENTIFIER positionals, a --yes/-y flag

    Apply the `convention` CLI command docstring rule for the --help
    text (rendered verbatim by Click; omit Args/Returns/Raises).
  methods:
    "board(remote: bool = False, info: bool = False, host: tuple[str, ...] | None = None, per_host: bool = False, json_output: bool = False) -> exit_code: int": |
      Subcommand goga topics board: print the board of the scoped
      year — by default one entry per topic as a four-column table,
      five with the todo column under --info/-i; under --per-host one
      row per topic and hosting branch; under --json the
      machine-readable record array instead of a table.

      `remote`: the --remote/-r flag — read remote-tracking refs instead
                of local branches
      `info`: the --info/-i flag — add the todo column to the table
      `host`: the repeatable --host option — hosting-branch display
              names, exact match, union across values; None or empty —
              no filtering; an unknown name yields the empty board,
              never an error
      `per_host`: the --per-host flag — the expanded audit view, one
                  row per topic and hosting branch
      `json_output`: the --json flag — print the board as a
                     pretty-printed JSON array instead of a table
      `exit_code`: 0 on success (an empty board included), 1 on error

      Apply the `topic-board` practice for the board contract of the
      domain.
      Apply the `click` practice for the flags, the repeatable option,
      echo, and the color rules.
      Apply the `beautiful_json` practice for the JSON serialization.

      Algorithm:
      1. `json_output` together with `info` -> clean error: the todo is
         always present in the JSON records
      2. The default view: collect the per-host records via
         `collect_topic_board` with the scoped year and `remote`, then
         project via `aggregate_topic_board` with `host`
      3. The per-host view: collect via `collect_topic_board` with the
         scoped year, `remote`, and `host` as the record filter
      4. The table output: measure the terminal width and render — the
         default view via `render_topic_board` with the entries, the
         per-host view via `render_topic_host_rows` with the records;
         both take `info`
      5. The JSON output: render via `render_board_json` with the
         entries or the records
      6. An empty board renders nothing as a table and [] as JSON —
         exit 0

      Requirements:
      - Read-only — nothing is created, written, or switched
      - The year scoping and `remote` apply to the JSON output exactly
        as to the table

      Constraints:
      - Do not print the year or the artifacts, and no heading line
        outside the table or the JSON array — the table carries topic,
        branch, hosts, the todo column under `info`, and statuses only
      - Do not compute the board here — the projection of the default
        view and both filter semantics belong to the domain
    "create(branch_name: str, todo: str | None = None, todo_from_stdin: bool = False, publish: bool = False, base_ref: str | None = None, from_current: bool = False, commit_message: str | None = None, switch: bool = False) -> exit_code: int": |
      Subcommand goga topics create: create fresh work — a branch off
      the resolved base with the name as entered, its topic of the
      scoped year, and an optional multi-line todo; by default the
      branch is planted at one commit carrying the topic's todo.md and
      the caller stays on their branch; under --switch the branch is
      checked out with its topic directory in the working copy; under
      --publish the work is created off the base and published to
      origin without switching.

      `branch_name`: NAME positional — the branch name as entered
      `todo`: the --todo/-t value — the todo text; an empty value
               counts as an absent option
      `todo_from_stdin`: True when --todo was given without a value —
                         the declared stdin source of the todo
      `publish`: the --publish/-p flag — the publication path without
                 the ask
      `base_ref`: the --base-ref value — the base of the branch; valid
                  with and without `publish`
      `from_current`: the --from-current flag — the current HEAD as
                      the base
      `commit_message`: the --commit/-c value — the message template;
                        publication-only
      `switch`: the --switch/-s flag — the checked-out creation; acts
                only without `publish`
      `exit_code`: 0 on success, 1 on error

      Apply the `creating` practice for the creation contract of the
      domain.
      Apply the `publishing` practice for the publication contract of
      the domain.
      Apply the `project-configuration` practice for the topics
      section schema.
      Apply the `click` practice for the options and exit-code
      propagation.

      Algorithm:
      1. `commit_message` without `publish` -> clean error: the option
         is publication-only
      2. `switch` together with `publish` -> clean error: the
         publication never switches
      3. Resolve the base — `base_ref`, otherwise the topics section of
         the effective configuration of the `ConfigOverlay` (loaded via
         `load_project_config`; the configuration load delivers the
         config amendment checkpoint per the `checkpoints` practice via
         the `ConfigHooks` checkpoint surface — amend_config(config=...)),
         otherwise the
         current HEAD under `from_current`; no base at all ->
         clean error naming the flag and the configuration line,
         before anything else
      4. Resolve the template — `commit_message`, otherwise the topics
         section, otherwise None (the built-in default lives in the
         domain)
      5. Map the optional-value todo option: a non-empty `todo` value is
         the todo and declares the source; the value-less form sets
         `todo_from_stdin` with no value; an absent option or an empty
         value declares nothing
      6. Delegate to `create_topic` with the name, the base, the todo
         value, the stdin declaration, `publish`, the template, the
         scoped year, and `switch`
      7. Echo the single result line
      8. Propagate the exit code

      Requirements:
      - The configuration is read only for values no flag provided; a
        missing configuration file counts as an unset value; a present
        but invalid one surfaces its own clean error
      - The amendment summary lines of the `ConfigOverlay` print to
        stderr (nothing when empty)

      Constraints:
      - Do not validate the name at the CLI layer — the domain and git
        own that
      - Do not open the editor or read stdin here — the entry and the
        stdin channel belong to the domain
      - Do not switch branches or render the board here — every
        computation belongs to the domain
    "switch(identifier: str, todo: bool = False) -> exit_code: int": |
      Subcommand goga topics switch: bring the repository onto the
      branch hosting the requested work; under --todo enter the todo
      of the switched topic after the switch.

      `identifier`: IDENTIFIER positional — a branch name, a topic
                    slug, or their prefix
      `todo`: the --todo flag — enter the todo of the switched topic
      `exit_code`: 0 on success, 1 on error

      Apply the `switching` practice for the switching contract of the
      domain.
      Apply the `click` practice for the flag and exit-code
      propagation.

      Algorithm:
      1. Delegate to `switch_topic` with the identifier, the flag, and
         the scoped year
      2. Echo the single result line
      3. Propagate the exit code

      Constraints:
      - Do not launch any pipeline — continuation is a separate
        command
    "delete(identifiers: tuple[str, ...], yes: bool = False) -> exit_code: int": |
      Subcommand goga topics delete: resolve and delete identified
      topics — the local branch, the origin twin, and the topic
      directory — under one confirmation for the whole list.

      `identifiers`: IDENTIFIER positionals — branch names, topic
                     slugs, or their prefixes
      `yes`: the --yes/-y flag — skip the confirmation
      `exit_code`: 0 on success (a declined confirmation included), 1
                   on error

      Apply the `deleting` practice for the deletion contract of the
      domain.
      Apply the `click` practice for the confirmation, echo, and
      exit-code propagation.

      Algorithm:
      1. Resolve the targets via `resolve_delete_targets` with the
         identifiers and the scoped year — a resolution error is clean
         and deletes nothing
      2. Without `yes`: no interactive terminal -> clean error;
         otherwise print the topic-to-branch pairs of the list and ask
         one confirmation for the whole list; a declined answer exits
         0 with nothing deleted
      3. Delegate to `delete_topics` with the targets and the scoped
         year
      4. Echo the single result line
      5. Propagate the exit code

      Requirements:
      - One confirmation for the whole list — never per topic
      - The -y short form collides with the group --year; the
        positions on the command line distinguish them

      Constraints:
      - Do not offer an interactive choice among ambiguous candidates —
        ambiguity is a domain error
      - Do not delete anything before the resolution and the
        confirmation are complete

"render_topic_board(entries: list[BoardEntry], width: int, info: bool = False)":
  location: render.py
  annotations: |
    Render the default board as a table: topic, branch, and hosts —
    under `info` the todo column sits between hosts and statuses.

    `entries`: the aggregated board entries — already sorted by the domain
    `width`: the measured terminal width in columns
    `info`: True adds the todo column and switches to the five-column
            width rule

    Apply the `click` practice for echo.

    Algorithm:
    1. Compute the column widths from `width` alone per the width rule of
       the requirements — the four-column rule without `info`, the
       five-column rule with it; the grid is fixed and independent of the
       record content
    2. Print one header row and one separator row with column and row
       dividers — the column order is topic, branch, hosts, todo,
       statuses under `info`, and topic, branch, hosts, statuses
       otherwise
    3. Print each entry: every text column truncated with an ellipsis when
       it exceeds its column, the hosts and the statuses wrapped onto
       continuation lines without affecting the column widths
    4. Print one row divider after every record — the same dash run as the
       header separator — the last record included; the wrapped
       continuation lines of one record stay undivided
    5. Mark the entry hosting the current branch with an asterisk; keep
       the remote prefix of a remote own branch visible in the branch
       column
    6. An empty `entries` prints nothing

    Requirements:
    - Four-column widths: topic, branch, and hosts get an equal share
      first, statuses take the remainder — each of topic, branch, and
      hosts is capped at one third of `width` minus the dividers,
      statuses receives what is left, and every column keeps a minimum
      of 8 columns before truncation applies
    - Five-column widths under `info`: topic, branch, hosts, and todo get
      an equal share — each capped at one quarter of `width` minus the
      dividers, statuses receives the non-negative remainder, and every
      column keeps a minimum of 8 columns before truncation applies
    - The hosts column header is the word hosts; the todo column header
      is the word todo
    - A todo of None or an empty string renders an empty cell
    - The truncation marker is a single ellipsis character
    - An overlong status or host name is truncated like the other
      columns
    - A row divider — identical to the header separator row — closes every
      record: it prints after the wrapped statuses of each record, the
      last record included, and never between the continuation lines of
      one record
    - The table never exceeds `width`, with one documented exception: when
      the minimum columns no longer fit — below the narrow threshold of the
      active column rule — every column keeps its minimum of 8 and the
      table may exceed `width`; minimum readability wins over the width cap
      on ultra-narrow terminals

    Constraints:
    - Read-only on `entries` — do not mutate, do not re-sort, do not filter
    - Do not print the year or the artifacts

"render_topic_host_rows(records: list[BoardRecord], width: int, info: bool = False)":
  location: render.py
  annotations: |
    Render the per-host audit view as a table — one row per topic and
    hosting branch: topic, branch, and statuses, under `info` the todo
    column between branch and statuses.

    `records`: the collected per-host records — already sorted by the domain
    `width`: the measured terminal width in columns
    `info`: True adds the todo column and switches to the four-column
            width rule

    Apply the `click` practice for echo.

    Algorithm:
    1. Compute the column widths from `width` alone per the width rule of
       the requirements — the three-column rule without `info`, the
       four-column rule with it; the grid is fixed and independent of the
       record content
    2. Print one header row and one separator row with column and row
       dividers — the column order is topic, branch, todo, statuses
       under `info`
    3. Print each record: every text column truncated with an ellipsis when
       it exceeds its column, the statuses wrapped onto continuation lines
       without affecting the column widths
    4. Print one row divider after every record — the same dash run as the
       header separator — the last record included; the wrapped
       continuation lines of one record stay undivided
    5. Mark the record hosting the current branch with an asterisk; keep
       the remote prefix of a remote host visible in the branch column
    6. An empty `records` prints nothing

    Requirements:
    - Three-column widths: topic and branch get an equal share first,
      statuses take the remainder — each of topic and branch is capped at
      one third of `width` minus the dividers, statuses receives what is
      left, and every column keeps a minimum of 8 columns before
      truncation applies
    - Four-column widths under `info`: topic, branch, and todo get an
      equal share — each capped at one quarter of `width` minus the
      dividers, statuses receives the non-negative remainder, and every
      column keeps a minimum of 8 columns before truncation applies
    - The todo column header is the word todo
    - A todo of None or an empty string renders an empty cell
    - The truncation marker is a single ellipsis character
    - An overlong status is truncated like the other columns
    - A row divider — identical to the header separator row — closes every
      record: it prints after the wrapped statuses of each record, the
      last record included, and never between the continuation lines of
      one record
    - The table never exceeds `width`, with one documented exception: when
      the minimum columns no longer fit — below the narrow threshold of the
      active column rule — every column keeps its minimum of 8 and the
      table may exceed `width`; minimum readability wins over the width cap
      on ultra-narrow terminals

    Constraints:
    - Read-only on `records` — do not mutate, do not re-sort, do not filter
    - Do not print the year or the artifacts

"render_board_json(board: list[BoardEntry] | list[BoardRecord])":
  location: render.py
  annotations: |
    Render the board as a pretty-printed JSON array on stdout — the
    machine-readable projection of either board view.

    `board`: the board to print — the aggregated entries of the default
             view or the per-host records of the audit view

    Apply the `beautiful_json` practice for the serialization format.
    Apply the `click` practice for echo.

    Algorithm:
    1. Shape every `BoardEntry` into the record with exactly the keys
       topic, branch, hosts, statuses, current, remote, todo; every
       `BoardRecord` into the same record without hosts; the todo key
       carries the summary string or None
    2. Serialize the array through the `beautiful_json` practice and
       echo it with one trailing newline
    3. An empty `board` prints []

    Requirements:
    - The record fields and shapes are a stable consumer contract —
      later changes stay additive; the key order is not part of it
    - The todo key is a string or null — never omitted
    - Read-only on `board` — do not mutate, re-sort, or filter

    Constraints:
    - Do not render a table, a heading, or any line outside the JSON
      array

---

Author: Goga
CreatedAt: 29/08/26
Description: |
  The goga topics command group — board in its two views and its JSON
  form, create with the optional-value todo option, switch, and
  delete — over the topics domain.

```

**.usages files**:

**File:** `goga/commands/topics/.usages/topics-command.md` (UPDATED)

```md
# commands/topics — the topics command group

Consumer scenarios of the `goga topics` command group. For users who
manage work as topics: boarding, creating, and switching; for the
command facade that registers the group.

The group scopes every subcommand to one year (--year/-y, default the
current year); the board subcommand reads remote-tracking refs with
--remote/-r, adds the todo column with --info/-i, filters by hosting
branch with the repeatable --host, switches to the expanded per-host
audit view with --per-host, and prints machine-readable records with
--json; the create subcommand creates fresh work without switching by
default, switches under --switch/-s, and publishes under --publish/-p;
--todo/-t takes a value, or no value to read the todo from stdin.

## Boarding all work

    goga topics board
    goga topics --year 2025 board
    goga topics board --remote
    goga topics board --info
    goga topics board --host main --host release/1.3

The default board shows exactly one entry per topic of the scoped
year that still has its own branch — the hosting branch whose branch
part (the whole name of a local branch, the short name of a
remote-tracking ref) normalizes into the topic slug; a
remote-tracking ref qualifies, so remote-only topics keep their
entry; a topic whose history survives only in merged hosts shows no
entry (--per-host keeps its rows). The table columns are topic,
branch, hosts, todo (--info), statuses. The branch column shows the
own branch —
several colliding own branches resolve deterministically (the
current branch, else a local branch over a remote-tracking one, else
the alphabet). The hosts column lists every branch carrying the
topic's history, the own branch included, alphabetical; entries wrap
onto continuation lines. The statuses are the own branch's maximal
statuses — artifacts that exist solely on merged hosts do not advance
them. The current branch's entry carries `*`. The todo cell shows the
first line of the topic's `todo.md` that yields text after leading
`#` markers are stripped and the edges trimmed; a topic without
`todo.md` shows an empty cell. An empty board prints nothing and
exits 0. Reading is strictly read-only — no checkout, no fetch, no
mutation.

--host NAME (repeatable) filters by exact hosting-branch display
name; several values unite. In the default view the entries whose
hosts list contains any given name stay — an own branch is still
required, the filter never resurrects a hidden topic. In the per-host
view the rows of the named hosts stay. An unknown name leaves an
empty board (or [] under --json) with exit 0 — never an error.

## Auditing every hosting branch

    goga topics board --per-host
    goga topics board --per-host --info

--per-host switches to the expanded audit view: one row per topic and
hosting branch, showing that branch's own statuses — complete
including topics without an own branch. The table keeps the
established layout (topic, branch, statuses; the todo column under
--info); the current marker applies per hosting branch, the remote
marker per ref, and a local branch still absorbs its remote twin.

## Consuming the board as JSON

    goga topics board --json
    goga topics board --json --remote
    goga topics board --per-host --json

--json prints the board as a pretty-printed JSON array. Default
records carry exactly the fields topic, branch, hosts, statuses,
current, remote, todo — todo is a string or null. Per-host records
carry topic, branch, statuses, current, remote, todo — no hosts. The
year scoping and --remote apply exactly as to the table. An empty
board prints []. --json --info is a clean error — the todo is always
present in JSON. The field names and record shapes are a stable
contract for external tools; the key order is not.

## Creating fresh work

    goga topics create Feature/Foo_Bar --from-current
    goga topics create Feature/Foo_Bar --base-ref origin/main
    goga topics create Feature/Foo_Bar -t "Payment retry"
    printf 'First line\nSecond line\n' | goga topics create Feature/Foo_Bar --todo --from-current
    goga topics create Feature/Foo_Bar -s
    goga topics --year 2025 create Feature/Foo_Bar --base-ref origin/main

Creates the branch off the base — --base-ref, topics.base_ref of
.goga/config.yml, or --from-current (the current HEAD); no base at
all is a clean error before anything else, naming the flag and the
configuration line. The preflight (an empty slug, an occupied branch
name or slug, the current branch hosting the same slug) runs before
any todo source: creating the existing is an error with a hint to the
board — the todo of an existing topic is `goga topics switch ID
--todo`.

The --todo/-t option takes an optional value. With a value it is the
todo (an empty value counts as absent). Without a value it declares
stdin as the source: pipe the multi-line todo in and it becomes the
todo — no editor opens, nothing is asked, and the publication ask
never appears. Without the option, a terminal opens the external
editor ($VISUAL/$EDITOR/vi) — an empty or unchanged file cancels the
entry; without a terminal and without a value the command is a clean
error naming --todo "...". Piping content while declaring no source
(neither a value nor the value-less --todo) is a clean error naming
--todo — piped content is never silently ignored; piping bytes that
are not UTF-8 with the value-less --todo is the same clean error. A
terminal stdin is never read; a pipe is read fully exactly once, at
todo-resolution time. The stdin todo works on every creation path —
the default, --switch/-s, and --publish/-p.

By default the resolved text becomes one quarantined commit —
todo.md on top of the base — and the branch is planted at it: you
stay on your branch, nothing lands in the working copy, and the todo
is required. --switch/-s checks out the fresh branch instead — the
topic directory and todo.md appear in the working copy uncommitted,
and the todo is optional; --switch acts only without --publish. On a
terminal without --publish the "Publish the branch to origin? [y/N]"
ask appears only when a todo was obtained and did not come from
stdin; confirming publishes with a full rollback on failure, declining
takes the local path.

## Creating and publishing fresh work

    goga topics create Feature/Foo_Bar --publish -t "Payment retry" --base-ref origin/main
    goga topics create Feature/Foo_Bar -p -t "Payment retry" -c "chore: new topic {slug}"

The publish path needs no terminal and asks nothing: the todo comes
from --todo/-t or the piped stdin under the value-less form. The base
comes from --base-ref, topics.base_ref, or --from-current. --commit/-c
(topics.publish_commit, default `goga: create topic {slug}`) stays
publication-only — an error without --publish. A failed publication
rolls back fully — the branch is deleted and one clean error names
the reason.

## Switching to existing work

    goga topics switch history-com
    goga topics switch history-com --todo

Resolves the identifier — exact branch name, exact topic slug, then
prefixes — and switches. Several candidates offer a numbered list with
statuses; without interactive input the command fails with the list.
Already being on the host is an idempotent success. A dirty working
tree is a clean error when a mutation is needed. With --todo the
editor opens with the topic's todo.md after the switch: saving
overwrites the file without a commit, cancelling leaves it untouched.
--todo on a branch without a topic, or without a terminal, is a clean
error before the switch. Switching is always local.

## Deleting topics

    goga topics delete feature-foo release-1-3-0
    goga topics delete feature-foo --yes

Resolves every identifier (branch name, topic slug, prefix — plus
topic directories of the year no branch hosts); an unknown or
ambiguous identifier cancels the whole call before anything is
removed. One confirmation for the whole list — "Delete N topics?
[y/N]" with the topic-to-branch pairs; --yes/-y skips it (a
non-terminal without --yes is a clean error; the -y collision with the
group --year is resolved by position). The deletion is symmetric to
creation-and-publication: the local branch and its origin twin are
both removed (the local first; a failed remote deletion restores the
local branch and stops with one clean error), and the topic directory
joins the deletion of every target — branches or none. The current
branch hosting a target is a clean error — switch away first. Merged
work is out of scope: a topic hosted only by branches that are not its
own topic branch is a clean error naming the hosting branch; a topic
carried by both its own branch and a merged-work host deletes its
eligible refs but keeps its directory — the merged host's tree
survives. Unmerged commits never block: the deletion is unconditional
after the confirmation.

## Exit codes

Every subcommand exits 0 on success (an empty board and [] included)
and 1 on error, with the error on stderr and no traceback.

```

### Project practice: `.goga/usages/cooks/click.md` (UPDATED)

Section added under "Parameters", after the repeatable-parameters subsection:

```md
### Option — optional value (three states)

```python
@click.option('--todo', '-t', 'todo', is_flag=False, flag_value='__declared__', default=None)
def create(todo):
    ...
```

- An option with `is_flag=False` and a `flag_value` distinguishes three
  states: absent → `default` (None); the value-less form `--todo` → the
  flag value (a marker no real value produces); `--todo "text"` → the
  text.
- Map the three states in the callback: a non-empty real value is the
  value; the marker declares the alternative source; `default` — or an
  empty real value, when emptiness means absence — is the absent option.
- Keep the mapping in the callback; the decorators only declare the
  surface.
- The `flag_value` marker is a reserved sentinel: a real value equal to
  it is indistinguishable from the value-less form. Choose a marker no
  plausible value carries (a module-level constant reserved by the
  command) and treat it as reserved.

```

### Project practice: `.goga/usages/cooks/beautiful_json.md` (CONNECTED, no edit)

Referenced by the `beautiful_json` key of `goga/commands/topics`; its content already covers the JSON output fully (`json.dumps(data, indent=4, sort_keys=True, ensure_ascii=False)`).

## Dependency Map

```
goga/history ──────────┐
goga/topics/git ───────┤
goga/topics/editor ────┼──> goga/topics
goga/topics/hooks ─────┘        │
                                │ BoardRecord, BoardEntry, collect_topic_board,
                                │ aggregate_topic_board, create_topic, switch_topic,
                                │ resolve_delete_targets, delete_topics
                                │ (+ usages: creating, deleting, publishing,
                                │  registering-hooks, switching, todo-entry, topic-board)
                                v
goga/config ──────────> goga/commands/topics ──> goga/commands
goga/config/hooks ────>       │
                              └─ practices: convention, click, beautiful_json
```

No cycles; the leaves-to-root order is unchanged by this plan.

## Verification Checklist

After implementing each artifact:

- **`goga/topics/CODEMANIFEST`**
  - `goga lint` passes for the cell (DSL syntax, references, closed binding of names).
  - `goga schema` shows `BoardEntry` and `aggregate_topic_board` in the `goga/topics` types.
  - Facade check: `python -c "from goga.topics import BoardEntry, aggregate_topic_board"`.
  - Contract check: `goga contract goga/topics` — implementation matches the manifest.
- **`goga/commands/topics/CODEMANIFEST`**
  - `goga lint` passes; `goga schema` shows the new renderer types under the cell.
  - Facade check: `python -c "from goga.commands.topics import render_topic_host_rows, render_board_json"`.
  - Contract check: `goga contract goga/commands/topics`.
- **`.usages` files** — each updated file renders as valid Markdown; every referenced contract name matches a signature in the corresponding CODEMANIFEST; `goga usages status` reports no drift for the touched imports.
- **`click.md` practice** — the added section matches the implemented option declarations of `topics create` and `topics board`.
- **Behavior (final gate, maps to the task's 13 acceptance criteria)**:
  1. Piped multi-line + value-less `--todo` → exact `todo.md` content, no editor/prompt, one line, exit 0.
  2. Undeclared piped content → clean error naming `--todo`.
  3. Value wins over pipe; content-free stdin keeps editor / headless-error / todo-less switch flows.
  4. Stdin todo → no publication ask; `--publish` keeps full rollback.
  5. Own-branch topic appears once with full hosts list; merged-only topic absent by default, present under `--per-host`.
  6. Default statuses = own branch's; per-host rows carry per-branch statuses.
  7. `--json` exact stable keys; `todo` string|null; `[]`; `--json --info` clean error; per-host shape without `hosts`.
  8. Interactive editor / value todo / switch / delete byte-identical.
  9. All board invocations leave the working copy and repository untouched.
  10. `--host` union, exact match, no resurrection; unknown name → empty board / `[]`, exit 0.
  11. Colliding own branches resolve by current → local → alphabet; `--per-host` shows all rows.
  12. Non-UTF-8 pipe → clean error naming `--todo`, nothing created.
  13. Stdin todo + `--switch` → checked-out topic, uncommitted `todo.md`, no editor/prompt.
  - Full suite: `pytest tests/ -x` green; `ruff check goga/` clean.
