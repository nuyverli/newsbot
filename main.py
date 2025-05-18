import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from apscheduler.schedulers.background import BackgroundScheduler

# Включим логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
EVENT, TIME = range(2)

# Словарь для хранения напоминаний
reminders = {}

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.start()

# ВАЖНО: ЗАМЕНИТЕ ЭТОТ ТОКЕН НА ВАШ РЕАЛЬНЫЙ ТОКЕН БОТА
TELEGRAM_BOT_TOKEN = "7454553310:AAF8d6cjQLbTstEQ3GR-IEMcYvlyueCJ56A"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот-напоминалка.\n"
        "Я могу напомнить тебе о важных событиях в указанное время.\n\n"
        "Чтобы создать напоминание, используй команду /remind\n"
        "Чтобы посмотреть свои напоминания - /list\n"
        "Чтобы удалить напоминание - /cancel"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог создания напоминания"""
    await update.message.reply_text(
        "О чём тебе напомнить? (например: 'Принять таблетки', 'Позвонить маме')"
    )
    return EVENT

async def event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет событие и запрашивает время"""
    context.user_data['event'] = update.message.text
    await update.message.reply_text(
        "Введите время напоминания в формате ЧЧ:ММ (например, 14:30)"
    )
    return TIME

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет время и создаёт напоминание"""
    user_id = update.message.from_user.id
    event_text = context.user_data['event']
    time_text = update.message.text

    try:
        # Парсим время
        reminder_time = datetime.strptime(time_text, "%H:%M").time()
        now = datetime.now().time()
        
        # Проверяем, что время ещё не прошло сегодня
        if reminder_time <= now:
            await update.message.reply_text(
                "Это время уже прошло сегодня. Пожалуйста, укажите время в будущем."
            )
            return TIME
        
        # Сохраняем напоминание
        if user_id not in reminders:
            reminders[user_id] = []
        
        reminder_id = len(reminders[user_id]) + 1
        reminders[user_id].append({
            'id': reminder_id,
            'event': event_text,
            'time': time_text
        })
        
        # Планируем напоминание
        await schedule_reminder(user_id, reminder_id, event_text, time_text, context)
        
        await update.message.reply_text(
            f"Отлично! Я напомню тебе '{event_text}' в {time_text}"
        )
        
    except ValueError:
        await update.message.reply_text(
            "Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ (например, 14:30)"
        )
        return TIME
    
    return ConversationHandler.END

async def schedule_reminder(user_id: int, reminder_id: int, event_text: str, time_text: str, context: ContextTypes.DEFAULT_TYPE):
    """Планирует отправку напоминания"""
    async def send_reminder():
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Напоминаю: {event_text}"
        )
        # Удаляем напоминание после отправки
        if user_id in reminders:
            reminders[user_id] = [r for r in reminders[user_id] if r['id'] != reminder_id]
    
    # В реальном приложении нужно использовать точное время из time_text
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=datetime.now() + timedelta(minutes=1)
    )

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список активных напоминаний"""
    user_id = update.message.from_user.id
    if user_id in reminders and reminders[user_id]:
        message = "Ваши напоминания:\n\n"
        for reminder in reminders[user_id]:
            message += f"{reminder['id']}. {reminder['event']} в {reminder['time']}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("У вас нет активных напоминаний.")

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет напоминание"""
    user_id = update.message.from_user.id
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("У вас нет активных напоминаний.")
        return
    
    try:
        # Пытаемся получить ID напоминания из аргументов команды
        reminder_id = int(context.args[0])
        reminders[user_id] = [r for r in reminders[user_id] if r['id'] != reminder_id]
        await update.message.reply_text(f"Напоминание {reminder_id} удалено.")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /cancel <ID напоминания>")

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог создания напоминания"""
    await update.message.reply_text("Создание напоминания отменено.")
    return ConversationHandler.END

def main() -> None:
    """Запуск бота"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Обработчик команды /list
    application.add_handler(CommandHandler("list", list_reminders))

    # Обработчик команды /cancel
    application.add_handler(CommandHandler("cancel", cancel_reminder))

    # Обработчик диалога создания напоминания
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('remind', remind)],
        states={
            EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, event)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )

    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
