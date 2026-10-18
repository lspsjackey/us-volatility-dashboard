import sys, re
import pandas as pd
from finvizfinance.quote import finvizfinance

ticker = (sys.argv[1] if len(sys.argv) > 1 else input("請輸入美股代號（例如 MU, NVDA, COHR）：")).strip().upper()
if not ticker: ticker = "MU"

print(f"\n🔍 正在向華爾街數據庫抓取 {ticker} 各大投行的最新目標價與評級動態...")

try:
    stock = finvizfinance(ticker)
    df = stock.ticker_outer_ratings()

    if df is not None and not df.empty:
        # 欄位通常為 Date, Status, Outer, Rating, Price
        date_col = next((c for c in df.columns if 'date' in c.lower()), df.columns[0])
        firm_col = next((c for c in df.columns if 'outer' in c.lower() or 'firm' in c.lower() or 'analyst' in c.lower()), df.columns[2])
        action_col = next((c for c in df.columns if 'status' in c.lower() or 'action' in c.lower()), df.columns[1])
        rating_col = next((c for c in df.columns if 'rating' in c.lower()), df.columns[3])
        price_col = next((c for c in df.columns if 'price' in c.lower()), df.columns[4])

        # 數值解析：從 "$950 -> $1100" 或 "$1200" 中萃取最新目標價
        def parse_target(val):
            if pd.isna(val) or not str(val).strip(): return None
            s = str(val).replace('$', '').replace(',', '').strip()
            if '->' in s:
                s = s.split('->')[-1].strip()
            m = re.search(r'(\d+(\.\d+)?)', s)
            return float(m.group(1)) if m else None

        df['target_num'] = df[price_col].apply(parse_target)
        df_valid = df.dropna(subset=['target_num']).copy()

        # 每家投行只取最新一筆
        df_latest = df_valid.sort_values(date_col, ascending=False).groupby(firm_col).first().reset_index()
        df_sorted = df_latest.sort_values('target_num', ascending=False)

        highest = df_sorted.iloc[0]
        lowest = df_sorted.iloc[-1]

        print("\n" + "=" * 70)
        print(f"🎯 {ticker} 華爾街各大投行目標價極值天花板與地板")
        print("=" * 70)
        print(f"🏆 最高目標價：${highest['target_num']:.2f} ── 【{highest[firm_col]}】 (評級: {highest[rating_col]}, {str(highest[date_col])[:10]})")
        print(f"🛡️ 最低目標價：${lowest['target_num']:.2f} ── 【{lowest[firm_col]}】 (評級: {lowest[rating_col]}, {str(lowest[date_col])[:10]})")
        print(f"📊 覆蓋投行總數：{len(df_sorted)} 家機構")
        print("=" * 70)

        print(f"\n📋 各大投行最新目標價排行榜（由高到低排序）：\n")
        print(f"{'排名':<4} | {'券商投行機構 (Firm)':<22} | {'最新目標價':<10} | {'最新評級':<12} | {'調整動作':<12} | {'發布日期'}")
        print("-" * 85)

        rank = 1
        for _, r in df_sorted.iterrows():
            firm = str(r[firm_col])[:20]
            tgt = f"${r['target_num']:.1f}"
            rating = str(r.get(rating_col, '-'))[:10]
            action = str(r.get(action_col, '-'))[:10]
            dt = str(r[date_col])[:10]
            print(f"#{rank:<3} | {firm:<22} | {tgt:<10} | {rating:<12} | {action:<12} | {dt}")
            rank += 1

        print("=" * 85 + "\n")
    else:
        print(f"⚠️ 查無 {ticker} 的投行目標價數據。")

except Exception as e:
    print(f"❌ 查詢失敗：{e}")
