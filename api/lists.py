# lists.py

import json
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

APPROVED_FILE = 'approved.json'

def load_json(filename):
    with open(filename, 'r') as f:
        return json.load(f)

async def courselist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    approved_data = load_json(APPROVED_FILE)

    # Collect all course codes from approved resources
    course_codes = set()
    for entry in approved_data.values():
        if 'course_code' in entry:
            course_codes.add(entry['course_code'])

    if not course_codes:
        await update.message.reply_text(
            "No courses with resources available yet.\n\n"
            "You can add one using /upload 🚀"
        )
        return

    # Sort the course list alphabetically
    sorted_courses = sorted(course_codes)

    course_list_text = "\n".join(f"- {code}" for code in sorted_courses)
    footer = (
        "\n\nAvailable courses list with resources.\n\n"
        "➡️ Type /upload or /help to add another course here with resources.\n"
        "➡️ Type !CourseCode (e.g. !CSE421) or /help to access the materials."
    )

    final_text = f"📚 *Available Courses with Resources:*\n\n{course_list_text}{footer}"
    await update.message.reply_text(final_text, parse_mode='Markdown')

def get_courselist_handler():
    return CommandHandler("courselist", courselist)
