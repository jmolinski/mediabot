from typing import Any

from telegram.ext import Application, MessageHandler, filters

from handlers import handler_message, handler_picture, log_error_and_send_info_to_parent
from settings import disable_logger, get_settings

COMMANDS: list[Any] = []  # probably won't be used


async def post_init_set_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(
        [(command.name(), command.description) for command in COMMANDS]
    )


def main() -> None:
    settings = get_settings()

    application = (
        Application.builder()
        .token(settings.token)
        .post_init(post_init_set_bot_commands)
        .build()
    )

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handler_message)
    )
    application.add_handler(
        MessageHandler(filters.PHOTO, handler_picture),
    )

    application.add_error_handler(log_error_and_send_info_to_parent, block=False)

    disable_logger("hpack.hpack")
    disable_logger("httpx._client")
    disable_logger("PIL.Image")
    disable_logger("eyed3")

    application.run_polling()


if __name__ == "__main__":
    main()
