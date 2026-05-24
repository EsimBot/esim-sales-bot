import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import Forbidden
from config import ADMIN_IDS
from menus.main_menu import main_menu_keyboard
from utils.db import get_admin_stats, check_user_exists, get_all_user_ids, mark_user_blocked
from handlers.states import (
    ADMIN_PANEL_MAIN, ADMIN_MSG_USER_ID, ADMIN_MSG_TEXT,
    ADMIN_BROADCAST_INPUT, ADMIN_BROADCAST_CONFIRM,ADMIN_POLL_QUESTION,
    ADMIN_POLL_OPTIONS, ADMIN_POLL_CONFIRM
)

def admin_menu_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Check Stats", callback_data="admin_stats"),
            InlineKeyboardButton("💬 Message a User", callback_data="admin_msg_user")
        ],
        [
            InlineKeyboardButton("📢 Broadcast All", callback_data="admin_broadcast"),
            InlineKeyboardButton("🧹 Clean Blocked", callback_data="admin_clean_blocked")
        ],
        [   InlineKeyboardButton("📊 Create Live Poll", callback_data="admin_create_poll")
         
        ],
        
        [
            InlineKeyboardButton("🔙 Refresh Menu", callback_data="admin_home"),
            InlineKeyboardButton("🏠 Exit Admin", callback_data="admin_exit")
        ]
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
    
    # 🎯 UPDATED to include blocked_users
    total_users, total_revenue, active_esims, expired_esims, blocked_users = get_admin_stats()
    
    from datetime import datetime
    now_time = datetime.now().strftime("%H:%M:%S")
    
    text = (
        "📊 <b>Live Store Statistics</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Active Users:</b> {total_users}\n"
        f"🚫 <b>Blocked/Removed:</b> {blocked_users}\n"
        f"💰 <b>Total Revenue:</b> ${total_revenue:.2f}\n\n"
        f"🟢 <b>Active eSIMs:</b> {active_esims}\n"
        f"🔴 <b>Expired eSIMs:</b> {expired_esims}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<i>🔄 Last Refreshed: {now_time}</i>"
    )
    
    try:
        await query.edit_message_text(text, reply_markup=admin_menu_markup(), parse_mode="HTML")
    except Exception as e:
        if "not modified" not in str(e).lower():
            raise e
            
    return ADMIN_PANEL_MAIN


# --- BACKGROUND CLEANUP TASK ---
async def clean_blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_ids = get_all_user_ids()
    
    context.job_queue.run_once(cleanup_background_job, 1, data={'admin_chat_id': query.message.chat_id, 'user_ids': user_ids})
    
    await query.edit_message_text(
        "🧹 <b>Background Cleanup Started!</b>\n\nThe bot is silently pinging all users. It will not freeze, and you will receive a report when finished.", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="admin_home")]]), 
        parse_mode="HTML"
    )
    return ADMIN_PANEL_MAIN

