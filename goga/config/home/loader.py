from pathlib import Path

import yaml

from .home_config import DockerArgsConfig, HomeConfig


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
        here — that is the consumer's job.

    Raises:
        ValueError: if the parsed value is not a mapping, or ``env`` is present
            but not a mapping, or ``docker.run`` / ``docker.build`` are present
            but not lists.
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
    else:
        run = docker_data.get("run", [])
        build = docker_data.get("build", [])
        if not isinstance(run, list):
            raise ValueError("docker.run must be a list in ~/.goga/config.yml")
        if not isinstance(build, list):
            raise ValueError("docker.build must be a list in ~/.goga/config.yml")
        docker = DockerArgsConfig(run=list(run), build=list(build))

    return HomeConfig(env=env, docker=docker)
