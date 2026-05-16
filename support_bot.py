import logging
import traceback
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
    """Relays message from User -> Admin Topic with automatic self-healing for deleted topics."""
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    
    print(f"📥 [Support Bot] Received a message from {user_id} (@{username})")
    
    try:
        topic_id = get_support_topic(user_id)
        
        # 🛡️ SELF-HEALING: If we have a saved topic ID, try to send to it
        if topic_id:
            try:
                await update.message.copy(
                    chat_id=SUPPORT_GROUP_ID,
                    message_thread_id=topic_id
                )
                print(f"✅ Message successfully relayed to existing topic: {topic_id}")
                return
            except Exception as copy_error:
                print(f"⚠️ Stored topic {topic_id} is dead or was deleted ({copy_error}). Clearing and generating a fresh one...")
                topic_id = None # Force the creation loop below to run

        # 🆕 CREATION FLOW: Run this if no topic exists or if the old one was deleted
        if not topic_id:
            print(f"🆕 Creating a brand new forum topic for @{username} in group {SUPPORT_GROUP_ID}...")
            topic = await context.bot.create_forum_topic(
                chat_id=SUPPORT_GROUP_ID,
                name=f"💬 {username}"
            )
            topic_id = topic.message_thread_id
            set_support_topic(user_id, topic_id)
            
            # Send initial context card to the group topic
            await context.bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                message_thread_id=topic_id,
                text=f"📬 <b>New Support Thread Opened</b>\n━━━━━━━━━━━━━━━━━━\n👤 <b>User:</b> @{username}\n🆔 <b>ID:</b> <code>{user_id}</code>\n━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML"
            )
            
            # Copy their message into the newly constructed topic
            await update.message.copy(
                chat_id=SUPPORT_GROUP_ID,
                message_thread_id=topic_id
            )
            print(f"✅ Message successfully relayed to new topic: {topic_id}")

    except Exception as e:
        print(f"❌ CRITICAL SUPPORT RELAY FAILURE: {e}")
        traceback.print_exc()

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Relays message from Admin Topic -> User DM."""
    if update.effective_chat.id != SUPPORT_GROUP_ID or not update.message.message_thread_id:
        return

    user_id = get_user_by_topic(update.message.message_thread_id)
    
    if user_id:
        try:
            await update.message.copy(chat_id=user_id)
            print(f"📤 Relayed admin reply back to user {user_id}")
        except Exception as e:
            logging.error(f"Failed to deliver reply to {user_id}: {e}")

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(SUPPORT_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    
    # 🎯 FIXED FILTER TYPE
    app.add_handler(MessageHandler(filters.Chat.PRIVATE & ~filters.COMMAND, handle_user_message))
    app.add_handler(MessageHandler(filters.Chat(SUPPORT_GROUP_ID), handle_admin_reply))

    print("📬 Support Relay Bot is running...")
    app.run_polling()