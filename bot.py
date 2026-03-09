import os
import logging
import asyncio
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv
import yt_dlp
from collections import OrderedDict

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Folder untuk menyimpan unduhan sementara
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Cache untuk menyimpan URL (Agar callback data tidak kepanjangan)
class LimitedCache:
    def __init__(self, limit=500):
        self.cache = OrderedDict()
        self.limit = limit

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.limit:
            self.cache.popitem(last=False)

    def get(self, key):
        return self.cache.get(key)

url_cache = LimitedCache(limit=500)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya adalah Bot Downloader Multi-Platform.\n\n"
        "Kirimkan link video (YouTube, TikTok, IG, dll), dan saya akan mengunduhnya untukmu.\n\n"
        "Gunakan /help untuk bantuan."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Panduan Penggunaan:*\n\n"
        "1. Tempelkan link video ke sini.\n"
        "2. Pilih format (Video/Audio).\n"
        "3. Tunggu proses selesai.\n\n"
        "⚠️ *Catatan:* Batas upload Telegram Bot standar adalah 50MB."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"):
        return

    sent_msg = await update.message.reply_text("🔍 Menganalisis link...")

    try:
        ydl_opts = {'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'Video')
            url_id = str(uuid.uuid4())[:12]
            url_cache.set(url_id, url)

            keyboard = [[
                InlineKeyboardButton("📹 Video", callback_data=f"vid|{url_id}"),
                InlineKeyboardButton("🎵 Audio", callback_data=f"aud|{url_id}")
            ]]
            
            await sent_msg.delete()
            await update.message.reply_text(
                f"🎬 *Judul:* {title}\nPilih format di bawah:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        await sent_msg.edit_text("❌ Gagal mengambil informasi video.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('|')
    mode, url_id = data[0], data[1]
    url = url_cache.get(url_id)

    if not url:
        await query.message.reply_text("❌ Sesi kedaluwarsa.")
        return

    status_msg = await query.message.reply_text("⏳ Mengunduh... Sabar ya.")
    unique_id = str(uuid.uuid4())[:8]

    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best' if mode == 'vid' else 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s',
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            file_path = ydl.prepare_filename(info)

        if os.path.getsize(file_path) > 50 * 1024 * 1024:
            await status_msg.edit_text("❌ File lebih dari 50MB. Tidak bisa dikirim.")
        else:
            await status_msg.edit_text("✅ Mengirim file...")
            with open(file_path, 'rb') as f:
                if mode == 'vid':
                    await query.message.reply_video(video=f, caption=info.get('title'))
                else:
                    await query.message.reply_audio(audio=f, caption=info.get('title'))
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    if not TOKEN:
        print("Masukkan TOKEN di file .env!")
    else:
        # Menggunakan Polling: 100% jalan di hosting tanpa perlu setting port/webhook
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(button_handler))

        print("Bot running via Polling...")
        app.run_polling(drop_pending_updates=True)
            
