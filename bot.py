"""
Бот, который отвечает на сообщения в Telegram.
Сначала определяются несколько функций-обработчиков.
Затем эти функции передаются в приложение и регистрируются в соответствующих местах.
После этого бот запускается и работает до тех пор, пока вы не нажмете Ctrl-C в командной строке.
"""

import logging
from logging.handlers import RotatingFileHandler
import os

# Настройка логирования: файл + вывод в консоль
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "bot.log")

file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
# Удаляем возможные хендлеры, чтобы не дублировать вывод при повторном импорте
if root_logger.handlers:
    root_logger.handlers.clear()
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

logger = logging.getLogger(__name__)

# Запрещаем propagate, чтобы сообщения не шли в root и не писались другими глобальными хендлерами
logger.propagate = False

# Отключаем детальные логи библиотеки httpcore
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from telegram import ForceReply, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from model import chat_with_llm

import dotenv
# Загружаем переменные окружения из файла .env
try:
    env = dotenv.dotenv_values(".env")
    TELEGRAM_BOT_TOKEN = env["TELEGRAM_BOT_TOKEN"]
except FileNotFoundError:
    raise FileNotFoundError("Файл .env не найден. Убедитесь, что он существует в корневой директории проекта.")
except KeyError as e:
    raise KeyError(f"Переменная окружения {str(e)} не найдена в файле .env. Проверьте его содержимое.")


# Определим команды и функции-обработчики сообщений
from telegram.helpers import mention_html

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message

    if user is None or message is None:
        return

    await message.reply_html(
        f"Hi {mention_html(user.id, user.first_name)}!",
        reply_markup=ForceReply(selective=True),
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None or message.text is None:
        return

    user_message = f"{message.text}. Имя пользователя: {user.first_name or 'друг'}"
    history = context.chat_data.get("history", []) # pyright: ignore[reportOptionalMemberAccess]
    logger.debug(f"History: {history}")

    llm_response = chat_with_llm(user_message, history=history)
    context.chat_data["history"] = history # pyright: ignore[reportOptionalSubscript]
    await message.reply_text(llm_response or "В доступной информации это не указано.")


def main() -> None:
    """Функция инициализации бот-приложения."""

    if TELEGRAM_BOT_TOKEN is None or not TELEGRAM_BOT_TOKEN.strip():
        raise ValueError("TELEGRAM_BOT_TOKEN пустой или не загружен")

    try:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        chat_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, chat)

        application.add_handler(CommandHandler("start", start))
        application.add_handler(chat_handler)

        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.exception("Ошибка при запуске бота")
        raise


if __name__ == "__main__":
    main()