async def cleanup_background_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    admin_chat_id, user_ids = data['admin_chat_id'], data['user_ids']
    
    blocked, active = 0, 0
    for u_id in user_ids:
        try:
            # Silent action that throws a Forbidden error if blocked
            await context.bot.send_chat_action(chat_id=u_id, action="typing")
            active += 1
            await asyncio.sleep(0.05)
        except Forbidden:
            mark_user_blocked(u_id)
            blocked += 1
        except Exception:
            pass # Ignore random network drops
            
    text = (
        f"🧹 <b>Cleanup Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🚫 <b>New Blocked Users Removed:</b> {blocked}\n"
        f"👥 <b>Healthy Active Users:</b> {active}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=admin_chat_id, text=text, parse_mode="HTML")


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
        if msg.photo:
            photo_id = msg.photo[-1].file_id
            caption = f"🔔 <b>Message from Admin:</b>\n\n{msg.caption}" if msg.caption else "🔔 <b>Message from Admin</b>"
            await context.bot.send_photo(chat_id=target_id, photo=photo_id, caption=caption, parse_mode="HTML")
        elif msg.video:
            video_id = msg.video.file_id
            caption = f"🔔 <b>Message from Admin:</b>\n\n{msg.caption}" if msg.caption else "🔔 <b>Message from Admin</b>"
            await context.bot.send_video(chat_id=target_id, video=video_id, caption=caption, parse_mode="HTML")
        elif msg.text:
            await context.bot.send_message(chat_id=target_id, text=f"🔔 <b>Message from Admin:</b>\n\n{msg.text}", parse_mode="HTML")
            
        await msg.reply_text("✅ Message delivered successfully!")
    except Forbidden:
        mark_user_blocked(target_id)
        await msg.reply_text("❌ Failed. User has blocked the bot. They have been removed from the active list.")
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
    msg = update.effective_message
    
    if msg.photo:
        context.user_data['broadcast_photo'] = msg.photo[-1].file_id
        context.user_data['broadcast_text'] = msg.caption or ""
        preview_type = "🖼️ PHOTO WITH CAPTION" if msg.caption else "🖼️ PURE PHOTO (NO TEXT)"
    elif msg.video:
        context.user_data['broadcast_video'] = msg.video.file_id
        context.user_data['broadcast_text'] = msg.caption or ""
        preview_type = "🎥 VIDEO WITH CAPTION" if msg.caption else "🎥 PURE VIDEO (NO TEXT)"
    else:
        context.user_data['broadcast_photo'] = None
        context.user_data['broadcast_video'] = None
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

    if context.user_data.get('broadcast_photo'):
        await msg.reply_photo(photo=context.user_data['broadcast_photo'], caption=preview_message[:1024], reply_markup=keyboard, parse_mode="HTML")
    elif context.user_data.get('broadcast_video'):
        await msg.reply_video(video=context.user_data['broadcast_video'], caption=preview_message[:1024], reply_markup=keyboard, parse_mode="HTML")
    else:
        await msg.reply_text(preview_message, reply_markup=keyboard, parse_mode="HTML")

    return ADMIN_BROADCAST_CONFIRM


async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_ids = get_all_user_ids()
    
    # 🎯 PREPARE BACKGROUND JOB PAYLOAD
    payload = {
        'admin_chat_id': query.message.chat_id,
        'broadcast_text': context.user_data.get('broadcast_text'),
        'broadcast_photo': context.user_data.get('broadcast_photo'),
        'broadcast_video': context.user_data.get('broadcast_video'),
        'user_ids': user_ids
    }
    
    # 🚀 DISPATCH TO BACKGROUND (Frees up the bot instantly)
    context.job_queue.run_once(broadcast_background_job, 1, data=payload)
    
    # Cleanup memory state values
    context.user_data.pop('broadcast_text', None)
    context.user_data.pop('broadcast_photo', None)
    context.user_data.pop('broadcast_video', None)

    try:
        await query.message.delete()
    except Exception:
        pass
        
    await context.bot.send_message(
        chat_id=query.message.chat_id, 
        text=f"🚀 <b>Broadcast Started!</b>\n\nDispatching to {len(user_ids)} users in the background. The bot will not freeze. You will receive a receipt here when it finishes.", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="admin_home")]]), 
        parse_mode="HTML"
    )
    return ADMIN_PANEL_MAIN


