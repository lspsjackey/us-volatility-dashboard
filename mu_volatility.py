from openbb import obb

print("🔍 正在向 CBOE 抓取美光 (MU) 波動率數據...")
q = obb.cboe.equity.quote(symbol="MU", provider="cboe").to_dataframe()

def fmt(v):
    if v is None or str(v) == 'nan': return 'N/A'
    v = float(v)
    return f'{v*100:.2f}%' if v < 2.0 else f'{v:.2f}%'

name = q["name"].iloc[0] if "name" in q else "Micron Technology"
bid = q["bid"].iloc[0] if "bid" in q else "N/A"

print("\n" + "=" * 50)
print("📊 美光 (Micron - MU) 官方波動率數據總覽")
print("=" * 50)
print(f"公司名稱：{name}")
print(f"目前價格：${bid}")

print("\n【🔮 隱含波動率 (IV) - 市場預期未來的劇烈程度】")
for d in [30, 60, 90]:
    if f"iv{d}" in q:
        print(f"  • {d} 天期預期年化波動率：{fmt(q[f'iv{d}'].iloc[0])}")

print("\n【📜 歷史波動率 (HV) - 過去實際股價的震盪幅度】")
for d in [30, 60, 90]:
    if f"hv{d}" in q:
        print(f"  • 過去 {d} 天實際年化波動率：{fmt(q[f'hv{d}'].iloc[0])}")

if "iv90_annual_high" in q and "iv90_annual_low" in q:
    print("\n【📈 過去一年 (52週) 波動率極值】")
    print(f"  • 52 週 IV 最高點：{fmt(q['iv90_annual_high'].iloc[0])}")
    print(f"  • 52 週 IV 最低點：{fmt(q['iv90_annual_low'].iloc[0])}")
print("=" * 50 + "\n")
