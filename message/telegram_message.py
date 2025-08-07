from telegram import Bot

from config.config import TELEGRAM_TOKEN, CHAT_ID
from logger.logger import logger

bot = Bot(token=TELEGRAM_TOKEN)

# 텔레그램 알림 함수
async def send_telegram_message(message):
  try:
    await bot.send_message(chat_id=CHAT_ID, text=message)
    logger.info(f"Telegram message sent: {message}")
  except Exception as e:
    logger.error(f"Telegram message failed: {e}")

