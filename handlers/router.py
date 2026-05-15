from telegram.ext import (
    MessageHandler, 
    filters, 
    ConversationHandler, 
    CommandHandler, 
    CallbackQueryHandler
)
from handlers.esim_flow import (
    handle_buy_esim, handle_usa_selected, 
    handle_plan_selected, handle_final_purchase, back_to_main,
    handle_renewal_selection,
    SELECTING_REGION, SELECTING_PLAN, CONFIRMING_ORDER
)
from handlers.wallet_flow import (
    handle_wallet, start_topup, 
    receive_amount, process_crypto_payment,
    show_usdt_networks, back_to_coins,
    handle_cancel_payment
)
# 🎯 1. IMPORT THE NEW ORDERS LOGIC
from handlers.orders_flow import handle_my_orders, handle_orders_pagination
from handlers.interceptor import handle_interceptor_decision
from handlers.admin_fulfillment import (
    start_fulfill, receive_smdp, receive_activation, receive_qr, confirm_delivery, cancel_wizard
)

from handlers.support import handle_support_click

from handlers.states import (
    SELECTING_REGION, SELECTING_PLAN, DEPOSITING, 
    ENTERING_AMOUNT, CHOOSING_COIN, CONFIRMING_ORDER, 
    WAITING_FOR_PAYMENT,INTERCEPTING,
    ADMIN_SMDP, ADMIN_ACTIVATION, ADMIN_QR, ADMIN_CONFIRM,SELECT_RENEWAL_TYPE
)



async def debug_fallback(update, context):
    query = update.callback_query
    current_state = context.user_data.get('state') 
    print(f"👻 Ignored Click: {query.data} | Bot is in State: {current_state}")
    await query.answer("This button is not active right now.", show_alert=False)
    return None 

purchase_router = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^🌍 Buy eSIM$"), handle_buy_esim),
        MessageHandler(filters.Regex("^💰 Credits$"), handle_wallet),
        
        # 🎯 2. HOOK UP "MY ORDERS" BUTTON
        MessageHandler(filters.Regex("^📊 My Orders$"), handle_my_orders),
        
        MessageHandler(filters.Regex("^🛠️ Support$"), handle_support_click),
        
        CallbackQueryHandler(handle_wallet, pattern="^view_wallet$"),
        
        # 🎯 3. HOOK UP PAGINATION CLICKS (Catches clicks even outside of flows)
        CallbackQueryHandler(handle_orders_pagination, pattern="^orders_page_"),
    ],
    states={
        # ... (Leave all your existing states exactly as they are) ...
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
    allow_reentry=True
)

admin_router = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_fulfill, pattern="^fulfill_"),
        CallbackQueryHandler(start_fulfill, pattern="^editdelivery_") # Phase 5 entry
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
            CallbackQueryHandler(start_fulfill, pattern="^fulfill_"), # The 'Edit Details' button loops back to start
            CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_wizard, pattern="^cancel_wizard$")],
    per_chat=True,  # Allows it to work isolated inside specific group topics
    per_user=True
)
