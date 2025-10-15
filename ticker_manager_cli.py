#!/usr/bin/env python3
"""
티커 관리용 CLI 도구
텔레그램 없이 명령줄에서 직접 티커를 관리합니다.
"""
import os
import json
import sys
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
    return True
  except Exception as e:
    print(f"❌ Error saving tickers: {e}")
    return False


def add_ticker(ticker):
  """티커 추가"""
  ticker = ticker.upper()
  tickers = load_tickers()

  if ticker in tickers:
    print(f"ℹ️  {ticker} is already in the list")
    print(f"📊 Current tickers: {len(tickers)}")
    return

  # 티커 유효성 검증
  print(f"🔍 Validating {ticker}...")

  try:
    test_ticker = Ticker(ticker)
    test_data = test_ticker.history(period='5d', interval='1d')

    if test_data.empty:
      print(f"❌ {ticker} is not a valid ticker or has no data")
      return

    # 티커 추가
    tickers.append(ticker)

    if save_tickers(tickers):
      print(f"✅ Successfully added {ticker}")
      print(f"📊 Total tickers: {len(tickers)}")
    else:
      print(f"❌ Failed to save {ticker}")

  except Exception as e:
    print(f"❌ Error validating {ticker}: {e}")


def remove_ticker(ticker):
  """티커 삭제"""
  ticker = ticker.upper()
  tickers = load_tickers()

  if ticker not in tickers:
    print(f"ℹ️  {ticker} is not in the list")
    return

  tickers.remove(ticker)

  if save_tickers(tickers):
    print(f"✅ Successfully removed {ticker}")
    print(f"📊 Total tickers: {len(tickers)}")
  else:
    print(f"❌ Failed to save changes")


def list_tickers():
  """티커 목록 표시"""
  tickers = load_tickers()

  if not tickers:
    print("📭 No tickers in monitoring list")
    return

  print(f"\n📊 Monitoring {len(tickers)} tickers:\n")
  print("=" * 60)

  # 정렬하여 표시
  sorted_tickers = sorted(tickers)

  # 5개씩 한 줄에 표시
  for i in range(0, len(sorted_tickers), 5):
    line = sorted_tickers[i:i + 5]
    print(", ".join(f"{t:8}" for t in line))

  print("=" * 60)


def search_tickers(keyword):
  """티커 검색"""
  keyword = keyword.upper()
  tickers = load_tickers()

  matches = [t for t in tickers if keyword in t]

  if matches:
    print(f"\n🔍 Found {len(matches)} ticker(s) matching '{keyword}':")
    print(", ".join(matches))
  else:
    print(f"❌ No tickers found matching '{keyword}'")


def count_tickers():
  """티커 개수 표시"""
  tickers = load_tickers()
  print(f"📊 Currently monitoring {len(tickers)} ticker(s)")


def show_help():
  """도움말 표시"""
  help_text = """
📖 Ticker Manager CLI

Usage: python ticker_manager_cli.py [command] [arguments]

Commands:
  add TICKER       Add a new ticker
                   Example: python ticker_manager_cli.py add TSLA

  remove TICKER    Remove a ticker
                   Example: python ticker_manager_cli.py remove TSLA

  list             Show all monitored tickers
                   Example: python ticker_manager_cli.py list

  search KEYWORD   Search for tickers
                   Example: python ticker_manager_cli.py search AAPL

  count            Show total number of tickers
                   Example: python ticker_manager_cli.py count

  help             Show this help message

💡 Note: Changes take effect in the next monitoring cycle (within 1 hour)
"""
  print(help_text)


def main():
  """메인 함수"""
  if len(sys.argv) < 2:
    show_help()
    return

  command = sys.argv[1].lower()

  if command == "add":
    if len(sys.argv) < 3:
      print("❌ Usage: python ticker_manager_cli.py add TICKER")
      return
    add_ticker(sys.argv[2])

  elif command == "remove":
    if len(sys.argv) < 3:
      print("❌ Usage: python ticker_manager_cli.py remove TICKER")
      return
    remove_ticker(sys.argv[2])

  elif command == "list":
    list_tickers()

  elif command == "search":
    if len(sys.argv) < 3:
      print("❌ Usage: python ticker_manager_cli.py search KEYWORD")
      return
    search_tickers(sys.argv[2])

  elif command == "count":
    count_tickers()

  elif command == "help":
    show_help()

  else:
    print(f"❌ Unknown command: {command}")
    print("Use 'python ticker_manager_cli.py help' for usage information")


if __name__ == '__main__':
  main()