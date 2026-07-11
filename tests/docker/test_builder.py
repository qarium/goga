from __future__ import annotations

import inspect
import logging

import goga.docker
import pytest
from goga.docker import DockerBuilder, docker_pull, docker_update
from goga.docker.builder import DockerBuildError


class _Result:
    """Stand-in for a CompletedProcess with just the returncode we care about."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


class RecordingRun:
    """A fake ``subprocess.run`` that records every argv it is handed."""

    def __init__(self, returncode: int = 0) -> None:
        self._returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv, check=False) -> _Result:
        self.calls.append(list(argv))
        return _Result(self._returncode)


class TestContract:
    """Contract-surface lock: facade accessibility + callable shapes."""

    def test_docker_pull_is_callable_and_in_facade_all(self) -> None:
        assert callable(docker_pull)
        assert "docker_pull" in goga.docker.__all__

    def test_docker_builder_is_callable_and_in_facade_all(self) -> None:
        assert callable(DockerBuilder)
        assert "DockerBuilder" in goga.docker.__all__

    def test_docker_update_is_callable_and_in_facade_all(self) -> None:
        assert callable(docker_update)
        assert "docker_update" in goga.docker.__all__

    def test_docker_builder_constructor_shape_and_defaults(self) -> None:
        builder = DockerBuilder("img:tag", dockerfile="Dockerfile", context=".")
        assert builder.image == "img:tag"
        assert builder.dockerfile == "Dockerfile"
        assert builder.context == "."
        # defaults: dockerfile -> "Dockerfile", context -> "."
        defaults = DockerBuilder("img:tag")
        assert defaults.dockerfile == "Dockerfile"
        assert defaults.context == "."
        assert callable(defaults.build)

    def test_docker_update_signature_takes_primitives(self) -> None:
        # docker_update takes PRIMITIVES (image, dockerfile) — never a Config.
        sig = inspect.signature(docker_update)
        assert list(sig.parameters) == ["image", "dockerfile"]
        for param in sig.parameters.values():
            assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


class TestDockerBuilderBuild:
    """Behavior coverage for DockerBuilder.build — params translation + fatality."""

    def test_docker_builder_build_translates_params_and_runs(self, monkeypatch) -> None:
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        result = DockerBuilder("img:tag", "Dockerfile", context=".").build(add_host="127.0.0.1:localhost", pull=True)

        assert result is None
        # flags first (translated), then -f <dockerfile> -t <image> <context> last.
        assert fake.calls == [
            [
                "docker",
                "build",
                "--add-host",
                "127.0.0.1:localhost",
                "--pull",
                "-f",
                "Dockerfile",
                "-t",
                "img:tag",
                ".",
            ]
        ]

    def test_docker_builder_build_uses_constructor_image_and_context(self, monkeypatch) -> None:
        # -t is always the constructor image; <context> is the constructor value.
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        DockerBuilder("my:img", dockerfile="docker/Dockerfile.prod", context="srv").build()

        argv = fake.calls[0]
        assert argv[:2] == ["docker", "build"]
        # tail is -f <dockerfile> -t <image> <context> (5 tokens).
        assert argv[-5:] == ["-f", "docker/Dockerfile.prod", "-t", "my:img", "srv"]

    def test_docker_builder_build_raises_on_nonzero_exit(self, monkeypatch) -> None:
        fake = RecordingRun(returncode=1)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        with pytest.raises(DockerBuildError):
            DockerBuilder("img:tag").build()


class TestDockerPull:
    """Behavior coverage for docker_pull — streamed, non-fatal, never raises."""

    def test_docker_pull_returns_true_on_success(self, monkeypatch) -> None:
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        assert docker_pull("img:tag") is True
        assert fake.calls == [["docker", "pull", "img:tag"]]

    def test_docker_pull_returns_false_and_warns_on_failure(self, monkeypatch, caplog) -> None:
        fake = RecordingRun(returncode=1)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        with caplog.at_level(logging.WARNING, logger="goga.docker.builder"):
            result = docker_pull("img:tag")

        assert result is False
        assert "failed to pull image 'img:tag'" in caplog.text
        # non-fatal: never raises, exactly one docker invocation.
        assert len(fake.calls) == 1


def _recording_builder():
    """Return ``(cls, instances)``: a DockerBuilder stand-in that records itself.

    Each construction appends a fresh instance to ``instances``; ``build()`` is
    recorded per-instance. This lets the docker_update tests assert exactly what
    image/dockerfile/context docker_update forwarded to the constructor.
    """
    instances: list[_RecordingBuilder] = []

    class _RecordingBuilder:
        def __init__(self, image: str, dockerfile: str = "Dockerfile", context: str = ".") -> None:
            self.image = image
            self.dockerfile = dockerfile
            self.context = context
            self.built_with: list[dict] = []
            instances.append(self)

        def build(self, **params) -> None:
            self.built_with.append(params)

    return _RecordingBuilder, instances


class _BoomBuilder:
    """A builder whose build() always raises (build-failure propagation test).

    Accepts the DockerBuilder constructor shape so it can stand in for the class
    directly.
    """

    def __init__(self, image: str, dockerfile: str = "Dockerfile", context: str = ".") -> None:
        # All constructor args intentionally ignored — only build() matters here.
        del image, dockerfile, context

    def build(self, **params) -> None:
        del params
        raise DockerBuildError("boom")


class TestDockerUpdate:
    """Behavior coverage for docker_update — the single --update decision point."""

    def test_docker_update_builds_when_dockerfile_set(self, monkeypatch) -> None:
        builder_cls, instances = _recording_builder()
        pulls: list[str] = []
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)
        monkeypatch.setattr("goga.docker.builder.docker_pull", pulls.append)

        result = docker_update("img:tag", "Dockerfile")

        assert result is None
        # one DockerBuilder constructed with the forwarded primitives + default context.
        assert len(instances) == 1
        inst = instances[0]
        assert (inst.image, inst.dockerfile, inst.context) == ("img:tag", "Dockerfile", ".")
        # build() ran with default params (no extras).
        assert inst.built_with == [{}]
        assert pulls == []

    def test_docker_update_pulls_when_dockerfile_none(self, monkeypatch) -> None:
        builder_cls, instances = _recording_builder()
        pulls: list[str] = []

        def _fake_pull(image: str) -> bool:
            pulls.append(image)
            return False

        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)
        monkeypatch.setattr("goga.docker.builder.docker_pull", _fake_pull)

        result = docker_update("img:tag", None)

        assert result is None
        # exactly one pull, with the image; DockerBuilder never constructed.
        assert pulls == ["img:tag"]
        assert instances == []

    def test_docker_update_propagates_build_failure(self, monkeypatch) -> None:
        pulls: list[str] = []
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", _BoomBuilder)
        monkeypatch.setattr("goga.docker.builder.docker_pull", pulls.append)

        with pytest.raises(DockerBuildError):
            docker_update("img:tag", "Dockerfile")
        # fatal build short-circuits before any pull.
        assert pulls == []

    def test_docker_update_builds_on_empty_string_dockerfile(self, monkeypatch) -> None:
        # dockerfile="" is non-None (the branch is `is not None`, not a truthiness
        # check) -> build branch.
        builder_cls, instances = _recording_builder()
        pulls: list[str] = []
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)
        monkeypatch.setattr("goga.docker.builder.docker_pull", pulls.append)

        docker_update("img:tag", "")

        assert len(instances) == 1
        inst = instances[0]
        assert inst.dockerfile == ""
        assert inst.built_with == [{}]
        assert pulls == []
