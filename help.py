# help.py

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📋 *BRACU Resource Bot - Instructions*\n\n"
        "➡️ To get course resources, type like `!ECO101`\n_(Don’t forget to put '!' before the course code, another example : !CSE421)_\n\n"
        "➡️ To upload course materials, type `/upload`\n\n"
        "➡️ To check courses with resources, type `/courselist`\n\n"
        "➡️ To start over, type `/start`\n\n"
        "➡️ Get all instructions, type `/help`\n\n"
        "➡️ Inbox admin: [@stacklyy](https://t.me/stacklyy)"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

def get_help_handler():
    return CommandHandler("help", help_command)
