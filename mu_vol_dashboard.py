import json, os
import numpy as np
import pandas as pd
from openbb import obb

print("🔍 1/3 正在向 CBOE 抓取美光 (MU) 即時報價與波動率指標...")
q = obb.cboe.equity.quote(symbol="MU", provider="cboe").to_dataframe()

print("📈 2/3 正在抓取近一年歷史數據並計算 30 天滾動年化歷史波動率...")
hist = obb.cboe.equity.historical(symbol="MU", provider="cboe").to_dataframe()

print("⚡️ 3/3 正在抓取美光最新期權鏈數據...")
try:
    chains = obb.cboe.options.chains(symbol="MU")
except Exception:
    chains = obb.derivatives.options.chains(symbol="MU", provider="cboe")
df_chains = chains.to_dataframe()

# --- 1. 計算近一年歷史波動率走勢 ---
hist['close'] = pd.to_numeric(hist['close'], errors='coerce')
hist = hist.dropna(subset=['close']).tail(280).copy()
hist['return'] = hist['close'].pct_change()
# 30日滾動年化標準差 (歷史波動率 HV)
hist['vol_30d'] = hist['return'].rolling(window=30).std() * np.sqrt(252) * 100

hist_plot = hist.dropna(subset=['vol_30d']).copy()
dates = [str(d)[:10] for d in (hist_plot.index if 'date' not in hist_plot.columns else hist_plot['date'])]
prices = hist_plot['close'].round(2).tolist()
vols = hist_plot['vol_30d'].round(2).tolist()

# --- 2. 安全讀取數值 ---
def get_val(df, col):
    if col in df.columns and len(df[col]) > 0:
        val = df[col].iloc[0]
        if pd.notna(val):
            return val
    return None

def fmt_pct(val):
    if val is None or pd.isna(val): return 'N/A'
    v = float(val)
    return f"{v*100:.2f}%" if v < 2.0 else f"{v:.2f}%"

current_price = get_val(q, 'bid') or (prices[-1] if len(prices) > 0 else "N/A")
iv30 = fmt_pct(get_val(q, 'iv30'))
iv60 = fmt_pct(get_val(q, 'iv60'))
iv90 = fmt_pct(get_val(q, 'iv90'))
hv30 = fmt_pct(get_val(q, 'hv30'))
iv90_high = fmt_pct(get_val(q, 'iv90_annual_high'))
iv90_low = fmt_pct(get_val(q, 'iv90_annual_low'))

# --- 3. 整理期權鏈表格 ---
strike_col = next((c for c in df_chains.columns if "strike" in c.lower()), "strike")
iv_col = next((c for c in df_chains.columns if "implied_volatility" in c.lower() or c.lower() == "iv"), "implied_volatility")
exp_col = next((c for c in df_chains.columns if "expiration" in c.lower()), "expiration")
type_col = next((c for c in df_chains.columns if "type" in c.lower() or "side" in c.lower()), "option_type")
bid_col = next((c for c in df_chains.columns if "bid" in c.lower()), "bid")
ask_col = next((c for c in df_chains.columns if "ask" in c.lower()), "ask")

df_chains[strike_col] = pd.to_numeric(df_chains[strike_col], errors='coerce')
df_chains[iv_col] = pd.to_numeric(df_chains[iv_col], errors='coerce')
df_chains = df_chains.dropna(subset=[strike_col, iv_col])

available_exp = sorted(df_chains[exp_col].unique())
nearest_exp = available_exp[0]
df_near = df_chains[df_chains[exp_col] == nearest_exp].copy()

# 挑選平價附近的合約
ref_price = float(current_price) if current_price != "N/A" else 900.0
df_near['diff'] = (df_near[strike_col] - ref_price).abs()
table_data = df_near.sort_values('diff').head(24).sort_values(strike_col)

table_rows = ""
for _, r in table_data.iterrows():
    opt_type = str(r[type_col]).upper()
    badge_color = "#10b981" if "CALL" in opt_type or opt_type == "C" else "#ef4444"
    b_val = f"${float(r[bid_col]):.2f}" if bid_col in r and pd.notna(r[bid_col]) else "$0.00"
    a_val = f"${float(r[ask_col]):.2f}" if ask_col in r and pd.notna(r[ask_col]) else "$0.00"
    iv_val = f"{float(r[iv_col])*100:.2f}%" if iv_col in r and pd.notna(r[iv_col]) else "N/A"
    table_rows += f"""
    <tr>
        <td>{r[exp_col]}</td>
        <td><span style="background:{badge_color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{opt_type}</span></td>
        <td><b>${float(r[strike_col]):.1f}</b></td>
        <td>{b_val}</td>
        <td>{a_val}</td>
        <td style="color:#c084fc;font-weight:bold;">{iv_val}</td>
    </tr>
    """

