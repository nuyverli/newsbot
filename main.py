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
from apscheduler.jobstores.memory import MemoryJobStore

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
EVENT, TIME = range(2)

# Инициализация планировщика с хранилищем в памяти
jobstores = {
    'default': MemoryJobStore()
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

# Токен бота (ЗАМЕНИТЕ НА СВОЙ)
TELEGRAM_BOT_TOKEN = "7454553310:AAF8d6cjQLbTstEQ3GR-IEMcYvlyueCJ56A"

# Глобальный словарь для хранения напоминаний
user_reminders = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение"""
    await update.message.reply_text(
        "🔔 Я бот-напоминалка!\n"
        "Создавайте напоминания командой /remind\n"
        "Список напоминаний: /list\n"
        "Удалить: /cancel <номер>"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает процесс создания напоминания"""
    await update.message.reply_text("📝 Введите текст напоминания:")
    return EVENT

async def event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает текст напоминания"""
    context.user_data['event_text'] = update.message.text
    await update.message.reply_text("⏰ Введите время в формате ЧЧ:ММ:")
    return TIME

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает время и создает напоминание"""
    user_id = update.message.from_user.id
    event_text = context.user_data['event_text']
    time_str = update.message.text

    try:
        # Парсим время
        reminder_time = datetime.strptime(time_str, "%H:%M").time()
        now = datetime.now().time()
        
        # Если время уже прошло, добавляем 1 день
        run_time = datetime.combine(datetime.now().date(), reminder_time)
        if run_time < datetime.now():
            run_time += timedelta(days=1)
        
        # Генерируем уникальный ID
        reminder_id = str(user_id) + str(int(datetime.now().timestamp()))
        
        # Сохраняем напоминание
        if user_id not in user_reminders:
            user_reminders[user_id] = {}
        
        user_reminders[user_id][reminder_id] = {
            'text': event_text,
            'time': time_str,
            'run_time': run_time
        }
        
        # Планируем напоминание
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=run_time,
            args=[user_id, reminder_id, event_text],
            id=reminder_id
        )
        
        await update.message.reply_text(
            f"✅ Напоминание создано!\n"
            f"Текст: {event_text}\n"
            f"Время: {time_str}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ")
        return TIME
    
    return ConversationHandler.END

async def send_reminder(user_id: int, reminder_id: str, event_text: str):
    """Отправляет напоминание пользователю"""
    try:
        # Получаем бота из глобального контекста
        from main import application
        await application.bot.send_message(
            chat_id=user_id,
            text=f"🔔 Напоминание: {event_text}"
        )
        
        # Удаляем из списка после отправки
        if user_id in user_reminders and reminder_id in user_reminders[user_id]:
            del user_reminders[user_id][reminder_id]
            
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список активных напоминаний"""
    user_id = update.message.from_user.id
    if user_id in user_reminders and user_reminders[user_id]:
        message = "📋 Ваши напоминания:\n\n"
        for idx, (reminder_id, reminder) in enumerate(user_reminders[user_id].items(), 1):
            message += f"{idx}. ⏰ {reminder['time']} - {reminder['text']}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет указанное напоминание"""
    user_id = update.message.from_user.id
    if user_id not in user_reminders or not user_reminders[user_id]:
        await update.message.reply_text("📭 Нет активных напоминаний для удаления.")
        return
    
    try:
        if not context.args:
            raise ValueError
        
        # Получаем номер из списка
        reminder_num = int(context.args[0]) - 1
        if reminder_num < 0:
            raise ValueError
            
        # Получаем ID напоминания
        reminder_id = list(user_reminders[user_id].keys())[reminder_num]
        
        # Удаляем из планировщика
        scheduler.remove_job(reminder_id)
        
        # Удаляем из хранилища
        del user_reminders[user_id][reminder_id]
        
        await update.message.reply_text("✅ Напоминание удалено!")
        
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ Используйте: /cancel <номер>\n"
            "Номер можно посмотреть в /list"
        )

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог создания напоминания"""
    await update.message.reply_text("❌ Создание напоминания отменено.")
    return ConversationHandler.END

def main() -> None:
    """Запуск бота"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_reminders))
    application.add_handler(CommandHandler("cancel", cancel_reminder))

    # Обработчик создания напоминания
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('remind', remind)],
        states={
            EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, event)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )
    application.add_handler(conv_handler)

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
