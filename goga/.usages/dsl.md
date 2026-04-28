# DSL Specification

A DSL document (manifest) must be located in the folder whose interface it describes.
The folder is referred to as a cell. The manifest file name is strictly fixed — `CODEMANIFEST`.

Key case sensitivity in the `yaml` document is **IMPORTANT**: if the specification provides examples with a key in uppercase
or lowercase, the key must be named exactly as shown; any other spelling should result in a document structure error.

Within a folder (hereafter referred to as a cell), usages may be stored that describe practices for working with the cell and using its API.
Usages are stored inside the cell in the `.usages` folder but are not required.

## Cell Structure

```
cell/
├── CODEMANIFEST
└── .usages/*.md
```

* cell — folder named after the cell
* CODEMANIFEST — yaml DSL describing the API contract
* .usages — folder with practices that describe how to work with the cell

**IMPORTANT**: each cell stores descriptions of its practices in `.usages` that explain how to use the cell, but
they do not store and are not a source of requirements for the cell and its contract.

## Example CODEMANIFEST File

```yaml
Imports:
  - Types:
      - AnotherCellType
    Usages:
      - another_cell_usage
    From: path/to/another_cell

Usages:
  conventions: .usages/conventions.md
  pattern: |
    Some pattern here
  testing: |
    Requirements to tests

Annotations: |
  Use `conventions` for write code.
  Use `testing` for write tests.

---

"example_routine(param: str) -> return_value:str":
  annotations: |
    Description of routine.

    `param`: description of param

    Use `pattern` for implementation
    Next requirements to routine ...

"ExampleEntity(param: str)":
  annotations: |
    Description of entity.

    `param`: description of param

    Use `pattern` for implementation
    Next requirements to entity ...
  properties:
    example_property -> str: |
      Description of property
  methods:
    "example_method(method_param: str) -> result:str": |
      Description of method.

      `method_param`: description of method_param

      Use `pattern` for implementation
      Next requirements to method ...

---

Author: FirstName LastName
CreatedAt: 01/01/26
Description: |
  Description of CODEMANIFEST file
```

## CODEMANIFEST Document Structure

The DSL describes a **cell contract** — a set of types and their expected API, independent of any specific
programming language or implementation method, based on `yaml`.

The document is divided into three logical parts:

1. **Header (meta-level)** — defines the context:
   - type sources (`Imports`)
   - used practices (`Usages`)
   - global directives (`Annotations`)

2. **Body (contract description)** — type declarations and their expected behavior

3. **Footer (meta-level)** — defines additional meta information that does not affect the contract architecture:
   - author name (`Author`)
   - document creation date (`CreatedAt`)
   - manifest description (`Description`)

Separation is done according to the `yaml` standard using:

```yaml
---
```

The order of parts is **IMPORTANT**:
1. Header
2. Body
3. Footer

**IMPORTANT**: the document does not describe *how exactly to implement the code*, but fixes the **expectations for the API and behavior** that need to be implemented.

---

### Header

The header sets the context in which the entire file should be interpreted.

#### Importing Types and Practices

Types from other files are connected via `Imports` and then used in the body.

```yaml
Imports:
  - Types:
      - ObjectOne
      - ObjectTwo AS Object
    Usages:
      - example_one # path/to/cell/.usages/example_one.md
      - example_two AS example # path/to/cell/.usages/example_two.md
    From: path/to/cell
```

Connects available types and practices within the project.

- `Types` — list of names of imported types
- `Usages` — list of names of imported practices
- `From` — source (folder relative to the working directory where the `CODEMANIFEST` file is located)
- The syntax `ObjectTwo AS Object` means that `ObjectTwo` is imported with the alias name `Object`

**Case is important**.

Imported types can:
- be used in declared interfaces
- be mutated and extended
- be embedded into the current contract

Imported practices:
- are located in the source cell's folder at `{From}/.usages/`
- are imported by filename without the `.md` extension; the full file path is `{From}/.usages/{name}.md`
- create a **trackable dependency** — when a practice changes, consumers are found via the import graph
- do **not** create contractual obligations — they remain at the documentation level for the consumer
- must not have names conflicting with the current `Usages` in the document header (conflicts are resolved by creating an alias in `Imports`)

Restrictions:
- Imports cannot be cross-referential between cells, meaning cell `A` cannot import a type/practice from cell `B` if cell `B` imports a type from cell `A`
- Only cells at the same hierarchy level or below can be imported

#### Usages

`Usages` — a directive in the CODEMANIFEST header that defines a named set of practices for use
in the annotations of the current document.

A practice is documentation that can be about:
- a library
- a pattern
- a convention
- or any specification

