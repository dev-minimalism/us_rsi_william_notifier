import asyncio
import warnings
from datetime import datetime, time, timedelta

import pytz
from yahooquery import Ticker

from logger.logger import logger
from message.telegram_message import send_telegram_message
from tech_indicator.indicator import calculate_rsi, calculate_williams_r, \
  generate_signals

warnings.simplefilter(action='ignore', category=FutureWarning)


def is_us_market_open():
  """미국 주식 시장이 열렸는지 확인 (한국 시간 기준) - 프리마켓 포함"""
  # 한국 시간과 미국 동부시간 설정
  korea_tz = pytz.timezone('Asia/Seoul')
  us_eastern_tz = pytz.timezone('US/Eastern')

  # 현재 한국 시간
  korea_now = datetime.now(korea_tz)

  # 한국 시간을 미국 동부시간으로 변환
  us_now = korea_now.astimezone(us_eastern_tz)

  # 주말 확인 (토요일=5, 일요일=6)
  if us_now.weekday() in [5, 6]:
    korea_time_str = korea_now.strftime('%Y-%m-%d %H:%M:%S KST')
    us_time_str = us_now.strftime('%Y-%m-%d %H:%M:%S EST')
    time_info = f"Korea: {korea_time_str}, US: {us_time_str}, Market: WEEKEND"
    return False, time_info, "WEEKEND"

  # 미국 시장 시간 설정
  premarket_start = time(4, 0)    # 프리마켓 시작: 오전 4:00 (동부시간)
  market_open = time(9, 30)       # 정규장 시작: 오전 9:30 (동부시간)
  market_close = time(16, 0)      # 정규장 종료: 오후 4:00 (동부시간)
  afterhours_end = time(20, 0)    # 애프터아워 종료: 오후 8:00 (동부시간)

  current_time = us_now.time()

  # 시장 상태 판단
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

  # 한국 시간으로 변환하여 로그용 정보 제공
  korea_time_str = korea_now.strftime('%Y-%m-%d %H:%M:%S KST')
  us_time_str = us_now.strftime('%Y-%m-%d %H:%M:%S EST')

  time_info = f"Korea: {korea_time_str}, US: {us_time_str}, Market: {market_status}"

  return is_trading, time_info, market_status


async def send_heartbeat(counter, market_status="CLOSED"):
  """정기적인 heartbeat 메시지 전송"""
  is_trading, time_info, status = is_us_market_open()

  # 시장 상태별 다른 heartbeat 메시지
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
  tickers = [
    'NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL',  # 1-5위
    'META', 'AVGO', 'BRK.B', 'TSLA', 'TSM',   # 6-10위
    'JPM', 'WMT', 'LLY', 'ORCL', 'V',         # 11-15위
    'NFLX', 'MA', 'XOM', 'COST', 'JNJ',       # 16-20위
    'HD', 'PG', 'SAP', 'PLTR', 'BAC',         # 21-25위
    'ABBV', 'ASML', 'NVO', 'KO', 'GE',        # 26-30위
    'PM', 'CSCO', 'UNH', 'BABA', 'CVX',       # 31-35위
    'IBM', 'TMUS', 'WFC', 'AMD', 'CRM',       # 36-40위
    'NVS', 'ABT', 'MS', 'TM', 'AZN',          # 41-45위
    'AXP', 'LIN', 'HSBC', 'MCD', 'DIS'        # 46-50위
  ]

  period = 14
  check_interval = 3600  # 1시간 (3600초)
  last_alert = {}
  heartbeat_counter = 0

  # 시작 메시지
  is_trading, time_info, market_status = is_us_market_open()
  start_message = f"🚀 Trading bot with RSI and Williams %R started!\n{time_info}"

  logger.info("Trading bot with RSI and Williams %R started.")
  await send_telegram_message(start_message)

  while True:
    try:
      heartbeat_counter += 1

      # 현재 시장 상태 확인
      is_trading, time_info, market_status = is_us_market_open()
      logger.info(f"Market status check: {time_info}")

      if is_trading:
        logger.info(f"Market is active ({market_status}) - Starting stock analysis...")

        # 프리마켓/애프터아워는 실시간 데이터 제한이 있을 수 있음을 로그에 기록
        if market_status in ["PREMARKET", "AFTERHOURS"]:
          logger.info(f"Note: {market_status} data may have limitations")

        # 한 번에 모든 종목 가져오기
        tickers_obj = Ticker(tickers)
        df = tickers_obj.history(period='3mo', interval='1d')

        if df.empty:
          logger.warning("No data returned for any ticker.")
          await send_heartbeat(heartbeat_counter, market_status)
          await asyncio.sleep(check_interval)
          continue

        # 분석된 종목 수 카운터
        analyzed_count = 0
        signal_count = 0

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

            # 매수 알림 - 시장 상태 표시 추가
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

            # 매도 알림 - 시장 상태 표시 추가
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

        # 분석 완료 로그
        logger.info(f"Analysis completed: {analyzed_count}/{len(tickers)} stocks analyzed, {signal_count} signals generated")

        # 분석 완료 후 로그만 기록
        logger.info(f"Stock analysis completed for heartbeat #{heartbeat_counter}")

      else:
        # 시장이 닫힌 상태
        logger.info(f"Market is closed ({market_status}) - Standby mode")

      # 마켓 상태에 상관없이 무조건 1시간마다 heartbeat 전송
      if is_trading:
        # 시장별 이모지 설정
        status_emoji = {
          "PREMARKET": "🟡",
          "REGULAR": "✅",
          "AFTERHOURS": "🟠"
        }
        emoji = status_emoji.get(market_status, "✅")

        enhanced_heartbeat = f"{emoji} Heartbeat #{heartbeat_counter}: {market_status}\n📊 Analyzed: {analyzed_count if 'analyzed_count' in locals() else 0}/{len(tickers)} stocks\n🎯 Signals: {signal_count if 'signal_count' in locals() else 0} generated\n{time_info}"
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

    # 1시간 대기
    next_check_time = (datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')
    logger.info(f"Waiting 1 hour until next check... (Next check: {next_check_time})")
    await asyncio.sleep(check_interval)


# 비동기 루프 실행
if __name__ == '__main__':
  logger.info("Starting US Stock Market Monitor (Korea Time Zone)")
  asyncio.run(monitor_stocks())
