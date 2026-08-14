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
        with pytest.raises(ValueError, match="must be a YAML mapping"):
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
        with pytest.raises(ValueError, match="env must be a mapping"):
            load_home_config()

    def test_load_home_config_non_list_docker_token_raises(self, tmp_path, monkeypatch):
        """docker.run present but not a list → ValueError."""
        _write_home_yml(tmp_path, "docker:\n  run: not-a-list\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError, match=r"docker\.run must be a list"):
            load_home_config()

    def test_load_home_config_non_list_docker_build_token_raises(self, tmp_path, monkeypatch):
        """docker.build present but not a list → ValueError (mirrors the run-token guard)."""
        _write_home_yml(tmp_path, "docker:\n  build: not-a-list\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError, match=r"docker\.build must be a list"):
            load_home_config()

    def test_load_home_config_non_mapping_docker_raises(self, tmp_path, monkeypatch):
        """docker present but not a mapping → ValueError (not an AttributeError),
        so the launcher (ValueError, yaml.YAMLError) wrapping still catches it."""
        _write_home_yml(tmp_path, "docker: not-a-mapping\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError, match="docker must be a mapping"):
            load_home_config()

    def test_load_home_config_never_raises_on_missing_file(self, tmp_path, monkeypatch):
        """The never-raise-on-missing-file contract is inviolable — no exception type."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # tmp_path has no ~/.goga/config.yml — must not raise, any path form.
        config = load_home_config()
        assert isinstance(config, HomeConfig)


# --- Shell-tokenization of docker.run / docker.build entries ---


class TestDockerTokenShellSplit:
    """Each docker.run / docker.build entry is shell-tokenized at load so a
    shell-like fragment ``-v /host:/container`` reaches docker as two argv
    tokens (subprocess.Popen does not split a list argv on whitespace)."""

    def test_flag_value_entry_is_split_into_two_tokens(self, tmp_path, monkeypatch):
        """`-v /host:/container` (one YAML entry) → ['-v', '/host:/container']."""
        _write_home_yml(
            tmp_path,
            'docker:\n  run:\n    - "-v /Users/me/.ssh:/home/goga/.ssh"\n',
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["-v", "/Users/me/.ssh:/home/goga/.ssh"]

    def test_quoted_value_with_whitespace_is_preserved(self, tmp_path, monkeypatch):
        """A value containing whitespace is quoted by the author and kept whole."""
        _write_home_yml(
            tmp_path,
            "docker:\n  run:\n    - '-v \"/host with space:/c\"'\n",
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["-v", "/host with space:/c"]

    def test_single_token_entries_are_unchanged(self, tmp_path, monkeypatch):
        """Backward compat: --flag=value, boolean flags, and already-split tokens."""
        _write_home_yml(
            tmp_path,
            "docker:\n  run:\n    - --network=host\n    - --rm\n  build:\n    - --squash\n",
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["--network=host", "--rm"]
        assert config.docker.build == ["--squash"]

    def test_already_split_two_item_list_is_unchanged(self, tmp_path, monkeypatch):
        """A user who already split flag and value into two entries is unaffected."""
        _write_home_yml(
            tmp_path,
            'docker:\n  run:\n    - "-v"\n    - "/host:/c"\n',
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["-v", "/host:/c"]

    def test_multiple_flags_in_one_entry_are_split(self, tmp_path, monkeypatch):
        """A single entry carrying several flag/value pairs is fully tokenized."""
        _write_home_yml(
            tmp_path,
            'docker:\n  run:\n    - "-v /a:/b -v /c:/d"\n',
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["-v", "/a:/b", "-v", "/c:/d"]

    def test_malformed_quote_raises_value_error(self, tmp_path, monkeypatch):
        """A YAML entry whose parsed string is malformed shell (an unterminated
        quote) surfaces as ValueError from shlex at load — caught by the
        launcher preamble as a clean ClickException, never a raw traceback.

        (A quote unterminated at the YAML level is a separate case already
        handled — it raises yaml.YAMLError, also caught by the preamble.)"""
        _write_home_yml(
            tmp_path,
            "docker:\n  run:\n    - '-v /host:/c\"'\n",  # YAML ok; shell has a stray "
        )
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        with pytest.raises(ValueError, match="No closing quotation"):
            load_home_config()

    def test_non_string_entry_is_coerced_not_crashed(self, tmp_path, monkeypatch):
        """A non-string YAML scalar (e.g. an int) is coerced rather than raising
        an uncaught AttributeError — docker surfaces the resulting bad token."""
        _write_home_yml(tmp_path, "docker:\n  run:\n    - 123\n")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config = load_home_config()
        assert config.docker.run == ["123"]

    def test_shell_split_helper_directly(self):
        """The _shell_split helper is the documented tokenization entry point."""
        from goga.config.home.loader import _shell_split

        assert _shell_split(["--network=host"]) == ["--network=host"]
        assert _shell_split(["-v /h:/c"]) == ["-v", "/h:/c"]
        assert _shell_split([]) == []
