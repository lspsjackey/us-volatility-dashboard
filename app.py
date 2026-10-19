import math
import re

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from openbb import obb

st.set_page_config(page_title="⚡ 美股波動率戰情室", layout="wide", initial_sidebar_state="collapsed")

# 自訂樣式：精簡按鈕尺寸與垂直置中對齊，並優化指標數值自適應字體
st.markdown("""
<style>
    div[data-testid="stFormSubmitButton"] > button {
        height: 42px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 8px;
    }
    /* 確保高波動率數字（如 > 100%）在卡片內不被省略號 ... 截斷 */
    div[data-testid="stMetricValue"] {
        font-size: clamp(1.1rem, 1.45vw, 1.65rem) !important;
        white-space: nowrap !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ 美股波動率戰情室")
st.write("即時查詢 CBOE 官方 30天 隱含波動率 (IV)、30天 歷史波動率 (HV) 與最新期權鏈。")

# 1. FCN 結構與隱含波動率 (IV) 定價機制解說模組
with st.expander("🎯 什麼是FCN？", expanded=False):
    st.markdown(
        """FCN（Fixed Coupon Note）在金融工程結構上，本質為「固定收益票券」與「賣出賣權（Short Put Option）」的組合商品。

---

#### 1️⃣ 【合約架構】
假設標的股票目前市價為 **100 元**：  
投資人向發行機構提供承諾：  
> *「若合約存續期間標的價格跌破 **70 元（敲入保護價）**，投資人承諾依約以 **70 元**之約定價格受分配買進該股票。」*

---

#### 2️⃣ 【票息（Coupon）的本質】
市場上持有現貨的機構或部位具備避險需求，需要將「股價下行之尾部風險」轉移至市場。  
因為投資人承接了此項下行風險並提供流動性承諾，發行機構支付相對應的風險補償金——此即投資人定期領取之 **票息**。

---

#### 3️⃣ 【隱含波動率（IV）的定價機制】
隱含波動率（IV）代表期權市場依據供需，對標的資產在未來 **「價格波動幅度與不確定性」的量化評估**：
* **當 IV 較低（市場預期價格分佈收斂）**：標的觸及 70 元保護價的統計機率較低，避險轉移的市場成本較小，發行機構提供的年化票息相應偏低。
* **當 IV 較高（市場預期價格分佈發散）**：標的觸及 70 元保護價的統計機率顯著上升，市場對下行保護的定價更高，因此發行機構提供給投資人的年化票息會隨之提高。

---

#### 4️⃣ 【結算時的履約結果】
1. **標的未觸及保護門檻（全程維持在 70 元以上）**：無須履行買進義務，投資人領取全期約定之票息，本金以 **100% 現金全額返還**。
2. **標的跌破保護門檻（觸及 70 元且到期未能回升）**：投資人依然收取全期約定之票息，並依約定履行承諾，以 **70 元之約定折價價格轉換為股票現貨持有**。

---

> **📌 總結**：FCN 的票息本質上是「**承擔下行價格風險之風險溢價**」；而隱含波動率（IV）則是市場評估該波動幅度與事件機率的定價指標。"""
    )

# 1-2. 30天 隱含波動率 (IV) 與 30天 歷史波動率 (HV) 指標解說模組
with st.expander("🌊 什麼是波動率？", expanded=False):
    tab_vol_plain, tab_vol_academic = st.tabs(["💡 實戰判讀", "📘 數學定義"])

    with tab_vol_plain:
        st.markdown(
            """### 1️⃣ 一句話分清楚兩者差別
* **📈 30天 隱含波動率 (IV)（往前看未來）**：「**氣象預報**」—— 市場透過未來 30 天到期期權的成交價格，反推出大家**預期未來 30 天**這檔股票會有多震盪。
* **📊 30天 歷史波動率 (HV)（回頭看過去）**：「**過去一個月的實際天氣紀錄**」—— 統計這檔股票**過去 30 個交易日**每天實際漲跌的劇烈程度。

---

### 2️⃣ 為什麼這兩個 30 天指標，數值都有「年化（Annualized）」？
就像去銀行存 1 個月定存，銀行報給您的利率還是會寫「**年利率 2%**」（方便您跟 3 個月、1 年期商品比較）；金融市場為了讓不同天期（10 天、30 天、90 天）的 **IV** 與 **HV** 可以放在同一個天平上比較，**統一都換算成「一年期（252 個交易日）」的尺度來報價**。

> 💡 **實務上怎麼把報價還原成「未來 30 天的合理震盪範圍」？**  
> 只要把 **30天 隱含波動率 (IV)** **除以 $\\sqrt{12}$（約 `3.46`）**，就能算出**未來 30 天約有 68% 機率（1 個標準差）落在的漲跌幅範圍**：  
> * 例如某檔股票 **30天 隱含波動率 (IV) = `45%`**：  
>   * 代表市場預期**未來一年**股價約有 68% 的機率在 **±45%** 內波動。  
>   * 換算成**未來 30 天**：$45\\% \\div 3.46 \\approx \\mathbf{\\pm 13\\%}$（代表市場預期未來一個月股價大約在 **±13%** 範圍內擺動）。

---

### 3️⃣ 實戰對照表：用「IV vs HV」判斷現在發 FCN 划不划算
| 比較項目 | 📈 30天 隱含波動率 (IV) | 📊 30天 歷史波動率 (HV) |
| :--- | :--- | :--- |
| **時間方向** | **看未來 30 天**（市場預期） | **看過去 30 個交易日**（已發生的事實） |
| **數據來源** | CBOE 期權市場的買賣報價反推 | 過去 30 天每日收盤價報酬率的標準差（年化） |
| **對 FCN 的意義** | **直接決定現在下單 FCN 的票息高低** | **用來檢驗目前的 IV 報價是否「划算」** |

* 🟢 **當 30天 IV 明顯高於 30天 HV（例如 IV = 55%，HV = 38%）**：代表市場因為財報將至或短期事件而「過度緊張」，保險費偏貴 ➡️ **此時詢價 FCN 通常能拿到相對優渥的票息（溢價空間大）**，但需留意近期是否有財報跳空風險。
* 🟡 **當 30天 IV 與 30天 HV 接近**：代表市場預期的未來波動與過去一個月實際震盪差不多，定價處於合理常態。
* 🔵 **當 30天 IV 低於 30天 HV**：代表過去一個月雖然震盪大，但市場認為風暴已經過去、未來會趨於平靜 ➡️ **FCN 票息可能會比想像中收斂**。"""
        )

    with tab_vol_academic:
        st.markdown(
            r"""### 1️⃣ 30天 歷史波動率（30-Day Historical Volatility, $\text{HV}_{30}$）
取過去 $N = 30$ 個交易日的每日收盤價 $P_t$，先計算每日報酬率 $r_t$，再求出樣本標準差 $\sigma_{\text{daily}}$，最後乘上**年化因子 $\sqrt{252}$**（美股一年約 252 個交易日，依據布朗運動下變異數與時間成正比、標準差與時間平方根 $\sqrt{T}$ 成正比之性質）：

$$\sigma_{\text{daily}} = \sqrt{\frac{1}{N - 1} \sum_{t=1}^{N} (r_t - \bar{r})^2}, \quad \text{HV}_{30} = \sigma_{\text{daily}} \times \sqrt{252}$$

* **本戰情室圖表中的「30天 歷史波動率 (HV)」紫色曲線**：即為每日滾動（Rolling 30-Day Window）計算出的 $\text{HV}_{30}$ 軌跡，可直觀觀察股價急跌或財報跳空時，實際歷史波動率如何急遽飆升。

---

### 2️⃣ 30天 隱含波動率（30-Day Implied Volatility, $\text{IV}_{30}$）
由 CBOE 根據未來約 30 天到期之平價（At-The-Money, ATM）與價外期權市場報價 $C_{\text{mkt}}, P_{\text{mkt}}$，代入期權定價模型反解出的年化波動率參數 $\sigma_{\text{imp}}$：

$$V_{\text{BSM}}(S, K, T, r, \sigma_{\text{imp}}) = V_{\text{market}}$$

* **與特定期間波動幅度之轉換公式**：若已知年化波動率為 $\sigma_{\text{annual}}$，則在未來 $d$ 個交易日內（1 個標準差，約 68.2% 信賴區間）的預期波動幅度為：

$$\sigma_{d\text{ days}} = \sigma_{\text{annual}} \times \sqrt{\frac{d}{252}}$$"""
        )

# 2. 搜尋表單（空白無預設、按鈕等高水平對齊、支援鍵盤 Enter 送出）
with st.form("search_form", clear_on_submit=False):
    st.markdown("<div style='font-size:14px; color:#94a3b8; margin-bottom: 6px;'>輸入美股代號</div>", unsafe_allow_html=True)
    col_input, col_btn = st.columns([5, 1.2])
    with col_input:
        ticker = st.text_input(
            "ticker_input",
            value="",
            placeholder="例如：NVDA, TSM",
            label_visibility="collapsed"
        ).strip().upper()
    with col_btn:
        submitted = st.form_submit_button("🚀 開始分析", width="stretch")


# ============================================================
# 資料存取層（含快取：避免每次互動都重新向 CBOE 抓取）
# ============================================================
HISTORY_YEARS = 5          # 歷史股價回溯年數（供 FCN 回測使用）
TRADING_DAYS_PER_MONTH = 21
CHART_DAYS = 252           # 總覽圖表顯示近一年


@st.cache_resource(show_spinner=False)
def _install_cboe_directory_cache() -> bool:
    """快取 openbb_cboe 的公司與指數名錄，避免每次查詢重複下載大型清單導致逾時。"""
    import openbb_cboe.utils.helpers as cboe_helpers

    orig_company_dir = cboe_helpers.get_company_directory
    orig_index_dir = cboe_helpers.get_index_directory
    mem_cache: dict[str, pd.DataFrame] = {}

    async def cached_company_dir(use_cache: bool = True, **kwargs) -> pd.DataFrame:
        if "company" not in mem_cache:
            try:
                mem_cache["company"] = await orig_company_dir(use_cache=False, **kwargs)
            except Exception:
                return pd.DataFrame(columns=["dpm_name", "post_station", "name"]).rename_axis("symbol")
        return mem_cache["company"]

    async def cached_index_dir(use_cache: bool = True, **kwargs) -> pd.DataFrame:
        if "index" not in mem_cache:
            try:
                mem_cache["index"] = await orig_index_dir(use_cache=False, **kwargs)
            except Exception:
                return pd.DataFrame(columns=["index_symbol", "name", "source"])
        return mem_cache["index"]

    cboe_helpers.get_company_directory = cached_company_dir
    cboe_helpers.get_index_directory = cached_index_dir
    return True


_install_cboe_directory_cache()


@st.cache_data(ttl=600, show_spinner=False)
def load_quote(symbol: str) -> pd.DataFrame:
    return obb.equity.price.quote(symbol=symbol, provider="cboe", use_cache=False).to_dataframe()


@st.cache_data(ttl=3600, show_spinner=False)
def load_history(symbol: str) -> pd.DataFrame:
    start = (pd.Timestamp.today() - pd.DateOffset(years=HISTORY_YEARS)).strftime("%Y-%m-%d")
    df = obb.equity.price.historical(
        symbol=symbol, provider="cboe", start_date=start, use_cache=False
    ).to_dataframe()
    df.index = pd.to_datetime(df.index)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_index()
    df["hv30"] = df["close"].pct_change().rolling(30).std() * np.sqrt(252) * 100
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_chain(symbol: str) -> pd.DataFrame:
    df = obb.cboe.options.chains(symbol=symbol, use_cache=False).to_dataframe()
    for col in ["strike", "implied_volatility", "bid", "ask", "delta", "dte", "underlying_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def quote_val(q: pd.DataFrame, col: str):
    """安全讀取報價欄位：欄位不存在、缺值或為 0 時回傳 None。"""
    if col in q.columns and len(q) > 0:
        v = q[col].iloc[0]
        if pd.notna(v) and v != 0:
            return float(v)
    return None


# ============================================================
# 計算工具
# ============================================================
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def theoretical_fcn_prob(sigma: float, years: float, ki: float, strike: float) -> tuple[float, float]:
    """以幾何布朗運動（風險中性、r=0、連續觀察、不含股息）估算：
    1) 期間內觸及敲入價的機率；2) 到期轉換為股票（曾觸及 KI 且到期低於轉換價）的機率。"""
    if not sigma or sigma <= 0 or years <= 0:
        return float("nan"), float("nan")
    mu = -0.5 * sigma ** 2
    s = sigma * math.sqrt(years)
    b, k = math.log(ki), math.log(strike)
    reflect = math.exp(2 * mu * b / sigma ** 2)
    p_touch = norm_cdf((b - mu * years) / s) + reflect * norm_cdf((b + mu * years) / s)
    if k >= b:
        p_conv = norm_cdf((b - mu * years) / s) + reflect * (
            norm_cdf((b + mu * years) / s) - norm_cdf((2 * b - k + mu * years) / s)
        )
    else:  # 轉換價低於敲入價（少見）：到期低於轉換價即代表期間內必已觸及 KI
        p_conv = norm_cdf((k - mu * years) / s)
    return min(max(p_touch, 0.0), 1.0), min(max(p_conv, 0.0), 1.0)


def backtest_fcn(close: pd.Series, tenor_days: int, ki: float, strike: float) -> pd.DataFrame:
    """滾動回測：假設每個交易日都以當日收盤價為期初價發行一檔同條件 FCN（每日收盤觀察 KI）。"""
    c = close.to_numpy(dtype=float)
    n = len(c)
    if n <= tenor_days + 1:
        return pd.DataFrame()
    windows = np.lib.stride_tricks.sliding_window_view(c[1:], tenor_days)  # 第 j 列 = c[j+1 : j+1+N]
    s0 = c[: len(windows)]
    min_ratio = windows.min(axis=1) / s0
    final_ratio = windows[:, -1] / s0
    ki_hit = min_ratio <= ki
    converted = ki_hit & (final_ratio < strike)
    return pd.DataFrame(
        {
            "min_ratio": min_ratio,
            "final_ratio": final_ratio,
            "ki_hit": ki_hit,
            "converted": converted,
            # 轉換股票時，以轉換價承接：每 1 元本金的到期市值 = 到期價 / 轉換價（不含票息）
            "conv_return": np.where(converted, final_ratio / strike - 1, np.nan),
        },
        index=close.index[: len(windows)],
    )


def term_structure(chain: pd.DataFrame, spot: float, strike_pct: float) -> pd.DataFrame:
    """各到期日的 ATM 隱含波動率，以及轉換價附近賣權（Put）的隱含波動率。"""
    df = chain[(chain["implied_volatility"] > 0) & (chain["dte"] >= 7)]
    rows = []
    for (exp, dte), g in df.groupby(["expiration", "dte"]):
        atm_strike = g.loc[(g["strike"] - spot).abs().idxmin(), "strike"]
        atm_iv = g.loc[g["strike"] == atm_strike, "implied_volatility"].mean()
        puts = g[g["option_type"].astype(str).str.lower().str.startswith("p")]
        put_iv = np.nan
        if len(puts) > 0:
            target = spot * strike_pct
            put_iv = puts.loc[(puts["strike"] - target).abs().idxmin(), "implied_volatility"]
        rows.append({"expiration": exp, "dte": int(dte), "atm_iv": atm_iv * 100, "put_iv": put_iv * 100})
    return pd.DataFrame(rows).sort_values("dte").reset_index(drop=True)


def iv_rank_label(rank: float) -> str:
    if rank >= 67:
        return "位於一年區間高檔"
    if rank <= 33:
        return "位於一年區間低檔"
    return "位於一年區間中段"


# 熱門標的標準化對照表（確保知名公司呈現整潔專業名稱）
KNOWN_COMPANY_NAMES = {
    "NVDA": "NVIDIA Corporation",
    "TSM": "Taiwan Semiconductor (台積電)",
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "GOOG": "Alphabet Inc. (Google)",
    "META": "Meta Platforms, Inc.",
    "MU": "Micron Technology, Inc.",
    "COHR": "Coherent Corp.",
    "AMD": "Advanced Micro Devices, Inc.",
    "INTC": "Intel Corporation",
    "AVGO": "Broadcom Inc.",
    "QCOM": "Qualcomm Inc.",
    "TSLA": "Tesla, Inc.",
    "ASML": "ASML Holding",
    "ARM": "Arm Holdings plc",
    "SMCI": "Super Micro Computer, Inc.",
    "PLTR": "Palantir Technologies Inc.",
    "BABA": "Alibaba Group Holding Ltd.",
    "QQQ": "Invesco QQQ Trust (ETF)",
    "SPY": "SPDR S&P 500 ETF Trust",
    "SOXX": "iShares Semiconductor ETF",
}


def clean_company_name(raw_name: str | None, symbol: str) -> str:
    """清理交易所回傳之公司名稱（去除 COM、INC COM、SPONSORED ADS 等贅詞並標準化大小寫）。"""
    if symbol in KNOWN_COMPANY_NAMES:
        return KNOWN_COMPANY_NAMES[symbol]
    if not raw_name or str(raw_name).strip().upper() == symbol:
        return symbol
    s = str(raw_name).strip()
    s = re.sub(r"\bCOM\s+INC\s+COM\b", "Inc.", s, flags=re.I)
    s = re.sub(r"\bINC\s+COM\b", "Inc.", s, flags=re.I)
    s = re.sub(r"\bCORP\s+COM\b", "Corp.", s, flags=re.I)
    s = re.sub(r"\bCO\s+COM\b", "Co.", s, flags=re.I)
    s = re.sub(r"\bSPONSORED\s+ADS\b", "ADR", s, flags=re.I)
    s = re.sub(r"\bSPON\s+ADR\b", "ADR", s, flags=re.I)
    s = re.sub(r"\bOrdinary\s+Shares\b", "", s, flags=re.I)
    s = re.sub(r"\bCommon\s+Stock\b", "", s, flags=re.I)
    s = re.sub(r"\bClass\s+[A-Z]\b", "", s, flags=re.I)
    s = re.sub(r"\s+COM$", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    words = s.split()
    cleaned = []
    acronyms = {"ADR", "ETF", "USA", "PLC", "LLC", "LP", "REIT", "AI", "TSMC"}
    for w in words:
        w_clean = re.sub(r"[^\w.]", "", w)
        if w_clean.upper() in acronyms:
            cleaned.append(w.upper())
        elif "." in w:
            cleaned.append(".".join(part.capitalize() for part in w.split(".")))
        else:
            cleaned.append(w.capitalize())
    return " ".join(cleaned)


def format_company_header(raw_name: str | None, symbol: str) -> str:
    """生成乾淨一致的公司標題，避免出現 NVDA（NVDA）等重複代號情況。"""
    clean = clean_company_name(raw_name, symbol)
    if clean.upper() == symbol.upper():
        return symbol
    return f"{clean}（{symbol}）"


def format_iv_range(low: float | None, high: float | None) -> str:
    """格式化 52 週 IV 區間，若數值達到三位數（>=100%）自動轉為無小數整數百分比，確保在卡片內不被截斷。"""
    if low is None or high is None:
        return "N/A"
    l_pct, h_pct = low * 100, high * 100
    if h_pct >= 100 or l_pct >= 100:
        return f"{l_pct:.0f}% ~ {h_pct:.0f}%"
    return f"{l_pct:.1f}% ~ {h_pct:.1f}%"


# ============================================================
# 3. 狀態判斷與數據分析
# ============================================================
if not ticker:
    st.info("💡 請在上方輸入框鍵入美股或 ETF 代號（如 NVDA、TSM），按 Enter 或點擊「開始分析」即可即時產出報表。")
    st.stop()

try:
    with st.spinner(f"正在向 CBOE 抓取 {ticker} 最新市場數據中，請稍候..."):
        q = load_quote(ticker)
        hist = load_history(ticker)
        df_chains = load_chain(ticker)
except Exception as e:
    st.error(f"查詢失敗，可能是該代號無期權數據或交易所暫時繁忙：{e}")
    st.stop()

if hist.empty:
    st.error(f"查無 {ticker} 的歷史股價資料。")
    st.stop()

# --- 核心指標（修正：參考價改用成交價、52週區間改用與 30天 IV 同口徑的數據） ---
price = (
    quote_val(q, "last_price")
    or quote_val(q, "close")
    or quote_val(q, "prev_close")
    or float(hist["close"].iloc[-1])
)
iv30 = quote_val(q, "iv30")                  # 小數，例如 0.2777
iv30_low = quote_val(q, "iv30_annual_low")
iv30_high = quote_val(q, "iv30_annual_high")
hv30 = hist["hv30"].dropna().iloc[-1] if hist["hv30"].notna().any() else None  # 百分比

iv_rank = None
if iv30 is not None and iv30_low is not None and iv30_high is not None and iv30_high > iv30_low:
    iv_rank = min(max((iv30 - iv30_low) / (iv30_high - iv30_low) * 100, 0.0), 100.0)

raw_name = q["name"].iloc[0] if "name" in q.columns and len(q) > 0 and pd.notna(q["name"].iloc[0]) else None
company_header = format_company_header(raw_name, ticker)

st.divider()
st.subheader(company_header)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "即時參考價",
    f"${price:,.2f}",
    help="CBOE 延遲報價的最新成交價（若無成交則依序改用收盤價、前一日收盤價）。",
    border=True,
)
c2.metric(
    "30天 隱含波動率 (IV)",
    f"{iv30 * 100:.2f}%" if iv30 is not None else "N/A",
    help="【看未來】由期權市場報價反推，代表市場預期該股票「未來 30 天」的震盪程度（年化百分比）。IV 越高，FCN 票息通常越高；除以 3.46 即為未來一個月約 68% 機率的漲跌幅區間。",
    border=True,
)
c3.metric(
    "30天 歷史波動率 (HV)",
    f"{hv30:.2f}%" if hv30 is not None else "N/A",
    help="【看過去】統計該股票「過去 30 個交易日」每日收盤報酬率的標準差 × √252 年化而成。可用來與「30天 隱含波動率 (IV)」對照，判斷目前市場預期是否高於近期實際波動。",
    border=True,
)
c4.metric(
    "52週 30天 IV 區間",
    format_iv_range(iv30_low, iv30_high),
    help="過去一年（52 週）「30天 隱含波動率 (IV)」的最低點與最高點，與左方 30天 IV 為相同口徑，可直接比較。",
    border=True,
)
c5.metric(
    "IV Rank（52週）",
    f"{iv_rank:.0f}%" if iv_rank is not None else "N/A",
    help="IV Rank =（目前 30天 IV − 52週最低）÷（52週最高 − 52週最低）。0% 代表處於一年最低點、100% 代表處於一年最高點，用來衡量目前 IV 在一年區間中的相對位置。",
    border=True,
)
if iv_rank is not None:
    st.progress(int(round(iv_rank)), text=f"目前 30天 IV {iv_rank_label(iv_rank)}（IV Rank {iv_rank:.0f}%）")

# --- 分頁 ---
tab_overview, tab_fcn, tab_term, tab_chain = st.tabs(
    ["📊 波動率總覽", "🎯 FCN 條件模擬", "📈 IV 期限結構", "📋 期權鏈"]
)

# ------------------------------------------------------------
# 分頁 1：波動率總覽
# ------------------------------------------------------------
with tab_overview:
    st.markdown(
        f"#### {ticker} 過去一年「股價走勢 vs 30天 歷史波動率 (HV)」",
        help="紫色曲線為滾動計算過去 30 個交易日實際漲跌幅的「30天 歷史波動率 (HV)」，藍色曲線為每日收盤價；橘色虛線為目前的 30天 隱含波動率 (IV)，可對照市場預期與過去實際波動。",
    )
    hist_plot = hist.dropna(subset=["hv30"]).tail(CHART_DAYS)

    # 動態計算波動率 Y 軸上限，確保即使當前 IV 遠高於過去歷史 HV，水平線與文字也絕不高出圖表框框
    max_vol = float(hist_plot["hv30"].max()) if len(hist_plot["hv30"]) > 0 else 50.0
    if iv30 is not None:
        max_vol = max(max_vol, float(iv30) * 100)
    y1_max = max(max_vol * 1.15, 10.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist_plot.index, y=hist_plot["hv30"], name="30天 歷史波動率 (HV)", line=dict(color="#c084fc", width=2), yaxis="y1"))
    fig.add_trace(go.Scatter(x=hist_plot.index, y=hist_plot["close"], name="收盤價 (USD)", line=dict(color="#38bdf8", width=2), yaxis="y2"))
    if iv30 is not None:
        fig.add_hline(
            y=iv30 * 100, line=dict(color="#fb923c", dash="dash", width=1.5),
            annotation_text=f"目前 30天 IV {iv30 * 100:.1f}%", annotation_position="top left",
            annotation_font_color="#fb923c",
        )
    fig.update_layout(
        template="plotly_dark",
        height=450,
        xaxis=dict(title="日期"),
        yaxis=dict(
            title="波動率 (%)",
            title_font=dict(color="#c084fc"),
            tickfont=dict(color="#c084fc"),
            range=[0, y1_max],
        ),
        yaxis2=dict(title="股價 (USD)", title_font=dict(color="#38bdf8"), tickfont=dict(color="#38bdf8"), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99),
        margin=dict(t=30),
    )
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------
# 分頁 2：FCN 條件模擬（歷史回測 + IV 理論估計）
# ------------------------------------------------------------
with tab_fcn:
    st.markdown(
        "#### 🎯 FCN 條件模擬",
        help="設定 FCN 條件後，系統會：①回測過去每一個交易日若發行同條件 FCN 的結果；②以 IV 期限結構估算理論機率。兩者皆為統計參考，不代表未來結果。",
    )

    with st.container(border=True):
        p1, p2, p3 = st.columns(3)
        with p1:
            tenor_months = st.segmented_control(
                "天期（月）", options=[3, 6, 9, 12], default=6, key="fcn_tenor",
                format_func=lambda m: f"{m} 個月",
            ) or 6
        with p2:
            strike_pct = st.slider(
                "轉換價（Strike，期初價 %）", min_value=50, max_value=100, value=85, step=1, key="fcn_strike",
                help="若到期時需轉換為股票，投資人以此價格承接股票。",
            ) / 100
        with p3:
            ki_pct = st.slider(
                "敲入價（KI，期初價 %）", min_value=40, max_value=100, value=65, step=1, key="fcn_ki",
                help="合約期間內只要任一交易日收盤價觸及此價位，即視為「已敲入」。",
            ) / 100
        if ki_pct > strike_pct:
            st.warning("敲入價高於轉換價，與一般 FCN 結構不同，請確認條件設定。", icon=":material/warning:")

    tenor_days = tenor_months * TRADING_DAYS_PER_MONTH
    strike_price = price * strike_pct
    ki_price = price * ki_pct

    # --- 若今日發行的價位對照 ---
    l1, l2, l3 = st.columns(3)
    l1.metric("期初參考價", f"${price:,.2f}", border=True)
    l2.metric(f"轉換價（{strike_pct:.0%}）", f"${strike_price:,.2f}", border=True)
    l3.metric(f"敲入價（{ki_pct:.0%}）", f"${ki_price:,.2f}", border=True)

    # --- ① 歷史滾動回測 ---
    bt = backtest_fcn(hist["close"], tenor_days, ki_pct, strike_pct)
    st.markdown(
        f"##### ① 歷史回測：過去每個交易日發行一檔 {tenor_months} 個月期 FCN 的結果",
        help="以每個交易日的收盤價作為期初價，檢查之後 N 個交易日內最低收盤價是否觸及敲入價，以及到期收盤價是否低於轉換價。",
    )
    if bt.empty:
        st.info("歷史資料長度不足以回測此天期。")
    else:
        n_samples = len(bt)
        ki_rate = bt["ki_hit"].mean()
        conv_rate = bt["converted"].mean()
        avg_conv = bt["conv_return"].mean()
        worst_conv = bt["conv_return"].min()

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("回測樣本數", f"{n_samples:,} 檔", help=f"資料區間：{bt.index[0]:%Y-%m-%d} ～ {bt.index[-1]:%Y-%m-%d}（期初日）", border=True)
        b2.metric("期間內觸及敲入價比例", f"{ki_rate:.1%}", border=True)
        b3.metric("到期轉換為股票比例", f"{conv_rate:.1%}", help="曾觸及敲入價，且到期收盤價低於轉換價的比例。", border=True)
        b4.metric(
            "轉換時平均本金變化（不含票息）",
            f"{avg_conv:+.1%}" if pd.notna(avg_conv) else "—",
            help=(f"以轉換價承接股票後，按到期收盤價計算的本金變化。最差情境：{worst_conv:+.1%}" if pd.notna(worst_conv) else "回測期間未發生轉換。"),
            border=True,
        )

        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(
            x=bt.index, y=bt["min_ratio"] * 100, name="期間最低價 / 期初價 (%)",
            line=dict(color="#38bdf8", width=1.5), fill="tozeroy", fillcolor="rgba(56,189,248,0.08)",
        ))
        hit = bt[bt["ki_hit"]]
        if len(hit) > 0:
            fig_bt.add_trace(go.Scatter(
                x=hit.index, y=hit["min_ratio"] * 100, name="觸及敲入價的發行日",
                mode="markers", marker=dict(color="#ef4444", size=4),
            ))
        fig_bt.add_hline(y=ki_pct * 100, line=dict(color="#ef4444", dash="dash"), annotation_text=f"敲入價 {ki_pct:.0%}", annotation_font_color="#ef4444")
        fig_bt.add_hline(y=strike_pct * 100, line=dict(color="#facc15", dash="dot"), annotation_text=f"轉換價 {strike_pct:.0%}", annotation_font_color="#facc15", annotation_position="bottom right")
        fig_bt.update_layout(
            template="plotly_dark", height=380,
            xaxis=dict(title="FCN 期初發行日"),
            yaxis=dict(title="期間最低價 / 期初價 (%)", range=[max(0, bt["min_ratio"].min() * 100 - 5), 105]),
            legend=dict(x=0.01, y=0.02), margin=dict(t=30),
        )
        st.plotly_chart(fig_bt, width="stretch")
        st.caption("每一個點代表「若在該日發行 FCN，合約期間內股價最低曾跌到期初價的幾 %」。低於紅色虛線即代表該檔 FCN 曾觸及敲入價。")

    # --- ② IV 理論估計 ---
    st.markdown(
        "##### ② IV 理論估計：依目前期權市場定價推算的機率",
        help="使用 IV 期限結構中與 FCN 天期相近的 ATM 隱含波動率，以幾何布朗運動（風險中性、r=0、連續觀察、不含股息）估算。屬模型近似值，僅供與歷史回測交叉參考。",
    )
    ts = pd.DataFrame()
    try:
        ts = term_structure(df_chains, price, strike_pct)
    except Exception:
        pass
    target_dte = tenor_months * 30.4
    if not ts.empty and ts["atm_iv"].notna().any():
        valid = ts.dropna(subset=["atm_iv"])
        sigma_tenor = float(np.interp(target_dte, valid["dte"], valid["atm_iv"])) / 100
        sigma_src = f"{tenor_months} 個月 ATM IV（期限結構內插）"
    else:
        sigma_tenor = iv30
        sigma_src = "30天 IV（無期限結構資料時的替代值）"

    p_touch, p_conv = theoretical_fcn_prob(sigma_tenor, tenor_months / 12, ki_pct, strike_pct)
    t1, t2, t3 = st.columns(3)
    t1.metric("採用波動率", f"{sigma_tenor * 100:.2f}%" if sigma_tenor else "N/A", help=f"來源：{sigma_src}", border=True)
    t2.metric("理論觸及敲入價機率", f"{p_touch:.1%}" if pd.notna(p_touch) else "N/A", border=True)
    t3.metric("理論到期轉換機率", f"{p_conv:.1%}" if pd.notna(p_conv) else "N/A", border=True)

    st.caption(
        "⚠️ 以上回測與理論估計僅為統計參考：歷史回測反映過去走勢，理論估計假設價格服從對數常態分佈，兩者皆未考慮財報跳空、股息與實際合約條款（如提前出場、每月觀察日）。實際條件請以發行機構條款為準。"
    )

# ------------------------------------------------------------
# 分頁 3：IV 期限結構
# ------------------------------------------------------------
with tab_term:
    st.markdown(
        "#### 📈 IV 期限結構（Term Structure）",
        help="橫軸為期權距到期日天數，縱軸為隱含波動率。可觀察不同天期的市場預期波動，對照 3／6／9／12 個月 FCN 的定價基礎。",
    )
    if ts.empty:
        st.info("此標的期權鏈資料不足，無法繪製期限結構。")
    else:
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=ts["dte"], y=ts["atm_iv"], name="ATM 隱含波動率", mode="lines+markers",
            line=dict(color="#c084fc", width=2),
            customdata=ts["expiration"].astype(str), hovertemplate="到期日 %{customdata}<br>%{x} 天<br>ATM IV %{y:.2f}%<extra></extra>",
        ))
        fig_ts.add_trace(go.Scatter(
            x=ts["dte"], y=ts["put_iv"], name=f"轉換價（{strike_pct:.0%}）附近賣權 IV", mode="lines+markers",
            line=dict(color="#fb923c", width=2, dash="dot"),
            customdata=ts["expiration"].astype(str), hovertemplate="到期日 %{customdata}<br>%{x} 天<br>Put IV %{y:.2f}%<extra></extra>",
        ))
        for m in [3, 6, 9, 12]:
            fig_ts.add_vline(
                x=m * 30.4, line=dict(color="#facc15" if m == tenor_months else "#475569", dash="dash", width=1),
                annotation_text=f"{m}M", annotation_position="top",
                annotation_font_color="#facc15" if m == tenor_months else "#94a3b8",
            )
        fig_ts.update_layout(
            template="plotly_dark", height=420,
            xaxis=dict(title="距到期日天數 (DTE)", range=[0, min(ts["dte"].max(), 400) + 10]),
            yaxis=dict(title="隱含波動率 (%)"),
            legend=dict(x=0.01, y=0.99), margin=dict(t=40),
        )
        st.plotly_chart(fig_ts, width="stretch")
        st.caption(
            f"黃色虛線為目前 FCN 模擬分頁所選天期（{tenor_months} 個月）。"
            "橘色曲線高於紫色曲線，代表市場對下檔保護的定價高於平價期權（即賣權偏斜 Put Skew），FCN 賣出賣權所收取的權利金相對較高。"
        )

# ------------------------------------------------------------
# 分頁 4：期權鏈（可切換到期日）
# ------------------------------------------------------------
with tab_chain:
    st.markdown("#### 📋 平價周邊期權鏈")
    chain_valid = df_chains[df_chains["implied_volatility"] > 0].copy()
    if chain_valid.empty:
        st.info("此標的目前無有效期權報價。")
    else:
        exp_table = (
            chain_valid[["expiration", "dte"]].drop_duplicates().sort_values("dte").reset_index(drop=True)
        )
        default_idx = int((exp_table["dte"] - tenor_months * 30.4).abs().idxmin())

        f1, f2 = st.columns([2, 1], vertical_alignment="bottom")
        with f1:
            sel_exp = st.selectbox(
                "到期日",
                options=exp_table["expiration"].tolist(),
                index=default_idx,
                format_func=lambda d: f"{d}（{int(exp_table.loc[exp_table['expiration'] == d, 'dte'].iloc[0])} 天）",
                help="預設為最接近 FCN 模擬分頁所選天期的到期日。",
                key="chain_exp",
            )
        with f2:
            side = st.segmented_control("類型", options=["Put", "Call", "全部"], default="Put", key="chain_side") or "全部"

        df_near = chain_valid[chain_valid["expiration"] == sel_exp].copy()
        if side != "全部":
            df_near = df_near[df_near["option_type"].astype(str).str.lower() == side.lower()]
        df_near["diff"] = (df_near["strike"] - price).abs()
        table_display = df_near.nsmallest(24, "diff").sort_values(["strike", "option_type"])

        display_df = pd.DataFrame({
            "類型": table_display["option_type"].astype(str).str.upper(),
            "履約價": table_display["strike"],
            "履約價 / 現價": table_display["strike"] / price * 100,
            "買價": table_display["bid"],
            "賣價": table_display["ask"],
            "隱含波動率 (IV)": table_display["implied_volatility"] * 100,
            "Delta": table_display["delta"] if "delta" in table_display else np.nan,
        })
        st.dataframe(
            display_df,
            hide_index=True,
            width="stretch",
            column_config={
                "履約價": st.column_config.NumberColumn(format="$%.2f"),
                "履約價 / 現價": st.column_config.NumberColumn(format="%.1f%%", help="履約價相對目前參考價的位置，可對照 FCN 轉換價 %。"),
                "買價": st.column_config.NumberColumn(format="$%.2f"),
                "賣價": st.column_config.NumberColumn(format="$%.2f"),
                "隱含波動率 (IV)": st.column_config.NumberColumn(format="%.2f%%"),
                "Delta": st.column_config.NumberColumn(format="%.3f"),
            },
        )
