import shlex
from pathlib import Path

import yaml

from .home_config import DockerArgsConfig, HomeConfig


def _shell_split(entries: list[str]) -> list[str]:
    """Shell-tokenize each docker CLI entry into argv tokens.

    Home-config ``docker.run`` / ``docker.build`` entries are authored as
    shell-like fragments (e.g. ``-v /host:/container``). They reach docker via
    ``subprocess.Popen(argv)`` with a list argv, which does NOT split on
    whitespace — so an entry carrying ``flag value`` must be tokenized HERE
    into separate argv tokens, otherwise docker receives ``-v /host:/container``
    as a single argument and rejects the leading-space source as an invalid
    volume name.

    ``shlex.split`` applies POSIX shell rules, which makes the documented
    single-token forms behave identically (backward compatible):

    - ``--network=host`` → ``["--network=host"]`` (no whitespace → one token)
    - ``-v /host:/container`` → ``["-v", "/host:/container"]``
    - ``-v "/host with space:/c"`` → ``["-v", "/host with space:/c"]`` (quote
      values that contain whitespace)
    - an already-split single token (``"-v"``) → ``["-v"]`` (unchanged)

    Variables (``$HOME``) and ``~`` are NOT expanded — same as a literal in a
    real shell quote. A malformed entry (e.g. an unterminated quote) raises
    ``ValueError``, caught by the launcher's home-config preamble so it surfaces
    as a clean ClickException rather than a traceback.

    Args:
        entries: the raw ``docker.run`` / ``docker.build`` list from YAML. Each
            element is coerced to ``str`` so a non-string YAML scalar
            (``- 123``) never crashes the loader with an uncaught
            ``AttributeError`` — docker surfaces the resulting bad token.

    Returns:
        The flattened list of shell-tokenized argv tokens.
    """
    tokens: list[str] = []

    for entry in entries:
        tokens.extend(shlex.split(str(entry)))

    return tokens


def load_home_config(path: Path | None = None) -> HomeConfig:
    """Load the optional home (machine-wide) goga configuration.

    Reads ``~/.goga/config.yml`` (or an explicit ``path`` for testability).
    Absence of the file is the normal state — an empty :class:`HomeConfig` is
    returned and **never** raises on a missing file.

    Args:
        path: optional explicit path; ``None`` -> ``Path.home()/".goga"/"config.yml"``.

    Returns:
        A :class:`HomeConfig`. Empty (``env={}``, ``docker=DockerArgsConfig(run=[], build=[])``)
        when the file is absent. Layering with the project config is NOT performed
        here — that is the consumer's job. Each ``docker.run`` / ``docker.build``
        entry is shell-tokenized (``shlex.split``) so an entry like
        ``-v /host:/container`` reaches docker as two argv tokens rather than one.

    Raises:
        ValueError: if the parsed value is not a mapping, ``env`` or ``docker``
            are present but not mappings, ``docker.run`` / ``docker.build``
            are present but not lists, or a ``docker.run`` / ``docker.build``
            entry is malformed shell (e.g. an unterminated quote).
        yaml.YAMLError: if YAML parsing fails.
    """
    config_path = path if path is not None else Path.home() / ".goga" / "config.yml"

    if not config_path.exists():
        return HomeConfig(env={}, docker=DockerArgsConfig(run=[], build=[]))

    data = yaml.safe_load(config_path.read_text())

    if not isinstance(data, dict):
        raise ValueError("~/.goga/config.yml must be a YAML mapping")

    env = data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("env must be a mapping in ~/.goga/config.yml")
    env = dict(env)

    docker_data = data.get("docker")
    if docker_data is None:
        docker = DockerArgsConfig(run=[], build=[])
    elif not isinstance(docker_data, dict):
        raise ValueError("docker must be a mapping in ~/.goga/config.yml")
    else:
        run = docker_data.get("run", [])
        build = docker_data.get("build", [])
        if not isinstance(run, list):
            raise ValueError("docker.run must be a list in ~/.goga/config.yml")
        if not isinstance(build, list):
            raise ValueError("docker.build must be a list in ~/.goga/config.yml")
        # Each entry is a shell-like fragment tokenized into argv tokens here
        # (see _shell_split) so `-v /host:/container` reaches docker as two
        # tokens, not one. The structural list[str] contract is unchanged.
        docker = DockerArgsConfig(run=_shell_split(run), build=_shell_split(build))

    return HomeConfig(env=env, docker=docker)
