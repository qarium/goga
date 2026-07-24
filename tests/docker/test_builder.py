from __future__ import annotations

import inspect
import logging

import goga.docker
import pytest
from goga.docker import DockerBuilder, docker_build_if_not_exist, docker_pull, docker_update
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

    def test_docker_build_if_not_exist_is_callable_and_in_facade_all(self) -> None:
        assert callable(docker_build_if_not_exist)
        assert "docker_build_if_not_exist" in goga.docker.__all__

    def test_docker_build_if_not_exist_signature_takes_primitives(self) -> None:
        # Takes PRIMITIVES (image, dockerfile, extra_args) — never a Config — so
        # the docker cell stays a pure leaf with no Imports, mirroring docker_update.
        sig = inspect.signature(docker_build_if_not_exist)
        assert list(sig.parameters) == ["image", "dockerfile", "extra_args"]
        for param in sig.parameters.values():
            assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    def test_docker_build_if_not_exist_has_extra_args_default(self) -> None:
        # extra_args is a primitive list[str] channel defaulting to None (mutable
        # default avoidance); the build branch forwards it verbatim.
        sig = inspect.signature(docker_build_if_not_exist)
        extra_args = sig.parameters["extra_args"]
        assert extra_args.default is None

    def test_docker_builder_build_accepts_extra_args(self) -> None:
        # build accepts extra_args (raw tokens appended verbatim before -f) as a
        # separate keyword channel from the translated **params.
        sig = inspect.signature(DockerBuilder.build)
        params = list(sig.parameters)
        assert params[0] == "self"
        assert "extra_args" in params
        assert sig.parameters["extra_args"].default is None
        # extra_args sits BEFORE the VAR_KEYWORD params channel.
        extra_idx = params.index("extra_args")
        var_kw = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
        assert var_kw
        var_kw_idx = params.index(var_kw[0].name)
        assert extra_idx < var_kw_idx

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
        # docker_update takes PRIMITIVES (image, dockerfile, extra_args) — never a Config.
        sig = inspect.signature(docker_update)
        assert list(sig.parameters) == ["image", "dockerfile", "extra_args"]
        for param in sig.parameters.values():
            assert param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD

    def test_docker_update_has_extra_args_default(self) -> None:
        # extra_args is a primitive list[str] channel defaulting to None (mutable
        # default avoidance); the build branch forwards it verbatim.
        sig = inspect.signature(docker_update)
        assert sig.parameters["extra_args"].default is None


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

    def test_docker_builder_build_inserts_extra_args_before_dash_f(self, monkeypatch) -> None:
        # extra_args are appended verbatim AFTER the translated params flags and
        # BEFORE -f (a separate channel from params — no translation).
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        DockerBuilder("img:tag", "Dockerfile", context=".").build(pull=True, extra_args=["--network=host", "--squash"])

        argv = fake.calls[0]
        assert argv[:2] == ["docker", "build"]
        # both extra tokens present verbatim (no translation to a flag form).
        assert "--network=host" in argv
        assert "--squash" in argv
        # every extra_args token precedes -f.
        dash_f_idx = argv.index("-f")
        assert argv.index("--squash") < dash_f_idx
        assert argv.index("--network=host") < dash_f_idx
        # -t <image> <context> tail is preserved.
        assert argv[-5:] == ["-f", "Dockerfile", "-t", "img:tag", "."]

    def test_docker_builder_build_empty_extra_args_matches_prior_argv(self, monkeypatch) -> None:
        # No extra_args -> argv equals the pre-refactor form (no extra slot); a
        # true no-op when extra_args is omitted.
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        DockerBuilder("img:tag", "Dockerfile", context=".").build(add_host="127.0.0.1:localhost")

        assert fake.calls == [
            [
                "docker",
                "build",
                "--add-host",
                "127.0.0.1:localhost",
                "-f",
                "Dockerfile",
                "-t",
                "img:tag",
                ".",
            ]
        ]


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
        # build() ran with pull=True (so base images refresh from the registry) and
        # forwarded the extra_args primitive (None here — not passed).
        assert inst.built_with == [{"pull": True, "extra_args": None}]
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
        assert inst.built_with == [{"pull": True, "extra_args": None}]
        assert pulls == []

    def test_docker_update_build_branch_invokes_docker_build_with_pull_flag(self, monkeypatch) -> None:
        # End-to-end through the real DockerBuilder + translate_params + subprocess.run:
        # the build branch of docker_update must emit --pull so base images (FROM ...)
        # refresh from the registry rather than being served from the local cache.
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        docker_update("img:tag", "Dockerfile")

        assert len(fake.calls) == 1
        argv = fake.calls[0]
        assert argv[0:2] == ["docker", "build"]
        assert "--pull" in argv
        # -f <dockerfile> -t <image> <context> tail is preserved.
        assert argv[-5:] == ["-f", "Dockerfile", "-t", "img:tag", "."]

    def test_docker_update_ignores_extra_args_on_pull_branch(self, monkeypatch) -> None:
        # docker_update(image, None, extra_args=[...]) -> pull branch: docker_pull
        # runs once; DockerBuilder.build is NEVER called (extra_args applies to
        # image BUILD only, not a registry pull).
        builder_cls, instances = _recording_builder()
        pulls: list[str] = []

        def _fake_pull(image: str) -> bool:
            pulls.append(image)
            return False

        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)
        monkeypatch.setattr("goga.docker.builder.docker_pull", _fake_pull)

        result = docker_update("img:tag", None, extra_args=["--squash"])

        assert result is None
        assert pulls == ["img:tag"]
        assert instances == []  # no DockerBuilder constructed -> extra_args never reached

    def test_docker_update_forwards_extra_args_to_build_branch(self, monkeypatch) -> None:
        # docker_update(image, dockerfile, extra_args=[...]) -> build branch:
        # extra_args forwarded verbatim to DockerBuilder.build (appended before -f).
        builder_cls, instances = _recording_builder()
        pulls: list[str] = []
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)
        monkeypatch.setattr("goga.docker.builder.docker_pull", pulls.append)

        docker_update("img:tag", "Dockerfile", extra_args=["--squash", "--network=host"])

        assert pulls == []
        assert len(instances) == 1
        assert instances[0].built_with == [{"pull": True, "extra_args": ["--squash", "--network=host"]}]


