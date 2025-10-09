"""
주식 스캔 공통 모듈
메인 봇과 텔레그램 명령어 봇에서 공통으로 사용
"""
from yahooquery import Ticker
from tech_indicator.indicator import calculate_rsi, calculate_williams_r, generate_signals
from logger.logger import logger


async def scan_stocks(tickers, period=14):
  """
  주식 스캔 실행

  Args:
    tickers: 티커 리스트
    period: RSI/Williams %R 계산 기간

  Returns:
    dict: {
      'analyzed_count': 분석된 종목 수,
      'signal_count': 신호 발생 수,
      'buy_signals': 매수 신호 리스트,
      'sell_signals': 매도 신호 리스트,
      'errors': 에러 발생 종목 리스트
    }
  """
  if not tickers:
    logger.warning("No tickers to scan")
    return {
      'analyzed_count': 0,
      'signal_count': 0,
      'buy_signals': [],
      'sell_signals': [],
      'errors': []
    }

  logger.info(f"Starting scan for {len(tickers)} tickers...")

  # 결과 저장
  analyzed_count = 0
  signal_count = 0
  buy_signals = []
  sell_signals = []
  errors = []

  try:
    # 한 번에 모든 종목 가져오기
    tickers_obj = Ticker(tickers)
    df = tickers_obj.history(period='3mo', interval='1d')

    if df.empty:
      logger.warning("No data returned for any ticker")
      return {
        'analyzed_count': 0,
        'signal_count': 0,
        'buy_signals': [],
        'sell_signals': [],
        'errors': ['No data available']
      }

    # 종목별로 데이터 분리 및 분석
    for stock_ticker in tickers:
      try:
        stock_data = df[df.index.get_level_values(0) == stock_ticker].copy()

        if stock_data.empty:
          logger.warning(f"No data available for {stock_ticker}")
          errors.append(f"{stock_ticker}: No data")
          continue

        # 인덱스 정리
        stock_data.reset_index(inplace=True)
        stock_data.set_index('date', inplace=True)

        # 지표 계산
        stock_data['Williams %R'] = calculate_williams_r(stock_data, period)
        stock_data['RSI'] = calculate_rsi(stock_data, period)

        # 데이터 유효성 확인
        if stock_data[['Williams %R', 'RSI']].isna().all(axis=None):
          logger.warning(f"{stock_ticker}: Indicator data is not valid")
          errors.append(f"{stock_ticker}: Invalid indicators")
          continue

        analyzed_count += 1

        # 신호 생성
        buy_signal_series, sell_signal_series = generate_signals(
          stock_data['Williams %R'], stock_data['RSI']
        )

        latest_date = stock_data.index[-1]
        williams_r_value = stock_data.loc[latest_date, 'Williams %R']
        rsi_value = stock_data.loc[latest_date, 'RSI']
        close_price = stock_data.loc[latest_date, 'close']

        # 매수 신호
        if buy_signal_series.iloc[-1]:
          signal_info = {
            'ticker': stock_ticker,
            'date': latest_date.strftime('%Y-%m-%d'),
            'williams_r': williams_r_value,
            'rsi': rsi_value,
            'price': close_price,
            'type': 'BUY'
          }
          buy_signals.append(signal_info)
          signal_count += 1
          logger.info(f"BUY signal detected for {stock_ticker}")

        # 매도 신호
        if sell_signal_series.iloc[-1]:
          signal_info = {
            'ticker': stock_ticker,
            'date': latest_date.strftime('%Y-%m-%d'),
            'williams_r': williams_r_value,
            'rsi': rsi_value,
            'price': close_price,
            'type': 'SELL'
          }
          sell_signals.append(signal_info)
          signal_count += 1
          logger.info(f"SELL signal detected for {stock_ticker}")

      except Exception as e:
        logger.error(f"Error processing {stock_ticker}: {e}")
        errors.append(f"{stock_ticker}: {str(e)}")

  except Exception as e:
    logger.error(f"Error in scan_stocks: {e}")
    errors.append(f"General error: {str(e)}")

  logger.info(f"Scan completed: {analyzed_count}/{len(tickers)} analyzed, {signal_count} signals")

  return {
    'analyzed_count': analyzed_count,
    'signal_count': signal_count,
    'buy_signals': buy_signals,
    'sell_signals': sell_signals,
    'errors': errors
  }


def format_signal_message(signal):
  """신호 정보를 텔레그램 메시지 형식으로 변환"""
  if signal['type'] == 'BUY':
    emoji = '🟢'
  else:
    emoji = '🔴'

  message = (
    f"{emoji} [{signal['type']} SIGNAL] {signal['ticker']}\n"
    f"📅 Date: {signal['date']}\n"
    f"📊 Williams %R: {signal['williams_r']:.2f}\n"
    f"📊 RSI: {signal['rsi']:.2f}\n"
    f"💰 Price: ${signal['price']:.2f}"
  )

  return message