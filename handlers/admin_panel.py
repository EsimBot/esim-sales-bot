# handlers/admin_panel.py
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_IDS
from menus.main_menu import main_menu_keyboard
from utils.db import get_admin_stats, check_user_exists, get_all_user_ids
from handlers.states import (
    ADMIN_PANEL_MAIN, ADMIN_MSG_USER_ID, ADMIN_MSG_TEXT,
    ADMIN_BROADCAST_INPUT, ADMIN_BROADCAST_CONFIRM
)

def admin_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Check Stats", callback_data="admin_stats"),
            InlineKeyboardButton("💬 Message a User", callback_data="admin_msg_user")
        ],
        [
            InlineKeyboardButton("📢 Broadcast All", callback_data="admin_broadcast"),
            InlineKeyboardButton("🔙 Refresh Menu", callback_data="admin_home")
        ],
        [InlineKeyboardButton("🏠 Exit Admin", callback_data="admin_exit")]
    ])

async def start_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return ConversationHandler.END

    text = (
        "👑 <b>eSIM Store Admin Panel</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Welcome back, Admin. Select an administrative utility below:"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=admin_menu_markup(), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=admin_menu_markup(), parse_mode="HTML")
    return ADMIN_PANEL_MAIN

async def handle_check_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    total_users, total_revenue, active_esims, expired_esims = get_admin_stats()
    
    text = (
        "📊 <b>Live Store Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Users:</b> {total_users}\n"
        f"💰 <b>Total Revenue:</b> ${total_revenue:.2f}\n\n"
        f"🟢 <b>Active eSIMs:</b> {active_esims}\n"
        f"🔴 <b>Expired eSIMs:</b> {expired_esims}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(text, reply_markup=admin_menu_markup(), parse_mode="HTML")
    return ADMIN_PANEL_MAIN

# --- MESSAGE A USER FLOW ---
async def start_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    btns = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_home")]]
    await query.edit_message_text(
        "💬 <b>Message a User</b>\n\nPlease enter the exact Telegram User ID you want to message:",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )
    return ADMIN_MSG_USER_ID

async def receive_message_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id_str = update.message.text.strip()
    
    if not target_id_str.isdigit():
        await update.message.reply_text("❌ Invalid ID. Please enter numbers only.")
        return ADMIN_MSG_USER_ID
        
    target_id = int(target_id_str)
    if not check_user_exists(target_id):
        btns = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_home")]]
        await update.message.reply_text("❌ User not found in the database.", reply_markup=InlineKeyboardMarkup(btns))
        return ADMIN_MSG_USER_ID
        
    context.user_data['target_msg_id'] = target_id
    btns = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_home")]]
    await update.message.reply_text(
        f"✅ <b>User {target_id} found!</b>\n\nType the message you want to send them now:",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )
    return ADMIN_MSG_TEXT

async def receive_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = context.user_data.get('target_msg_id')
    msg_text = update.message.text
    
    try:
        await context.bot.send_message(chat_id=target_id, text=f"🔔 <b>Message from Admin:</b>\n\n{msg_text}", parse_mode="HTML")
        await update.message.reply_text("✅ Message sent successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send message: {e}")
        
    return await start_admin_panel(update, context)

# --- GLOBAL BROADCAST FLOW ---
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    btns = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_home")]]
    await query.edit_message_text(
        "📢 <b>Global Broadcast</b>\n\nType your announcement below (HTML formatting is supported):",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )
    return ADMIN_BROADCAST_INPUT

async def receive_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_text'] = update.message.text
    
    text = (
        "⚠️ <b>BROADCAST PREVIEW</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{update.message.text}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Are you sure you want to send this to ALL users?"
    )
    btns = [
        [InlineKeyboardButton("✅ Send Live Now", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_home")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
    return ADMIN_BROADCAST_CONFIRM

async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    broadcast_text = context.user_data.get('broadcast_text')
    users = get_all_user_ids()
    
    await query.edit_message_text(f"🚀 Sending broadcast to {len(users)} users. Please wait...")
    
    success, fail = 0, 0
    for u_id in users:
        try:
            await context.bot.send_message(chat_id=u_id, text=broadcast_text, parse_mode="HTML")
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05) # Crucial: Prevents Telegram Flood Limits (20 msgs/sec)
        
    await query.message.reply_text(f"✅ <b>Broadcast Complete!</b>\n\nSent: {success}\nFailed: {fail}", parse_mode="HTML")
    return await start_admin_panel(update, context)

# --- NAVIGATION ---
async def exit_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Exited admin panel.", 
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END