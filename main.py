import os, shutil, time, asyncio, uuid, re, yt_dlp, aiohttp, aiofiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.error import RetryAfter, BadRequest

# --- CONFIG ---
TOKEN = '8653746545:AAEKYOEnbdPJrI8WhbB3p-XEt78EhWPBC24'
DOWNLOAD_PATH = os.path.abspath('./downloads')
TG_MAX_UPLOAD_MB = 50  
CONCURRENT_DOWNLOADS = 3
FILE_EXPIRY_SECONDS = 3600 

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

download_semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)
last_ui_update = {}

# --- UTILS ---
async def safe_edit(bot, chat_id, message_id, text, reply_markup=None):
    try:
        await bot.edit_message_text(
            chat_id=chat_id, 
            message_id=message_id, 
            text=text, 
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after)
    except (BadRequest, Exception):
        pass 

def sync_progress_hook(d, chat_id, message_id, loop, bot):
    if d['status'] == 'downloading':
        now = time.time()
        if now - last_ui_update.get(message_id, 0) > 8: 
            last_ui_update[message_id] = now
            p_str = d.get('_percent_str', '0%').replace('%','')
            try: p_float = float(p_str)
            except: p_float = 0
            
            bar = '🔹' * int(p_float / 10) + '◽' * (10 - int(p_float / 10))
            text = f"📥 **Downloading...**\n`{bar}` {p_float:.1f}%\n⚡ `{d.get('_speed_str', 'N/A')}`"
            
            asyncio.run_coroutine_threadsafe(
                safe_edit(bot, chat_id, message_id, text),
                loop
            )

# --- CLEANUP TASK ---
async def cleanup_expired_files(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    to_delete = []
    for fid, data in context.bot_data.items():
        if isinstance(data, dict) and now - data.get('timestamp', 0) > FILE_EXPIRY_SECONDS:
            path = data.get('path')
            if path and os.path.exists(path):
                try: os.remove(path)
                except: pass
            to_delete.append(fid)
    for fid in to_delete:
        del context.bot_data[fid]

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    text = (
        f"👋 **Hello, {user_name}!**\n\n"
        "I can download videos from **YouTube, TikTok, Instagram, and X**.\n"
        "Just paste a link below to get started!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **How to use this bot:**\n"
        "1. Copy a video link from your browser or app.\n"
        "2. Paste it here and wait for the download.\n"
        "3. Click **Upload** to receive the file.\n\n"
        "⚠️ **Current Limits:**\n"
        "• Max File Size: `50 MB` (Telegram Limit)\n"
        "• Max Quality: `480p/720p` (to save space)\n"
        "• Files are deleted after 1 hour if not uploaded."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- CORE FUNCTIONS ---
async def download_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Regex to extract the first URL from a message (useful for TikTok shares)
    urls = re.findall(r'(https?://\S+)', update.message.text)
    if not urls: return
    url = urls[0]

    async with download_semaphore:
        status_msg = await update.message.reply_text("⏳ Queued and processing...")
        loop = asyncio.get_running_loop()

        try:
            def ydl_run():
                # Added unique ID to filename to prevent collisions
                unique_name = f"{uuid.uuid4().hex[:6]}"
                opts = {
                    'outtmpl': f'{DOWNLOAD_PATH}/{unique_name}_%(title).50s.%(ext)s',
                    'format': 'best[ext=mp4][filesize<50M]/bestvideo[height<=480]+bestaudio/best[height<=480]',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                    'progress_hooks': [lambda d: sync_progress_hook(
                        d, update.effective_chat.id, status_msg.message_id, loop, context.bot
                    )],
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return ydl.prepare_filename(info)

            file_path = await loop.run_in_executor(None, ydl_run)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError("File failed to download.")

            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            if size_mb > TG_MAX_UPLOAD_MB:
                await status_msg.edit_text(f"❌ **File too large ({size_mb:.1f}MB).**\nTelegram limit is 50MB.")
                os.remove(file_path)
                return

            fid = uuid.uuid4().hex[:8]
            context.bot_data[fid] = {'path': file_path, 'timestamp': time.time()}
            
            kb = [[InlineKeyboardButton("📤 Upload", callback_data=f"up:{fid}"),
                   InlineKeyboardButton("🗑️ Delete", callback_data=f"del:{fid}")]]
            
            await safe_edit(context.bot, update.effective_chat.id, status_msg.message_id, 
                            f"✅ **Ready!**\n⚖️ `{size_mb:.1f} MB`", InlineKeyboardMarkup(kb))

        except Exception as e:
            await safe_edit(context.bot, update.effective_chat.id, status_msg.message_id, 
                            f"❌ **Error:** `{str(e)[:100]}`")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 2: return
    cmd, fid = parts
    data = context.bot_data.get(fid)

    if not data or not os.path.exists(data['path']):
        return await query.edit_message_text("❌ File expired or already deleted.")

    path = data['path']
    if cmd == "up":
        await query.edit_message_text("📤 **Uploading...**")
        try:
            with open(path, 'rb') as f:
                await context.bot.send_document(chat_id=query.message.chat_id, document=f)
            await query.edit_message_text("✅ Sent!")
        except Exception as e:
            await query.edit_message_text(f"❌ Upload failed: {str(e)[:50]}")
        finally:
            if os.path.exists(path): os.remove(path)
            if fid in context.bot_data: del context.bot_data[fid]
    elif cmd == "del":
        if os.path.exists(path): os.remove(path)
        if fid in context.bot_data: del context.bot_data[fid]
        await query.edit_message_text("🗑️ Deleted from server.")

# --- MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # Run cleanup job
    app.job_queue.run_repeating(cleanup_expired_files, interval=600, first=10)

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), download_manager))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 Bot is running...")
    app.run_polling()
