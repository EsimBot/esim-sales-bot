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
    msg = update.effective_message
    
    try:
        # 1. Did the admin send a Photo?
        if msg.photo:
            photo_id = msg.photo[-1].file_id
            caption = f"🔔 <b>Message from Admin:</b>\n\n{msg.caption}" if msg.caption else "🔔 <b>Message from Admin</b>"
            await context.bot.send_photo(chat_id=target_id, photo=photo_id, caption=caption, parse_mode="HTML")
            
        # 2. Did the admin send a Video?
        elif msg.video:
            video_id = msg.video.file_id
            caption = f"🔔 <b>Message from Admin:</b>\n\n{msg.caption}" if msg.caption else "🔔 <b>Message from Admin</b>"
            await context.bot.send_video(chat_id=target_id, video=video_id, caption=caption, parse_mode="HTML")
            
        # 3. Just normal Text
        elif msg.text:
            await context.bot.send_message(chat_id=target_id, text=f"🔔 <b>Message from Admin:</b>\n\n{msg.text}", parse_mode="HTML")
            
        await msg.reply_text("✅ Message delivered successfully!")
    except Exception as e:
        await msg.reply_text(f"❌ Failed to deliver message. Error: {e}")
        
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
    """Captures the broadcast payload (handles text, photos, and photo captions)."""
    msg = update.effective_message
    
    # 🎯 Capture text or photo details
    if msg.photo:
        # Get the highest resolution version of the photo
        context.user_data['broadcast_photo'] = msg.photo[-1].file_id
        context.user_data['broadcast_text'] = msg.caption or ""
        preview_type = "🖼️ PHOTO WITH CAPTION" if msg.caption else "🖼️ PURE PHOTO (NO TEXT)"
    else:
        context.user_data['broadcast_photo'] = None
        context.user_data['broadcast_text'] = msg.text
        preview_type = "📝 TEXT ONLY"

    text_to_show = context.user_data['broadcast_text'] or "<i>(No caption text)</i>"
    
    preview_message = (
        f"📢 <b>Broadcast Preview ({preview_type}):</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{text_to_show}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Do you want to send this to ALL registered users?"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Send It", callback_data="confirm_broadcast")],
        [InlineKeyboardButton("❌ Cancel & Exit", callback_data="admin_home")]
    ])

    # If it's a photo, show them the exact image preview with the verification button
    if context.user_data['broadcast_photo']:
        await msg.reply_photo(
            photo=context.user_data['broadcast_photo'],
            caption=preview_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await msg.reply_text(preview_message, reply_markup=keyboard, parse_mode="HTML")

    return ADMIN_BROADCAST_CONFIRM


async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dispatches the broadcast payload to every user in the database database."""
    query = update.callback_query
    await query.answer("🚀 Dispatching broadcast...")

    from utils.db import get_all_user_ids
    user_ids = get_all_user_ids()
    
    broadcast_text = context.user_data.get('broadcast_text')
    broadcast_photo = context.user_data.get('broadcast_photo')

    await query.edit_message_text(f"⏳ Sending message to {len(user_ids)} users... Please wait.", parse_mode="HTML")

    success_count = 0
    fail_count = 0

    for u_id in user_ids:
        try:
            # 🎯 FIX: Dynamically send photo or text based on captured data payload
            if broadcast_photo:
                await context.bot.send_photo(
                    chat_id=u_id,
                    photo=broadcast_photo,
                    caption=broadcast_text,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=u_id,
                    text=broadcast_text,
                    parse_mode="HTML"
                )
            success_count += 1
            await asyncio.sleep(0.05) # Prevent Telegram API flood limitations
        except Exception:
            fail_count += 1

    # Cleanup memory state values
    context.user_data.pop('broadcast_text', None)
    context.user_data.pop('broadcast_photo', None)

    summary = (
        f"📢 <b>Broadcast Delivery Complete</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Successfully Sent:</b> <code>{success_count}</code>\n"
        f"🔴 <b>Blocked/Failed:</b> <code>{fail_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    
    # Send summary back to admin panel view
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="admin_home")]])
    await context.bot.send_message(chat_id=query.message.chat_id, text=summary, reply_markup=keyboard, parse_mode="HTML")
    return ADMIN_PANEL_MAIN

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