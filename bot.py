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

# Cache untuk menyimpan URL dengan batas ukuran (Max 1000 entri)
class LimitedCache:
    def __init__(self, limit=1000):
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
        "Kirimkan link video dari YouTube, TikTok, Instagram, Twitter, dll., dan saya akan membantu mengunduhnya untukmu.\n\n"
        "Gunakan /help untuk bantuan lebih lanjut."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Panduan Penggunaan:*\n\n"
        "1. Salin link video (YouTube, TikTok, IG, dll).\n"
        "2. Tempelkan link tersebut di sini.\n"
        "3. Pilih tombol format (Video atau Audio).\n"
        "4. Tunggu bot memproses dan mengirimkan filenya.\n\n"
        "💡 *Fitur Tambahan:*\n"
        "- `/search <kata kunci>` : Cari video YouTube langsung dari bot.\n\n"
        "⚠️ *Catatan:* Batas unggah Telegram adalah 50MB.",
        parse_mode='Markdown'
    )

async def search_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Silakan masukkan kata kunci pencarian. Contoh: `/search lagu baru`", parse_mode='Markdown')
        return

    await update.message.reply_text(f"🔍 Mencari '{query}' di YouTube...")

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Gunakan to_thread agar tidak blocking
            info = await asyncio.to_thread(ydl.extract_info, f"ytsearch5:{query}", download=False)
            search_results = info.get('entries', [])

            if not search_results:
                await update.message.reply_text("Tidak ditemukan hasil.")
                return

            text = "🔎 *Hasil Pencarian:*\n\n"
            for i, res in enumerate(search_results):
                text += f"{i+1}. [{res.get('title', 'Video')}]({res.get('url')})\n"

            await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)
            await update.message.reply_text("Kirimkan salah satu link di atas untuk mengunduh.")

    except Exception as e:
        logging.error(f"Search error: {e}")
        await update.message.reply_text("Gagal melakukan pencarian.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url or not url.startswith("http"):
        return

    sent_msg = await update.message.reply_text("🔍 Menganalisis link... Mohon tunggu.")

    try:
        ydl_opts = {'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Gunakan to_thread agar tidak blocking
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'Video')
            duration = info.get('duration', 0)
            thumbnail = info.get('thumbnail')

            # Generate ID unik untuk URL ini agar muat di callback_data (max 64 bytes)
            url_id = str(uuid.uuid4())[:12]
            url_cache.set(url_id, url)

            keyboard = [
                [
                    InlineKeyboardButton("📹 Video", callback_data=f"vid|{url_id}"),
                    InlineKeyboardButton("🎵 Audio", callback_data=f"aud|{url_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            caption = f"🎬 *Judul:* {title}\n"
            if duration:
                caption += f"⏱ *Durasi:* {duration // 60}:{duration % 60:02d}\n"

            await sent_msg.delete()
            if thumbnail:
                try:
                    await update.message.reply_photo(photo=thumbnail, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
                except:
                    await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error extracting info: {e}")
        await sent_msg.edit_text(f"❌ Maaf, terjadi kesalahan saat memproses link tersebut.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('|')
    mode = data[0]
    url_id = data[1]

    url = url_cache.get(url_id)
    if not url:
        await query.message.reply_text("❌ Sesi kedaluwarsa atau link tidak ditemukan. Silakan kirim ulang link video.")
        return

    unique_id = str(uuid.uuid4())[:8]
    status_msg = await query.message.reply_text("⏳ Sedang memproses... Mohon bersabar.")

    try:
        if mode == 'vid':
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s',
                'quiet': True,
                'max_filesize': 50 * 1024 * 1024, # Batasi 50MB
            }
        else:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{DOWNLOAD_DIR}/%(title)s_{unique_id}.%(ext)s',
                'quiet': True,
                'max_filesize': 50 * 1024 * 1024, # Batasi 50MB
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            file_path = ydl.prepare_filename(info)

        # Cek ukuran file manual sebagai jaga-jaga
        filesize = os.path.getsize(file_path)
        if filesize > 50 * 1024 * 1024:
            await status_msg.edit_text("❌ File terlalu besar (> 50MB). Batas maksimal Telegram adalah 50MB.")
            os.remove(file_path)
            return

        await status_msg.edit_text("✅ Selesai! Sedang mengirim file...")

        with open(file_path, 'rb') as f:
            if mode == 'vid':
                await query.message.reply_video(video=f, caption=f"Selesai: {info['title']}")
            else:
                # Kirim sebagai audio jika memungkinkan, atau dokumen
                await query.message.reply_audio(audio=f, caption=f"Selesai: {info['title']}")

        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Download error: {e}")
        error_msg = str(e)
        if "File is larger than max_filesize" in error_msg:
            await status_msg.edit_text("❌ File terlalu besar untuk dikirim via Telegram (Batas 50MB).")
        else:
            await status_msg.edit_text(f"❌ Terjadi kesalahan: {error_msg}")

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_telegram_bot_token_here":
        print("Error: TELEGRAM_TOKEN tidak ditemukan atau belum diset di file .env")
    else:
        application = ApplicationBuilder().token(TOKEN).build()

        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('search', search_youtube))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        application.add_handler(CallbackQueryHandler(button_handler))

        print("Bot sedang berjalan...")
        application.run_polling()
