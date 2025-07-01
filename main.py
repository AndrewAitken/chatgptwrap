import os
import sys
import logging
from typing import cast
from openai import AsyncOpenAI
import time
import asyncio

# Импорты Telegram
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters
)

# Импорт dotenv
from dotenv import load_dotenv

# Настройка логирования
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Сообщения для разных команд
WELCOME_MESSAGE = """🌟 Добро пожаловать в ChatGPT Telegram Bot! 🌟

Теперь у вас есть прямой доступ к мощи ChatGPT прямо в Telegram:

✨ Никакого VPN
✨ Не нужна отдельная подписка на ChatGPT
✨ Всё работает прямо здесь, в Telegram
✨ Мгновенные ответы на любые вопросы

Используйте команду /menu чтобы открыть интерактивное меню.
Или просто напишите свой вопрос, и я отвечу вам! 🚀"""

HELP_MESSAGE = """📚 Доступные команды:

/start - Начать работу с ботом
/menu - Открыть интерактивное меню
/help - Показать это сообщение
/about - Информация о боте
/examples - Примеры вопросов
/categories - Категории вопросов
/settings - Настройки бота

Просто напишите свой вопрос в чат, и я отвечу вам! 💬"""

ABOUT_MESSAGE = """ℹ️ О боте:

Этот бот использует ChatGPT - самую продвинутую языковую модель от OpenAI.

🔑 Основные преимущества:
• Доступ к ChatGPT без VPN
• Не нужна регистрация на OpenAI
• Работает в вашем любимом мессенджере
• Быстрые и точные ответы

🛡 Конфиденциальность:
Мы не храним историю ваших запросов
Каждый разговор начинается с чистого листа

🚀 Версия: 1.0"""

EXAMPLES_MESSAGE = """💡 Примеры вопросов:

1️⃣ Общие знания:
• "Что такое квантовая физика?"
• "Расскажи о причинах Первой мировой войны"

2️⃣ Программирование:
• "Как создать простой веб-сервер на Python?"
• "Объясни принцип работы garbage collection"

3️⃣ Математика:
• "Помоги решить квадратное уравнение"
• "Объясни теорему Пифагора"

4️⃣ Творчество:
• "Придумай историю о космическом путешествии"
• "Сочини стихотворение о весне"

Просто скопируйте интересующий вопрос или задайте свой! 🎯"""

CATEGORIES_MESSAGE = """🗂 Категории вопросов:

🎓 Образование
• Математика и физика
• История и география
• Языки и литература

💻 Технологии
• Программирование
• Компьютерные науки
• Искусственный интеллект

🎨 Творчество
• Написание текстов
• Генерация идей
• Стихи и рассказы

💼 Бизнес
• Маркетинг
• Менеджмент
• Анализ данных

🌍 Другое
• Путешествия
• Кулинария
• Здоровье

Выберите интересующую категорию и задайте вопрос! 🎯"""

SETTINGS_MESSAGE = """⚙️ Настройки:

Текущие настройки бота:
📝 Модель: GPT-3.5-turbo
🌐 Язык: Автоопределение
✨ Креативность: Стандартная

❗️ Настройки пока недоступны для изменения.
В следующих версиях вы сможете:
• Выбирать язык ответов
• Настраивать длину ответов
• Регулировать креативность

Следите за обновлениями! 🔄"""

def setup_environment() -> tuple[str, str]:
    """Настройка окружения и проверка зависимостей."""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Проверяем наличие токенов
    bot_token = os.getenv('BOT_TOKEN')
    openai_token = os.getenv('OPENAI_API_KEY')
    
    if not bot_token:
        logger.error("BOT_TOKEN не найден в переменных окружения")
        sys.exit(1)
    
    if not openai_token:
        logger.error("OPENAI_API_KEY не найден в переменных окружения")
        sys.exit(1)
    
    return bot_token, openai_token

async def get_chatgpt_response(client: AsyncOpenAI, message: str) -> str:
    """Получаем ответ от ChatGPT."""
    try:
        # Устанавливаем таймаут для запроса
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - полезный ассистент, который отвечает кратко и по делу."},
                    {"role": "user", "content": message}
                ],
                max_tokens=2048  # Ограничиваем длину ответа
            ),
            timeout=30.0  # Таймаут 30 секунд
        )
        
        content = response.choices[0].message.content
        if not content:
            return "Извините, произошла ошибка при обработке вашего запроса."
        
        # Если ответ слишком длинный, разбиваем его на части
        if len(content) > 4000:  # Оставляем небольшой запас от лимита в 4096
            parts = [content[i:i+4000] for i in range(0, len(content), 4000)]
            return parts[0] + "\n\n(Ответ был сокращен из-за ограничений Telegram)"
            
        return content
    except asyncio.TimeoutError:
        logger.error("Таймаут при запросе к ChatGPT")
        return "Извините, запрос занял слишком много времени. Пожалуйста, попробуйте еще раз или сформулируйте вопрос иначе."
    except Exception as e:
        logger.error(f"Ошибка при запросе к ChatGPT: {e}")
        return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."

async def setup_commands(application: Application) -> None:
    """Настраиваем команды бота."""
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("menu", "Открыть интерактивное меню"),
        BotCommand("help", "Показать список команд"),
        BotCommand("about", "Информация о боте"),
        BotCommand("examples", "Примеры вопросов"),
        BotCommand("categories", "Категории вопросов"),
        BotCommand("settings", "Настройки бота"),
    ]
    await application.bot.set_my_commands(commands)

