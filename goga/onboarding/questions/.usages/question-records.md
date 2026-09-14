# Question records — goga/onboarding/questions

## Domain

The declarative question-and-answer model of the onboarding session:
question records of every kind, nesting groups, and the session answer
space. Target audience: cells that build or survey a question tree, and
tool package authors whose session questions are declared as these
records.

## Public API

    from goga.onboarding import Question, QuestionGroup, SessionAnswers

- `Question(id, kind, prompt, choices=None, default=None, keys=None)` — one
  simple question. Kinds: `choice` (answer — a string from `choices`),
  `input` (answer — a free-form string), `confirm` (answer — a bool),
  `pairs` (answer — a mapping of strings; `keys` proposes the keys).
- `QuestionGroup(id, prompt=None, children=None)` — one nesting level; the
  group's answer is the mapping of its children's answers.
- `SessionAnswers(tools=None)` — the answer space of one run: `record`,
  `amend`, `view_for`, `snapshot`. `tools` reserves the top-level keys of
  the tool sections (the plan block names) — with it, `view_for(tool)`
  isolates the core plus the tool's own answers; without it the space is
  core-only.

## Ready-to-use patterns

### Declare a question of each kind

```python
from goga.onboarding import Question, QuestionGroup

language = Question(id="language", kind="choice", prompt="Project language",
                    choices=["python", "golang"], default="python")
image = Question(id="image", kind="input", prompt="Image name")
setup = Question(id="setup", kind="confirm", prompt="Configure the tool?", default=False)
env = Question(id="env", kind="pairs", prompt="Environment variables",
               keys=["API_URL", "TOKEN"])
```

### Declare a group

```python
block = QuestionGroup(id="reporting", prompt="Reporting settings",
                      children=[setup, env])
```

A group carries one nesting level with simple children; its answer is a
mapping keyed by child ids.

### Address answers

Paths join ids with dots (`reporting.env`); stored answers are nested
mappings — groups hold mappings, no dotted keys. `record` replaces at the
path; `amend` merges mappings recursively and replaces scalars and lists
(last applied wins); `view_for(tool)` returns the core plus the tool's own
answers under local names — other tools' answers are never visible;
`snapshot` returns the committed whole for generation.

## Notes for the consumer

- Question records are immutable value objects — build them fresh, never
  mutate.
- The `id` is local to its parent; uniqueness matters among siblings of the
  same tree position.
