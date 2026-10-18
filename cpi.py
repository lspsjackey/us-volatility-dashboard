import pandas as pd
import json, os

print("正在從美國聯準會 (FRED) 抓取 CPI 最新數據...")

# 下載官方 CPI 數據 (CPIAUCSL)
url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
df = pd.read_csv(url)
df.columns = ["date", "cpi"]
df["cpi"] = pd.to_numeric(df["cpi"], errors="coerce")
df = df.dropna()

# 篩選 2019 年至今的走勢
df_recent = df[df["date"] >= "2019-01-01"]
labels = json.dumps(df_recent["date"].tolist())
data = json.dumps(df_recent["cpi"].tolist())

# 建立乾淨的互動圖表
html_code = f"""
<html>
<head>
    <meta charset="utf-8">
    <title>美國 CPI 走勢圖</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f6f8; padding: 30px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; max-width: 900px; margin: 0 auto; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
        h2 {{ margin-top: 0; color: #1f2937; }}
        p {{ color: #6b7280; font-size: 14px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>📈 美國消費者物價指數（CPI）走勢 (2019 - 至今)</h2>
        <p>數據來源：美國勞工統計局 (BLS) / 聖路易斯聯邦準備銀行 (FRED)</p>
        <canvas id="cpiChart" height="120"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('cpiChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {labels},
                datasets: [{{
                    label: 'CPI 指數 (CPIAUCSL)',
                    data: {data},
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.08)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 2,
                    pointHoverRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                interaction: {{ intersect: false, mode: 'index' }},
                plugins: {{
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{ return ' 指數：' + context.parsed.y; }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ grid: {{ display: false }} }},
                    y: {{ grid: {{ color: '#f3f4f6' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

with open("cpi_chart.html", "w", encoding="utf-8") as f:
    f.write(html_code)

os.system("open cpi_chart.html")
print("已成功產出並在瀏覽器打開 cpi_chart.html！")