def get_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками меню."""
    keyboard = [
        [
            InlineKeyboardButton("ℹ️ О боте", callback_data="about"),
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ],
        [
            InlineKeyboardButton("💡 Примеры", callback_data="examples"),
            InlineKeyboardButton("🗂 Категории", callback_data="categories")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    if not update.message:
        return
    
    user_id = update.message.from_user.id if update.message.from_user else 'Unknown'
    logger.info(f"Новый пользователь {user_id} запустил бота")
    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    if not update.message:
        return
    await update.message.reply_text(HELP_MESSAGE)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /about."""
    if not update.message:
        return
    await update.message.reply_text(ABOUT_MESSAGE)

async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /examples."""
    if not update.message:
        return
    await update.message.reply_text(EXAMPLES_MESSAGE)

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /categories."""
    if not update.message:
        return
    await update.message.reply_text(CATEGORIES_MESSAGE)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /settings."""
    if not update.message:
        return
    await update.message.reply_text(SETTINGS_MESSAGE)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /menu."""
    if not update.message:
        return
    
    await update.message.reply_text(
        "Выберите нужный раздел:",
        reply_markup=get_menu_keyboard()
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки меню."""
    query = cast(CallbackQuery, update.callback_query)
    if not query or not query.message:
        return
    
    message = cast(Message, query.message)
    await query.answer()  # Убираем часики с кнопки

    # Определяем, какое сообщение показать в зависимости от нажатой кнопки
    messages = {
        "about": ABOUT_MESSAGE,
        "help": HELP_MESSAGE,
        "examples": EXAMPLES_MESSAGE,
        "categories": CATEGORIES_MESSAGE,
        "settings": SETTINGS_MESSAGE
    }

    try:
        if query.data in messages:
            # Отправляем новое сообщение с кнопкой "Назад в меню"
            keyboard = [[InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]]
            await message.edit_text(
                messages[query.data],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif query.data == "back_to_menu":
            # Возвращаемся в главное меню
            await message.edit_text(
                "Выберите нужный раздел:",
                reply_markup=get_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке нажатия кнопки: {e}")
        # Если не удалось отредактировать сообщение, отправляем новое
        await message.reply_text(
            "Произошла ошибка. Пожалуйста, попробуйте снова: /menu"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений."""
    if not update.message or not update.message.text:
        logger.warning("Получено сообщение без текста")
        return

    user_message = update.message.text
    user_id = update.message.from_user.id if update.message.from_user else 'Unknown'
    username = update.message.from_user.username if update.message.from_user else 'Unknown'
    
    logger.info(f"Получено сообщение от пользователя {user_id} (@{username}): {user_message}")
    
    try:
        # Отправляем индикатор набора текста
        await update.message.chat.send_chat_action("typing")
        
        # Получаем клиент OpenAI из контекста бота
        client = context.bot_data.get('openai_client')
        if not client:
            logger.error("OpenAI client не инициализирован")
            await update.message.reply_text(
                "Извините, произошла техническая ошибка. Пожалуйста, попробуйте позже или обратитесь к администратору."
            )
            return

        # Получаем ответ от ChatGPT
        response = await get_chatgpt_response(client, user_message)
        
        # Отправляем ответ пользователю
        await update.message.reply_text(response)
        logger.info(f"Отправлен ответ пользователю {user_id} (@{username})")
        
    except Exception as e:
        error_message = (
            "Извините, произошла ошибка при обработке вашего сообщения. "
            "Пожалуйста, попробуйте позже или используйте команду /help для получения справки."
        )
        await update.message.reply_text(error_message)
        logger.error(f"Ошибка при обработке сообщения от {user_id} (@{username}): {str(e)}", exc_info=True)

def main() -> None:
    """Основная функция бота."""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            # Получаем токены
            bot_token, openai_token = setup_environment()
            
            # Создаем клиент OpenAI
            openai_client = AsyncOpenAI(api_key=openai_token)
            
            # Создаем и настраиваем приложение
            logger.info("Запуск бота...")
            application = ApplicationBuilder().token(bot_token).post_init(setup_commands).build()
            
            # Сохраняем клиент OpenAI в данных бота
            application.bot_data['openai_client'] = openai_client
            
            # Добавляем обработчики
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(CommandHandler("help", help_command))
            application.add_handler(CommandHandler("about", about_command))
            application.add_handler(CommandHandler("examples", examples_command))
            application.add_handler(CommandHandler("categories", categories_command))
            application.add_handler(CommandHandler("settings", settings_command))
            application.add_handler(CommandHandler("menu", menu_command))
            application.add_handler(CallbackQueryHandler(button_click))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            # Запускаем бота
            logger.info("Бот запущен и ожидает сообщений. Для остановки нажмите Ctrl+C")
            application.run_polling(drop_pending_updates=True)
            break
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Ошибка при запуске бота (попытка {retry_count} из {max_retries}): {e}")
            if retry_count < max_retries:
                logger.info("Повторная попытка через 10 секунд...")
                time.sleep(10)
            else:
                logger.critical("Превышено максимальное количество попыток перезапуска")
                sys.exit(1)

if __name__ == '__main__':
    main() 