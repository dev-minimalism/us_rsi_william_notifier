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

# 환경 변수에서 텔레그램 토큰 가져오기
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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


def ensure_log_directory():
  """로그 디렉토리가 없으면 생성"""
  log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')
  if not os.path.exists(log_dir):
    os.makedirs(log_dir)
    print(f"Created log directory: {log_dir}")
  return log_dir


def load_tickers():
  """티커 리스트를 파일에서 로드"""
  if os.path.exists(TICKERS_FILE):
    try:
      with open(TICKERS_FILE, 'r') as f:
        tickers = json.load(f)
      logger.info(f"📂 Loaded {len(tickers)} tickers from file")
      return tickers
    except Exception as e:
      logger.error(f"Error loading tickers file: {e}")
      return DEFAULT_TICKERS.copy()
  else:
    save_tickers(DEFAULT_TICKERS)
    logger.info(f"📂 Created new tickers file with {len(DEFAULT_TICKERS)} default tickers")
    return DEFAULT_TICKERS.copy()


def save_tickers(tickers):
  """티커 리스트를 파일에 저장"""
  try:
    with open(TICKERS_FILE, 'w') as f:
      json.dump(tickers, f, indent=2)
    logger.info(f"💾 Saved {len(tickers)} tickers to file")
  except Exception as e:
    logger.error(f"Error saving tickers file: {e}")


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
    heartbeat_msg = f"🖐️ Heartbeat #{counter}: WEEKEND - Standby mode\n{time_info}"
  else:
    heartbeat_msg = f"💤 Heartbeat #{counter}: MARKET CLOSED - Standby mode\n{time_info}"

  try:
    await send_telegram_message(heartbeat_msg)
    logger.info(f"Heartbeat #{counter} sent successfully - Status: {status}")
  except Exception as e:
    logger.error(f"Failed to send heartbeat #{counter}: {e}")


async def perform_stock_scan(period=14, source="manual"):
  """주식 스캔 실행 (수동/자동 모두 사용)"""
  tickers = load_tickers()

  if not tickers:
    logger.warning("⚠️ No tickers to monitor!")
    return {
      'success': False,
      'message': "❌ No tickers configured to scan",
      'analyzed': 0,
      'signals': 0
    }

  is_trading, time_info, market_status = is_us_market_open()

  logger.info(f"[{source.upper()}] Starting scan for {len(tickers)} tickers - {market_status}")

  try:
    # 한 번에 모든 종목 가져오기
    tickers_obj = Ticker(tickers)
    df = tickers_obj.history(period='3mo', interval='1d')

    if df.empty:
      logger.warning("No data returned for any ticker.")
      return {
        'success': False,
        'message': "❌ No market data available",
        'analyzed': 0,
        'signals': 0,
        'market_status': market_status
      }

    analyzed_count = 0
    signal_count = 0
    last_alert = {}  # 스캔마다 초기화

    # 종목별로 데이터 분리
    for stock_ticker in tickers:
      try:
        stock_data = df[df.index.get_level_values(0) == stock_ticker].copy()

        if stock_data.empty:
          logger.warning(f"No data available for {stock_ticker}.")
          continue

        # 인덱스 정리
        stock_data.reset_index(inplace=True)
        stock_data.set_index('date', inplace=True)

        # 지표 계산
        stock_data['Williams %R'] = calculate_williams_r(stock_data, period)
        stock_data['RSI'] = calculate_rsi(stock_data, period)

        # 데이터 유효성 확인
        if stock_data[['Williams %R', 'RSI']].isna().all(axis=None):
          logger.warning(f"{stock_ticker}: Indicator data is not valid.")
          continue

        analyzed_count += 1

        # 신호 생성
        buy_signals, sell_signals = generate_signals(
          stock_data['Williams %R'], stock_data['RSI']
        )

        latest_date = stock_data.index[-1]
        williams_r_value = stock_data.loc[latest_date, 'Williams %R']
        rsi_value = stock_data.loc[latest_date, 'RSI']
        close_price = stock_data.loc[latest_date, 'close']

        # 매수 알림
        if buy_signals.iloc[-1]:
          scan_tag = "🔍 MANUAL SCAN" if source == "manual" else "🤖 AUTO SCAN"
          message = (
            f"🟢 [BUY SIGNAL] {stock_ticker} ({market_status})\n"
            f"{scan_tag}\n"
            f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
            f"📊 Williams %R: {williams_r_value:.2f}\n"
            f"📊 RSI: {rsi_value:.2f}\n"
            f"💰 Price: ${close_price:.2f}"
          )
          await send_telegram_message(message)
          logger.info(f"[{source.upper()}] BUY signal sent for {stock_ticker}")
          signal_count += 1

        # 매도 알림
        if sell_signals.iloc[-1]:
          scan_tag = "🔍 MANUAL SCAN" if source == "manual" else "🤖 AUTO SCAN"
          message = (
            f"🔴 [SELL SIGNAL] {stock_ticker} ({market_status})\n"
            f"{scan_tag}\n"
            f"📅 Date: {latest_date.strftime('%Y-%m-%d')}\n"
            f"📊 Williams %R: {williams_r_value:.2f}\n"
            f"📊 RSI: {rsi_value:.2f}\n"
            f"💰 Price: ${close_price:.2f}"
          )
          await send_telegram_message(message)
          logger.info(f"[{source.upper()}] SELL signal sent for {stock_ticker}")
          signal_count += 1

      except Exception as e:
        logger.error(f"Error processing {stock_ticker}: {e}")

    return {
      'success': True,
      'analyzed': analyzed_count,
      'signals': signal_count,
      'total_tickers': len(tickers),
      'market_status': market_status,
      'time_info': time_info
    }

  except Exception as e:
    logger.error(f"Error in stock scan: {e}")
    return {
      'success': False,
      'message': f"❌ Error during scan: {str(e)}",
      'analyzed': 0,
      'signals': 0
    }


