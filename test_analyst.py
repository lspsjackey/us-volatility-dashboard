import pandas as pd

print("\n🔍 正在向華爾街數據庫抓取美光 (MU) 分析師目標價與共識評級...")

data_printed = False

# 嘗試方式 1: 透過 OpenBB 官方標準接口
try:
    from openbb import obb
    res = obb.equity.estimates.consensus(symbol="MU", provider="yfinance")
    df = res.to_dataframe()
    print("\n" + "=" * 50)
    print("📊 美光 (Micron - MU) 華爾街分析師共識數據 (via OpenBB)")
    print("=" * 50)
    for col in df.columns:
        print(f" • {col} : {df[col].iloc[0]}")
    print("=" * 50 + "\n")
    data_printed = True
except Exception:
    pass

# 嘗試方式 2: 透過剛才已安裝好的 yfinance 引擎直連
if not data_printed:
    import yfinance as yf
    t = yf.Ticker("MU")
    info = t.info
    print("\n" + "=" * 50)
    print("📊 美光 (Micron - MU) 華爾街分析師目標價與評級 (via Yahoo Finance)")
    print("=" * 50)
    print(f" • 分析師總人數：{info.get('numberOfAnalystOpinions', 'N/A')} 位")
    print(f" • 綜合投資評級：{str(info.get('recommendationKey', 'N/A')).upper()}")
    print(f" • 評級分數 (1強烈買進 ~ 5強烈賣出)：{info.get('recommendationMean', 'N/A')}")
    print(f" • 華爾街平均目標價：${info.get('targetMeanPrice', 'N/A')}")
    print(f" • 中位數目標價：${info.get('targetMedianPrice', 'N/A')}")
    print(f" • 最高目標價：${info.get('targetHighPrice', 'N/A')}")
    print(f" • 最低目標價：${info.get('targetLowPrice', 'N/A')}")
    print(f" • 目前最新市價：${info.get('currentPrice', 'N/A')}")
    print("=" * 50 + "\n")
