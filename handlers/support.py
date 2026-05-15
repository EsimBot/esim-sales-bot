# handlers/support.py
from telegram import Update
from telegram.ext import ContextTypes
from menus.main_menu import support_link_menu

async def handle_support_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛠️ <b>Support Center</b>\n\n"
        "To keep our service fast, all support chats are handled in our dedicated support bot.\n\n"
        "Click below to start your private conversation:"
    )
    
    await update.message.reply_text(
        text=text, 
        reply_markup=support_link_menu(), 
        parse_mode="HTML"
    )