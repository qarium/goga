# TODO: Add hook events to the schema domain

Add hook events to the `schema` domain so that tools can extend the cell contract.

## Constraints

- Existing fields must NOT be changed or removed — extension only.
- The extension mechanism is hook events: tools subscribe to schema lifecycle events and extend the cell contract through them.
