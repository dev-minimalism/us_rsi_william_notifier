import asyncio
import os
import warnings
import json
from datetime import datetime, time, timedelta

import pytz
from yahooquery import Ticker
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from logger.logger import logger
from message.telegram_message import send_telegram_message
from tech_indicator.indicator import calculate_rsi, calculate_williams_r, \
  generate_signals

warnings.simplefilter(action='ignore', category=FutureWarning)

# 티커 리스트 파일 경로
TICKERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tickers.json')

# 기본 티커 리스트
DEFAULT_TICKERS = [
  'NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL',  # 1-5위
  'META', 'AVGO', 'BRK.B', 'TSLA', 'TSM',  # 6-10위
  'JPM', 'WMT', 'LLY', 'ORCL', 'V',  # 11-15위
  'NFLX', 'MA', 'XOM', 'COST', 'JNJ',  # 16-20위
  'HD', 'PG', 'SAP', 'PLTR', 'BAC',  # 21-25위
  'ABBV', 'ASML', 'NVO', 'KO', 'GE',  # 26-30위
  'PM', 'CSCO', 'UNH', 'BABA', 'CVX',  # 31-35위
  'IBM', 'TMUS', 'WFC', 'AMD', 'CRM',  # 36-40위
  'NVS', 'ABT', 'MS', 'TM', 'AZN',  # 41-45위
  'AXP', 'LIN', 'HSBC', 'MCD', 'DIS'  # 46-50위
]

# 전역 변수
current_tickers = []


def ensure_log_directory():
  """로그 디렉토리가 없으면 생성"""
  log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')
  if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    print(f"Created log directory: {log_dir}")
  return log_dir


def load_tickers():
  """티커 리스트를 파일에서 로드"""
  global current_tickers
  if os.path.exists(TICKERS_FILE):
    try:
      with open(TICKERS_FILE, 'r') as f:
        current_tickers = json.load(f)
      logger.info(f"Loaded {len(current_tickers)} tickers from file")
    except Exception as e:
      logger.error(f"Error loading tickers file: {e}")
      current_tickers = DEFAULT_TICKERS.copy()
  else:
    current_tickers = DEFAULT_TICKERS.copy()
    save_tickers()
  return current_tickers


def save_tickers():
  """티커 리스트를 파일에 저장"""
  try:
    with open(TICKERS_FILE, 'w') as f:
      json.dump(current_tickers, f, indent=2)
    logger.info(f"Saved {len(current_tickers)} tickers to file")
  except Exception as e:
    logger.error(f"Error saving tickers file: {e}")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 추가 명령어 처리"""
  global current_tickers

  if not context.args:
    await update.message.reply_text("❌ Usage: /add TICKER\nExample: /add TSLA")
    return

  ticker = context.args[0].upper()

  if ticker in current_tickers:
    await update.message.reply_text(f"ℹ️ {ticker} is already in the monitoring list")
    return

  # 티커 유효성 검증
  try:
    test_ticker = Ticker(ticker)
    test_data = test_ticker.history(period='5d', interval='1d')

    if test_data.empty:
      await update.message.reply_text(f"❌ {ticker} is not a valid ticker or has no data")
      return

    current_tickers.append(ticker)
    save_tickers()

    message = f"✅ {ticker} added to monitoring list\n📊 Total tickers: {len(current_tickers)}"
    await update.message.reply_text(message)
    logger.info(f"Ticker {ticker} added. Total: {len(current_tickers)}")

  except Exception as e:
    await update.message.reply_text(f"❌ Error adding {ticker}: {str(e)}")
    logger.error(f"Error adding ticker {ticker}: {e}")


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 삭제 명령어 처리"""
  global current_tickers

  if not context.args:
    await update.message.reply_text("❌ Usage: /remove TICKER\nExample: /remove TSLA")
    return

  ticker = context.args[0].upper()

  if ticker not in current_tickers:
    await update.message.reply_text(f"ℹ️ {ticker} is not in the monitoring list")
    return

  current_tickers.remove(ticker)
  save_tickers()

  message = f"✅ {ticker} removed from monitoring list\n📊 Total tickers: {len(current_tickers)}"
  await update.message.reply_text(message)
  logger.info(f"Ticker {ticker} removed. Total: {len(current_tickers)}")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """현재 모니터링 중인 티커 목록 표시"""
  if not current_tickers:
    await update.message.reply_text("📭 No tickers in monitoring list")
    return

  # 10개씩 나누어 표시
  message = f"📊 Monitoring {len(current_tickers)} tickers:\n\n"
  for i, ticker in enumerate(current_tickers, 1):
    message += f"{i}. {ticker}\n"
    if i % 30 == 0 and i < len(current_tickers):
      await update.message.reply_text(message)
      message = ""

  if message:
    await update.message.reply_text(message)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """티커 리스트를 기본값으로 리셋"""
  global current_tickers
  current_tickers = DEFAULT_TICKERS.copy()
  save_tickers()

  message = f"🔄 Ticker list reset to default\n📊 Total tickers: {len(current_tickers)}"
  await update.message.reply_text(message)
  logger.info(f"Ticker list reset to default ({len(current_tickers)} tickers)")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """도움말 표시"""
  help_text = """
📖 Available Commands:

/add TICKER - Add a ticker to monitoring list
  Example: /add TSLA

/remove TICKER - Remove a ticker from list
  Example: /remove TSLA

/list - Show all monitored tickers

/reset - Reset to default ticker list

/help - Show this help message

Bot monitors stocks for RSI and Williams %R signals
Signals are sent automatically every hour during market hours
"""
  await update.message.reply_text(help_text)


