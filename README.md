[![GoDoc](https://img.shields.io/badge/python-v3.12.4-lightblue)](https://www.python.org/)
[![GoDoc](https://img.shields.io/badge/yfinance-v0.2.51-green)](https://pypi.org/project/yfinance/)



# 소개
* 미 주식에 대해서 RSI + william r% 지표를 기반으로 매도 매수 텔레그램 알리미 초기 버전

## 실행 환경
* python virtual env 가 가능한 모든 OS
* telegram chat bot은 직접 만들어서 /config/config.py에 설정해야 함.


## 실행 방법
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
nohup python3 us-rsi-william-notifier.py > /dev/null 2>&1 &
```


## 백테스트 결과
* 기간 2022-01-05 ~ 2025-01-05

```
=== Overall Performance ===
Total Initial Cash: 14_000 USD
Total Final Value: 24_513.997630413818 USD
Total Profit: 10_513.997630413818 USD
Total Return Rate: 75.10%
Annualized Return: 32.10%

=== Yearly Returns ===
2023: 32.81%
2024: 28.02%
2025: 0.81%

=== Backtest Results ===
   Ticker  Initial Cash  Final Value       Profit  Profit (%)
0    AAPL          1000  1434.171864   434.171864   43.417186
1    NVDA          1000  3028.038773  2028.038773  202.803877
2    MSFT          1000  1437.078291   437.078291   43.707829
3    GOOG          1000  1649.140633   649.140633   64.914063
4    AMZN          1000  1923.699725   923.699725   92.369972
5    TSLA          1000  1720.329554   720.329554   72.032955
6    AVGO          1000  3489.632561  2489.632561  248.963256
7     LLY          1000  1611.513247   611.513247   61.151325
8     WMT          1000  1467.806862   467.806862   46.780686
9     JPM          1000  1556.076839   556.076839   55.607684
10    XOM          1000   904.407801   -95.592199   -9.559220
11   ORCL          1000  1555.285179   555.285179   55.528518
12   NFLX          1000  1680.931713   680.931713   68.093171
13    BAC          1000  1055.884588    55.884588    5.588459

=== Final Summary ===
Total Profit: 10514.00 USD
Overall Return: 75.10%
Annualized Return: 32.10%

```
