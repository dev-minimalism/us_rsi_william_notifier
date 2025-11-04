import pandas as pd
import warnings
import os
from datetime import datetime
from yahooquery import Ticker

warnings.simplefilter(action='ignore', category=FutureWarning)


# 윌리엄 %R 계산 함수
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


def save_results_to_files(results_df, total_profit, total_return_rate,
    annualized_return, year_avg_returns,
    start_date, end_date, initial_cash, tickers,
    output_dir="output_files"):
  """백테스트 결과를 파일로 저장하는 함수"""

  # 출력 디렉토리 생성
  if not os.path.exists(output_dir):
    os.makedirs(output_dir)

  # 현재 시간을 파일명에 추가
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

  # 1. CSV 파일로 상세 결과 저장
  csv_filename = f"{output_dir}/backtest_results_{timestamp}.csv"
  results_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
  print(f"상세 결과가 저장되었습니다: {csv_filename}")

  # 2. 텍스트 파일로 요약 보고서 저장
  txt_filename = f"{output_dir}/backtest_summary_{timestamp}.txt"

  with open(txt_filename, 'w', encoding='utf-8') as f:
    f.write("=== 백테스트 결과 요약 보고서 ===\n")
    f.write(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    f.write("=== 백테스트 설정 ===\n")
    f.write(f"대상 종목: {', '.join(tickers)}\n")
    f.write(f"백테스트 기간: {start_date} ~ {end_date}\n")
    f.write(f"종목당 초기 투자금액: {initial_cash:,} USD\n")
    f.write(f"총 투자 종목 수: {len(tickers)}개\n\n")

    f.write("=== 전체 성과 ===\n")
    f.write(f"총 초기 투자금액: {len(tickers) * initial_cash:,} USD\n")
    f.write(f"총 최종 가치: {len(tickers) * initial_cash + total_profit:,.2f} USD\n")
    f.write(f"총 수익: {total_profit:,.2f} USD\n")
    f.write(f"총 수익률: {total_return_rate:.2f}%\n")
    f.write(f"연평균 수익률: {annualized_return:.2f}%\n\n")

    f.write("=== 연도별 평균 수익률 ===\n")
    for year, avg_return in sorted(year_avg_returns.items()):
      f.write(f"{year}년: {avg_return:.2f}%\n")
    f.write("\n")

    f.write("=== 종목별 상세 결과 ===\n")
    for _, row in results_df.iterrows():
      f.write(f"{row['Ticker']}: ")
      f.write(f"투자금 {row['Initial Cash']:,} → 최종가치 {row['Final Value']:,.2f} ")
      f.write(f"(수익: {row['Profit']:+,.2f}, {row['Profit (%)']:+.2f}%)\n")

    f.write("\n=== 성과 분석 ===\n")
    profitable_stocks = len(results_df[results_df['Profit'] > 0])
    total_stocks = len(results_df)
    f.write(f"수익 종목 수: {profitable_stocks}/{total_stocks} ({profitable_stocks/total_stocks*100:.1f}%)\n")
    f.write(f"최고 수익 종목: {results_df.loc[results_df['Profit (%)'].idxmax(), 'Ticker']} ")
    f.write(f"({results_df['Profit (%)'].max():.2f}%)\n")
    f.write(f"최저 수익 종목: {results_df.loc[results_df['Profit (%)'].idxmin(), 'Ticker']} ")
    f.write(f"({results_df['Profit (%)'].min():.2f}%)\n")
    f.write(f"평균 종목별 수익률: {results_df['Profit (%)'].mean():.2f}%\n")

  print(f"요약 보고서가 저장되었습니다: {txt_filename}")

  # 3. Excel 파일로도 저장 (선택사항)
  try:
    excel_filename = f"{output_dir}/backtest_results_{timestamp}.xlsx"
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
      # 종목별 결과 시트
      results_df.to_excel(writer, sheet_name='종목별결과', index=False)

      # 요약 정보 시트
      summary_data = {
        '항목': ['총 초기 투자금액', '총 최종 가치', '총 수익', '총 수익률', '연평균 수익률'],
        '값': [f"{len(tickers) * initial_cash:,} USD",
              f"{len(tickers) * initial_cash + total_profit:,.2f} USD",
              f"{total_profit:,.2f} USD",
              f"{total_return_rate:.2f}%",
              f"{annualized_return:.2f}%"]
      }
      summary_df = pd.DataFrame(summary_data)
      summary_df.to_excel(writer, sheet_name='전체요약', index=False)

      # 연도별 수익률 시트
      yearly_df = pd.DataFrame(list(year_avg_returns.items()),
                               columns=['연도', '평균수익률(%)'])
      yearly_df.to_excel(writer, sheet_name='연도별수익률', index=False)

    print(f"Excel 파일이 저장되었습니다: {excel_filename}")
  except ImportError:
    print("Excel 저장을 위해서는 'openpyxl' 라이브러리가 필요합니다.")

  return csv_filename, txt_filename


def backtest_strategy(tickers, start_date, end_date, initial_cash=1000,
    buy_threshold=-80, sell_threshold=-20):
  results = []
  year_returns = {}
  total_initial_cash = len(tickers) * initial_cash
  total_final_value = 0

  tickers_data = Ticker(tickers)

  for ticker in tickers:
    print(f"Processing {ticker}...")
    try:
      df = tickers_data.history(start=start_date, end=end_date, interval='1d')
    except Exception as e:
      print(f"Error downloading {ticker}: {e}")
      continue

    if isinstance(df, pd.DataFrame):
      df = df[df.index.get_level_values(0) == ticker].copy()
    else:
      print(f"No data for {ticker}. Skipping...")
      continue

    if df.empty:
      print(f"No data for {ticker}. Skipping...")
      continue

    df.reset_index(inplace=True)
    df.set_index('date', inplace=True)

    df['Williams %R'] = calculate_williams_r(df)
    df['RSI'] = calculate_rsi(df)

    buy_signals = (df['Williams %R'] < buy_threshold) & (df['RSI'] < 40)
    sell_signals = (df['Williams %R'] > sell_threshold) & (df['RSI'] > 70)

    cash = initial_cash
    position = 0
    year_initial_balance = {}
    year_final_balance = {}

    for i in range(len(df)):
      current_year = df.index[i].year
      close_price = df['close'].iloc[i].item()

      if current_year not in year_initial_balance:
        year_initial_balance[current_year] = cash + (
          position * close_price if position > 0 else 0)

      if buy_signals.iloc[i] and cash > 0:
        position = cash / close_price
        cash = 0
        print(
            f"{df.index[i].strftime('%Y-%m-%d')} BUY {ticker} at {close_price:.2f}")

      if sell_signals.iloc[i] and position > 0:
        cash = position * close_price
        position = 0
        print(
            f"{df.index[i].strftime('%Y-%m-%d')} SELL {ticker} at {close_price:.2f}")

      year_final_balance[current_year] = cash + (
        position * close_price if position > 0 else 0)

    final_value = cash + (
      position * df['close'].iloc[-1].item() if position > 0 else 0)
    profit = final_value - initial_cash
    total_final_value += final_value

    results.append({
      'Ticker': ticker,
      'Initial Cash': initial_cash,
      'Final Value': final_value,
      'Profit': profit,
      'Profit (%)': (profit / initial_cash) * 100
    })

    for year in year_initial_balance:
      year_profit = year_final_balance[year] - year_initial_balance[year]
      year_return = (year_profit / year_initial_balance[year]) * 100
      if year not in year_returns:
        year_returns[year] = []
      year_returns[year].append(year_return)

  results_df = pd.DataFrame(results)
  total_profit = total_final_value - total_initial_cash
  total_return_rate = (total_profit / total_initial_cash) * 100

  start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
  end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")
  investment_period_years = (end_date_dt - start_date_dt).days / 365.25
  annualized_return = ((1 + total_return_rate / 100) ** (
      1 / investment_period_years) - 1) * 100

  year_avg_returns = {year: sum(returns) / len(returns) for year, returns in
                      year_returns.items()}

  print("\n=== Overall Performance ===")
  print(f"Total Initial Cash: {total_initial_cash:_} USD")
  print(f"Total Final Value: {total_final_value:_} USD")
  print(f"Total Profit: {total_profit:_} USD")
  print(f"Total Return Rate: {total_return_rate:.2f}%")
  print(f"Annualized Return: {annualized_return:.2f}%")
  print("\n=== Yearly Returns ===")
  for year, avg_return in year_avg_returns.items():
    print(f"{year}: {avg_return:.2f}%")

  return results_df, total_profit, total_return_rate, annualized_return, year_avg_returns


# 실행
if __name__ == "__main__":
  tickers = [
    # 'NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL',  # 1-5위
    # 'META', 'AVGO', 'BRK.B', 'TSLA', 'TSM',   # 6-10위
    # 'JPM', 'WMT', 'LLY', 'ORCL', 'V',         # 11-15위
    # 'NFLX', 'MA', 'XOM', 'COST', 'JNJ',       # 16-20위
    # 'HD', 'PG', 'SAP', 'PLTR', 'BAC',         # 21-25위
    # 'ABBV', 'ASML', 'NVO', 'KO', 'GE',        # 26-30위
    # 'PM', 'CSCO', 'UNH', 'BABA', 'CVX',       # 31-35위
    # 'IBM', 'TMUS', 'WFC', 'AMD', 'CRM',       # 36-40위
    # 'NVS', 'ABT', 'MS', 'TM', 'AZN',          # 41-45위
    # 'AXP', 'LIN', 'HSBC', 'MCD', 'DIS'        # 46-50위
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "NVDA",
    "AMD",
    "AVGO",
    "TSLA",
    "NFLX",
    "CRM",
    "ADBE",
    "PLTR",
    "SNOW",
    "CRWD",
    "NET",
    "DDOG",
    "ZS",
    "COIN",
    "SQ",
    "PYPL",
    "SHOP",
    "TSM",
    "JPM",
    "WMT",
    "LLY",
    "ORCL",
    "V",
    "MA",
    "XOM",
    "COST",
    "JNJ",
    "HD",
    "PG",
    "SAP",
    "BAC",
    "ABBV",
    "ASML",
    "NVO",
    "KO",
    "GE",
    "PM",
    "CSCO",
    "UNH",
    "BABA",
    "CVX",
    "IBM",
    "TMUS",
    "WFC",
    "NVS",
    "ABT",
    "MS",
    "TM",
    "AZN",
    "AXP",
    "LIN",
    "HSBC",
    "MCD",
    "DIS",
    "HOOD",
    "UMC",
    "BMNR",
    "CRCL",
    "RDDT",
    "QUBT",
    "WBTN",
    "CRWV",
    "VRT",
    "LMT",
    "BLK",
    "RBLX",
    "FIG",
    "SMR",
    "CPNG",
    "CRSP",
    "SOUN",
    "TLN",
    "SERV",
    "RZLV",
    "TTWO",
    "RKLB",
    "ASTS",
    "IREN",
    "RGTI",
    "MP",
    "CLS",
    "MELI"
  ]

  start_date = "2023-01-01"
  end_date = "2025-01-05"
  initial_cash = 1000

  results, total_profit, total_return_rate, annualized_return, year_avg_returns = backtest_strategy(
      tickers, start_date, end_date, initial_cash)

  print("\n=== Backtest Results ===")
  print(results)

  print("\n=== Final Summary ===")
  print(f"Total Profit: {total_profit:.2f} USD")
  print(f"Overall Return: {total_return_rate:.2f}%")
  print(f"Annualized Return: {annualized_return:.2f}%")

  # 결과를 파일로 저장
  print("\n=== Saving Results to Files ===")
  csv_file, txt_file = save_results_to_files(
      results, total_profit, total_return_rate,
      annualized_return, year_avg_returns,
      start_date, end_date, initial_cash, tickers
  )

  print(f"\n백테스트가 완료되었습니다!")
  print(f"결과 파일들이 현재 디렉토리의 'output_files' 폴더에 저장되었습니다.")
