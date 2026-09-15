# Minor line of a version — goga/version

## Domain

Deriving the minor line (N.M) of a version string. Target audience: features
that present values matching the installed minor — image tag hints,
compatibility labels — and need the same minor the host↔image comparison
uses.

## Public API

    from goga.version import minor_version, host_goga_version

- `minor_version(version: str) -> str` — the N.M line of `version`. A missing
  minor segment reads as 0; dev/pre/post/local tails are discarded; an
  undeterminable major segment raises ValueError.
- `host_goga_version() -> str` — the installed goga version; the single
  reading point. Propagates the metadata exception when undeterminable.

## Ready-to-use pattern

### Offer a hint matching the installed minor

Read once, derive, format at the consumer:

```python
from goga.version import host_goga_version, minor_version

version = host_goga_version()   # may raise when metadata is unreadable — handle at the caller
tag = minor_version(version)    # "1.3.2" -> "1.3"
image_hint = f"qarium/goga-python-3.12:{tag}"
```

- `minor_version` is pure — the caller owns the metadata boundary and passes
  the string; the routine never reads, prints, or exits.
- A hint built from the returned line agrees with the (major, minor)
  host↔image check by construction.

## Notes for the consumer

- Do not parse the version string at the call site — this routine owns the
  reduction.
- An unreadable installed version is the caller's error to translate into a
  clean message.
