# Williams %R 계산 함수
def calculate_williams_r(data, period=14):
  high = data['high'].rolling(window=period).max()
  low = data['low'].rolling(window=period).min()
  close = data['close']
  williams_r = -100 * ((high - close) / (high - low))
  return williams_r

# RSI 계산 함수
def calculate_rsi(data, period=14):
  delta = data['close'].diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
  rs = gain / loss
  rsi = 100 - (100 / (1 + rs))
  return rsi

# 매수/매도 신호 생성 함수
def generate_signals(williams_r, rsi, buy_threshold=-80, sell_threshold=-20):
  buy_signals = (williams_r < buy_threshold) & (rsi < 30)
  sell_signals = (williams_r > sell_threshold) & (rsi > 70)
  return buy_signals, sell_signals
