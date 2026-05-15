from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.states import INTERCEPTING, WAITING_FOR_PAYMENT
from utils.db import force_cancel_order, get_connection

async def show_interceptor_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, pending_order, next_action):
    """Displays the Action Required screen with a live countdown calculation."""
    o_type, order_id, amount, sec_left = pending_order
    
    # Format the remaining seconds into MM:SS
    mins, secs = divmod(int(sec_left), 60)
    time_str = f"{mins}m {secs}s"
    
    text = (
        f"⏳ <b>Action Required: Pending Order Found</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧾 <b>Order Number:</b> <code>#{order_id}</code>\n"
        f"💰 <b>Amount:</b> ${float(amount):.2f}\n"
        f"⏳ <b>Remaining Time:</b> {time_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>You must finish your current payment or cancel it before starting a new transaction.</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Continue Order", callback_data=f"resume_{o_type}_{order_id}")],
        [InlineKeyboardButton("❌ Cancel & Start New", callback_data=f"forcecancel_{o_type}_{order_id}_{next_action}")]
    ]
    
    markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
        
    return INTERCEPTING

async def handle_interceptor_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the button click from the Interceptor screen."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action, o_type, order_id = parts[0], parts[1], parts[2]
    
    if action == "forcecancel":
        next_action = parts[3]
        force_cancel_order(order_id, o_type)
        
        # Teleport user directly to what they originally requested
        if next_action == "buyesim":
            from handlers.esim_flow import handle_buy_esim
            return await handle_buy_esim(update, context)
        elif next_action == "topup":
            from handlers.wallet_flow import start_topup
            return await start_topup(update, context)

    elif action == "resume":
        if o_type == "wallet":
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT amount, coin_amount, currency, invoice_url FROM transactions WHERE order_id = %s", 
                        (str(order_id),)
                    )
                    row = cur.fetchone()
            
            if row and row[3]:
                amount, coin_amount, currency, invoice_url = row
                text = (
                    f"✅ <b>Invoice Resumed!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🧾 <b>Order ID:</b> <code>{order_id}</code>\n"
                    f"💰 <b>Amount:</b> ${float(amount):.2f}\n"
                    f"🪙 <b>Amount in {currency}:</b> <code>{coin_amount}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Please complete your payment below.</i>"
                )
                
                keyboard = [
                    [InlineKeyboardButton("💳 Pay Now", url=invoice_url)],
                    [InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_pay_{order_id}")]
                ]
                
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
                return WAITING_FOR_PAYMENT
            else:
                await query.edit_message_text("⚠️ Cannot locate the payment link for this old order. Please click 'Cancel & Start New'.")
                return INTERCEPTING