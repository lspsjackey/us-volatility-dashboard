import json, os
import pandas as pd
from openbb import obb

print("🔍 正在從 CBOE 抓取美光 (MU) 完整期權鏈數據，請稍候...")

# 抓取 CBOE 期權鏈
try:
    chains = obb.cboe.options.chains(symbol="MU")
except Exception:
    chains = obb.derivatives.options.chains(symbol="MU", provider="cboe")

df = chains.to_dataframe()

# 自動偵測關鍵欄位
strike_col = next((c for c in df.columns if "strike" in c.lower()), "strike")
iv_col = next((c for c in df.columns if "implied_volatility" in c.lower() or c.lower() == "iv"), "implied_volatility")
exp_col = next((c for c in df.columns if "expiration" in c.lower()), "expiration")
type_col = next((c for c in df.columns if "type" in c.lower() or "side" in c.lower()), "option_type")

# 清理數值格式
df[strike_col] = pd.to_numeric(df[strike_col], errors='coerce')
df[iv_col] = pd.to_numeric(df[iv_col], errors='coerce')
df = df.dropna(subset=[strike_col, iv_col])

# 取最近的一個到期日
available_expirations = sorted(df[exp_col].unique())
nearest_exp = available_expirations[0]
df_near = df[df[exp_col] == nearest_exp].sort_values(strike_col)

# 篩選 Call 買權來繪製波動率曲線
df_calls = df_near[df_near[type_col].astype(str).str.lower().str.contains("call|c")]

chart_strikes = df_calls[strike_col].tolist()
chart_ivs = (df_calls[iv_col] * 100).round(2).tolist()  # 轉成百分比顯示

print(f"\n📊 美光 (MU) 數據獲取成功！最近到期日：{nearest_exp}")
print(f"📈 涵蓋履約價範圍：${df_near[strike_col].min()} ~ ${df_near[strike_col].max()}")

# 產生網頁報表
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>美光 (MU) 期權隱含波動率 (IV)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f8f9fa; padding: 25px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; max-width: 960px; margin: 0 auto; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
        h2 {{ color: #1a1a1a; margin-top: 0; }}
        p {{ color: #666; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 25px; font-size: 13px; }}
        th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #eee; }}
        th {{ background: #0f172a; color: white; }}
        th:first-child, td:first-child {{ text-align: left; }}
        tr:hover {{ background: #f1f5f9; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡️ 美光 (Micron - MU) 期權隱含波動率（IV 微笑曲線）</h2>
        <p>到期日：<b>{nearest_exp}</b> ｜ 數據來源：CBOE（芝加哥期權交易所）</p>
        <canvas id="ivChart" height="110"></canvas>
        
        <h3 style="margin-top: 35px; color: #333;">📋 最近到期日履約價與 IV 列表（前 25 筆）</h3>
        {df_near[[exp_col, type_col, strike_col, iv_col]].head(25).to_html(classes='table', index=False)}
    </div>
    <script>
        const ctx = document.getElementById('ivChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(chart_strikes)},
                datasets: [{{
                    label: 'Call 隱含波動率 (IV %)',
                    data: {json.dumps(chart_ivs)},
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            label: function(ctx) {{ return ' 隱含波動率：' + ctx.parsed.y + '%'; }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ title: {{ display: true, text: '履約價 Strike ($)' }} }},
                    y: {{ title: {{ display: true, text: '隱含波動率 IV (%)' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

with open("mu_options.html", "w", encoding="utf-8") as f:
    f.write(html_content)

os.system("open mu_options.html")
print("✅ 已成功產出並自動在瀏覽器打開 mu_options.html！")
