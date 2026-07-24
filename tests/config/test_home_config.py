# tests/config/test_home_config.py — contract + logic tests for the goga/config/home cell

import dataclasses
from pathlib import Path

import goga.config.home as home_mod
import pytest
from goga.config.home import (
    DockerArgsConfig,
    HomeConfig,
    load_home_config,
)

# --- Helpers ---


def _write_home_yml(home_dir: Path, content: str) -> Path:
    goga_dir = home_dir / ".goga"
    goga_dir.mkdir(parents=True, exist_ok=True)
    path = goga_dir / "config.yml"
    path.write_text(content)
    return path


# --- Contract tests ---


class TestHomeCellReexports:
    def test_public_names_importable_from_home_cell(self):
        """The 3 public names are importable from goga.config.home."""
        for name in ("HomeConfig", "DockerArgsConfig", "load_home_config"):
            assert hasattr(home_mod, name), f"{name} missing from goga.config.home"
            assert name in home_mod.__all__, f"{name} missing from home __all__"

    def test_home_config_constructs_and_is_frozen(self):
        """HomeConfig builds with the documented kwargs and is frozen."""
        config = HomeConfig(env={"FOO": "bar"}, docker=DockerArgsConfig(run=[], build=[]))
        assert config.env == {"FOO": "bar"}
        assert config.docker.run == []
        assert config.docker.build == []
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.env = {}  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.docker = DockerArgsConfig(run=[], build=[])  # type: ignore[misc]

    def test_docker_args_config_is_frozen(self):
        """DockerArgsConfig is frozen per convention."""
        docker = DockerArgsConfig(run=["--network=host"], build=["--squash"])
        with pytest.raises(dataclasses.FrozenInstanceError):
            docker.run = []  # type: ignore[misc]

    def test_load_home_config_returns_home_config_annotation(self):
        """load_home_config declares HomeConfig as its return annotation."""
        ret = load_home_config.__annotations__.get("return", None)
        assert ret is HomeConfig


# --- Logic tests (verbatim scenarios from design §10.3 / §10.4) ---


class TestLoadHomeConfigLogic:
    def test_load_home_config_returns_empty_when_file_absent(self, tmp_path, monkeypatch):
        """Absence of ~/.goga/config.yml is the normal state — empty HomeConfig, never raises."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert isinstance(config, HomeConfig)
        assert config.env == {}
        assert config.docker.run == []
        assert config.docker.build == []

    def test_load_home_config_parses_env_and_docker_tokens(self, tmp_path, monkeypatch):
        """env and docker tokens parse from the home config."""
        _write_home_yml(
            tmp_path,
            "env:\n  FOO: bar\ndocker:\n  run:\n    - --network=host\n  build:\n    - --squash\n",
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.env == {"FOO": "bar"}
        assert config.docker.run == ["--network=host"]
        assert config.docker.build == ["--squash"]

    def test_load_home_config_raises_on_non_mapping_root(self, tmp_path, monkeypatch):
        """A non-mapping root (e.g. a list) raises ValueError."""
        _write_home_yml(tmp_path, "- not a mapping\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError):
            load_home_config()

    def test_load_home_config_explicit_path(self, tmp_path):
        """An explicit path argument overrides Path.home()."""
        path = _write_home_yml(tmp_path, "env:\n  X: y\n")
        config = load_home_config(path=path)
        assert config.env == {"X": "y"}
        assert config.docker.run == []
        assert config.docker.build == []

    def test_load_home_config_unknown_keys_ignored(self, tmp_path, monkeypatch):
        """Unknown top-level keys are ignored (forward-compat)."""
        _write_home_yml(tmp_path, "env:\n  A: b\nsomething_else:\n  - 1\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.env == {"A": "b"}

    def test_load_home_config_absent_docker_block(self, tmp_path, monkeypatch):
        """Absent docker block → empty DockerArgsConfig."""
        _write_home_yml(tmp_path, "env:\n  A: b\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == []
        assert config.docker.build == []

    def test_load_home_config_absent_env(self, tmp_path, monkeypatch):
        """Absent env → empty dict."""
        _write_home_yml(tmp_path, "docker:\n  run:\n    - --rm\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.env == {}
        assert config.docker.run == ["--rm"]

    def test_load_home_config_non_mapping_env_raises(self, tmp_path, monkeypatch):
        """env present but not a mapping → ValueError."""
        _write_home_yml(tmp_path, "env:\n  - not a mapping\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError):
            load_home_config()

    def test_load_home_config_non_list_docker_token_raises(self, tmp_path, monkeypatch):
        """docker.run present but not a list → ValueError."""
        _write_home_yml(tmp_path, "docker:\n  run: not-a-list\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError):
            load_home_config()

    def test_load_home_config_never_raises_on_missing_file(self, tmp_path, monkeypatch):
        """The never-raise-on-missing-file contract is inviolable — no exception type."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # tmp_path has no ~/.goga/config.yml — must not raise, any path form.
        config = load_home_config()
        assert isinstance(config, HomeConfig)
