import os
import json
import random
from uuid import uuid4
from http.server import BaseHTTPRequestHandler
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ===== CONFIGURATION =====
TOKEN = os.getenv('BOT_TOKEN', '7846786334:AAFNwjBQq7gdnwzdl7EKi4Nre2tI9WMFISk')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5214922760'))

# ===== FILE PATHS =====
DATA_DIR = '/tmp'  # Vercel only allows writes to /tmp

APPROVED_FILE = os.path.join(DATA_DIR, 'approved.json')
PENDING_FILE = os.path.join(DATA_DIR, 'pending.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
POINTS_FILE = os.path.join(DATA_DIR, 'points.json')
USER_IDS_FILE = os.path.join(DATA_DIR, 'user_ids.json')

# ===== UTILITY FUNCTIONS =====
FUN_NAMES = [
    "a cool person", "a beautiful soul", "a living legend",
    "an awesome human", "a kind heart", "a genius mind",
    "a resource hero", "a BRACU superstar", "an academic champion",
    "a generous soul", "an inspiring peer"
]

def get_fun_name():
    return random.choice(FUN_NAMES)

def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            if 'user_ids' in filename:
                json.dump([], f)
            else:
                json.dump({}, f)
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    try:
        return load_json(CONFIG_FILE)
    except FileNotFoundError:
        config = {'admin_approval_required': True}
        save_json(config, CONFIG_FILE)
        return config

# ===== STATE MANAGEMENT =====
user_states = {}
admin_delete_reject_states = {}

# ===== COMMAND HANDLERS =====
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

    # Handle delete reason
    if user.id in user_states and user_states[user.id]['state'] == 'awaiting_delete_reason':
        delete_info = user_states[user.id]
        resource_entry = delete_info['resource_entry']
        course_code = resource_entry['course_code']
        file_id = resource_entry['file_id']
        file_type = resource_entry['file_type']
        resource_key = delete_info['resource_key']
        reason = text

        # Reset state
        del user_states[user.id]

        # Send delete request to admin
        buttons = [
            [InlineKeyboardButton("✅ Approve Delete", callback_data=f"delete_approve|{resource_key}|{user.id}"),
             InlineKeyboardButton("❌ Reject Delete", callback_data=f"delete_reject|{resource_key}|{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        caption = (
            f"🗑️ Delete Request Received\n"
            f"Course: {course_code}\n"
            f"Requested by: {user.first_name}\n\n"
            f"Reason:\n{reason}\n\n"
            f"Approve or Reject below:"
        )

        if file_type == 'photo':
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=file_id,
                caption=caption,
                reply_markup=reply_markup
            )

        await update.message.reply_text("✅ Your delete request has been sent to admin for review.")
        return

    # Resource request
    text_upper = text.upper()
    if text_upper.startswith("!"): 
        course_code = text_upper[1:]
        approved_data = load_json(APPROVED_FILE)

        files_found = []
        for key, entry in approved_data.items():
            if 'file_type' not in entry or 'file_id' not in entry:
                continue

            if entry['course_code'] == course_code:
                entry_copy = entry.copy()
                entry_copy['resource_key'] = key
                files_found.append(entry_copy)

        if files_found:
            await update.message.reply_text(f"📚 Resources for {course_code}:\n")

            for entry in files_found:
                fun_name = get_fun_name()
                caption = f"👤 Shared by {fun_name}\nCourse: {course_code}"

                buttons = [[
                    InlineKeyboardButton("🗑️ Request Delete", callback_data=f"request_delete|{entry['resource_key']}")
                ]]
                reply_markup = InlineKeyboardMarkup(buttons)

                if entry['file_type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=entry['file_id'],
                        caption=caption,
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=entry['file_id'],
                        caption=caption,
                        reply_markup=reply_markup
                    )

            msg = "\nYou can use 'Save to Downloads' in Telegram to save files.\n\n"
            msg += "🚀 Help others! Use /upload to share more resources. Do not upload existing file again." 
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                f"No resources found for {course_code}.\n"
                "You can contribute resources with /upload 🚀"
            )
        return

    # Upload flow
    if user.id in user_states and user_states[user.id]['state'] == 'awaiting_course_code':
        user_states[user.id]['state'] = 'awaiting_file'
        user_states[user.id]['course_code'] = text_upper
        await update.message.reply_text(
            f"Got course code: {text_upper}\nNow upload the file. Zipping all in one file is recommended instead of sending one by one" 
        )
        return

    # Handle admin reject reason
    if user.id == ADMIN_ID and user.id in admin_delete_reject_states:
        info = admin_delete_reject_states[user.id]
        requester_id = info['requester_id']
        course_code = info['course_code']
        reason_text = text

        caption = f"❌ Your delete request for {course_code} was rejected.\nReason from admin:\n{reason_text}"
        await context.bot.send_message(chat_id=requester_id, text=caption)
        await update.message.reply_text("✅ Rejection reason sent to requester.")

        # Clear state
        del admin_delete_reject_states[user.id]
        return

    # Default reply
    await update.message.reply_text(
        "ℹ️ I didn't understand that.\nType `/help` to see how to use the bot.",
        parse_mode='Markdown'
    )

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document
    photo = update.message.photo

    if document:
        file_id = document.file_id
        file_type = 'document'
    elif photo:
        file_id = photo[-1].file_id
        file_type = 'photo'
    else:
        await update.message.reply_text("Please send a file or image.")
        return

    if user.id not in user_states or user_states[user.id].get('state') != 'awaiting_file':
        await update.message.reply_text("First send the course code as text using /upload!")
        return

    course_code = user_states[user.id]['course_code']
    del user_states[user.id]

    config = load_config()
    admin_approval_required = config.get('admin_approval_required', True)

    if admin_approval_required:
        pending_data = load_json(PENDING_FILE)
        short_key = str(uuid4())[:8]

        pending_data[short_key] = {
            "course_code": course_code,
            "file_id": file_id,
            "file_type": file_type,
            "uploader_id": user.id,
            "uploader_name": user.first_name
        }

        save_json(pending_data, PENDING_FILE)

        await update.message.reply_text(f"File received for {course_code}. Awaiting admin approval.")

        buttons = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve|{short_key}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject|{short_key}")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        caption = f"📥 Pending resource:\nCourse: {course_code}\nUploader: {user.first_name}\n\nApprove or Reject below:"

        if file_type == 'photo':
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=file_id,
                caption=caption,
                reply_markup=reply_markup
            )
    else:
        approved_data = load_json(APPROVED_FILE)
        approved_key = str(uuid4())[:8]

        approved_data[approved_key] = {
            "course_code": course_code,
            "file_id": file_id,
            "file_type": file_type,
            "uploader_id": user.id,
            "uploader_name": user.first_name
        }

        save_json(approved_data, APPROVED_FILE)

        await update.message.reply_text(f"✅ Your file for {course_code} has been auto-approved and added. Type  !{course_code}  to check the resources.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve") or data.startswith("reject"):
        action, short_key = data.split("|")
        pending_data = load_json(PENDING_FILE)

        if short_key not in pending_data:
            await query.edit_message_caption("This resource is no longer pending.")
            return

        entry = pending_data.pop(short_key)
        save_json(pending_data, PENDING_FILE)

        uploader_id = entry['uploader_id']
        uploader_name = entry['uploader_name']
        course_code = entry['course_code']
        file_id = entry['file_id']
        file_type = entry['file_type']

        if action == "approve":
            approved_data = load_json(APPROVED_FILE)
            approved_key = str(uuid4())[:8]
            approved_data[approved_key] = entry
            save_json(approved_data, APPROVED_FILE)

            await query.edit_message_caption(f"✅ Approved resource for {course_code} from {uploader_name}")

            caption = f"✅ Your resource for {course_code} has been approved!\n\nYou can find resources by typing !CourseCode (example: !CSE421)"
            if file_type == 'photo':
                await context.bot.send_photo(chat_id=uploader_id, photo=file_id, caption=caption)
            else:
                await context.bot.send_document(chat_id=uploader_id, document=file_id, caption=caption)

        elif action == "reject":
            await query.edit_message_caption(f"❌ Rejected resource for {course_code} from {uploader_name}")

            caption = f"❌ Your resource for {course_code} was rejected by admin."
            if file_type == 'photo':
                await context.bot.send_photo(chat_id=uploader_id, photo=file_id, caption=caption)
            else:
                await context.bot.send_document(chat_id=uploader_id, document=file_id, caption=caption)

    elif data.startswith("request_delete"):
        _, resource_key = data.split("|")
        approved_data = load_json(APPROVED_FILE)

        if resource_key not in approved_data:
            await query.answer("This resource no longer exists.", show_alert=True)
            return

        resource_entry = approved_data[resource_key]
        user_states[query.from_user.id] = {
            'state': 'awaiting_delete_reason',
            'resource_entry': resource_entry,
            'resource_key': resource_key
        }
        await query.message.reply_text("📝 Please type the reason why you think this resource should be deleted:")

    elif data.startswith("delete_approve") or data.startswith("delete_reject"):
        parts = data.split("|")
        action, resource_key, requester_id = parts[0], parts[1], int(parts[2])

        approved_data = load_json(APPROVED_FILE)

        if resource_key not in approved_data:
            await query.answer("This resource no longer exists.", show_alert=True)
            return

        entry = approved_data[resource_key]
        course_code = entry['course_code']

        if action == "delete_approve":
            del approved_data[resource_key]
            save_json(approved_data, APPROVED_FILE)

            await query.edit_message_caption(f"✅ Resource for {course_code} deleted as per request.")

            caption = f"✅ Your delete request for {course_code} resource has been approved and removed."
            await context.bot.send_message(chat_id=requester_id, text=caption)

        elif action == "delete_reject":
            admin_delete_reject_states[ADMIN_ID] = {
                'requester_id': requester_id,
                'course_code': course_code
            }
            await query.message.reply_text("✏️ Please type the reason why you are rejecting the delete request:")

# ===== VERCEL WEBHOOK HANDLER =====
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update = Update.de_json(json.loads(post_data.decode('utf-8')), app.bot)
            app.update_queue.put(update)
            self.send_response(200)
        except Exception as e:
            print(f"Error processing update: {e}")
            self.send_response(500)
        finally:
            self.end_headers()

# ===== BOT INITIALIZATION =====
def setup_handlers():
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, receive_file))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Import and add other handlers
    from help import get_help_handler
    from lists import get_courselist_handler
    from admin import get_admin_handler
    
    app.add_handler(get_help_handler())
    app.add_handler(get_courselist_handler())
    app.add_handler(get_admin_handler())

app = Application.builder().token(TOKEN).build()
setup_handlers()

# ===== VERCEL ENTRY POINT =====
def handler(request):
    webhook_handler = WebhookHandler()
    webhook_handler.request = request
    webhook_handler.do_POST()
    return {'statusCode': 200}

# ===== LOCAL TESTING =====
if __name__ == '__main__':
    print("Bot running in polling mode...")
    app.run_polling()