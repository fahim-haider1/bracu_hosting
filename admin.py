# admin.py

import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

CONFIG_FILE = 'config.json'
ADMIN_ID = 5214922760   # Your admin ID

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Default config (approval ON)
        config = {'admin_approval_required': True}
        save_config(config)
        return config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    config = load_config()
    current_status = config['admin_approval_required']

    new_status = not current_status
    config['admin_approval_required'] = new_status
    save_config(config)

    status_text = "🟢 Admin approval is now *REQUIRED* for uploads." if new_status else "🟡 Admin approval is now *NOT REQUIRED* for uploads (uploads are auto-approved)."
    await update.message.reply_text(f"✅ Setting updated.\n\n{status_text}", parse_mode='Markdown')

def get_admin_handler():
    return CommandHandler("admin", admin_command)
