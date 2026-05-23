import logging
import traceback
import asyncio
from fastapi import FastAPI, Request
import uvicorn
from telegram import Update, BotCommand 
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest 

# Import config variables
from config import (
    BOT_TOKEN, PAYMENT_ALERTS_GROUP_ID, 
    SUPPORT_BOT_TOKEN, SUPPORT_GROUP_ID,
    STATISTICS_GROUP_ID
)
from utils.db import (
    init_db, close_db, handle_payment_status, 
    get_user_payment_topic, set_user_payment_topic,
    expire_old_orders,
    get_admin_stats
)
from handlers.router import purchase_router, admin_router, control_panel_router

# Import support handlers directly from your support script
from support_bot import start as support_start, handle_user_message, handle_admin_reply
from handlers.start import start

# 1. Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# 2. FastAPI Setup
app = FastAPI()
telegram_app = None
support_app = None  # Track the support bot instance here

# 🎯 ASYNC CRASH ENGINE NATIVE TO THE APPLICATION CONTEXT
async def send_crash_alert(context_name: str, error: Exception):
    """Gathers errors across the bot framework and dispatches a live traceback notification inside Telegram."""
    import traceback
    
    # 🎯 FIX 1: Check for the Statistics Group instead of Payment Alerts
    if not STATISTICS_GROUP_ID or not telegram_app:
        return
        
    tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
    tb_text = "".join(tb_lines)
    
    if len(tb_text) > 3500:
        tb_text = tb_text[-3500:]
        
    error_message = (
        f"💥 <b>CRITICAL APPLICATION CRASH ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>Context:</b> <code>{context_name}</code>\n"
        f"🚨 <b>Reason:</b> <code>{str(error)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💻 <b>Stack Trace:</b>\n"
        f"<pre><code class='language-python'>{tb_text}</code></pre>"
    )
    
    try:
        await telegram_app.bot.send_message(
            chat_id=STATISTICS_GROUP_ID, # 🎯 FIX 2: Route directly to Statistics Group
            text=error_message,
            parse_mode="HTML"
        )
    except Exception as telegram_fail:
        print(f"🔥 Fail-safe alert mechanism collapsed: {telegram_fail}")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "🏠 Return to Main Menu")
    ])
    
async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    """Background task that runs every 30 mins to clean up dead invoices."""
    try:
        expired_list = expire_old_orders()
        if expired_list:
            print(f"🧹 Cleaned up {len(expired_list)} expired orders.")
        for order in expired_list:
            try:
                user_id = order['user_id']
                order_id = order['order_id']
                text = (
                    f"<b>⚠️ Invoice Expired</b>\n\n"
                    f"🚨 <i>Your deposit order <code>#{order_id}</code> has been cancelled because the 59-minute payment window closed.</i>\n\n"
                    f"To try again, please click 💰 <b>Credits</b> to generate a new invoice."
                )
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            except Exception as e:
                print(f"⚠️ Failed to send expiration notice to {user_id}: {e}")
    except Exception as background_error:
        await send_crash_alert("Background Task: check_expirations", background_error)

