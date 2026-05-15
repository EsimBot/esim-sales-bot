import logging
import traceback
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from telegram import Update
from telegram import BotCommand 
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters,ContextTypes
from telegram.request import HTTPXRequest 

from config import BOT_TOKEN,PAYMENT_ALERTS_GROUP_ID
from utils.db import (
    init_db, close_db, handle_payment_status, 
    get_user_payment_topic, set_user_payment_topic,
    expire_old_orders
)
from handlers.start import start
from handlers.router import purchase_router,admin_router

# 1. Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 2. FastAPI Setup
app = FastAPI()
telegram_app = None

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "🏠 Return to Main Menu")
    ])
    
    
async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    """Background task that runs every 30 mins to clean up dead invoices."""
    expired_list = expire_old_orders()
    
    if expired_list:
        print(f"🧹 Cleaned up {len(expired_list)} expired orders.")
        
    for order in expired_list:
        try:
            user_id = order['user_id']
            order_id = order['order_id']
            
            # The updated formatted text
            text = (
                f"<b>⚠️ Invoice Expired</b>\n\n"
                f"🚨 <i>Your deposit order <code>#{order_id}</code> has been cancelled because the 59-minute payment window closed.</i>\n\n"
                f"To try again, please click 💰 <b>Credits</b> to generate a new invoice."
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML" # 🎯 Make sure this is set to HTML!
            )
        except Exception as e:
            print(f"⚠️ Failed to send expiration notice to {user_id}: {e}")

@app.on_event("startup")
async def startup_event():
    """This runs when the server starts"""
    global telegram_app
    init_db()
    
    # Configure Bot
    request_config = HTTPXRequest(connect_timeout=30, read_timeout=30)
    telegram_app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request_config)
        .post_init(post_init)
        .build()
    )

    # Register Handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(purchase_router)
    telegram_app.add_handler(admin_router)

    # Initialize and start the bot in the background
    await telegram_app.initialize()
    telegram_app.job_queue.run_repeating(check_expirations, interval=1800, first=10)
    await telegram_app.updater.start_polling()
    await telegram_app.start()
    print("🚀 Bot & FastAPI are live on Railway!")

@app.on_event("shutdown")
async def shutdown_event():
    """This runs when the server stops"""
    await telegram_app.stop()
    await telegram_app.updater.stop()
    await telegram_app.shutdown()
    close_db()

@app.post("/plisio/webhook")
async def plisio_webhook(request: Request):
    try:
        form_data = await request.form()
        order_id = form_data.get("order_number")
        status = form_data.get("status")

        # 🎯 1. Receive the new data from the DB
        should_alert, user_id, amount, currency, coin_amount = handle_payment_status(order_id, status)

        if should_alert and telegram_app:
            
            # --- 🎯 THE NEW USER ALERT ---
            user_text = f"⚡ <b>Payment Detected!</b>\n<b>${amount:.2f}</b> Added to balance. Click 💰 <b>Credits</b> menu to check balance."
            await telegram_app.bot.send_message(chat_id=user_id, text=user_text, parse_mode="HTML")

            # --- ADMIN ALERT ---
            if PAYMENT_ALERTS_GROUP_ID:
                topic_id = get_user_payment_topic(user_id)
                
                if not topic_id:
                    user_info = await telegram_app.bot.get_chat(user_id)
                    title = f"👤 {user_info.username or user_id}"
                    
                    topic = await telegram_app.bot.create_forum_topic(
                        chat_id=PAYMENT_ALERTS_GROUP_ID,
                        name=title
                    )
                    topic_id = topic.message_thread_id
                    set_user_payment_topic(user_id, topic_id)

                # --- 🎯 THE NEW ADMIN ALERT ---
                admin_text = (
                    f"💰 <b>DEPOSIT DETECTED</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> <code>{user_id}</code>\n"
                    f"🧾 <b>Order:</b> <code>#{order_id}</code>\n"
                    f"💵 <b>Amount:</b> ${amount:.2f}\n"
                    f"🪙 <b>Amount in {currency}:</b> <code>{coin_amount}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━"
                )
                await telegram_app.bot.send_message(
                    chat_id=PAYMENT_ALERTS_GROUP_ID,
                    message_thread_id=topic_id,
                    text=admin_text,
                    parse_mode="HTML"
                )

    except Exception as e:
        print("❌ WEBHOOK CRASHED:")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

    return {"status": "ok"}

if __name__ == "__main__":
    # For local testing
    uvicorn.run(app, host="0.0.0.0", port=5000)