from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class DockerArgsConfig:
    """Extra docker CLI tokens from the home config docker block — each raw YAML entry shell-tokenized at load.

    Attributes:
        run: Tokens appended to every ``docker run`` (pipeline and build containers).
        build: Tokens appended to ``docker build`` (image build).
    """

    run: list[str] = field(default_factory=list)
    build: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class HomeConfig:
    """Home (machine-wide) goga configuration from ``~/.goga/config.yml`` — a docker-only layer.

    Attributes:
        env: Base (lowest-priority) environment layer for ``docker run`` containers; overridden by
            project config and CLI on key conflict.
        docker: Extra docker CLI tokens (:class:`DockerArgsConfig`).
    """

    env: dict[str, str] = field(default_factory=dict)
    docker: DockerArgsConfig = field(default_factory=DockerArgsConfig)
