from __future__ import annotations

import inspect
import typing

import pytest
from goga.docker import ensure_in_docker, is_in_docker


class TestContract:
    """Contract-surface lock: facade accessibility and callable shape."""

    def test_ensure_in_docker_is_callable(self) -> None:
        assert callable(ensure_in_docker)

    def test_ensure_in_docker_facade_export(self) -> None:
        import goga.docker

        assert "ensure_in_docker" in goga.docker.__all__


class TestIsInDockerContract:
    """Contract-surface lock for the non-terminal marker query."""

    def test_is_in_docker_facade_export(self) -> None:
        import goga.docker
        from goga.docker import is_in_docker

        assert callable(is_in_docker)
        assert goga.docker.is_in_docker is is_in_docker
        assert "is_in_docker" in goga.docker.__all__

    def test_is_in_docker_declared_signature(self) -> None:
        from goga.docker import is_in_docker

        parameters = inspect.signature(is_in_docker).parameters

        assert list(parameters) == []
        assert typing.get_type_hints(is_in_docker) == {"return": bool}


class TestIsInDocker:
    """Behavior coverage for both branches of the marker query."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("1", True), (None, False), ("0", False), ("yes", False)],
        ids=["marker-one", "unset", "marker-zero", "marker-word"],
    )
    def test_is_in_docker_branches(self, monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool) -> None:
        """True only for the exact marker "1"; every other value including unset is False."""
        if value is None:
            monkeypatch.delenv("GOGA_DOCKER", raising=False)
        else:
            monkeypatch.setenv("GOGA_DOCKER", value)

        assert is_in_docker() is expected

    @pytest.mark.parametrize("value", ["1", "0", "yes"])
    def test_is_in_docker_agrees_with_ensure_in_docker(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
        value: str,
    ) -> None:
        """The marker rule is shared: is_in_docker is True exactly where the guard does not refuse."""
        monkeypatch.setenv("GOGA_DOCKER", value)

        marker_seen = is_in_docker()

        if value == "1":
            ensure_in_docker()  # no refusal, no output
            assert marker_seen is True
        else:
            with pytest.raises(SystemExit):
                ensure_in_docker()

            assert marker_seen is False

        capsys.readouterr()


class TestEnsureInDocker:
    """Behavior coverage for both branches of the in-container guard."""

    def test_ensure_in_docker_success_marker_set(self, monkeypatch, capsys) -> None:
        monkeypatch.setenv("GOGA_DOCKER", "1")

        result = ensure_in_docker()

        assert result is None
        assert capsys.readouterr().err == ""

    def test_ensure_in_docker_refuses_when_marker_missing(self, monkeypatch, capsys, tmp_path) -> None:
        monkeypatch.delenv("GOGA_DOCKER", raising=False)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            ensure_in_docker()

        assert exc_info.value.code == 1
        assert "goga Docker image" in capsys.readouterr().err
        # Observable proof that no filesystem work ran before exit: the guard
        # must not leave any marker directory of its own. The autouse
        # `_isolate_home` fixture creates `.pytest_home` under tmp_path for
        # HOME redirection, so we assert only that the guard itself added
        # nothing (no `.ralphex/`, no state directory), not that tmp_path is
        # literally empty.
        created = {p.name for p in tmp_path.iterdir()}
        assert ".pytest_home" in created
        assert ".ralphex" not in created

    @pytest.mark.parametrize("value", ["0", "true", "", "yes"])
    def test_ensure_in_docker_refuses_when_marker_wrong_value(self, monkeypatch, capsys, value) -> None:
        monkeypatch.setenv("GOGA_DOCKER", value)

        with pytest.raises(SystemExit) as exc_info:
            ensure_in_docker()

        assert exc_info.value.code == 1
        # The refusal message is written on every non-"1" path, not only when
        # the marker is missing.
        assert "goga Docker image" in capsys.readouterr().err

    def test_ensure_in_docker_marker_empty_string(self, monkeypatch) -> None:
        # Boundary value: present but falsy — locks exact-string semantics, not a truthy check.
        monkeypatch.setenv("GOGA_DOCKER", "")

        with pytest.raises(SystemExit) as exc_info:
            ensure_in_docker()

        assert exc_info.value.code == 1
