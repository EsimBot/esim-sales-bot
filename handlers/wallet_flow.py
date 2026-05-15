from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils.db import get_user_balance
from menus.catalog_menus import crypto_menu
from utils.plisio_api import create_plisio_invoice
import random
from handlers.esim_flow import back_to_main
from handlers.interceptor import show_interceptor_screen
from utils.db import log_new_transaction,get_transaction_history,cancel_transaction,check_and_get_pending_order

from handlers.states import (
    DEPOSITING, 
    ENTERING_AMOUNT, 
    CHOOSING_COIN, 
    WAITING_FOR_PAYMENT
)



async def handle_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The Hub: Handles both text commands and button clicks"""
    # 1. Detect if this is a button click or a text message
    query = update.callback_query
    if query:
        await query.answer()
        user_id = update.effective_user.id
    else:
        user_id = update.effective_user.id

    balance = get_user_balance(user_id)
    history = get_transaction_history(user_id, limit=5)
    
    # ... (History formatting logic remains exactly the same as before) ...
    history_text = ""
    if not history:
        history_text = "<i>No recent transactions.</i>"
    else:
        for row in history:
            date, oid, status, amt = row
            status_icon = "✅" if status == ['completed', 'mempool_credited'] else "⏳" if status == 'pending' else "❌"
            history_text += f"• {date} | {oid} | {status_icon} ${amt:.2f}\n"

    text = (
        f"💳 <b>Your Wallet</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Balance:</b> ${balance:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>Last 5 Transactions:</b>\n"
        f"{history_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Select an option below:"
    )
    
    btns = [[
        InlineKeyboardButton("💎 Top Up", callback_data="start_topup"),
        InlineKeyboardButton("❌ Cancel", callback_data="back_to_main")
    ]]
    markup = InlineKeyboardMarkup(btns)

    # 2. Respond correctly based on the trigger
    if query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
        
    return DEPOSITING


async def start_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    # 🛡️ THE GATEKEEPER: Check for unpaid orders first
    pending = check_and_get_pending_order(user_id)
    if pending:
        # If found, trap them in the INTERCEPTING state
        return await show_interceptor_screen(update, context, pending, next_action="topup")

    # If clean, proceed to the normal amount entry
    await query.answer()
    await query.edit_message_text("📝 <b>Top Up</b>\n\n Minimum: <b>$6.00</b>\nEnter amount (USD):", parse_mode="HTML")
    return ENTERING_AMOUNT

async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount < 6.0:
            await update.message.reply_text("❌ Minimum deposit is $6.")
            return ENTERING_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ENTERING_AMOUNT

    context.user_data['deposit_amount'] = amount
    await update.message.reply_text(f"✅ <b>Amount You Entered is :</b> ${amount:.2f}\nSelect your cryptocurrency for payment:", reply_markup=crypto_menu(), parse_mode="HTML")
    return CHOOSING_COIN


async def process_crypto_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🎯 BTC Button Clicked!")
    query = update.callback_query
    
    coin = query.data.replace("pay_", "").upper()
    amount = context.user_data.get('deposit_amount')

    if amount is None:
        await query.answer("⚠️ Session expired. Please start over.", show_alert=True)
        return ConversationHandler.END

    if coin == "USDT_ERC20" and amount < 12.0:
        await query.answer("❌ ERC-20 Minimum is $12.00.", show_alert=True)
        return CHOOSING_COIN

    await query.answer()
    
    order_id = random.randint(10000000, 99999999)
    await query.edit_message_text(f"🔄 <b>Generating {coin} Invoice... Please Wait</b>", parse_mode="HTML")

    invoice_url, coin_amount = await create_plisio_invoice(
        amount, 
        coin, 
        order_id, 
        update.effective_user.id
    )

    if invoice_url:
        log_new_transaction(order_id, update.effective_user.id, amount, coin_amount, coin,invoice_url)

        text = (
            f"✅ <b>Invoice Ready!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🧾 <b>Order ID:</b> <code>{order_id}</code>\n"
            f"💰 <b>Amount:</b> ${amount:.2f}\n"
            f"🪙 <b>Amount in {coin}:</b> <code>{coin_amount}</code>\n"
            f"🔗 <b>Currency:</b> {coin}\n"
            f"⏳ <b>Expires in:</b> 59:00 minutes\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Note: If you do not pay within 59 minutes, this invoice will be canceled.</b>"
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Pay Now", url=invoice_url)],
            [InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_pay_{order_id}")]
        ]
        
        await query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="HTML"
        )
        
        # 🎯 THE FIX: Return here so it triggers on SUCCESS
        print(f"✅ Success: Moving to WAITING_FOR_PAYMENT (ID: {WAITING_FOR_PAYMENT})")
        return WAITING_FOR_PAYMENT

    else:
        await query.edit_message_text(
            "⚠️ <b>Error:</b> Payment gateway rejected the request.\n"
            "Please try a different coin or contact support.", 
            parse_mode="HTML"
        )
        # 🎯 If it fails, we stay in CHOOSING_COIN so they can try another button
        return CHOOSING_COIN


async def show_usdt_networks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the USDT Network options and the $12 warning."""
    query = update.callback_query
    await query.answer()
    
    amount = context.user_data.get('deposit_amount')
    
    # 🎯 SAFETY CHECK: If amount is missing, stop the flow
    if amount is None:
        await query.answer("⚠️ Session expired. Please enter the amount again.", show_alert=True)
        return ConversationHandler.END
    
    text = (
        f"🟢 <b>Select USDT Network</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Your Entered Deposit:</b> ${amount:.2f}\n\n"
        f"⚠️ <b>Network Rules:</b>\n"
        f"• <b>TRC-20 (Tron):</b> $6.00 Minimum\n"
        f"• <b>ERC-20 (Ethereum):</b> $12.00 Minimum\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    keyboard = [
        [InlineKeyboardButton("Tron (TRC-20)", callback_data="pay_usdt_trc20")],
        [InlineKeyboardButton("Ethereum (ERC-20)", callback_data="pay_usdt_erc20")],
        [InlineKeyboardButton("🔙 Back to Coins", callback_data="back_to_coins")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return CHOOSING_COIN

async def back_to_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns the user to the main crypto selection menu."""
    query = update.callback_query
    await query.answer()
    amount = context.user_data.get('deposit_amount')
    
    # 🎯 SAFETY CHECK: If amount is missing, stop the flow
    if amount is None:
        await query.answer("⚠️ Session expired. Please enter the amount again.", show_alert=True)
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"✅ <b>Amount Set:</b> ${amount:.2f}\n\nSelect your cryptocurrency for payment:",
        reply_markup=crypto_menu(),
        parse_mode="HTML"
    )
    return CHOOSING_COIN



async def handle_cancel_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Extract the ID from the callback data (e.g., 'cancel_pay_12345678')
    order_id = query.data.split("_")[2]
    
    # 1. Update the Database
    cancel_transaction(order_id)
    
    # 2. Alert the user
    await query.answer("🚫 Payment top up has been canceled\n click top up to create a new topup", show_alert=False)
    
    # 3. Send them to the Main Menu
    await back_to_main(update, context)
    return ConversationHandler.END