async def broadcast_background_job(context: ContextTypes.DEFAULT_TYPE):
    """The silent worker that actually sends the messages without freezing the bot."""
    data = context.job.data
    admin_chat_id = data['admin_chat_id']
    b_text = data['broadcast_text']
    b_photo = data['broadcast_photo']
    b_video = data['broadcast_video']
    user_ids = data['user_ids']
    
    success, fail, auto_blocked = 0, 0, 0
    safe_caption = b_text[:1024] if b_text else None

    for u_id in user_ids:
        try:
            if b_photo: 
                await context.bot.send_photo(chat_id=u_id, photo=b_photo, caption=safe_caption, parse_mode="HTML")
            elif b_video: 
                await context.bot.send_video(chat_id=u_id, video=b_video, caption=safe_caption, parse_mode="HTML")
            else: 
                await context.bot.send_message(chat_id=u_id, text=b_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Forbidden:
            # 🎯 DETECTED BLOCKED USER - Mark them automatically
            mark_user_blocked(u_id)
            auto_blocked += 1
        except Exception:
            # HTML Fallback
            try:
                if b_photo: await context.bot.send_photo(chat_id=u_id, photo=b_photo, caption=safe_caption)
                elif b_video: await context.bot.send_video(chat_id=u_id, video=b_video, caption=safe_caption)
                else: await context.bot.send_message(chat_id=u_id, text=b_text)
                success += 1
                await asyncio.sleep(0.05)
            except Forbidden:
                mark_user_blocked(u_id)
                auto_blocked += 1
            except Exception:
                fail += 1

    summary = (
        f"📢 <b>Broadcast Delivery Complete</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Sent Successfully:</b> <code>{success}</code>\n"
        f"🚫 <b>Auto-Removed (Blocked Bot):</b> <code>{auto_blocked}</code>\n"
        f"🔴 <b>Network Fails:</b> <code>{fail}</code>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=admin_chat_id, text=summary, parse_mode="HTML")



# --- INTERACTIVE POLL BUILDER WIZARD ---

async def start_poll_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: Ask for the Poll Question."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['poll_building'] = {'question': '', 'options': []}
    
    btns = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_home")]]
    await query.edit_message_text(
        "📊 <b>Interactive Poll Builder</b>\n\nStep 1: Please type the <b>Question</b> for your poll:",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )
    return ADMIN_POLL_QUESTION

async def receive_poll_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Save question and instruct how to provide options."""
    question_text = update.message.text.strip()
    context.user_data['poll_building']['question'] = question_text
    
    btns = [[InlineKeyboardButton("❌ Cancel & Exit", callback_data="admin_home")]]
    await update.message.reply_text(
        f"✅ <b>Question Saved:</b>\n<i>\"{question_text}\"</i>\n\n"
        f"Step 2: Provide the answer options.\n"
        f"Please send your choices **one message at a time**.\n\n"
        f"<i>💡 Type the word <b>done</b> when you are finished adding options (Minimum 2, Maximum 10).</i>",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
    )
    return ADMIN_POLL_OPTIONS

async def receive_poll_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: Collect options sequentially until admin types 'done'."""
    input_text = update.message.text.strip()
    poll_data = context.user_data.get('poll_building')
    
    # Check if admin is finished entering options
    if input_text.lower() == 'done':
        if len(poll_data['options']) < 2:
            await update.message.reply_text("⚠️ You must provide at least <b>2 options</b> before concluding. Send another choice:")
            return ADMIN_POLL_OPTIONS
            
        # Show configuration preview card
        options_list = "\n".join([f"🔹 {opt}" for opt in poll_data['options']])
        preview_text = (
            f"📊 <b>Poll Broadcast Preview</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"❓ <b>Question:</b> {poll_data['question']}\n\n"
            f"📋 <b>Options:</b>\n{options_list}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Do you want to dispatch this native poll to ALL active users in the background?"
        )
        
        btns = [
            [InlineKeyboardButton("🚀 Launch Poll Broadcast", callback_data="confirm_poll_send")],
            [InlineKeyboardButton("❌ Cancel & Discard", callback_data="admin_home")]
        ]
        await update.message.reply_text(preview_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")
        return ADMIN_POLL_CONFIRM

    # Add option up to Telegram's maximum 10 constraints
    if len(poll_data['options']) >= 10:
        await update.message.reply_text("🛑 Maximum threshold reached (10 choices total). Please type <b>done</b> to proceed.")
        return ADMIN_POLL_OPTIONS

    poll_data['options'].append(input_text)
    current_count = len(poll_data['options'])
    
    await update.message.reply_text(f"✅ Option {current_count} added: <code>{input_text}</code>\n<i>Send next choice, or type <b>done</b> if ready.</i>", parse_mode="HTML")
    return ADMIN_POLL_OPTIONS

async def confirm_poll_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: Dispatch collected configurations to our background job queue manager."""
    query = update.callback_query
    await query.answer()
    
    user_ids = get_all_user_ids()
    poll_data = context.user_data.get('poll_building')
    
    payload = {
        'admin_chat_id': query.message.chat_id,
        'question': poll_data['question'],
        'options': poll_data['options'],
        'user_ids': user_ids
    }
    
    # 🚀 Run asynchronously through background scheduler
    context.job_queue.run_once(poll_background_job, 1, data=payload)
    context.user_data.pop('poll_building', None)
    
    try: await query.message.delete()
    except: pass
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"🚀 <b>Poll Broadcast Dispatched!</b>\n\nDistributing dynamically to {len(user_ids)} users in the background. The bot will remain responsive, and a delivery report will materialize when finished.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="admin_home")]]),
        parse_mode="HTML"
    )
    return ADMIN_PANEL_MAIN

async def poll_background_job(context: ContextTypes.DEFAULT_TYPE):
    """Asynchronous worker that distributes the custom poll without locking interface interactions."""
    data = context.job.data
    admin_chat_id = data['admin_chat_id']
    question = data['question']
    options = data['options']
    user_ids = data['user_ids']
    
    success, fail = 0, 0
    
    for u_id in user_ids:
        try:
            await context.bot.send_poll(
                chat_id=u_id,
                question=question,
                options=options,
                is_anonymous=True # Set to False if you want to trace users' responses
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    summary = (
        f"📊 <b>Poll Delivery Campaign Concluded</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Delivered Perfectly:</b> <code>{success}</code>\n"
        f"🔴 <b>Undelivered/Errors:</b> <code>{fail}</code>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    await context.bot.send_message(chat_id=admin_chat_id, text=summary, parse_mode="HTML")
    
    
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