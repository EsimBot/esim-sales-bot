from telegram import Update
from telegram.ext import ContextTypes
from menus.main_menu import main_menu_keyboard
from utils.db import add_user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username)

    # We use <b> for bold and <code> for that 'copyable' look on the ID
    welcome_text = (
        f"👋 <b>Welcome to the eSIM Store User {user.id}, Get high-speed digital SIMs instantly. </b>\n\n"
        f"<i>Pay Using Crypto Currency Anonymously</i>\n\n"
        
        f"Choose an option from the menu below to start."
    )

    await update.message.reply_text(
        text=welcome_text,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"  # <--- Make sure this says HTML
    )
    
    