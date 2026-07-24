from __future__ import annotations

import inspect
import signal

import goga.docker
import pytest
from goga.docker import DockerRunner


class _FakeProc:
    """Stand-in for a Popen object exposing only the ``wait`` we care about."""

    def __init__(self, returncode: int = 0, wait_side_effect: BaseException | None = None) -> None:
        self._returncode = returncode
        self._wait_side_effect = wait_side_effect
        self.argv: list[str] | None = None

    def wait(self) -> int:
        if self._wait_side_effect is not None:
            raise self._wait_side_effect
        return self._returncode


class _FakePopen:
    """A fake ``subprocess.Popen`` that records every argv and returns a fake proc."""

    def __init__(self, proc: _FakeProc) -> None:
        self._proc = proc
        self.calls: list[list[str]] = []

    def __call__(self, argv) -> _FakeProc:
        self.calls.append(list(argv))
        self._proc.argv = list(argv)
        return self._proc


class _RecordingRun:
    """A fake ``subprocess.run`` (for ``docker kill``) recording every argv."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, check=False, capture_output=False):
        self.calls.append(list(argv))
        result = type("_R", (), {"returncode": 0})()
        return result


class _RecordingSignal:
    """A fake ``signal.signal`` recording installs and restoring prior handlers.

    The real ``signal.signal`` returns the previously-installed handler. To make
    the runner's save/restore testable in isolation, this fake remembers the
    handlers each signum is set to and hands the previous one back on the next
    install. Callers seed prior handlers via ``priors``.
    """

    def __init__(self, priors: dict[int, object] | None = None) -> None:
        self.current = dict(priors) if priors else {}
        self.installs: list[tuple[int, object]] = []

    def __call__(self, signum, handler):
        self.installs.append((signum, handler))
        prev = self.current.get(signum, signal.SIG_DFL)
        self.current[signum] = handler
        return prev


class TestContract:
    """Contract-surface lock: facade accessibility + callable shapes."""

    def test_docker_runner_is_callable_and_in_facade_all(self) -> None:
        assert callable(DockerRunner)
        assert "DockerRunner" in goga.docker.__all__

    def test_docker_runner_constructor_takes_image(self) -> None:
        runner = DockerRunner("img:tag")
        assert runner.image == "img:tag"

    def test_docker_runner_run_method_shape(self) -> None:
        sig = inspect.signature(DockerRunner.run)
        params = list(sig.parameters)
        # First positional is self; second is the required `args` positional.
        assert params[0] == "self"
        assert "args" in params
        # args is positional-or-keyword (a required positional command), the
        # docker options arrive via **params (VAR_KEYWORD).
        assert sig.parameters["args"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        var_keyword = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
        assert var_keyword, "run must accept **params (VAR_KEYWORD)"

    def test_docker_runner_run_accepts_extra_args(self) -> None:
        # run accepts extra_args (raw tokens appended verbatim before the image)
        # as a separate keyword channel from the translated **params.
        sig = inspect.signature(DockerRunner.run)
        params = list(sig.parameters)
        assert "extra_args" in params
        assert sig.parameters["extra_args"].default is None
        # extra_args sits AFTER the required args positional and BEFORE the
        # VAR_KEYWORD params channel.
        args_idx = params.index("args")
        extra_idx = params.index("extra_args")
        var_kw = [p for p in sig.parameters.values() if p.kind is inspect.Parameter.VAR_KEYWORD]
        assert var_kw
        var_kw_idx = params.index(var_kw[0].name)
        assert args_idx < extra_idx < var_kw_idx

    def test_docker_runner_run_returns_int(self, monkeypatch) -> None:
        fake_popen = _FakePopen(_FakeProc(returncode=7))
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", fake_popen)
        monkeypatch.setattr("goga.docker.runner.signal.signal", _RecordingSignal())
        monkeypatch.setattr("goga.docker.runner.subprocess.run", _RecordingRun())

        result = DockerRunner("img:tag").run(["-m", "goga.build"], name="goga-build-1")

        assert isinstance(result, int)
        assert result == 7


class TestDockerRunnerRun:
    """Behavior coverage for DockerRunner.run — argv, name, kill, handler restore."""

    def test_docker_runner_run_assembles_argv_and_returns_exit_code(self, monkeypatch) -> None:
        fake_popen = _FakePopen(_FakeProc(returncode=7))
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", fake_popen)
        # Seed distinct sentinel prior handlers so the restore can be verified by
        # VALUE (the D7 nesting property), not merely by install count.
        sentinel_term = object()
        sentinel_int = object()
        fake_signal = _RecordingSignal(priors={signal.SIGTERM: sentinel_term, signal.SIGINT: sentinel_int})
        monkeypatch.setattr("goga.docker.runner.signal.signal", fake_signal)
        fake_kill = _RecordingRun()
        monkeypatch.setattr("goga.docker.runner.subprocess.run", fake_kill)

        exit_code = DockerRunner("img:tag").run(
            ["-m", "goga.build", "plan"],
            name="goga-build-1",
            rm=True,
            entrypoint="python3",
            workdir="/workspace",
            v=["/p:/workspace", "/r:/workspace/.ralphex"],
            add_host="h:1",
            env_file="/e",
        )

        argv = fake_popen.calls[0]
        assert argv[:2] == ["docker", "run"]
        # name flag + workdir flag present.
        assert "--name" in argv
        name_idx = argv.index("--name")
        assert argv[name_idx + 1] == "goga-build-1"
        assert "--workdir" in argv
        workdir_idx = argv.index("--workdir")
        assert argv[workdir_idx + 1] == "/workspace"
        # -v appears twice (two mounts).
        assert argv.count("-v") == 2
        # image precedes the args (the command after the image).
        img_idx = argv.index("img:tag")
        assert argv[img_idx + 1 : img_idx + 3] == ["-m", "goga.build"]
        # all args present after the image.
        assert argv[img_idx + 1 :] == ["-m", "goga.build", "plan"]
        # exit code returned.
        assert exit_code == 7
        # docker kill targets the name.
        assert fake_kill.calls == [["docker", "kill", "goga-build-1"]]
        # handlers installed + restored for BOTH SIGTERM and SIGINT.
        installed_signums = [signum for signum, _h in fake_signal.installs]
        assert signal.SIGTERM in installed_signums
        assert signal.SIGINT in installed_signums
        # D7 nesting: the runner saves the prior handler and restores it in
        # `finally`. Assert the restore (2nd install per signum) hands back the
        # SAME sentinel that was the prior handler — not SIG_DFL or another
        # handler — so the runner nests correctly under a caller's handler.
        term_handlers = [h for sig, h in fake_signal.installs if sig == signal.SIGTERM]
        int_handlers = [h for sig, h in fake_signal.installs if sig == signal.SIGINT]
        assert len(term_handlers) == 2
        assert len(int_handlers) == 2
        assert term_handlers[1] is sentinel_term
        assert int_handlers[1] is sentinel_int

    def test_docker_runner_run_requires_name(self, monkeypatch) -> None:
        # `name` is the required kill target; its absence must raise BEFORE Popen.
        popped = _FakePopen(_FakeProc())
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", popped)
        monkeypatch.setattr("goga.docker.runner.signal.signal", _RecordingSignal())
        monkeypatch.setattr("goga.docker.runner.subprocess.run", _RecordingRun())

        with pytest.raises((KeyError, ValueError)):
            DockerRunner("img:tag").run(["-m", "goga.build"], rm=True)

        # Popen never reached — validation happens before launch.
        assert popped.calls == []

    def test_docker_runner_kill_in_finally_on_signal(self, monkeypatch) -> None:
        # A SystemExit(130) raised during wait (e.g. SIGINT mid-run) unwinds
        # through finally: docker kill runs, handlers restore, and the
        # SystemExit propagates with code 130.
        fake_popen = _FakePopen(_FakeProc(wait_side_effect=SystemExit(130)))
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", fake_popen)
        fake_signal = _RecordingSignal()
        monkeypatch.setattr("goga.docker.runner.signal.signal", fake_signal)
        fake_kill = _RecordingRun()
        monkeypatch.setattr("goga.docker.runner.subprocess.run", fake_kill)

        with pytest.raises(SystemExit) as exc_info:
            DockerRunner("img:tag").run(["-m", "goga.build"], name="goga-build-1")

        assert exc_info.value.code == 130
        # finally ran docker kill against the name even on the signal path.
        assert fake_kill.calls == [["docker", "kill", "goga-build-1"]]
        # handlers restored (each signum set then reset → 2 installs each).
        installed_signums = [signum for signum, _h in fake_signal.installs]
        assert installed_signums.count(signal.SIGTERM) == 2
        assert installed_signums.count(signal.SIGINT) == 2

    def test_docker_runner_run_empty_extra_args_matches_prior_argv(self, monkeypatch) -> None:
        # No extra_args -> argv equals the pre-refactor form (no extra slot);
        # a true no-op when extra_args is omitted.
        fake_popen = _FakePopen(_FakeProc(returncode=0))
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", fake_popen)
        monkeypatch.setattr("goga.docker.runner.signal.signal", _RecordingSignal())
        monkeypatch.setattr("goga.docker.runner.subprocess.run", _RecordingRun())

        DockerRunner("img:tag").run(["-m", "goga.build"], name="goga-build-1", rm=True)

        argv = fake_popen.calls[0]
        # flags (insertion order: name then rm) then image then args — no extra
        # slot between flags and image (the pre-refactor argv form).
        assert argv == [
            "docker",
            "run",
            "--name",
            "goga-build-1",
            "--rm",
            "img:tag",
            "-m",
            "goga.build",
        ]

    def test_docker_runner_run_inserts_extra_args_before_image(self, monkeypatch) -> None:
        # extra_args are appended verbatim AFTER the translated params flags and
        # BEFORE the image (a separate channel from params — no translation).
        fake_popen = _FakePopen(_FakeProc(returncode=0))
        monkeypatch.setattr("goga.docker.runner.subprocess.Popen", fake_popen)
        monkeypatch.setattr("goga.docker.runner.signal.signal", _RecordingSignal())
        monkeypatch.setattr("goga.docker.runner.subprocess.run", _RecordingRun())

        DockerRunner("img:tag").run(
            ["-m", "goga.build", "plan"],
            extra_args=["--network=host", "--gpus", "all"],
            name="goga-build-1",
            rm=True,
        )

        argv = fake_popen.calls[0]
        # both extra tokens present verbatim.
        assert "--network=host" in argv
        assert argv.count("--gpus") == 1
        assert argv[argv.index("--gpus") + 1] == "all"
        # every extra_args token precedes the image.
        img_idx = argv.index("img:tag")
        assert argv.index("--network=host") < img_idx
        assert argv.index("--gpus") < img_idx
        # image precedes the args (the command after the image) — unchanged.
        assert argv[img_idx + 1 : img_idx + 4] == ["-m", "goga.build", "plan"]
