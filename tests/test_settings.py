from __future__ import annotations

import json

from pathlib import Path

import pytest

import settings as settings_module


def _write_config(path: Path, cache_dir: Path, **overrides: object) -> Path:
    config = {
        "token": "abc",
        "log_file": str(path.parent / "log.log"),
        "allowed_users": [1, 2],
        "allowed_groups": [-100],
        "cache_dir": str(cache_dir),
        "cache_timeout_minutes": 12,
    }
    config.update(overrides)
    config_path = path.parent / "config.json"
    config_path.write_text(json.dumps(config))
    return config_path


class TestSettings:
    def test_parses_fields(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        config_path = _write_config(tmp_path / "x", cache_dir)

        settings = settings_module.Settings(str(config_path))

        assert settings.token == "abc"
        assert settings.authorized_users == [1, 2]
        assert settings.authorized_chats == [-100]
        assert settings.authorize_all is False
        assert settings.cache_timeout_seconds == 12 * 60

    def test_creates_cache_dir(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "new_cache"
        config_path = _write_config(tmp_path / "x", cache_dir)

        settings_module.Settings(str(config_path))

        assert cache_dir.is_dir()

    def test_touches_log_file(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        config_path = _write_config(tmp_path / "x", cache_dir)

        settings = settings_module.Settings(str(config_path))

        assert settings.log_file.exists()

    def test_no_users_or_groups_without_flag_raises(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        config_path = _write_config(
            tmp_path / "x", cache_dir, allowed_users=[], allowed_groups=[]
        )

        with pytest.raises(ValueError, match="No allowed_users or allowed_groups"):
            settings_module.Settings(str(config_path))

    def test_allow_all_users_flag_enables_authorize_all(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        config_path = _write_config(
            tmp_path / "x",
            cache_dir,
            allowed_users=[],
            allowed_groups=[],
            allow_all_users=True,
        )

        settings = settings_module.Settings(str(config_path))

        assert settings.authorize_all is True


class TestGetLogger:
    def test_returns_cached_logger(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Reset the module-level cache so the test is deterministic.
        monkeypatch.setattr(settings_module, "LOGGER", None)
        cache_dir = tmp_path / "cache"
        config_path = _write_config(tmp_path / "x", cache_dir)
        settings = settings_module.Settings(str(config_path))

        logger1 = settings_module.get_logger(settings)
        logger2 = settings_module.get_logger(settings)

        assert logger1 is logger2
        assert logger1.name == "mediabot_logger"


class TestDisableLogger:
    def test_sets_level_to_warning(self) -> None:
        import logging

        settings_module.disable_logger("some.noisy.logger")
        assert logging.getLogger("some.noisy.logger").level == logging.WARNING