# 텔레그램 봇 명령어 핸들러
async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """텔레그램 /scan 명령어 핸들러"""
  logger.info(f"Manual scan requested by user {update.effective_user.id}")

  # 스캔 시작 메시지
  await update.message.reply_text("🔍 Manual scan started...\nAnalyzing stocks now...")

  # 스캔 실행
  result = await perform_stock_scan(source="manual")

  # 결과 메시지 생성
  if result['success']:
    summary_message = (
      f"✅ Manual scan completed!\n\n"
      f"📊 Market: {result['market_status']}\n"
      f"✔️ Analyzed: {result['analyzed']}/{result['total_tickers']} stocks\n"
      f"🎯 Signals found: {result['signals']}\n\n"
      f"{result['time_info']}"
    )
  else:
    summary_message = result.get('message', '❌ Scan failed')

  await update.message.reply_text(summary_message)
  logger.info(f"Manual scan completed - Signals: {result.get('signals', 0)}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """텔레그램 /status 명령어 핸들러"""
  tickers = load_tickers()
  is_trading, time_info, market_status = is_us_market_open()

  status_message = (
    f"📊 Bot Status\n\n"
    f"🔴 Market: {market_status}\n"
    f"📈 Monitoring: {len(tickers)} tickers\n"
    f"⏱️ Auto scan: Every 30 minutes\n\n"
    f"{time_info}\n\n"
    f"💡 Commands:\n"
    f"/scan - Run immediate scan\n"
    f"/status - Show this status"
  )

  await update.message.reply_text(status_message)


async def start_telegram_bot():
  """텔레그램 봇 시작"""
  if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    return

  app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

  # 명령어 핸들러 추가
  app.add_handler(CommandHandler("scan", scan_command))
  app.add_handler(CommandHandler("status", status_command))

  logger.info("Telegram bot handlers registered")

  # 봇 시작 (polling)
  await app.initialize()
  await app.start()
  await app.updater.start_polling()

  logger.info("Telegram bot started and listening for commands")


async def monitor_stocks():
  """주식 모니터링 메인 루프 (자동 스캔)"""
  check_interval = 1800  # 30분 (1800초)
  heartbeat_interval = 6  # 6시간마다 heartbeat
  heartbeat_counter = 0
  cycle_counter = 0

  tickers = load_tickers()
  is_trading, time_info, market_status = is_us_market_open()

  start_message = (
    f"🚀 Trading bot with RSI and Williams %R started!\n"
    f"📊 Monitoring {len(tickers)} tickers\n"
    f"⏱️ Auto scan: Every 30 minutes\n"
    f"💬 Heartbeat: Every 6 hours\n"
    f"{time_info}\n\n"
    f"💡 Commands:\n"
    f"/scan - Run immediate scan\n"
    f"/status - Check bot status"
  )

  logger.info(f"Trading bot started with {len(tickers)} tickers")
  await send_telegram_message(start_message)

  while True:
    try:
      cycle_counter += 1
      should_send_heartbeat = (cycle_counter % (heartbeat_interval * 2) == 1)

      if should_send_heartbeat:
        heartbeat_counter += 1

      is_trading, time_info, market_status = is_us_market_open()
      logger.info(f"[Cycle {cycle_counter}] Market status check: {time_info}")

      if is_trading:
        logger.info(f"Market is active ({market_status}) - Starting automatic scan...")

        # 자동 스캔 실행
        result = await perform_stock_scan(source="auto")

        if result['success']:
          logger.info(
            f"Auto scan completed: {result['analyzed']}/{result['total_tickers']} analyzed, "
            f"{result['signals']} signals"
          )

      else:
        logger.info(f"Market is closed ({market_status}) - Standby mode")

      # Heartbeat 전송
      if should_send_heartbeat:
        if is_trading and 'result' in locals():
          status_emoji = {
            "PREMARKET": "🟡",
            "REGULAR": "✅",
            "AFTERHOURS": "🟠"
          }
          emoji = status_emoji.get(market_status, "✅")

          enhanced_heartbeat = (
            f"{emoji} Heartbeat #{heartbeat_counter}: {market_status}\n"
            f"⏱️ Cycles: {cycle_counter} (every 30min)\n"
            f"📊 Monitoring: {len(load_tickers())} tickers\n"
            f"✔️ Analyzed: {result['analyzed']}/{result['total_tickers']} stocks\n"
            f"🎯 Signals: {result['signals']} generated\n"
            f"{time_info}"
          )
          await send_telegram_message(enhanced_heartbeat)
          logger.info(f"Enhanced heartbeat #{heartbeat_counter} sent")
        else:
          await send_heartbeat(heartbeat_counter, market_status)

    except Exception as e:
      logger.error(f"Error in main loop: {e}")
      error_message = f"❌ Error in monitoring loop (cycle #{cycle_counter}): {str(e)}"
      try:
        await send_telegram_message(error_message)
      except:
        pass

    next_check_time = (datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')
    logger.info(f"Waiting 30 minutes until next check... (Next: {next_check_time})")
    await asyncio.sleep(check_interval)


async def main():
  """메인 함수 - 봇과 모니터링을 동시 실행"""
  # 로그 디렉토리 확인
  ensure_log_directory()

  logger.info("Starting US Stock Market Monitor with Telegram Bot")

  # 텔레그램 봇과 모니터링을 동시에 실행
  await asyncio.gather(
    start_telegram_bot(),
    monitor_stocks()
  )


if __name__ == '__main__':
  asyncio.run(main())