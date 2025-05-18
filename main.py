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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
EVENT, TIME = range(2)

# Глобальный словарь для хранения напоминаний
reminders = {}

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.start()

# Токен бота (замените на ваш)
TELEGRAM_BOT_TOKEN = "7454553310:AAF8d6cjQLbTstEQ3GR-IEMcYvlyueCJ56A"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот-напоминалка.\n"
        "Я могу напомнить тебе о важных событиях.\n\n"
        "Команды:\n"
        "/remind - создать напоминание\n"
        "/list - показать напоминания\n"
        "/cancel <номер> - удалить напоминание"
    )

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает процесс создания напоминания"""
    await update.message.reply_text(
        "📝 О чём тебе напомнить?\n"
        "Например: Принять таблетки, Позвонить маме, Сделать зарядку"
    )
    return EVENT

async def event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает текст напоминания"""
    # Сохраняем текст как есть, без обработки кавычек
    context.user_data['event'] = update.message.text
    await update.message.reply_text(
        "⏰ Введите время в формате ЧЧ:ММ\n"
        "Например: 14:30 или 09:15"
    )
    return TIME

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает время и сохраняет напоминание"""
    user_id = update.message.from_user.id
    event_text = context.user_data['event']
    time_text = update.message.text

    try:
        # Парсим время
        reminder_time = datetime.strptime(time_text, "%H:%M").time()
        now = datetime.now().time()
        
        # Проверяем что время в будущем
        if reminder_time <= now:
            await update.message.reply_text(
                "⏳ Это время уже прошло сегодня. Укажите время в будущем."
            )
            return TIME
        
        # Инициализируем список напоминаний для пользователя, если его нет
        if user_id not in reminders:
            reminders[user_id] = []
        
        # Создаем ID для нового напоминания
        reminder_id = len(reminders[user_id]) + 1
        
        # Сохраняем напоминание
        reminders[user_id].append({
            'id': reminder_id,
            'event': event_text,
            'time': time_text,
            'datetime': datetime.combine(datetime.now().date(), reminder_time)
        })
        
        # Планируем напоминание
        await schedule_reminder(user_id, reminder_id, event_text, time_text, context)
        
        await update.message.reply_text(
            f"✅ Запомнил! Напомню о:\n"
            f"'{event_text}'\n"
            f"в {time_text}"
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30)"
        )
        return TIME
    
    return ConversationHandler.END

async def schedule_reminder(user_id: int, reminder_id: int, event_text: str, time_text: str, context: ContextTypes.DEFAULT_TYPE):
    """Планирует отправку напоминания"""
    async def send_reminder():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 Напоминание!\n{event_text}"
            )
            # Удаляем из списка после отправки
            if user_id in reminders:
                reminders[user_id] = [r for r in reminders[user_id] if r['id'] != reminder_id]
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
    
    # Получаем время из сохраненного напоминания
    reminder = next((r for r in reminders[user_id] if r['id'] == reminder_id), None)
    if reminder:
        run_time = reminder['datetime']
        if run_time < datetime.now():
            run_time += timedelta(days=1)  # Переносим на завтра, если время прошло
            
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=run_time
        )

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список активных напоминаний"""
    user_id = update.message.from_user.id
    if user_id in reminders and reminders[user_id]:
        message = "📋 Ваши напоминания:\n\n"
        for reminder in sorted(reminders[user_id], key=lambda x: x['time']):
            message += f"{reminder['id']}. ⏰ {reminder['time']} - {reminder['event']}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("📭 У вас нет активных напоминаний.")

async def cancel_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет указанное напоминание"""
    user_id = update.message.from_user.id
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("📭 У вас нет активных напоминаний для удаления.")
        return
    
    try:
        if not context.args:
            raise ValueError
        
        reminder_id = int(context.args[0])
        # Проверяем существование напоминания
        if not any(r['id'] == reminder_id for r in reminders[user_id]):
            await update.message.reply_text(f"❌ Напоминание с ID {reminder_id} не найдено.")
            return
            
        # Удаляем напоминание
        reminders[user_id] = [r for r in reminders[user_id] if r['id'] != reminder_id]
        await update.message.reply_text(f"✅ Напоминание {reminder_id} удалено.")
        
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ Используйте: /cancel <номер>\n"
            "Например: /cancel 1\n"
            "Посмотреть номера: /list"
        )

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет диалог создания напоминания"""
    await update.message.reply_text("❌ Создание напоминания отменено.")
    return ConversationHandler.END

def main() -> None:
    """Запуск бота"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_reminders))
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

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
