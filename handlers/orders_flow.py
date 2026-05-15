from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils.db import get_user_orders

async def handle_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when the user clicks the 📊 My Orders button"""
    await display_orders_page(update, context, page=0, is_edit=False)
    # Return END because this is a standalone view, not a multi-step conversation
    return ConversationHandler.END

async def handle_orders_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when the user clicks Prev or Next"""
    query = update.callback_query
    await query.answer()
    
    # Extract the page number from the callback data (e.g., 'orders_page_1')
    page = int(query.data.split("_")[2])
    await display_orders_page(update, context, page=page, is_edit=True)

async def display_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int, is_edit: bool):
    """The engine that generates the list and the buttons"""
    user_id = update.effective_user.id
    limit = 5
    offset = page * limit
    
    # Fetch data from DB
    orders, total_count = get_user_orders(user_id, offset=offset, limit=limit)
    
    if not orders and page == 0:
        text = "📦 <b>Your eSIM Purchase History</b>\n━━━━━━━━━━━━━━━━━━\n<i>No eSIM orders found yet.</i>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]])
    else:
        text = f"📦 <b>Your eSIM Purchase History (Page {page + 1})</b>\n━━━━━━━━━━━━━━━━━━\n"
        
        # Status Dictionary for clean visual formatting
        status_emojis = {
            'completed': '🟢 Completed',
            'pending': '🟡 Pending',
            'expired': '🔴 Expired',
            'canceled': '⚪ Canceled'
        }
        
        for row in orders:
            status, date, region, duration, order_code,is_renewable = row
            emoji_status = status_emojis.get(status.lower(), f"🔵 {status}")
            renewal_label = "RenW." if is_renewable else "NonR"
            
            # Format: 🟢 Completed | 2026-04-27 | USA 10GB | #90631841
            text += f"{emoji_status} | {date} | {region} {duration} | {renewal_label} | #{order_code}\n\n"
        
        # Build the Pagination Buttons
        buttons = []
        nav_row = []
        
        # Only show "Prev" if we are past Page 1
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"orders_page_{page - 1}"))
            
        # Only show "Next" if there are more items left to display
        if offset + limit < total_count:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"orders_page_{page + 1}"))
            
        if nav_row:
            buttons.append(nav_row)
            
        buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
        markup = InlineKeyboardMarkup(buttons)
        
    # Send or Edit the message
    if is_edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")