def is_us_market_open():
  """미국 주식 시장이 열렸는지 확인 (한국 시간 기준) - 프리마켓 포함"""
  korea_tz = pytz.timezone('Asia/Seoul')
  us_eastern_tz = pytz.timezone('US/Eastern')

  korea_now = datetime.now(korea_tz)
  us_now = korea_now.astimezone(us_eastern_tz)

  if us_now.weekday() in [5, 6]:
    korea_time_str = korea_now.strftime('%Y-%m-%d %H:%M:%S KST')
    us_time_str = us_now.strftime('%Y-%m-%d %H:%M:%S EST')
    time_info = f"Korea: {korea_time_str}, US: {us_time_str}, Market: WEEKEND"
    return False, time_info, "WEEKEND"

  premarket_start = time(4, 0)
  market_open = time(9, 30)
  market_close = time(16, 0)
  afterhours_end = time(20, 0)

  current_time = us_now.time()

  if premarket_start <= current_time < market_open:
    market_status = "PREMARKET"
    is_trading = True
  elif market_open <= current_time <= market_close:
    market_status = "REGULAR"
    is_trading = True
  elif market_close < current_time <= afterhours_end:
    market_status = "AFTERHOURS"
    is_trading = True
  else:
    market_status = "CLOSED"
    is_trading = False

  korea_time_str = korea_now.strftime('%Y-%m-%d %H:%M:%S KST')
  us_time_str = us_now.strftime('%Y-%m-%d %H:%M:%S EST')

  time_info = f"Korea: {korea_time_str}, US: {us_time_str}, Market: {market_status}"

  return is_trading, time_info, market_status


async def send_heartbeat(counter, market_status="CLOSED"):
  """정기적인 heartbeat 메시지 전송"""
  is_trading, time_info, status = is_us_market_open()

  if status == "PREMARKET":
    heartbeat_msg = f"🟡 Heartbeat #{counter}: PREMARKET - Monitoring active\n{time_info}"
  elif status == "REGULAR":
    heartbeat_msg = f"✅ Heartbeat #{counter}: REGULAR HOURS - Monitoring active\n{time_info}"
  elif status == "AFTERHOURS":
    heartbeat_msg = f"🟠 Heartbeat #{counter}: AFTERHOURS - Monitoring active\n{time_info}"
  elif status == "WEEKEND":
    heartbeat_msg = f"🏖️ Heartbeat #{counter}: WEEKEND - Standby mode\n{time_info}"
  else:
    heartbeat_msg = f"💤 Heartbeat #{counter}: MARKET CLOSED - Standby mode\n{time_info}"

  try:
    await send_telegram_message(heartbeat_msg)
    logger.info(f"Heartbeat #{counter} sent successfully - Status: {status}")
  except Exception as e:
    logger.error(f"Failed to send heartbeat #{counter}: {e}")