class TestDockerBuildIfNotExist:
    """Behavior coverage for docker_build_if_not_exist — the first-run safety net.

    Complementary to TestDockerUpdate: docker_update is gated by --update (force
    refresh); docker_build_if_not_exist runs unconditionally at launch entry and
    builds only when the image is absent AND a Dockerfile is declared. Never
    pulls — a registry image is left to docker run / --update.
    """

    def test_noop_when_image_already_present(self, monkeypatch) -> None:
        # image present -> short-circuit before any DockerBuilder construction.
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: True)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        result = docker_build_if_not_exist("img:tag", "Dockerfile")

        assert result is None
        assert instances == []  # no build attempted

    def test_builds_when_image_absent_and_dockerfile_set(self, monkeypatch) -> None:
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        result = docker_build_if_not_exist("img:tag", "Dockerfile")

        assert result is None
        # one DockerBuilder constructed with the forwarded primitives + default context.
        assert len(instances) == 1
        inst = instances[0]
        assert (inst.image, inst.dockerfile, inst.context) == ("img:tag", "Dockerfile", ".")
        # build() ran with pull=True (so base images refresh from the registry) and
        # forwarded the extra_args primitive (None here — not passed) — mirrors
        # docker_update build branch.
        assert inst.built_with == [{"pull": True, "extra_args": None}]

    def test_noop_when_image_absent_and_dockerfile_none(self, monkeypatch) -> None:
        # dockerfile None + image absent -> no-op (NEVER pulls; a registry image
        # is pulled by docker run itself or by an explicit --update).
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        result = docker_build_if_not_exist("img:tag", None)

        assert result is None
        assert instances == []  # no build attempted

    def test_propagates_build_failure(self, monkeypatch) -> None:
        # Fatal build propagates — same contract as docker_update build branch.
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", _BoomBuilder)

        with pytest.raises(DockerBuildError):
            docker_build_if_not_exist("img:tag", "Dockerfile")

    def test_noop_on_empty_string_dockerfile_is_still_treated_as_set(self, monkeypatch) -> None:
        # dockerfile="" is non-None (the branch is `is not None`, not a truthiness
        # check) — same convention as docker_update. Empty string still triggers
        # the build branch when the image is absent.
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        docker_build_if_not_exist("img:tag", "")

        assert len(instances) == 1
        inst = instances[0]
        assert inst.dockerfile == ""
        assert inst.built_with == [{"pull": True, "extra_args": None}]

    def test_build_branch_invokes_docker_build_with_pull_flag(self, monkeypatch) -> None:
        # End-to-end through the real DockerBuilder + translate_params + subprocess.run:
        # the build branch of docker_build_if_not_exist must emit --pull so base images
        # (FROM ...) refresh from the registry. Mirrors docker_update build branch.
        fake = RecordingRun(returncode=0)
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake)

        docker_build_if_not_exist("img:tag", "Dockerfile")

        assert len(fake.calls) == 1
        argv = fake.calls[0]
        assert argv[0:2] == ["docker", "build"]
        assert "--pull" in argv
        # -f <dockerfile> -t <image> <context> tail is preserved.
        assert argv[-5:] == ["-f", "Dockerfile", "-t", "img:tag", "."]

    def test_forwards_extra_args_to_build_branch(self, monkeypatch) -> None:
        # image absent + dockerfile set -> extra_args forwarded verbatim to
        # DockerBuilder.build (appended before -f).
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        docker_build_if_not_exist("img:tag", "Dockerfile", extra_args=["--squash", "--network=host"])

        assert len(instances) == 1
        assert instances[0].built_with == [{"pull": True, "extra_args": ["--squash", "--network=host"]}]

    def test_ignores_extra_args_when_image_present(self, monkeypatch) -> None:
        # image present -> no-op: extra_args never reaches DockerBuilder.build.
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: True)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        result = docker_build_if_not_exist("img:tag", "Dockerfile", extra_args=["--squash"])

        assert result is None
        assert instances == []

    def test_ignores_extra_args_when_image_absent_no_dockerfile(self, monkeypatch) -> None:
        # image absent + dockerfile None -> no-op: extra_args never reaches build.
        builder_cls, instances = _recording_builder()
        monkeypatch.setattr("goga.docker.builder._image_exists", lambda _image: False)
        monkeypatch.setattr("goga.docker.builder.DockerBuilder", builder_cls)

        result = docker_build_if_not_exist("img:tag", None, extra_args=["--squash"])

        assert result is None
        assert instances == []


