# Examples

This page demonstrates all CODEMANIFEST DSL features through progressively more complex examples.

A CODEMANIFEST file always consists of three YAML documents separated by `---`:

1. **Header** -- Imports, usages, annotations
2. **Body** -- Type declarations (entities and routines)
3. **Footer** -- Author, creation date, description

## Example 1: Minimal routine

The simplest CODEMANIFEST defines a single routine:

```yaml
---

"send_email(to: str, subject: str) -> void:null":
  location: mailer.py
  annotations: |
    Sends an email to the specified recipient.

---
Author: Developer
CreatedAt: 01/06/26
Description: Email sending cell
```

A **routine** is a function signature written as a YAML key in the format `"name(params) -> return_type"`. The value is a mapping with:

- `location` -- the source file where the routine is implemented
- `annotations` -- description and instructions for implementation

## Example 2: Entity with methods and properties

An **entity** is a type that has properties and/or methods:

```yaml
---

"User()":
  location: models/user.py
  annotations: |
    Represents a user in the system.
  properties:
    "id -> int": Unique identifier
    "name -> str": Display name
    "email -> str": Email address
  methods:
    "full_name() -> str:null": |
      Returns the full display name.
    "send_welcome_email() -> void:null": |
      Sends a welcome email to this user.

---
Author: Developer
CreatedAt: 01/06/26
Description: User entity
```

Entities are detected when the body key has `properties`, `methods`, or uses the mutation syntax (`::`). Otherwise the key is treated as a routine.

## Example 3: Imports between cells

Imports allow one cell to reference types from another cell:

```yaml
Imports:
  - Types:
      - User
      - EmailService
    From: myapp/models

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  This cell imports types from the models cell.

---

"create_user(name: str, email: str) -> User:null":
  location: service.py
  annotations: |
    Creates a new user using the `User` type imported from models.
    Sends a welcome email via `EmailService`.

---
Author: Developer
CreatedAt: 02/06/26
Description: User creation service
```

The `Imports` section lists types and/or usages to import. Each entry specifies:

- `Types` -- list of type names to import
- `Usages` -- list of usage names to import (with optional `AS` alias)
- `From` -- the path to the cell directory containing the imported types

Validation rules enforce that imports are used, are not duplicated, do not form cycles, and reference existing types.

## Example 4: Usages

Usages define named practices (conventions, recipes, instructions) available within the cell:

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  testing: .goga/usages/testing.md
  api_docs: |
    Follow REST API design guidelines for all endpoints.
    Use proper HTTP status codes and JSON response format.
  external_guide: https://example.com/docs/best-practices

Annotations: |
  Use `conventions` for coding standards.
  Use `testing` for test patterns.
  Use `api_docs` for API design rules.

---

"get_users() -> list[User]:null":
  location: handlers.py
  annotations: |
    Returns all users. Follow `api_docs` practice for response format.

---
Author: Developer
CreatedAt: 03/06/26
Description: User API handlers
```

Usage values support three formats:

- **Filepath** -- a path ending in `.md` (e.g. `.goga/usages/conventions.md`)
- **URL** -- an HTTP/HTTPS link (e.g. `https://example.com/docs`)
- **Inline text** -- any other string value used directly

The linter validates that referenced files exist and URLs are accessible.

## Example 5: Mutations

Mutations allow extending an existing entity with new methods and properties:

```yaml
---

"BaseEntity()":
  location: base.py
  annotations: |
    Base entity with core functionality.
  methods:
    "save() -> void:null": |
      Persists the entity to storage.

"BaseEntity::ExtendedEntity()":
  location: extended.py
  annotations: |
    Extends BaseEntity with additional methods.
  methods:
    "validate() -> bool:null": |
      Validates the entity data.

---
Author: Developer
CreatedAt: 04/06/26
Description: Entity mutation example
```

Mutation syntax uses `::` in the type name. `BaseEntity::ExtendedEntity` means `ExtendedEntity` mutates (extends) `BaseEntity`. The mutation chain can be multi-level:

```yaml
"Base::Middle::Leaf()":
  location: leaf.py
  methods:
    "custom_method() -> void:null": |
      Custom method on the leaf entity.
```

The linter validates that all base types in the mutation chain exist in the project.

## Example 6: Embeddings

Embeddings import a type from another cell and make it available locally:

```yaml
Imports:
  - Types:
      - ExternalService
    From: shared/services

---

# Embed the ExternalService type into this cell
"->ExternalService()":
  location: service.py
  annotations: |
    Embedded reference to the shared ExternalService.

---
Author: Developer
CreatedAt: 05/06/26
Description: Cell with embedded type
```

The `->` prefix before a type name marks it as **embedded**. Embedded types are enriched with metadata (signature, annotations, properties, methods) from their original definition in the imported cell.

Key rules for embeddings:

- Embedded types must be imported in the `Imports` section
- Embedded entities cannot have mutations (they inherit from the original)
- Embedded types are resolved against their original definitions in the document tree
