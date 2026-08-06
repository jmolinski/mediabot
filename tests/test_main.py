from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import main

from handlers import HelpCommandHandler


class TestCommands:
    def test_help_command_registered(self) -> None:
        assert HelpCommandHandler in main.COMMANDS


class TestPostInitSetBotCommands:
    async def test_sets_commands_from_registry(self) -> None:
        bot = AsyncMock()
        application: Any = type("App", (), {"bot": bot})()

        await main.post_init_set_bot_commands(application)

        bot.set_my_commands.assert_awaited_once()
        (commands,), _ = bot.set_my_commands.await_args
        assert (HelpCommandHandler.name, HelpCommandHandler.description) in commands