async def monitor_stocks():
  """주식 모니터링 메인 루프"""
  period = 14
  check_interval = 3600  # 1시간
  last_alert = {}
  heartbeat_counter = 0

  is_trading, time_info, market_status = is_us_market_open()
  start_message = f"🚀 Trading bot started with {len(current_tickers)} tickers!\n{time_info}\n\n💡 Use /help to see available commands"

  logger.info(f"Trading bot started with {len(current_tickers)} tickers")
  await send_telegram_message(start_message)

  while True:
    try:
      heartbeat_counter += 1

      is_trading, time_info, market_status = is_us_market_open()
      logger.info(f"Market status check: {time_info}")

      # 현재 모니터링 중인 티커 가져오기
      tickers = current_tickers.copy()

      if not tickers:
        logger.warning("No tickers to monitor")
        await send_heartbeat(heartbeat_counter, market_status)
        await asyncio.sleep(check_interval)
        continue

      if is_trading:
        logger.info(f"Market is active ({market_status}) - Analyzing {len(tickers)} stocks...")

        if market_status in ["PREMARKET", "AFTERHOURS"]:
          logger.info(f"Note: {market_status} data may have limitations")

        tickers_obj = Ticker(tickers)
        df = tickers_obj.history(period='3mo', interval='1d')

        if df.empty:
          logger.warning("No data returned for any ticker.")
          await send_heartbeat(heartbeat_counter, market_status)
          await asyncio.sleep(check_interval)
          continue

        analyzed_count = 0
        signal_count = 0

        for stock_ticker in tickers:
          try:
            stock_data = df[df.index.get_level_values(0) == stock_ticker].copy()

            if stock_data.empty:
              logger.warning(f"No data available for {stock_ticker}.")
              continue

            stock_data.reset_index(inplace=True)
            stock_data.set_index('date', inplace=True)

            stock_data['Williams %R'] = calculate_williams_r(stock_data, period)
            stock_data['RSI'] = calculate_rsi(stock_data, period)

            if stock_data[['Williams %R', 'RSI']].isna().all(axis=None):
              logger.warning(f"{stock_ticker}: Indicator data is not valid.")
              continue

            analyzed_count += 1

            buy_signals, sell_signals = generate_signals(
              stock_data['Williams %R'], stock_data['RSI']
            )

            latest_date = stock_data.index[-1]
            williams_r_value = stock_data.loc[latest_date, 'Williams %R']
            rsi_value = stock_data.loc[latest_date, 'RSI']
            close_price = stock_data.loc[latest_date, 'close']

            if buy_signals.iloc[-1] and last_alert.get(stock_ticker) != 'buy':
              message = (
                f"🟢 [BUY SIGNAL] {stock_ticker} ({market_status})\n"
                f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
                f"📊 Williams %R: {williams_r_value:.2f}\n"
                f"📊 RSI: {rsi_value:.2f}\n"
                f"💰 Price: ${close_price:.2f}"
              )
              await send_telegram_message(message)
              logger.info(f"BUY signal sent for {stock_ticker} during {market_status}")
              last_alert[stock_ticker] = 'buy'
              signal_count += 1

            if sell_signals.iloc[-1] and last_alert.get(stock_ticker) != 'sell':
              message = (
                f"🔴 [SELL SIGNAL] {stock_ticker} ({market_status})\n"
                f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
                f"📊 Williams %R: {williams_r_value:.2f}\n"
                f"📊 RSI: {rsi_value:.2f}\n"
                f"💰 Price: ${close_price:.2f}"
              )
              await send_telegram_message(message)
              logger.info(f"SELL signal sent for {stock_ticker} during {market_status}")
              last_alert[stock_ticker] = 'sell'
              signal_count += 1

          except Exception as e:
            logger.error(f"Error processing {stock_ticker}: {e}")

        logger.info(
          f"Analysis completed: {analyzed_count}/{len(tickers)} stocks analyzed, {signal_count} signals generated")
        logger.info(f"Stock analysis completed for heartbeat #{heartbeat_counter}")

      else:
        logger.info(f"Market is closed ({market_status}) - Standby mode")

      if is_trading:
        status_emoji = {
          "PREMARKET": "🟡",
          "REGULAR": "✅",
          "AFTERHOURS": "🟠"
        }
        emoji = status_emoji.get(market_status, "✅")

        enhanced_heartbeat = (
          f"{emoji} Heartbeat #{heartbeat_counter}: {market_status}\n"
          f"📊 Monitoring: {len(tickers)} tickers\n"
          f"✓ Analyzed: {analyzed_count if 'analyzed_count' in locals() else 0}/{len(tickers)} stocks\n"
          f"🎯 Signals: {signal_count if 'signal_count' in locals() else 0} generated\n"
          f"{time_info}"
        )
        await send_telegram_message(enhanced_heartbeat)
        logger.info(f"Enhanced heartbeat #{heartbeat_counter} sent - Status: {market_status}")
      else:
        await send_heartbeat(heartbeat_counter, market_status)

    except Exception as e:
      logger.error(f"Error in main loop: {e}")
      error_message = f"❌ Error in monitoring loop #{heartbeat_counter}: {str(e)}"
      try:
        await send_telegram_message(error_message)
      except:
        pass

    next_check_time = (datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')
    logger.info(f"Waiting 1 hour until next check... (Next check: {next_check_time})")
    await asyncio.sleep(check_interval)


async def run_telegram_bot():
  """텔레그램 봇 실행"""
  # 환경 변수에서 봇 토큰 가져오기
  bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

  if not bot_token:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    return

  app = Application.builder().token(bot_token).build()

  # 명령어 핸들러 등록
  app.add_handler(CommandHandler("add", cmd_add))
  app.add_handler(CommandHandler("remove", cmd_remove))
  app.add_handler(CommandHandler("list", cmd_list))
  app.add_handler(CommandHandler("reset", cmd_reset))
  app.add_handler(CommandHandler("help", cmd_help))

  logger.info("Telegram bot handlers registered")

  # 봇 시작
  await app.initialize()
  await app.start()
  await app.updater.start_polling()

  logger.info("Telegram bot started and listening for commands")

  # 봇을 계속 실행 상태로 유지
  try:
    while True:
      await asyncio.sleep(1)
  except asyncio.CancelledError:
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


async def main():
  """메인 실행 함수"""
  # 로그 디렉토리 확인 및 생성
  ensure_log_directory()

  # 티커 리스트 로드
  load_tickers()

  logger.info("Starting US Stock Market Monitor with Dynamic Ticker Management")

  # 모니터링과 텔레그램 봇을 병렬로 실행
  await asyncio.gather(
    monitor_stocks(),
    run_telegram_bot()
  )


if __name__ == '__main__':
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    logger.info("Bot stopped by user")
  except Exception as e:
    logger.error(f"Fatal error: {e}")