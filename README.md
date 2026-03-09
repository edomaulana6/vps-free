# Telegram Multi-Platform Downloader Bot

Bot Telegram untuk mengunduh video dan audio dari berbagai platform (YouTube, TikTok, Instagram, dll).

## Fitur
- Unduh Video (MP4)
- Unduh Audio (MP3/Original)
- Pencarian YouTube langsung via bot (`/search`)
- Informasi video (Judul, Durasi, Thumbnail)
- Mendukung hampir semua platform populer (via yt-dlp)

## Persyaratan
- Python 3.8+
- [FFmpeg](https://ffmpeg.org/) (Sangat disarankan untuk fitur audio terbaik)

## Instalasi
1. Clone repositori ini.
2. Instal dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` dan masukkan token bot Telegram Anda:
   ```env
   TELEGRAM_TOKEN=your_bot_token_here
   ```
4. Jalankan bot:
   ```bash
   python bot.py
   ```

## Catatan
- Batas unggah bot Telegram standar adalah **50MB**. Jika file lebih besar dari itu, bot akan memberikan pesan kesalahan.
