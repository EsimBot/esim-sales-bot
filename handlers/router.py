from telegram.ext import (
    MessageHandler, 
    filters, 
    ConversationHandler, 
    CommandHandler, 
    CallbackQueryHandler
)

# Core Flow Imports
from handlers.esim_flow import (
    handle_buy_esim, handle_usa_selected, 
    handle_plan_selected, handle_final_purchase, back_to_main,
    handle_renewal_selection
)
from handlers.wallet_flow import (
    handle_wallet, start_topup, 
    receive_amount, process_crypto_payment,
    show_usdt_networks, back_to_coins,
    handle_cancel_payment
)

from handlers.orders_flow import handle_my_orders, handle_orders_pagination
from handlers.interceptor import handle_interceptor_decision
from handlers.support import handle_support_click

# Fulfillment Imports
from handlers.admin_fulfillment import (
    start_fulfill, receive_smdp, receive_activation, receive_qr, confirm_delivery, cancel_wizard
)

# 🎯 The missing imports for the Admin Panel
from handlers.admin_panel import (
    start_admin_panel, handle_check_stats, start_message_user,
    receive_message_user_id, receive_message_text, start_broadcast,
    receive_broadcast_text, confirm_broadcast,clean_blocked_users,exit_admin
)

# All States
from handlers.states import (
    SELECTING_REGION, SELECTING_PLAN, DEPOSITING, 
    ENTERING_AMOUNT, CHOOSING_COIN, CONFIRMING_ORDER, 
    WAITING_FOR_PAYMENT, INTERCEPTING, SELECT_RENEWAL_TYPE,
    ADMIN_SMDP, ADMIN_ACTIVATION, ADMIN_QR, ADMIN_CONFIRM,
    ADMIN_PANEL_MAIN, ADMIN_MSG_USER_ID, ADMIN_MSG_TEXT,
    ADMIN_BROADCAST_INPUT, ADMIN_BROADCAST_CONFIRM
)

async def debug_fallback(update, context):
    query = update.callback_query
    current_state = context.user_data.get('state') 
    print(f"👻 Ignored Click: {query.data} | Bot is in State: {current_state}")
    await query.answer("This button is not active right now.", show_alert=False)
    return None 

# ----------------------------------------
# 1. MAIN PURCHASE & WALLET ROUTER
# ----------------------------------------
purchase_router = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^🌍 Buy eSIM$"), handle_buy_esim),
        MessageHandler(filters.Regex("^💰 Credits$"), handle_wallet),
        MessageHandler(filters.Regex("^📊 My Orders$"), handle_my_orders),
        MessageHandler(filters.Regex("^🛠️ Support$"), handle_support_click),
        CallbackQueryHandler(handle_wallet, pattern="^view_wallet$"),
        CallbackQueryHandler(handle_orders_pagination, pattern="^orders_page_"),
    ],
    states={
        SELECTING_REGION: [
            CallbackQueryHandler(handle_usa_selected, pattern="^region_usa$"),
            CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
        ],
        SELECTING_PLAN: [
            CallbackQueryHandler(handle_plan_selected, pattern="^plan_"),
            CallbackQueryHandler(handle_buy_esim, pattern="^back_to_regions$")
        ],
        SELECT_RENEWAL_TYPE: [
            CallbackQueryHandler(handle_renewal_selection, pattern="^renewal_"),
            CallbackQueryHandler(handle_renewal_selection, pattern="^back_to_regions$")
        ],
        DEPOSITING: [
            CallbackQueryHandler(start_topup, pattern="^start_topup$"),
            CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
        ],
        ENTERING_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)
        ],
        CHOOSING_COIN: [
            CallbackQueryHandler(show_usdt_networks, pattern="^show_usdt_networks$"),
            CallbackQueryHandler(back_to_coins, pattern="^back_to_coins$"),
            CallbackQueryHandler(process_crypto_payment, pattern="^pay_"), 
            CallbackQueryHandler(start_topup, pattern="^start_topup$"),
            CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
        ],
        CONFIRMING_ORDER: [
            CallbackQueryHandler(handle_final_purchase, pattern="^confirm_final$"),
            CallbackQueryHandler(start_topup, pattern="^start_topup$"), 
            CallbackQueryHandler(handle_wallet, pattern="^view_wallet$"),
            CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
        ],
        WAITING_FOR_PAYMENT: [
            CallbackQueryHandler(handle_cancel_payment, pattern="^cancel_pay_"),
            CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
        ],
        INTERCEPTING: [
            CallbackQueryHandler(handle_interceptor_decision, pattern="^(resume|forcecancel)_")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", back_to_main),
        CallbackQueryHandler(debug_fallback)
    ],
    per_message=False,
    allow_reentry=True
)

# ----------------------------------------
# 2. ADMIN FULFILLMENT WIZARD ROUTER
# ----------------------------------------
admin_router = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_fulfill, pattern="^fulfill_"),
        CallbackQueryHandler(start_fulfill, pattern="^editdelivery_")
    ],
    states={
        ADMIN_SMDP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_smdp),
            CallbackQueryHandler(receive_smdp, pattern="^skip_smdp$")
        ],
        ADMIN_ACTIVATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_activation),
            CallbackQueryHandler(receive_activation, pattern="^skip_activation$")
        ],
        ADMIN_QR: [
            MessageHandler(filters.PHOTO, receive_qr),
            CallbackQueryHandler(receive_qr, pattern="^skip_qr$")
        ],
        ADMIN_CONFIRM: [
            CallbackQueryHandler(confirm_delivery, pattern="^confirm_delivery$"),
            CallbackQueryHandler(start_fulfill, pattern="^fulfill_"), 
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")],
    per_chat=True,
    per_user=True
)

# ----------------------------------------
# 3. GLOBAL ADMIN CONTROL PANEL ROUTER
# ----------------------------------------
control_panel_router = ConversationHandler(
    entry_points=[CommandHandler("admin", start_admin_panel)],
    states={
        ADMIN_PANEL_MAIN: [
            CallbackQueryHandler(handle_check_stats, pattern="^admin_stats$"),
            CallbackQueryHandler(start_message_user, pattern="^admin_msg_user$"),
            CallbackQueryHandler(start_broadcast, pattern="^admin_broadcast$"),
            CallbackQueryHandler(start_admin_panel, pattern="^admin_home$"),
            CallbackQueryHandler(clean_blocked_users, pattern="^admin_clean_blocked$"),
            CallbackQueryHandler(exit_admin, pattern="^admin_exit$")
        ],
        ADMIN_MSG_USER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message_user_id),
            CallbackQueryHandler(start_admin_panel, pattern="^admin_home$")
        ],
        ADMIN_MSG_TEXT: [
            # 🎯 FIX 1: Allow the Direct Message feature to accept Photos and Videos
            MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_message_text),
            CallbackQueryHandler(start_admin_panel, pattern="^admin_home$")
        ],
        
        ADMIN_BROADCAST_INPUT: [
            MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_broadcast_text),
            CallbackQueryHandler(start_admin_panel, pattern="^admin_home$")
        ],
        
        ADMIN_BROADCAST_CONFIRM: [
            CallbackQueryHandler(confirm_broadcast, pattern="^confirm_broadcast$"),
            CallbackQueryHandler(start_admin_panel, pattern="^admin_home$"),
            # 🎯 FIX 2: Allow you to add captions while looking at the preview screen without getting stuck
            MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_broadcast_text)
        ]
    },
    fallbacks=[CommandHandler("admin", start_admin_panel)],
    per_message=False
)