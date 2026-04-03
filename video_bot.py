import asyncio
import os
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

user_links = {}


def get_media_info(url):
    ydl_opts = {'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration')
            if duration is None:
                duration = 0
            return {
                'title': info.get('title', 'media'),
                'duration': duration,
                'uploader': info.get('uploader', 'Unknown'),
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации: {e}")
        return None


async def download_video(url, output_path):
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания видео: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"📥 Видео загрузчик\n\n"
        f"Здравствуйте, {user.first_name or user.username}!\n\n"
        f"Я скачиваю видео с:\n"
        f"- YouTube\n"
        f"- TikTok\n"
        f"- Instagram\n"
        f"- Twitter/X\n"
        f"- Vimeo\n"
        f"- Rutube\n\n"
        f"Как пользоваться:\n"
        f"1. Отправьте ссылку на видео\n"
        f"2. Нажмите кнопку «Скачать видео»\n"
        f"3. Получите готовый файл\n\n"
        f"Просто отправьте ссылку!"
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id

    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("❌ Отправьте корректную ссылку.")
        return

    status_msg = await update.message.reply_text("🔍 Получаю информацию...")

    info = get_media_info(url)

    if not info:
        await status_msg.edit_text("❌ Не удалось получить информацию по ссылке.")
        return

    user_links[user_id] = url

    duration_min = int(info['duration']) // 60 if info['duration'] else 0
    duration_sec = int(info['duration']) % 60 if info['duration'] else 0

    info_text = (
        f"📹 Найдено видео\n\n"
        f"Название: {info['title'][:50]}\n"
        f"Автор: {info['uploader']}\n"
        f"Длительность: {duration_min}:{duration_sec:02d}\n\n"
        f"Скачать видео?"
    )

    keyboard = [[InlineKeyboardButton("📹 Скачать видео (MP4)", callback_data="download_video")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await status_msg.edit_text(info_text, reply_markup=reply_markup)


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    url = user_links.get(user_id)
    if not url:
        await query.edit_message_text("❌ Ссылка не найдена. Отправьте ссылку заново.")
        return

    await query.edit_message_text("⏳ Скачиваю видео... Пожалуйста, подождите.")

    file_id = str(user_id) + "_" + str(int(asyncio.get_event_loop().time()))
    output_path = os.path.join(TEMP_DIR, f"video_{file_id}.mp4")

    success = await download_video(url, output_path)

    if not success:
        await query.edit_message_text(
            "❌ Не удалось скачать видео.\n\n"
            "Возможные причины:\n"
            "- Видео слишком большое\n"
            "- Проблемы с доступом\n"
            "- Попробуйте другую ссылку"
        )
        if os.path.exists(output_path):
            os.remove(output_path)
        return

    try:
        with open(output_path, 'rb') as f:
            await query.message.reply_video(video=f, caption="✅ Видео готово!", supports_streaming=True)

        os.remove(output_path)
        user_links.pop(user_id, None)

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await query.edit_message_text("❌ Ошибка при отправке. Файл слишком большой (до 50 МБ).")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Помощь\n\n"
        "Поддерживаемые платформы:\n"
        "- YouTube\n"
        "- TikTok\n"
        "- Instagram\n"
        "- Twitter/X\n"
        "- Vimeo\n"
        "- Rutube\n\n"
        "Просто отправьте ссылку на видео!"
    )


async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_callback, pattern="download_video"))

    print("🤖 Видео загрузчик запущен!")
    print("   - Поддерживает: YouTube, TikTok, Instagram, Twitter, Vimeo, Rutube")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Остановка...")