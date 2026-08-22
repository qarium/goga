# Version consistency check — goga/version

## Domain

Host-side verification that the goga version installed on the host and the
goga version installed inside the project Docker image agree at the
(major, minor) level, plus reading the host goga version. This practice
covers the check entry points on the goga/version facade:
`version_check_enabled`, `ensure_version_match`, `host_goga_version`, and
`compare_versions`.

Target audience: code that launches the project Docker container and must
gate the launch on the version check, and CLI surfaces that display the
host goga version (the root --version/-v flag).

## Public API

    from goga.version import version_check_enabled, ensure_version_match, host_goga_version, compare_versions

- `version_check_enabled() -> bool` — True when the check must run. Only
  the exact environment value GOGA_SKIP_VERSION_CHECK=1 returns False;
  unset, empty, "0", or any other value returns True.
- `ensure_version_match(image_version: str | None) -> None` — apply the
  outcome matrix to the host version and the image version STRING.
  Refuses (stderr message + process exit code 1, no traceback) on
  mismatch, probe failure (None), or an undeterminable host version;
  warns and continues on "0.0.0"; silent on agreement.
- `host_goga_version() -> str` — the installed goga version on the host.
  Propagates the metadata exception when undeterminable; never prints.
- `compare_versions(host_version: str, image_version: str) -> bool` —
  pure (major, minor) comparison with release-segment reduction; patch and
  dev/pre/post/local tails do not affect the verdict.

## Ready-to-use pattern

### Gate a container launch on the version check

The caller owns the container launch and the image-version probe; the
check routines work on strings only. Sequence: decide, probe, verify — the
probe runs only when the check is enabled:

    from goga.version import version_check_enabled, ensure_version_match

    if version_check_enabled():
        image_version = probe_image_version(image)  # str | None, caller's probe
        ensure_version_match(image_version)

    launch_container(image)

Behavior matrix of `ensure_version_match`:

| image_version | host version | outcome |
|---|---|---|
| "1.2.0" | "1.2.1" | silent return — (major, minor) agree; patch is silent |
| "1.2.1.dev3" | "1.2.0" | silent return — tails reduce to release segments |
| "1.3.0" | "1.2.4" | refuse: both versions + remediation hint to stderr, exit 1 |
| "2.0.0" | "1.9.1" | refuse — a major difference is a mismatch |
| None (probe failed) | any | refuse: hint at GOGA_SKIP_VERSION_CHECK, exit 1 |
| "0.0.0" | any | warning to stderr, launch continues |
| any | undeterminable | refuse: clear message, exit 1, no traceback |

### Display the host version

    from importlib.metadata import PackageNotFoundError
    from goga.version import host_goga_version

    try:
        print(host_goga_version())
    except PackageNotFoundError:
        ...  # render a clean user-facing error and exit non-zero

The routine never prints; catching the metadata failure and rendering a
user-facing error belongs to the CLI surface.

## Preconditions

- Call the check after the image exists (acquisition done) and BEFORE the
  work container starts; never on paths that print without launching (a
  dry run).
- Call `ensure_version_match` only when `version_check_enabled()` is True
  — the gate decides whether the probe runs at all.
- Pass version STRINGS, never an image reference — the check routines do
  not launch containers.
- The caller obtains the image version itself (a short-lived probe
  container); None means "could not determine".

## Side effects

- Refusal paths write a message to sys.stderr and terminate the process
  with exit code 1; the stack unwinds so cleanup blocks of the callers
  (launcher temp-file removal, .ralphex cleanup) execute. When the check
  gates a launch, the refusal fires before the launcher's own
  try/finally, so no launcher teardown is due — nothing was started.
- The "0.0.0" path writes a warning to sys.stderr and returns normally.
- The agreeing path writes nothing.

## Anti-patterns

- Do NOT call `ensure_version_match` with an image name or a probe
  callable — it accepts the version string or None.
- Do NOT re-check GOGA_SKIP_VERSION_CHECK after gating on
  `version_check_enabled` — one gate, one place.
- Do NOT catch the refusal to continue anyway — a confirmed mismatch must
  stop the launch.
- Do NOT run the probe when the check is disabled — the escape skips both
  the probe and the comparison.
- Do NOT print anything around the agreeing path — the check is inaudible
  when versions agree.