Value formats in the `Usages` section:
- path to an md file (relative to the project's working directory)
- URL
- inline description

```yaml
Usages:
  library: .specs/importlib.md
  structures: http://goga.example/structures.md
  pattern: |
    Usage description here...
```

**Key** — the practice name for references in annotations using backticks, e.g. `pattern`.

Practices are connected in two ways:

1. **Declaration** in the `Usages` section — the practice is described by a value
2. **Import** via the `Imports` section — the practice is imported from the `.usages/` directory of another cell
   by filename without the `.md` extension. Import creates a trackable dependency but not a contractual obligation.

**IMPORTANT**: practices cannot be directly linked to contract interfaces, but they describe how the consumer should work with the cell's API.

#### Annotations

Global directives for the agent.

These are:
- implementation requirements
- constraints
- architectural expectations
- hints on using practices

They apply to the entire document.

```yaml
Annotations: |
  Logic of contract here
```

---

### Body

The body describes the **types of the contract** — what API elements should exist and how they should behave.

Three main constructs are used:

1. Type declaration
2. Type embedding
3. Type mutation

#### Types

A type in the DSL is an abstract unit of API.

It can be:
- a class
- a struct
- an object
- a function
- a service
- any other entity

The DSL does not fix the implementation form — only the expected contract.

#### Type Declaration

A type is defined by its signature:

```yaml
"<Name><Signature>":
  location: <file.ext>
  annotations: |
    ...
  methods:
    ...
  properties:
    ...
```

##### Signature

```yaml
"TypeName<Signature>":
  location: <file.ext>
  annotations: |
    ...
  methods:
    "<signature>": |
       ...
```

The signature is written in free form, close to programming languages, that an LLM can easily associate with.

It:
- describes the API shape
- helps the agent understand the expected model
- does not require strict formal grammar

Basic requirements:
* The signature describes the input and output of the contract
* Input and output must have a data type specified
* The output type is associated with a variable/label to convey the semantic meaning of what is returned with the specified data type

##### location

```yaml
Type():
  location: file.ext
```

Specifies the logical placement of the type relative to the root of the current directory in filename format.

Restrictions:
* The file must be at the same level as `CODEMANIFEST`
* The file must include an extension
* The path cannot go up a level or descend into subdirectories

It defines the **expected filesystem structure**, not the implementation method.

#### Entity Type

Must have `methods` and/or `properties`.

```yaml
SomeEntity():
  location: <file.ext>
  annotations: |
    ...
  methods:
    method() -> void:null: |
      ...
  properties:
    name -> str: |
      ...
```

##### Methods

Defines available operations.

```yaml
SomeEntity():
  methods:
    "method_name(param: str) -> result:str": |
      this is annotation of method

      `param`: param of method
```

Each method:
- has a unique name within the entity
- is defined by a signature
- is accompanied by an annotation

##### Properties

Defines type properties.

```yaml
SomeEntity():
    properties:
      name -> int: |
        What is it?
```

Each property:
- has a unique name within the entity
- specifies the data type of the returned value
- is accompanied by an annotation

#### Routine Type

A Routine does NOT have `methods` and `properties`; it has a contract of the form input -> output (optional if nothing is returned).

```yaml
"some_routine(param: int) -> number:int": |
  this is annotation of routine

  `param`: param of method
```

In this example, **number** is simply a semantic association of the `int` type for better understanding of the returned type's meaning.
**param** is an input parameter of type `int` for a class constructor, struct, or function call.

#### Minimal Declaration

If `methods` and `properties` are not specified, the type is treated as a callable unit — a routine (function, functor — depending on the programming language's features).

Example:

```yaml
"function(n: int) -> number:int":
  location: tools.py
  annotations: |
    ...
```

The DSL does not fix the implementation form — only the expected contract.

#### Type Mutation

For type mutation, the following form is used:

```yaml
"Object::SomeClass()":
  ...
```

This means:

- source type `Object`
- target form `SomeClass`

Important:
- the DSL does not define the mutation mechanism
- it can be:
  - inheritance
  - composition
  - adapter
  - interface implementation
  - decoration
  - or any other strategy

Only the fact is fixed:
**there exists a type that represents a concretization of the base type and its extension**

For routines, mutation can mean that the user wants to achieve the same result
but with a different signature and modified logic; this notation may require:
- extension via decoration
- complete replacement of the original logic
- or any other strategy

The number of types to mutate is not limited.

```yaml
"ObjectOne::ObjectTwo::SomeClass()":
  ...
```

Semantically, this means that `SomeClass` must mutate from both `ObjectOne` and `ObjectTwo`.

---

### Footer

The footer is optional and describes the manifest's metadata.

```yaml
Author: FirstName SecondName
CreatedAt: day/month/year

Description: |
  Manifest description
```

Fields:
- `Author`: first and last name of the manifest author
- `CreatedAt`: date the manifest was created
- `Description`: description of the manifest

---

## The .usages/ Directory

The `.usages/` directory is an optional folder inside a cell containing practice files (`*.md`)
for consumers of the cell's API.

`.usages/` files are documentation for the consumer: how to work with the cell's facade,
what practices to apply, what patterns to use (a cross-cell mechanism).

---

## Type Embedding

Embedding means including a type into the current contract.

Restrictions:
- the type must be available via `Imports`
- embedding from `Usages` is not recommended

```yaml
Imports:
  - Types:
      - Entity
    From: path/to/cell

---

->Entity: {}
```

Semantically, this means including the imported type (`Entity`) into the current contract.

---

## Annotations

Annotations are the key mechanism for controlling generation.

They are not a description of "what this is", but directives on:

- what is expected as output
- how the API should behave
- what practices to apply
- what constraints to follow

Annotations can reference practices from `Usages` in the header and from `Imports`.

```yaml
Imports:
  - Usages:
      # path/to/cell/.usages/example.md
      - example
    From: path/to/cell

Usages:
  pattern: |
    Pattern example

Annotations: |
  Use `example` from Imports
  Use `pattern` from Usages

---

"Object":
  annotations: |
    Use `example` from Imports
    Use `pattern` from Usages
  methods:
    "method() ->void:null": |
      Use `example` from Imports
      Use `pattern` from Usages
  properties:
    "name -> str": |
      Use `example` from Imports
      Use `pattern` from Usages
```

### Using References

References can be to:
- variables in the signature
- any types that are in the context of the current `CODEMANIFEST` file, including those in `Imports`
- practices in `Usages` and `Imports`

Restrictions:
- references must be enclosed in backticks, e.g. — \`link_name\`
- annotations must not reference things that do not exist in the context of the current `CODEMANIFEST` file

```yaml
Imports:
  - Types:
      - ObjectOne as Object
      - ObjectTwo
    Usages:
      - usage_from_imports
    From: path/to/cell

Usages:
  usage_link: |
    Pattern example

Annotations: |
  Use `usage_from_imports` from Imports

  Use `usage_link` in this annotations

  Use `ObjectTwo` link from imports
  Use `Object` link from imports with alias

---

Object():
  annotations: |
    Use `usage_from_imports` from Imports

    Use `usage_link` in this annotations

    Use `Object` link from imports with alias
    Use `ObjectTwo` link from imports
  methods:
    "method(param_link: str) -> return_value_link:str": |
      Use `usage_from_imports` from Imports

      Use `usage_link` in this annotations

      Use `Object` link from imports with alias
      Use `ObjectTwo` link from imports

      Use `param_link` in this annotations
      Use `return_value_link` in this annotations
  properties:
    "name -> str": |
      Use `usage_from_imports` from Imports

      Use `usage_link` in this annotations

      Use `Object` link from imports with alias
      Use `ObjectTwo` link from imports
```

### Global Annotations

```yaml
Annotations: |
  Global annotations in document header
```

Define the overall context:

- used libraries
- implementation principles
- runtime specifics
- etc.

Applied to the entire document.

### Practice Annotations

```yaml
Usages:
  usage_file: path/to/usage.md
  usage_url: http://usage.url/usage.md
  usage_text: |
    Inline text of usage in document header
```

Practices can be described as:

- path to an md file
- URL
- inline

They define:
- how to implement
- how to use
- what approaches to use
- what constraints to consider
- etc.

---

### Type Annotations

```yaml
ExampleType():
  annotations: |
    Type annotations here
```

Define expectations for the type entity:

- behavior
- purpose
- rules of operation
- interaction with other entities

They can:
- clarify the signature
- introduce requirements
- reference practices

---

### Property and Method Annotations

```yaml
ExampleType():
  properties:
    example_property -> str: |
      Property annotations here
  methods:
    example_method(): |
      Method annotations here
```

Used to clarify:

- operational logic
- data structure
- result format
- processing rules

This is not a description, but a **behavior contract** that must be implemented.

---

## Practices

Practices are a layer of documentation for consumers of the cell's API.

They do not create entities, but describe how to work with the cell's facade.

---

### Connecting and Using a Practice

```yaml
Imports:
  - Usages:
      - usage_from_cell
    From: path/to/cell

Usages:
  usage_from_doc: .specs/pattern.md
  usage_from_url: http://usage.example/usage.md

Annotations: |
  Use `usage_from_cell` for implementation
  Use `usage_from_doc` for implementation
  Use `usage_from_url` for implementation
```

**IMPORTANT**: a practice receives a local reference name in the document that can be used in annotations, such as \`pattern\`.

Practices are used inside annotations.

For example:

- an instruction to use a specific library
- a reference to a pattern
- a requirement to follow a specific structure
- etc.

Thus:

- the DSL describes **what should exist**
- practices define **how to use the cell's API**
- annotations link these two levels
