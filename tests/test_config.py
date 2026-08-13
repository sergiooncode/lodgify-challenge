from pathlib import Path

import pytest

from lodgify_challenge.config import (
    API_KEY_VAR,
    ENV_FILE_VAR,
    MissingAPIKeyError,
    Settings,
    find_repo_root,
    load_settings,
)


def write_env(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env.local"
    path.write_text(body)
    return path


def test_repo_root_is_found_by_marker_not_by_package_depth(tmp_path: Path) -> None:
    root = tmp_path / "somewhere"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert find_repo_root(root / "src" / "pkg" / "config.py") == root.resolve()


def test_repo_root_falls_back_when_no_marker_exists(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert find_repo_root(deep / "config.py").is_dir()


def test_loads_key_from_explicit_file(tmp_path: Path) -> None:
    env_file = write_env(tmp_path, f"{API_KEY_VAR}=from-file\n")
    settings = load_settings(env_file=env_file, environ={})
    assert settings.anthropic_api_key == "from-file"
    assert settings.has_api_key


def test_exported_variable_wins_over_file(tmp_path: Path) -> None:
    env_file = write_env(tmp_path, f"{API_KEY_VAR}=from-file\n")
    settings = load_settings(env_file=env_file, environ={API_KEY_VAR: "from-environ"})
    assert settings.anthropic_api_key == "from-environ"


def test_missing_file_and_empty_environ_is_not_an_error(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / "absent", environ={})
    assert settings.anthropic_api_key is None
    assert not settings.has_api_key


def test_does_not_walk_up_to_a_parent_env_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"{API_KEY_VAR}=parent-leak\n")
    child = tmp_path / "child"
    child.mkdir()
    settings = load_settings(env_file=child / ".env.local", environ={})
    assert settings.anthropic_api_key is None


def test_env_file_var_redirects_the_default_lookup(tmp_path: Path) -> None:
    elsewhere = write_env(tmp_path, f"{API_KEY_VAR}=from-override\n")
    settings = load_settings(environ={ENV_FILE_VAR: str(elsewhere)})
    assert settings.anthropic_api_key == "from-override"


def test_env_file_var_pointing_at_nothing_yields_no_key(tmp_path: Path) -> None:
    settings = load_settings(environ={ENV_FILE_VAR: str(tmp_path / "nope")})
    assert not settings.has_api_key


def test_explicit_env_file_argument_beats_the_override(tmp_path: Path) -> None:
    chosen = write_env(tmp_path, f"{API_KEY_VAR}=explicit\n")
    ignored = tmp_path / "other"
    ignored.write_text(f"{API_KEY_VAR}=override\n")
    settings = load_settings(env_file=chosen, environ={ENV_FILE_VAR: str(ignored)})
    assert settings.anthropic_api_key == "explicit"


def test_overrides_reach_the_settings_object(tmp_path: Path) -> None:
    """Without this, dropping `**overrides` entirely goes unnoticed — a custom
    log directory would be silently ignored."""
    settings = load_settings(env_file=None, environ={}, log_dir=tmp_path / "elsewhere")
    assert settings.log_dir == tmp_path / "elsewhere"


def test_require_api_key_raises_only_when_absent() -> None:
    with pytest.raises(MissingAPIKeyError):
        Settings().require_api_key()
    assert Settings(anthropic_api_key="k").require_api_key() == "k"


def test_export_does_not_touch_environment_until_called() -> None:
    environ: dict[str, str] = {}
    Settings(anthropic_api_key="k").export(environ)
    assert environ == {API_KEY_VAR: "k"}


def test_export_without_a_key_raises_rather_than_writing_empty() -> None:
    environ: dict[str, str] = {}
    with pytest.raises(MissingAPIKeyError):
        Settings().export(environ)
    assert environ == {}


def test_models_default_to_current_ids_and_are_overridable() -> None:
    settings = load_settings(env_file=None, environ={})
    assert settings.generator_model == "anthropic/claude-sonnet-5"
    assert settings.judge_model == "anthropic/claude-sonnet-5"
    swapped = settings.with_models(judge="anthropic/claude-opus-5")
    assert swapped.judge_model == "anthropic/claude-opus-5"
    assert swapped.generator_model == settings.generator_model
