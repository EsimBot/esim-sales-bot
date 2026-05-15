from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import PENDING_GROUP_ID, DELIVERED_GROUP_ID
from utils.db import save_delivery_details, get_order_by_code
from utils.pdf_gen import generate_esim_pdf
import os
from handlers.states import ADMIN_SMDP, ADMIN_ACTIVATION, ADMIN_QR, ADMIN_CONFIRM

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

async def start_fulfill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # 🎯 FIX 2: Detect if this is an "Edit" or "First Time"
    is_edit = query.data.startswith("editdelivery_")
    order_id = query.data.split("_")[1]
    
    context.user_data['admin_order_id'] = order_id
    context.user_data['admin_delivery'] = {}
    context.user_data['is_edit_flow'] = is_edit # Save this for later

    text = (
        f"⚙️ {'🔄 **RE-EDITING**' if is_edit else '**FULFILLING**'} **Order #{order_id}**\n\n"
        f"**Step 1 of 3:**\n"
        f"📝 Please paste the **SM-DP+ Address** below."
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip", callback_data="skip_smdp")]])
    
    try: await query.delete_message()
    except: pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        message_thread_id=update.effective_message.message_thread_id,
        text=text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    return ADMIN_SMDP

async def receive_smdp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Save SM-DP+ and ask for Activation Code"""
    query = update.callback_query
    
    if query:
        await query.answer()
        context.user_data['admin_delivery']['smdp'] = "N/A"
        message = query.message
    else:
        context.user_data['admin_delivery']['smdp'] = update.message.text
        message = update.message

    text = "**Step 2 of 3:**\n🔑 Please paste the **Activation Code** below."
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip (Leave Blank)", callback_data="skip_activation")]])
    
    await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ADMIN_ACTIVATION

async def receive_activation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: Save Activation and ask for QR Code"""
    query = update.callback_query
    
    if query:
        await query.answer()
        context.user_data['admin_delivery']['activation'] = "N/A"
        message = query.message
    else:
        context.user_data['admin_delivery']['activation'] = update.message.text
        message = update.message

    text = "**Step 3 of 3:**\n📷 Please **Upload the QR Code image** now."
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip (No QR)", callback_data="skip_qr")]])
    
    await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ADMIN_QR

async def receive_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 4: Save QR and Show the Final Preview"""
    query = update.callback_query
    
    if query:
        await query.answer()
        context.user_data['admin_delivery']['qr_file_id'] = None
        message = query.message
    else:
        # Grab the highest resolution version of the uploaded photo
        context.user_data['admin_delivery']['qr_file_id'] = update.message.photo[-1].file_id
        message = update.message

    order_id = context.user_data['admin_order_id']
    delivery = context.user_data['admin_delivery']

    text = (
        f"🔍 **PREVIEW: Delivery for #{order_id}**\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"**SM-DP+ Address:** `{delivery['smdp']}`\n\n"
        f"**Activation Code:** `{delivery['activation']}`\n\n"
        f"**QR Included:** {'✅ Yes' if delivery['qr_file_id'] else '❌ No'}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Please review carefully before sending to the user.*"
    )
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Send to User", callback_data="confirm_delivery")],
        [InlineKeyboardButton("🔙 Edit Details", callback_data=f"fulfill_{order_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_wizard")]
    ])
    
    await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    return ADMIN_CONFIRM

async def confirm_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    order_id = context.user_data['admin_order_id']
    print(f"DEBUG: Updating order {order_id} to delivered")
    query = update.callback_query
    await query.answer()
    
   
    delivery = context.user_data.get('admin_delivery')
    is_edit = context.user_data.get('is_edit_flow', False)
    current_thread_id = update.effective_message.message_thread_id
    
    # 1. Update Database
    save_delivery_details(order_id, delivery['smdp'], delivery['activation'], delivery['qr_file_id'])
    user_id, price, region, duration, status = get_order_by_code(order_id)

    await query.edit_message_text("🛠️ **Processing PDF & Delivery...**", parse_mode="Markdown")
    
    qr_temp_path = None
    pdf_path = None

    try:
        # 2. Handle File Downloads
        if delivery.get('qr_file_id'):
            qr_temp_path = os.path.join(BASE_DIR, f"temp_qr_{order_id}.jpg")
            new_file = await context.bot.get_file(delivery['qr_file_id'])
            await new_file.download_to_drive(qr_temp_path)

        # 3. Generate the PDF
        pdf_path = generate_esim_pdf(order_id, region, delivery['smdp'], delivery['activation'], qr_path=qr_temp_path)

        # 4. Send to User
        with open(pdf_path, 'rb') as pdf_file:
            caption = f"📦 **Update: Your eSIM for {region} is ready!**" if is_edit else f"📦 **Your eSIM for {region} is ready!**"
            await context.bot.send_document(
                chat_id=user_id,
                document=pdf_file,
                filename=f"eSIM_Order_{order_id}.pdf",
                caption=caption
            )
            
        # 🎯 FIX 3: THE RELOCATION LOGIC
        # If this was an EDIT, we don't move anything. We just update the summary in the current topic.
        if is_edit:
            await query.edit_message_text(f"✅ **Update Sent!** User has received the new PDF.")
        else:
            # If it's NEW, move from Pending -> Delivered
            new_topic = await context.bot.create_forum_topic(chat_id=DELIVERED_GROUP_ID, name=f"✅ #{order_id} | {region}")
            
            admin_receipt = (
                f"✅ **ORDER DELIVERED**\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **User ID:** `{user_id}`\n\n"
                f"🧾 **Order ID:** `#{order_id}`\n\n"
                f"SM-DP+: `{delivery['smdp']}`\n\n"
                f"Activation: `{delivery['activation']}`\n\n"
                f"━━━━━━━━━━━━━━━━━━"
        )
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit & Resend", callback_data=f"editdelivery_{order_id}")]])
            
            with open(pdf_path, 'rb') as pdf_file:
                await context.bot.send_document(chat_id=DELIVERED_GROUP_ID, message_thread_id=new_topic.message_thread_id, document=pdf_file, caption=admin_receipt, reply_markup=markup)

            # Only delete the topic if it's currently in the PENDING group
            await context.bot.delete_forum_topic(chat_id=PENDING_GROUP_ID, message_thread_id=current_thread_id)

    except Exception as e:
        print(f"Error: {e}")
        await query.message.reply_text(f"⚠️ Error: {e}")
    finally:
        if pdf_path and os.path.exists(pdf_path): os.remove(pdf_path)
        if qr_temp_path and os.path.exists(qr_temp_path): os.remove(qr_temp_path)

    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aborts the admin input process."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ **Fulfillment Canceled.** The order remains pending.")
    return ConversationHandler.END