"""
티커 관리용 텔레그램 봇
메인 모니터링 봇과 별도로 실행하여 티커를 추가/삭제합니다.
"""
import asyncio
import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from yahooquery import Ticker

# 티커 리스트 파일 경로
TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tickers.json')


def load_tickers():
  """티커 리스트를 파일에서 로드"""
  if os.path.exists(TICKERS_FILE):
    try:
      with open(TICKERS_FILE, 'r') as f:
        return json.load(f)
    except Exception as e:
      print(f"❌ Error loading tickers: {e}")
      return []
  return []


def save_tickers(tickers):
  """티커 리스트를 파일에 저장"""
  try:
    with open(TICKERS_FILE, 'w') as f:
      json.dump(tickers, f, indent=2)
    print(f"✅ Saved {len(tickers)} tickers")
    return True
  except Exception as e:
    print(f"❌ Error saving tickers: {e}")
    return False


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 추가 명령어"""
  if not context.args:
    await update.message.reply_text(
      "❌ Usage: /add TICKER\n"
      "Example: /add TSLA"
    )
    return

  ticker = context.args[0].upper()
  tickers = load_tickers()

  if ticker in tickers:
    await update.message.reply_text(
      f"ℹ️ {ticker} is already in the monitoring list\n"
      f"📊 Current tickers: {len(tickers)}"
    )
    return

  # 티커 유효성 검증
  await update.message.reply_text(f"🔍 Validating {ticker}...")

  try:
    test_ticker = Ticker(ticker)
    test_data = test_ticker.history(period='5d', interval='1d')

    if test_data.empty:
      await update.message.reply_text(
        f"❌ {ticker} is not a valid ticker or has no data\n"
        "Please check the ticker symbol and try again"
      )
      return

    # 티커 추가
    tickers.append(ticker)

    if save_tickers(tickers):
      await update.message.reply_text(
        f"✅ Successfully added {ticker}\n"
        f"📊 Total tickers: {len(tickers)}\n\n"
        f"The monitoring bot will automatically detect this change in the next cycle"
      )
      print(f"✅ Added ticker: {ticker} (Total: {len(tickers)})")
    else:
      await update.message.reply_text(
        f"❌ Failed to save {ticker}\n"
        "Please check file permissions"
      )

  except Exception as e:
    await update.message.reply_text(
      f"❌ Error validating {ticker}: {str(e)}\n"
      "Please check the ticker symbol"
    )


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 삭제 명령어"""
  if not context.args:
    await update.message.reply_text(
      "❌ Usage: /remove TICKER\n"
      "Example: /remove TSLA"
    )
    return

  ticker = context.args[0].upper()
  tickers = load_tickers()

  if ticker not in tickers:
    await update.message.reply_text(
      f"ℹ️ {ticker} is not in the monitoring list\n"
      f"Use /list to see all monitored tickers"
    )
    return

  # 티커 삭제
  tickers.remove(ticker)

  if save_tickers(tickers):
    await update.message.reply_text(
      f"✅ Successfully removed {ticker}\n"
      f"📊 Total tickers: {len(tickers)}\n\n"
      f"The monitoring bot will automatically detect this change"
    )
    print(f"✅ Removed ticker: {ticker} (Remaining: {len(tickers)})")
  else:
    await update.message.reply_text(
      f"❌ Failed to save changes\n"
      "Please check file permissions"
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """현재 모니터링 중인 티커 목록 표시"""
  tickers = load_tickers()

  if not tickers:
    await update.message.reply_text("📭 No tickers in monitoring list")
    return

  # 티커 목록을 정렬하여 표시
  sorted_tickers = sorted(tickers)

  # 30개씩 나누어 표시
  chunk_size = 30
  for i in range(0, len(sorted_tickers), chunk_size):
    chunk = sorted_tickers[i:i + chunk_size]

    if i == 0:
      message = f"📊 Monitoring {len(tickers)} tickers:\n\n"
    else:
      message = f"📊 Continued ({i + 1}-{min(i + chunk_size, len(tickers))}):\n\n"

    # 5개씩 한 줄에 표시
    for j in range(0, len(chunk), 5):
      line = chunk[j:j + 5]
      message += ", ".join(line) + "\n"

    await update.message.reply_text(message)
    await asyncio.sleep(0.5)  # 메시지 전송 간격


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 검색 (부분 일치)"""
  if not context.args:
    await update.message.reply_text(
      "❌ Usage: /search KEYWORD\n"
      "Example: /search AAPL"
    )
    return

  keyword = context.args[0].upper()
  tickers = load_tickers()

  matches = [t for t in tickers if keyword in t]

  if matches:
    await update.message.reply_text(
      f"🔍 Found {len(matches)} ticker(s) matching '{keyword}':\n\n"
      + ", ".join(matches)
    )
  else:
    await update.message.reply_text(
      f"❌ No tickers found matching '{keyword}'"
    )


async def cmd_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """현재 티커 개수 표시"""
  tickers = load_tickers()
  await update.message.reply_text(
    f"📊 Currently monitoring {len(tickers)} ticker(s)\n\n"
    f"Use /list to see all tickers"
  )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """도움말 표시"""
  help_text = """
📖 Ticker Manager Commands

➕ Adding/Removing Tickers:
/add TICKER - Add a new ticker
  Example: /add TSLA

/remove TICKER - Remove a ticker
  Example: /remove TSLA

📋 Viewing Tickers:
/list - Show all monitored tickers
/count - Show total number of tickers
/search KEYWORD - Search for tickers
  Example: /search AAPL

❓ Help:
/help - Show this help message

💡 Note: Changes take effect in the next monitoring cycle (within 1 hour)
"""
  await update.message.reply_text(help_text)


async def main():
  """메인 실행 함수"""
  # 환경 변수에서 봇 토큰 가져오기
  bot_token = os.getenv('US_RSI_WILLIAM_TELEGRAM_BOT_TOKEN')

  if not bot_token:
    print("=" * 60)
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
    print("=" * 60)
    print("Please set your bot token:")
    print("export TELEGRAM_BOT_TOKEN='your_bot_token_here'")
    print("=" * 60)
    return

  print("=" * 60)
  print("🤖 Ticker Manager Bot Starting...")
  print("=" * 60)
  print(f"Token: {bot_token[:10]}...{bot_token[-5:]}")

  try:
    # 애플리케이션 생성
    app = Application.builder().token(bot_token).build()

    # 명령어 핸들러 등록
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("count", cmd_count))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    print("✅ Command handlers registered")

    # 봇 시작
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    print("=" * 60)
    print("✅ TICKER MANAGER BOT IS RUNNING!")
    print("=" * 60)
    print("Available commands:")
    print("  /add TICKER    - Add a ticker")
    print("  /remove TICKER - Remove a ticker")
    print("  /list          - Show all tickers")
    print("  /help          - Show help")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # 계속 실행
    while True:
      await asyncio.sleep(1)

  except KeyboardInterrupt:
    print("\n\n👋 Stopping Ticker Manager Bot...")
  except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
  finally:
    try:
      await app.updater.stop()
      await app.stop()
      await app.shutdown()
      print("✅ Bot stopped cleanly")
    except:
      pass


if __name__ == '__main__':
  asyncio.run(main())