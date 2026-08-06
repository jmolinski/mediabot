from __future__ import annotations

import sys

from pathlib import Path

import pytest

# Make the project modules importable when tests are run from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeSettings:
    """Lightweight stand-in for settings.Settings used across the test suite.

    The real ``Settings`` object reads ``config.json`` from the working
    directory and touches a log file on construction, which we do not want in
    unit tests. Only the attributes that the code under test actually reads are
    provided here.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.token = "test-token"
        self.log_file = cache_dir / "log.log"
        self.authorized_users: list[int] = []
        self.authorized_chats: list[int] = []
        self.authorize_all = True
        self.cache_dir = cache_dir
        self.cache_timeout_seconds = 3600


@pytest.fixture
def fake_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSettings:
    """Patch ``get_settings`` in every module that imports it.

    Returns the ``FakeSettings`` instance so tests can tweak authorization
    lists or the cache directory as needed.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    settings = FakeSettings(cache_dir)

    import settings as settings_module

    def _get_settings() -> FakeSettings:
        return settings

    monkeypatch.setattr(settings_module, "get_settings", _get_settings)

    # Modules that did ``from settings import get_settings`` hold their own
    # reference to the function, so patch each of those namespaces too.
    for module_name in (
        "utils",
        "message",
        "telegram_helpers",
        "handlers",
        "media_fetcher",
    ):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "get_settings"):
            monkeypatch.setattr(module, "get_settings", _get_settings)

    return settings
