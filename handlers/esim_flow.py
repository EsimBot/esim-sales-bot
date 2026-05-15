import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from menus.catalog_menus import region_menu, plan_menu
from menus.main_menu import main_menu_keyboard
from handlers.interceptor import show_interceptor_screen
from config import PENDING_GROUP_ID,CHECK_ACTIVATION
from utils.db import (
    get_user_balance, 
    is_order_id_unique, 
    create_order_record, 
    deduct_user_balance,
    check_and_get_pending_order,
    is_user_activated
)

# 🛑 UNIVERSAL STATE MAP - MATCHING YOUR CODE
(
    SELECTING_REGION, 
    SELECTING_PLAN, 
    DEPOSITING, 
    ENTERING_AMOUNT, 
    CHOOSING_COIN, 
    CONFIRMING_ORDER,
    WAITING_FOR_PAYMENT,
    INTERCEPTING,
    SELECT_RENEWAL_TYPE
) = range(9)


USA_PLANS = {
    "plan_1m": {"name": "1 Month",  "price": 18.99},
    "plan_2m": {"name": "2 Months", "price": 37.99},
    "plan_3m": {"name": "3 Months", "price": 57.99},
    "plan_4m": {"name": "4 Months", "price": 75.99},
    "plan_5m": {"name": "5 Months", "price": 94.99},
    "plan_6m": {"name": "6 Months", "price": 114.99},
    "plan_1y": {"name": "1 Year",   "price": 227.99}
}

async def handle_buy_esim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending = check_and_get_pending_order(user_id)
    if pending:
        return await show_interceptor_screen(update, context, pending, next_action="buyesim")
    
    # 🎯 2. NEW: Check if user is activated (has ever topped up)
    if CHECK_ACTIVATION and not is_user_activated(user_id):
        text = (
            "👋 <b>First-Time Activation Required</b>\n\n"
            "To activate your account, please make your first deposit of at least <b>$6.00</b>.\n\n"
            "✨ <b>Why?</b>\n"
            "This is a one-time requirement to verify your account. "
            "The money will be <b>added to your balance</b> immediately and can be used to buy any eSIM!\n\n"
            "<i>Note: Once you top up once, you will never see this message again.</i>"
        )
        btns = [[
            InlineKeyboardButton("💎 Activate & Top Up Now", callback_data="view_wallet"),
        ]]
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
        # We don't return SELECTING_REGION here, so they stay on this screen
        return ConversationHandler.END

    await update.message.reply_text(
        "🌍 <b>Select Region</b>\nChoose the area for your eSIM:",
        reply_markup=region_menu(),
        parse_mode="HTML"
    )
    return SELECTING_REGION

async def handle_usa_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User clicked the 'region_usa' button"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['selected_region'] = 'usa'
    
    text = (
        "<b>🇺🇸 USA eSIM Configuration</b>\n\n"
        "Please choose your plan type:\n\n"
        "• <b>🔄 Renewable:</b> Can be Renewed / extended Once Expired.\n"
        "• <b>🚫 Non-Renewable:</b> Cannot Renew eSIM Once Plans End.\n\n"
        "<i>💰 Note: Renewable plans have an additional $2.00 fee.</i>"
    )
    
    await query.edit_message_text(
        text=text,
        reply_markup=renewal_type_keyboard(),
        parse_mode="HTML"
    )
    return SELECT_RENEWAL_TYPE