async def send_automated_stats(context: ContextTypes.DEFAULT_TYPE):
    """Gathers database metrics and logs them directly to your dedicated stats group chat."""
    if not STATISTICS_GROUP_ID:
        return
    try:
        total_users, total_revenue, active_esims, expired_esims = get_admin_stats()
        
        text = (
            "📊 <b>Automated Store Statistics Update</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n"
            f"💰 <b>Total Gross Revenue:</b> <code>${total_revenue:.2f}</code>\n\n"
            f"🟢 <b>Active eSIM Deliveries:</b> <code>{active_esims}</code>\n"
            f"🔴 <b>Expired/Dead Invoices:</b> <code>{expired_esims}</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>🤖 Next automated report scheduled in 12 hours.</i>"
        )
        await context.bot.send_message(
            chat_id=STATISTICS_GROUP_ID,
            text=text,
            parse_mode="HTML"
        )
        print("✅ Posted automated health metrics to the Statistics Group.")
    except Exception as stats_error:
        await send_crash_alert("Background Task: send_automated_stats", stats_error)

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Intercepts unexpected internal framework runtime crashes and alerts the team."""
    logging.error(msg="Exception occurred while handling an update:", exc_info=context.error)
    await send_crash_alert(f"Telegram Handler (Update Type: {type(update).__name__})", context.error)

@app.on_event("startup")
async def startup_event():
    """This runs when the server starts"""
    global telegram_app, support_app
    init_db()
    
    request_config = HTTPXRequest(connect_timeout=30, read_timeout=30)
    
    # --------------------------------------------------
    # 🤖 1. INITIALIZE MAIN ESIM BOT
    # --------------------------------------------------
    telegram_app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request_config)
        .post_init(post_init)
        .build()
    )
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(purchase_router)
    telegram_app.add_handler(admin_router)
    telegram_app.add_handler(control_panel_router)
    
    telegram_app.add_error_handler(global_error_handler)
    
    await telegram_app.initialize()
    telegram_app.job_queue.run_repeating(check_expirations, interval=1800, first=10)
    
    if STATISTICS_GROUP_ID:
        telegram_app.job_queue.run_repeating(send_automated_stats, interval=43200, first=15)
        
    await telegram_app.updater.start_polling()
    await telegram_app.start()
    print("🚀 Main eSIM Bot & FastAPI are live!")

    # --------------------------------------------------
    # 🛠️ 2. INITIALIZE SUPPORT RELAY BOT CONCURRENTLY
    # --------------------------------------------------
    if SUPPORT_BOT_TOKEN and SUPPORT_GROUP_ID:
        support_app = ApplicationBuilder().token(SUPPORT_BOT_TOKEN).request(request_config).build()
        
        support_app.add_handler(CommandHandler("start", support_start))
        support_app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
        support_app.add_handler(MessageHandler(filters.Chat(SUPPORT_GROUP_ID), handle_admin_reply))
        
        support_app.add_error_handler(global_error_handler)
        
        await support_app.initialize()
        await support_app.updater.start_polling()
        await support_app.start()
        print("📬 Support Relay Bot is live on the same container process!")

@app.on_event("shutdown")
async def shutdown_event():
    """This runs when the server stops"""
    global telegram_app, support_app
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.updater.stop()
        await telegram_app.shutdown()
    if support_app:
        await support_app.stop()
        await support_app.updater.stop()
        await support_app.shutdown()
    close_db()

@app.post("/plisio/webhook")
async def plisio_webhook(request: Request):
    try:
        # 🎯 FIX 1: Read both JSON and Form payloads properly
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)

        # Extract safely regardless of Plisio's naming conventions
        order_id = payload.get("order_number") or payload.get("orderNumber") or payload.get("order_id")
        status = payload.get("status") or payload.get("state")

        if not order_id:
            print(f"⚠️ Webhook Ignored: No order ID found in payload.")
            return {"status": "ignored"}

        should_alert, user_id, amount, currency, coin_amount = handle_payment_status(order_id, status)

        if should_alert and telegram_app:
            user_text = f"⚡ <b>Payment Detected!</b>\n<b>${amount:.2f}</b> Added to balance. Click 💰 <b>Credits</b> menu to check balance."
            await telegram_app.bot.send_message(chat_id=user_id, text=user_text, parse_mode="HTML")

            if PAYMENT_ALERTS_GROUP_ID:
                topic_id = get_user_payment_topic(user_id)
                if not topic_id:
                    user_info = await telegram_app.bot.get_chat(user_id)
                    title = f"👤 {user_info.username or user_id}"
                    topic = await telegram_app.bot.create_forum_topic(chat_id=PAYMENT_ALERTS_GROUP_ID, name=title)
                    topic_id = topic.message_thread_id
                    set_user_payment_topic(user_id, topic_id)

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
    except Exception as webhook_error:
        print("❌ WEBHOOK CRASHED:")
        traceback.print_exc()
        await send_crash_alert("FastAPI Endpoint: /plisio/webhook", webhook_error)
        return {"status": "error", "message": str(webhook_error)}
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)