class TestImageExistsHelper:
    """Behavior coverage for _image_exists — silent local-image probe."""

    def test_returns_true_on_zero_exit(self, monkeypatch) -> None:
        # _image_exists calls subprocess.run with capture_output=True (silent
        # probe), so a plain RecordingRun is not suitable — use a Mock that
        # accepts arbitrary kwargs and returns a CompletedProcess-like object.
        run_calls: list[list[str]] = []

        def fake_run(argv, **_kwargs):
            run_calls.append(list(argv))
            return _Result(0)

        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake_run)

        from goga.docker.builder import _image_exists

        assert _image_exists("img:tag") is True
        assert run_calls == [["docker", "image", "inspect", "img:tag"]]

    def test_returns_false_on_nonzero_exit(self, monkeypatch) -> None:
        # docker image inspect exits non-zero when the image is absent.
        def fake_run(_argv, **_kwargs):
            return _Result(1)

        monkeypatch.setattr("goga.docker.builder.subprocess.run", fake_run)

        from goga.docker.builder import _image_exists

        assert _image_exists("img:tag") is False

    def test_returns_false_when_docker_binary_missing(self, monkeypatch) -> None:
        # FileNotFoundError / PermissionError / OSError -> False (not a crash).
        # The caller has already verified docker availability via _check_docker,
        # so a missing binary here is treated as "image not present".
        def raise_filenotfound(*_args, **_kwargs):
            raise FileNotFoundError("docker")

        monkeypatch.setattr("goga.docker.builder.subprocess.run", raise_filenotfound)

        from goga.docker.builder import _image_exists

        assert _image_exists("img:tag") is False
