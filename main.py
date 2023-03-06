from telegram.ext import Application, MessageHandler, filters

from settings import get_settings

COMMANDS = []  # probably won't be used


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

    application.run_polling()


if __name__ == "__main__":
    main()
