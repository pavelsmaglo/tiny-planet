import logging
from datetime import time

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def start(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    context.job_queue.run_daily(
        good_morning,
        time(hour=9, minute=0),
        context=chat_id,
        name=str(chat_id)
    )
    update.message.reply_text('Теперь я буду желать вам доброго утра каждый день!')


def good_morning(context: CallbackContext) -> None:
    job = context.job
    context.bot.send_message(job.context, text='Доброе утро! Хорошего дня!')


def main() -> None:
    updater = Updater('YOUR_TELEGRAM_BOT_TOKEN')
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
