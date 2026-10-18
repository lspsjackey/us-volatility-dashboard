import sys
import pandas as pd
import yfinance as yf

# 支援傳入股票代號，預設為 MU
ticker = (sys.argv[1] if len(sys.argv) > 1 else input("請輸入股票代號（例如 MU, NVDA, COHR）：")).strip().upper()
if not ticker: ticker = "MU"

print(f"\n🔍 正在向華爾街數據庫抓取 {ticker} 各大投行最新升降級與目標價動態...")

try:
    t = yf.Ticker(ticker)
    
    # 抓取目標價總覽
    info = t.info
    mean_tgt = info.get('targetMeanPrice', 'N/A')
    high_tgt = info.get('targetHighPrice', 'N/A')
    low_tgt = info.get('targetLowPrice', 'N/A')
    current_p = info.get('currentPrice', 'N/A')

    print("\n" + "=" * 65)
    print(f"🎯 {ticker} 華爾街目標價總覽：目前市價 ${current_p}")
    print(f" • 平均目標價：${mean_tgt} ｜ 最低：${low_tgt} ｜ 最高：${high_tgt}")
    print("=" * 65)

    # 抓取各大投行具體升降級歷史
    df = t.upgrades_downgrades

    if df is not None and not df.empty:
        # 依日期由新到舊排序，取最新 15 筆
        df_recent = df.sort_index(ascending=False).head(15).copy()

        # 動作代碼轉換為直觀中文
        action_map = {
            "up": "🔼 升級 (Upgrade)",
            "down": "🔻 降級 (Downgrade)",
            "main": "⏸️ 維持 (Maintain)",
            "reit": "🔄 重申 (Reiterate)",
            "init": "🆕 初次評級 (Initiate)"
        }

        print(f"\n📋 各大投行最近 15 次評級調整明細：\n")
        print(f"{'發布日期':<12} | {'券商機構 (Firm)':<20} | {'調整動作':<16} | {'評級變更 (From ➜ To)'}")
        print("-" * 75)

        for idx, row in df_recent.iterrows():
            date_str = str(idx)[:10]
            firm = str(row.get('Firm', 'Unknown'))[:18]
            action_raw = str(row.get('Action', '')).lower()
            action = action_map.get(action_raw, action_raw.capitalize())
            
            from_grade = str(row.get('FromGrade', '')).strip()
            to_grade = str(row.get('ToGrade', '')).strip()
            
            if from_grade and from_grade != "nan" and from_grade != to_grade:
                grade_change = f"{from_grade} ➜ {to_grade}"
            else:
                grade_change = f"{to_grade}"

            print(f"{date_str:<12} | {firm:<20} | {action:<16} | {grade_change}")
        
        print("=" * 75 + "\n")
    else:
        print(f"⚠️ 查無 {ticker} 的投行升降級紀錄。")

except Exception as e:
    print(f"❌ 查詢失敗：{e}")
