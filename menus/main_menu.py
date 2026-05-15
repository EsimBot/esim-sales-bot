from telegram import ReplyKeyboardMarkup, KeyboardButton,InlineKeyboardButton,InlineKeyboardMarkup
from config import SUPPORT_BOT_URL

def main_menu_keyboard():
    # We group them: 2 buttons in the first list, 2 in the second.
    keyboard = [
        [KeyboardButton("🌍 Buy eSIM"), KeyboardButton("💰 Credits")],
        [KeyboardButton("📊 My Orders"), KeyboardButton("🛠️ Support")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def support_link_menu():
    """The link that sends users to your second bot"""
    # 🎯 REPLACE '@YourSupportBotName' with your new bot's username!
    keyboard = [[InlineKeyboardButton("💬 Start Chatting with Support", url=SUPPORT_BOT_URL)]]
    return InlineKeyboardMarkup(keyboard)


