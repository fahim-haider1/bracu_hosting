import json
import os
import random
import logging
from uuid import uuid4
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from admin import load_config, get_admin_handler
from help import get_help_handler
from lists import get_courselist_handler
import fix_json

# === Logging ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# === Auto-clean approved.json on bot start ===
fix_json.clean_json('approved.json')

# === CONFIG (loaded from environment variables) ===
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

PENDING_FILE = 'pending.json'
APPROVED_FILE = 'approved.json'

FUN_NAMES = [
    "a cool person", "a beautiful soul", "a living legend",
    "an awesome human", "a kind heart", "a genius mind",
    "a resource hero", "a BRACU superstar", "an academic champion",
    "a generous soul", "an inspiring peer"
]

# === JSON HELPERS ===
def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump({}, f)
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def get_fun_name():
    return random.choice(FUN_NAMES)

# === STATES ===
user_states = {}
admin_delete_reject_states = {}

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to BRACU Resource Bot 📚\n\n"
        "➡️Type !CSE421 (with your course code) to get resources.\n\n"
        "➡️Type or use /upload to contribute resources. Admin approval is required.\n\n"
        "➡️Type or use /help for all the instructions and features.\n\n"
        "Let's help each other by sharing resources! 🤝"
    )

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = {'state': 'awaiting_course_code'}
    await update.message.reply_text(
        "Please send the course code (like CSE421) as text, I will tell what to do next."
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    if user.id in user_states and user_states[user.id]['state'] == 'awaiting_delete_reason':
        delete_info = user_states.pop(user.id)
        resource_entry = delete_info['resource_entry']
        resource_key = delete_info['resource_key']
        reason = text

        buttons = [[
            InlineKeyboardButton("✅ Approve Delete", callback_data=f"delete_approve|{resource_key}|{user.id}"),
            InlineKeyboardButton("❌ Reject Delete", callback_data=f"delete_reject|{resource_key}|{user.id}")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)

        caption = (
            f"🗑️ Delete Request Received\n"
            f"Course: {resource_entry['course_code']}\n"
            f"Requested by: {user.first_name}\n\n"
            f"Reason:\n{reason}\n\n"
            f"Approve or Reject below:"
        )

        file_id = resource_entry['file_id']
        file_type = resource_entry['file_type']
        send_func = context.bot.send_photo if file_type == 'photo' else context.bot.send_document
        await send_func(chat_id=ADMIN_ID, photo=file_id if file_type == 'photo' else None,
                        document=file_id if file_type != 'photo' else None, caption=caption, reply_markup=reply_markup)

        await update.message.reply_text("✅ Your delete request has been sent to admin for review.")
        return

    text_upper = text.upper()
    if text_upper.startswith("!"):
        course_code = text_upper[1:]
        approved_data = load_json(APPROVED_FILE)
        files_found = [entry | {'resource_key': key} for key, entry in approved_data.items()
                       if entry.get('course_code') == course_code and 'file_type' in entry and 'file_id' in entry]

        if files_found:
            await update.message.reply_text(f"📚 Resources for {course_code}:\n")
            for entry in files_found:
                caption = f"👤 Shared by {get_fun_name()}\nCourse: {course_code}"
                buttons = [[InlineKeyboardButton("🗑️ Request Delete", callback_data=f"request_delete|{entry['resource_key']}")]]
                reply_markup = InlineKeyboardMarkup(buttons)

                send_func = context.bot.send_photo if entry['file_type'] == 'photo' else context.bot.send_document
                await send_func(chat_id=update.effective_chat.id,
                                photo=entry['file_id'] if entry['file_type'] == 'photo' else None,
                                document=entry['file_id'] if entry['file_type'] != 'photo' else None,
                                caption=caption, reply_markup=reply_markup)

            await update.message.reply_text(
                "\nYou can use 'Save to Downloads' in Telegram to save files.\n\n"
                "🚀 Help others! Use /upload to share more resources. Do not upload existing file again."
            )
        else:
            await update.message.reply_text(f"No resources found for {course_code}.\nYou can contribute resources with /upload 🚀")
        return

    if user.id in user_states and user_states[user.id]['state'] == 'awaiting_course_code':
        user_states[user.id] = {'state': 'awaiting_file', 'course_code': text_upper}
        await update.message.reply_text(f"Got course code: {text_upper}\nNow upload the file (zipping is recommended).")
        return

    if user.id == ADMIN_ID and user.id in admin_delete_reject_states:
        info = admin_delete_reject_states.pop(user.id)
        caption = f"❌ Your delete request for {info['course_code']} was rejected.\nReason from admin:\n{text}"
        await context.bot.send_message(chat_id=info['requester_id'], text=caption)
        await update.message.reply_text("✅ Rejection reason sent to requester.")
        return

    await update.message.reply_text("ℹ️ I didn’t understand that.\nType `/help` to see how to use the bot.", parse_mode='Markdown')

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in user_states and user_states[user.id]['state'] == 'awaiting_file':
        course_code = user_states[user.id]['course_code']
        file_type = 'photo' if update.message.photo else 'document'
        file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id

        resource_key = str(uuid4())
        pending_data = load_json(PENDING_FILE)
        pending_data[resource_key] = {
            'user_id': user.id,
            'course_code': course_code,
            'file_id': file_id,
            'file_type': file_type
        }
        save_json(pending_data, PENDING_FILE)
        del user_states[user.id]

        caption = f"📥 New Resource Submission\nCourse: {course_code}\nFrom: {user.first_name}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=caption)

        await update.message.reply_text("✅ Your resource has been submitted for admin approval. Thanks for contributing!")
    else:
        await update.message.reply_text("ℹ️ Please start upload with /upload command first.")

def main():
    app = Application.builder().token(TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('upload', upload))
    app.add_handler(CommandHandler('help', get_help_handler()))
    app.add_handler(CommandHandler('admin', get_admin_handler()))
    app.add_handler(CommandHandler('courselist', get_courselist_handler()))

    # Text + File handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, receive_file))

    # Inline callback
    app.add_handler(CallbackQueryHandler(load_config))

    app.run_polling()

if __name__ == '__main__':
    main()