def renewal_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔄 Renewable (+$2)", callback_data="renewal_true"),
            InlineKeyboardButton("🚫 Non-Renewable", callback_data="renewal_false")
        ],
        [InlineKeyboardButton("⬅️ Back to Regions", callback_data="back_to_regions")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_renewal_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Save the renewal choice
    context.user_data['is_renewable'] = (query.data == "renewal_true")
    
    await query.edit_message_text(
        text="📅 <b>Select Plan Duration:</b>\n\nChoose your preferred time period:",
        reply_markup=plan_menu(),
        parse_mode="HTML"
    )
    return SELECTING_PLAN


async def handle_plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    balance = get_user_balance(user_id) or 0.0

    # 🎯 1. Calculate the $2.00 Renewable Fee
    is_renewable = context.user_data.get('is_renewable', False)
    renewal_fee = 2.00 if is_renewable else 0.00
    
    plan_key = query.data 
    
    # 🎯 2. Get the plan details (Fixes KeyError: 'price')
    plan = USA_PLANS.get(plan_key, USA_PLANS["plan_1m"])
    
    # 🎯 3. Calculate the Total Price
    base_price = plan["price"]
    total_price = base_price + renewal_fee
    duration = plan["name"]

    # Generate unique Order ID
    while True:
        order_id = random.randint(10000000, 99999999)
        if is_order_id_unique(order_id): break
    
    context.user_data['pending_order'] = {
        'order_id': order_id, 
        'price': total_price, 
        'region': "USA", 
        'duration': duration,
        'is_renewable': is_renewable
    }

    # Visual Labels
    type_label = "Renewable." if is_renewable else "NonRenewable."
    type_icon = "🔄" if is_renewable else "🚫"

    # 🗺️ THE VISUAL ORDER MAP
    summary_text = (
        f"🗺️ <b>Order Confirmation</b>\n"
        f"<code>┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓</code>\n"
        f"<code>┃ ID    : #{order_id:<18}┃</code>\n"
        f"<code>┃ Region   : USA               ┃</code>\n"
        f"<code>┃ Type  : {type_icon} {type_label:<18}┃</code>\n"
        f"<code>┃ Duration : {duration:<18}┃</code>\n"
        f"<code>┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛</code>\n\n"
        f"💰 <b>Total Due:</b> ${total_price:.2f}\n\n"
        f"💳 <b>Wallet Balance:</b> ${balance:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )

    if balance >= total_price:
        summary_text += "✨ <b>Ready to activate?</b>"
        btns = [[InlineKeyboardButton("✅ Confirm Purchase", callback_data="confirm_final")],
                [InlineKeyboardButton("⬅️ Change Plan", callback_data="back_to_regions")]]
    else:
        diff = total_price - balance
        summary_text += f"⚠️ <b>Shortfall:</b> ${diff:.2f}\n<i>Insufficient funds.</i>"
        btns = [[InlineKeyboardButton("💎 Quick Top Up", callback_data="view_wallet")],
                [InlineKeyboardButton("❌ Cancel", callback_data="back_to_main")]]

    await query.edit_message_text(summary_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
    return CONFIRMING_ORDER

async def handle_final_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    order = context.user_data.get('pending_order')

    if not order:
        await query.edit_message_text("❌ Error: Order session expired. Please start over.")
        return ConversationHandler.END

    try:
        # 🎯 1. Save to DB with Renewable Boolean
        create_order_record(
            order['order_id'], 
            user_id, 
            order['price'], 
            order['region'], 
            order['duration'],
            order['is_renewable'] # Ensure your DB function handles this!
        )
        deduct_user_balance(user_id, order['price'])

        renewal_status = "🔄 RENEWABLE" if order['is_renewable'] else "🚫 NON-RENEWABLE"

        # 2. User Success UI
        success_text = (
            f"🥳 <b>Purchase Successful!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🧾 <b>Order ID:</b> <code>{order['order_id']}</code>\n"
            f"📦 <b>Item:</b> {order['region']} ({order['duration']})\n"
            f"⚙️ <b>Type:</b> {renewal_status}\n"
            f"💰 <b>Paid:</b> ${order['price']:.2f}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📥 Your eSIM QR code will be sent here in 1-2 hours\n\n"
            f"📥 <b>Do Not Reach Out To Support Until 24 Hours And Esim Did Not Arrive\n</b>"
        )
        await query.edit_message_text(success_text, parse_mode="HTML")

        # 🎯 3. ADMIN ALERT WITH RENEWAL INFO
        if PENDING_GROUP_ID:
            try:
                topic = await context.bot.create_forum_topic(
                    chat_id=PENDING_GROUP_ID,
                    name=f"#{order['order_id']} | {renewal_status}"
                )
                
                admin_text = (
                    f"🚨 <b>NEW ORDER PENDING</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                    f"🧾 <b>Order ID:</b> <code>{order['order_id']}</code>\n"
                    f"📦 <b>Plan:</b> {order['region']} ({order['duration']})\n"
                    f"⚙️ <b>Type:</b> {renewal_status}\n"
                    f"💰 <b>Paid:</b> ${order['price']:.2f}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<i>Click below to fulfill the eSIM details.</i>"
                )
                
                admin_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚀 Fulfill Order", callback_data=f"fulfill_{order['order_id']}")
                ]])
                
                await context.bot.send_message(
                    chat_id=PENDING_GROUP_ID,
                    message_thread_id=topic.message_thread_id,
                    text=admin_text,
                    reply_markup=admin_markup,
                    parse_mode="HTML"
                )
            except Exception as admin_e:
                print(f"⚠️ Admin Alert Error: {admin_e}")
        
    except Exception as e:
        print(f"❌ Purchase Error: {e}")
        await query.edit_message_text("⚠️ Processing error. Contact support.")

    return ConversationHandler.END

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.delete_message()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Back to main menu.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END