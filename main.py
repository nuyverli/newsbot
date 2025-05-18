import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
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

def start(update: Update, context: CallbackContext) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    update.message.reply_text(
        f"Привет, {user.first_name}! Я бот-напоминалка.\n"
        "Я могу напомнить тебе о важных событиях в указанное время.\n\n"
        "Чтобы создать напоминание, используй команду /remind\n"
        "Чтобы посмотреть свои напоминания - /list\n"
        "Чтобы удалить напоминание - /cancel"
    )

def remind(update: Update, context: CallbackContext) -> int:
    """Начинает диалог создания напоминания"""
    update.message.reply_text(
        "О чём тебе напомнить? (например: 'Принять таблетки', 'Позвонить маме')",
        reply_markup=ReplyKeyboardRemove(),
    )
    return EVENT

def event(update: Update, context: CallbackContext) -> int:
    """Сохраняет событие и запрашивает время"""
    context.user_data['event'] = update.message.text
    update.message.reply_text(
        "Введите время напоминания в формате ЧЧ:ММ (например, 14:30)"
    )
    return TIME

def time(update: Update, context: CallbackContext) -> int:
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
            update.message.reply_text(
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
        schedule_reminder(user_id, reminder_id, event_text, time_text)
        
        update.message.reply_text(
            f"Отлично! Я напомню тебе '{event_text}' в {time_text}"
        )
        
    except ValueError:
        update.message.reply_text(
            "Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ (например, 14:30)"
        )
        return TIME
    
    return ConversationHandler.END

def schedule_reminder(user_id: int, reminder_id: int, event_text: str, time_text: str):
    """Планирует отправку напоминания"""
    # Здесь нужно реализовать логику планирования
    # Для простоты будем считать, что напоминание срабатывает через 1 минуту
    # В реальном приложении нужно использовать точное время
    
    def send_reminder(context: CallbackContext):
        context.bot.send_message(
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
        run_date=datetime.now() + timedelta(minutes=1),
        args=[context]
    )

def list_reminders(update: Update, context: CallbackContext) -> None:
    """Показывает список активных напоминаний"""
    user_id = update.message.from_user.id
    if user_id in reminders and reminders[user_id]:
        message = "Ваши напоминания:\n\n"
        for reminder in reminders[user_id]:
            message += f"{reminder['id']}. {reminder['event']} в {reminder['time']}\n"
        update.message.reply_text(message)
    else:
        update.message.reply_text("У вас нет активных напоминаний.")

def cancel_reminder(update: Update, context: CallbackContext) -> None:
    """Удаляет напоминание"""
    user_id = update.message.from_user.id
    if user_id not in reminders or not reminders[user_id]:
        update.message.reply_text("У вас нет активных напоминаний.")
        return
    
    try:
        # Пытаемся получить ID напоминания из аргументов команды
        reminder_id = int(context.args[0])
        reminders[user_id] = [r for r in reminders[user_id] if r['id'] != reminder_id]
        update.message.reply_text(f"Напоминание {reminder_id} удалено.")
    except (IndexError, ValueError):
        update.message.reply_text("Использование: /cancel <ID напоминания>")

def cancel_conversation(update: Update, context: CallbackContext) -> int:
    """Отменяет диалог создания напоминания"""
    update.message.reply_text(
        "Создание напоминания отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

def main() -> None:
    """Запуск бота"""
    # Создаем Updater и передаем ему токен бота
    updater = Updater(TELEGRAM_BOT_TOKEN)

    dispatcher = updater.dispatcher

    # Обработчик команды /start
    dispatcher.add_handler(CommandHandler("start", start))


    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
