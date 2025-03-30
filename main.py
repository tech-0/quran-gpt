import os
import requests
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Telegram Bot Token
TELEGRAM_API_TOKEN = '7476023842:AAFyYp9fkQ5zXyJ7DXvXfj0TSg974q5q6O0'

# Flask app for keep-alive
app = Flask(__name__)


@app.route('/')
def home():
  return "I'm alive!"


def run_flask():
  app.run(host='0.0.0.0', port=8080)


flask_thread = Thread(target=run_flask)
flask_thread.start()


# Fetch Surahs
def get_surahs():
  url = "https://api.alquran.cloud/v1/surah"
  response = requests.get(url)
  if response.status_code == 200:
    data = response.json()
    return [{
        'id': surah['number'],
        'name': surah['name'],
        'ayah_count': surah['numberOfAyahs']
    } for surah in sorted(data['data'], key=lambda x: x['number'])]
  return []


# Get Surah Keyboard (Pagination)
def get_surah_keyboard(page=1, per_page=50):
  surahs = get_surahs()
  start_idx = (page - 1) * per_page
  end_idx = min(start_idx + per_page, len(surahs))

  keyboard = [[
      InlineKeyboardButton(f"{surah['id']}: {surah['name']}",
                           callback_data=f"surah-{surah['id']}")
  ] for surah in surahs[start_idx:end_idx]]

  navigation_buttons = []
  if page > 1:
    navigation_buttons.append(
        InlineKeyboardButton("⬅️ Previous", callback_data=f"page-{page-1}"))
  if end_idx < len(surahs):
    navigation_buttons.append(
        InlineKeyboardButton("Next ➡️", callback_data=f"page-{page+1}"))

  if navigation_buttons:
    keyboard.append(navigation_buttons)

  return InlineKeyboardMarkup(keyboard)


# Handle /start
async def start(update, context):
  reply_markup = get_surah_keyboard(page=1)
  await update.message.reply_text("Select a Surah:", reply_markup=reply_markup)


# Handle Pagination
async def handle_pagination(update, context):
  query = update.callback_query
  await query.answer()
  page = int(query.data.split('-')[1])
  reply_markup = get_surah_keyboard(page)
  await query.message.edit_text("Select a Surah:", reply_markup=reply_markup)


# Select Surah
async def select_ayah(update, context):
  query = update.callback_query
  await query.answer()
  surah_number = int(query.data.split('-')[1])
  context.user_data['selected_surah'] = surah_number

  surahs = get_surahs()
  selected_surah = next(surah for surah in surahs
                        if surah['id'] == surah_number)
  max_ayah = selected_surah['ayah_count']

  keyboard = [[
      InlineKeyboardButton(f"Ayah {i}",
                           callback_data=f"ayah-{surah_number}-{i}")
  ] for i in range(1, max_ayah + 1)]

  reply_markup = InlineKeyboardMarkup(keyboard)
  await query.message.reply_text(
      f"Surah {selected_surah['name']} selected. Now select an Ayah:",
      reply_markup=reply_markup)


# Fetch Ayah + Audio
async def fetch_ayah(update, context):
  query = update.callback_query
  await query.answer()
  _, surah_number, ayah_number = query.data.split('-')

  # Fetch Text Translation
  translation_url = f"https://quranenc.com/api/v1/translation/aya/kurdish_bamoki/{surah_number}/{ayah_number}"
  response = requests.get(translation_url)

  try:
    response.raise_for_status()
    data = response.json()
    if "result" in data:
      arabic_text = data["result"]["arabic_text"]
      kurdish_translation = data["result"]["translation"]

      surahs = get_surahs()
      surah = next(surah for surah in surahs
                   if surah['id'] == int(surah_number))

      message_text = f"📖 *Surah {surah['name']}, Ayah {ayah_number}:*\n\n\n"
      message_text += f"*Arabic: * \n\n{arabic_text}\n\n\n"
      message_text += f"*Kurdish: * \n\n {kurdish_translation}\n\n\n"

      # Fetch Audio Recitation (Mishary Rashid Alafasy)
      surah_number_str = str(surah_number).zfill(3)  # 1 -> 001, 10 -> 010
      ayah_number_str = str(ayah_number).zfill(3)  # 1 -> 001, 10 -> 010
      audio_url = f"https://everyayah.com/data/Alafasy_64kbps/{surah_number_str}{ayah_number_str}.mp3"

      # Send Text First
      await query.message.reply_text(message_text, parse_mode="Markdown")

      # Send Audio
      await query.message.reply_voice(
          audio_url,
          caption=
          f"🎧 *Recitation of Surah {surah['name']} - Ayah {ayah_number}*",
          parse_mode="Markdown")

    else:
      await query.message.reply_text("No data found for this Ayah.")
  except requests.exceptions.RequestException:
    await query.message.reply_text("Error retrieving Ayah.")


# Run Bot
def main():
  application = Application.builder().token(TELEGRAM_API_TOKEN).build()
  application.add_handler(CommandHandler('start', start))
  application.add_handler(
      CallbackQueryHandler(handle_pagination, pattern='^page-\d+$'))
  application.add_handler(
      CallbackQueryHandler(select_ayah, pattern='^surah-\d+$'))
  application.add_handler(
      CallbackQueryHandler(fetch_ayah, pattern='^ayah-\d+-\d+$'))

  print("Bot is running...")
  application.run_polling()


if __name__ == "__main__":
  main()
