import asyncio

from telegram.ext import (CommandHandler, ConversationHandler, MessageHandler,
                          filters, ContextTypes, ApplicationBuilder)
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from data_source import DataSource
import os
import threading
import time
import datetime
import logging
import sys

ADD_REMINDER_TEXT = 'Add a reminder ⏰'
INTERVAL = 30

MODE = os.getenv("MODE")
TOKEN = os.getenv("TOKEN")
ENTER_MESSAGE, ENTER_TIME = range(2)
dataSource = DataSource(os.environ.get("DATABASE_URL"))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

if MODE == "dev":
    def run():
        logger.info("Start in DEV mode")
        application.run_polling()
elif MODE == "prod":
    def run():
        logger.info("Start in PROD mode")
        application.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", "8443")), url_path=TOKEN,
                                webhook_url="https://{}.herokuapp.com/{}".format(os.environ.get("APP_NAME"), TOKEN))
else:
    logger.error("No mode specified!")
    sys.exit(1)


async def start_handler(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello, creator!", reply_markup=add_reminder_button())


def add_reminder_button():
    keyboard = [[KeyboardButton(ADD_REMINDER_TEXT)]]
    return ReplyKeyboardMarkup(keyboard)


async def add_reminder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter a message of the reminder:")
    return ENTER_MESSAGE


async def enter_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter a time when bot should remind:")
    context.user_data["message_text"] = update.message.text
    return ENTER_TIME


async def enter_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = context.user_data["message_text"]
    time = datetime.datetime.strptime(update.message.text, "%d/%m/%Y %H:%M")
    message_data = dataSource.create_reminder(update.message.chat_id, message_text, time)
    await update.message.reply_text("Your reminder: " + message_data.__repr__())
    return ConversationHandler.END


def start_check_reminders_task():
    thread = threading.Thread(target=wrapped_async_mcheck_reminders, args=())
    thread.daemon = True
    thread.start()


async def check_reminders():
    while True:
        for reminder_data in dataSource.get_all_reminders():
            if reminder_data.should_be_fired():
                dataSource.fire_reminder(reminder_data.reminder_id)
                await application.bot.send_message(reminder_data.chat_id, reminder_data.message)
        time.sleep(INTERVAL)


def wrapped_async_mcheck_reminders():
    asyncio.run(check_reminders())


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_handler))
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(ADD_REMINDER_TEXT), add_reminder_handler)],
        states={
            ENTER_MESSAGE: [MessageHandler(filters.ALL, enter_message_handler)],
            ENTER_TIME: [MessageHandler(filters.ALL, enter_time_handler)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)
    dataSource.create_tables()
    start_check_reminders_task()
    run()