# --- 4. 產生 HTML 儀表板 ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>美光 (MU) 波動率與期權分析戰情室</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 30px; margin: 0; }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 25px; border-bottom: 1px solid #334155; padding-bottom: 15px; }}
        h1 {{ margin: 0; font-size: 26px; color: #fff; }}
        .badge {{ background: #1e293b; color: #94a3b8; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .card {{ background: #1e293b; border-radius: 10px; padding: 18px; border: 1px solid #334155; }}
        .card-title {{ font-size: 13px; color: #94a3b8; margin-bottom: 8px; }}
        .card-val {{ font-size: 22px; font-weight: bold; color: #38bdf8; }}
        .chart-box {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 15px; }}
        th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; }}
        tr:hover {{ background: #334155; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 美光科技 (MU) 波動率與期權全景圖</h1>
                <span style="color:#94a3b8; font-size:14px;">數據來源：CBOE（芝加哥期權交易所）</span>
            </div>
            <div class="badge">即時參考價：<b>${current_price}</b></div>
        </div>

        <!-- 數據指標卡片 -->
        <div class="grid">
            <div class="card">
                <div class="card-title">🔮 30 天隱含波動率 (IV)</div>
                <div class="card-val" style="color:#c084fc;">{iv30}</div>
            </div>
            <div class="card">
                <div class="card-title">📜 30 天歷史波動率 (HV)</div>
                <div class="card-val" style="color:#38bdf8;">{hv30}</div>
            </div>
            <div class="card">
                <div class="card-title">📈 90 天 IV 預期</div>
                <div class="card-val" style="color:#a855f7;">{iv90}</div>
            </div>
            <div class="card">
                <div class="card-title">🎯 52 週 IV 歷史區間</div>
                <div class="card-val" style="font-size:16px; color:#facc15;">{iv90_low} ~ {iv90_high}</div>
            </div>
        </div>

        <!-- 近一年走勢圖 (雙軸: 股價 vs 波動率) -->
        <div class="chart-box">
            <h3 style="margin-top:0; color:#fff;">📈 美光過去一年「股價走勢 vs 30日年化波動率 (HV)」對照</h3>
            <canvas id="volChart" height="100"></canvas>
        </div>

        <!-- 期權鏈表格 -->
        <div class="chart-box">
            <h3 style="margin-top:0; color:#fff;">📋 最近到期日 ({nearest_exp}) 平價周邊期權鏈與 IV 表格</h3>
            <table>
                <thead>
                    <tr>
                        <th>到期日</th>
                        <th>類型</th>
                        <th>履約價 (Strike)</th>
                        <th>買價 (Bid)</th>
                        <th>賣價 (Ask)</th>
                        <th>隱含波動率 (IV)</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('volChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [
                    {{
                        label: '30日年化歷史波動率 (%)',
                        data: {json.dumps(vols)},
                        borderColor: '#c084fc',
                        backgroundColor: 'rgba(192, 132, 252, 0.1)',
                        borderWidth: 2,
                        yAxisID: 'yVol',
                        tension: 0.2,
                        pointRadius: 0
                    }},
                    {{
                        label: '美光收盤價 (USD)',
                        data: {json.dumps(prices)},
                        borderColor: '#38bdf8',
                        borderWidth: 2,
                        yAxisID: 'yPrice',
                        tension: 0.2,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                interaction: {{ mode: 'index', intersect: false }},
                scales: {{
                    x: {{ grid: {{ color: '#334155' }} }},
                    yVol: {{
                        type: 'linear',
                        position: 'left',
                        title: {{ display: true, text: '波動率 (%)', color: '#c084fc' }},
                        grid: {{ color: '#334155' }}
                    }},
                    yPrice: {{
                        type: 'linear',
                        position: 'right',
                        title: {{ display: true, text: '股價 (USD)', color: '#38bdf8' }},
                        grid: {{ drawOnChartArea: false }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

with open("mu_vol_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html_code)

os.system("open mu_vol_dashboard.html")
print("✅ 儀表板建置完成！已自動在瀏覽器打開 mu_vol_dashboard.html")
