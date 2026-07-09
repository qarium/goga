from __future__ import annotations

import pytest
from goga.docker import ensure_in_docker


class TestContract:
    """Contract-surface lock: facade accessibility and callable shape."""

    def test_ensure_in_docker_is_callable(self) -> None:
        assert callable(ensure_in_docker)

    def test_ensure_in_docker_facade_export(self) -> None:
        import goga.docker

        assert "ensure_in_docker" in goga.docker.__all__


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
