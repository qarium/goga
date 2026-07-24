from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class DockerArgsConfig:
    """Raw extra docker CLI tokens from the home config docker block.

    Structural validation only (list[str]); docker surfaces flag conflicts.

    `run`: tokens appended to every docker run (pipeline + build containers).
    `build`: tokens appended to docker build (image build).
    """

    run: list[str] = field(default_factory=list)
    build: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class HomeConfig:
    """Home (machine-wide) goga configuration from ~/.goga/config.yml.

    A narrow docker-only layer: base container environment and extra docker CLI
    tokens. Constructed by load_home_config; immutable per `convention`.

    `env`: base (lowest-priority) environment layer for docker run containers
        (pipeline + build); overridden by project config and CLI on key conflict.
    `docker`: extra docker CLI tokens (DockerArgsConfig).
    """

    env: dict[str, str] = field(default_factory=dict)
    docker: DockerArgsConfig = field(default_factory=DockerArgsConfig)
