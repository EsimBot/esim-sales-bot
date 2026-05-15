import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import SUPPORT_BOT_TOKEN, SUPPORT_GROUP_ID
from utils.db import init_db, get_support_topic, set_support_topic, get_user_by_topic

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent greeting for the support bot."""
    text = (
        "👋 <b>Support Center</b>\n\n"
        "Simply type your message or send a photo here. "
        "Our team will respond directly in this chat as soon as we are available."
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relays message from User -> Admin Topic."""
    user_id = update.effective_user.id
    username = update.effective_user.username or user_id
    
    topic_id = get_support_topic(user_id)
    
    if not topic_id:
        # Create new topic in admin group
        topic = await context.bot.create_forum_topic(
            chat_id=SUPPORT_GROUP_ID,
            name=f"🆘 {username}"
        )
        topic_id = topic.message_thread_id
        set_support_topic(user_id, topic_id)
        
        await context.bot.send_message(
            chat_id=SUPPORT_GROUP_ID,
            message_thread_id=topic_id,
            text=f"🆕 <b>New Support Thread</b>\nUser: <code>{user_id}</code>\n@{username}",
            parse_mode="HTML"
        )

    # 🎯 RELAY: Copy the message to the admin topic
    await update.message.copy(
        chat_id=SUPPORT_GROUP_ID,
        message_thread_id=topic_id
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relays message from Admin Topic -> User DM."""
    if update.effective_chat.id != SUPPORT_GROUP_ID or not update.message.message_thread_id:
        return

    user_id = get_user_by_topic(update.message.message_thread_id)
    
    if user_id:
        try:
            # 🎯 RELAY: Copy admin's reply back to the user
            await update.message.copy(chat_id=user_id)
        except Exception as e:
            logging.error(f"Failed to deliver reply to {user_id}: {e}")

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(SUPPORT_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    
    # 1. User messaging the bot in private
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    
    # 2. Admin replying in the support group topic
    app.add_handler(MessageHandler(filters.Chat(SUPPORT_GROUP_ID), handle_admin_reply))

    print("🚀 Support Relay Bot is running...")
    app.run_polling()