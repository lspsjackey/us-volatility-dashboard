import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from openbb import obb

st.set_page_config(page_title="美股波動率與 FCN 分析戰情室", layout="wide", initial_sidebar_state="collapsed")

# 自訂樣式：精簡按鈕尺寸與垂直置中對齊
st.markdown("""
<style>
    div[data-testid="stFormSubmitButton"] > button {
        height: 42px;
        font-size: 14px;
        font-weight: 600;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 美股個股波動率與 FCN 期權戰情室")
st.write("即時查詢 CBOE 官方 30天 隱含波動率 (IV)、30天 歷史波動率 (HV) 與最新期權鏈。")

# 1. FCN 結構與隱含波動率 (IV) 定價機制解說模組
with st.expander("📖 點此了解：什麼是FCN？", expanded=False):
    st.markdown("""
    **FCN（Fixed Coupon Note）**在金融工程結構上，本質為「**固定收益票券**」與「**賣出賣權（Short Put Option）**」的組合商品。

    ---

    #### 1️⃣ 【合約架構】
    假設標的股票目前市價為 **100 元**：  
    投資人向發行機構提供承諾：  
    > *「若合約存續期間標的價格跌破 **70 元（敲入保護價）**，投資人承諾依約以 **70 元**之約定價格受分配買進該股票。」*

    ---

    #### 2️⃣ 【票息（Coupon）的本質】
    市場上持有現貨的機構或部位具備避險需求，需要將「股價下行之尾部風險」轉移至市場。  
    因為投資人承接了此項下行風險並提供流動性承諾，發行機構支付相對應的風險補償金——此即投資人定期領取之 **Coupon（票面利息）**。

    ---

    #### 3️⃣ 【隱含波動率（IV）的定價機制】
    隱含波動率（IV）代表期權市場依據供需，對標的資產在未來 **「價格波動幅度與不確定性」的量化評估**：
    * **當 IV 較低（市場預期價格分佈收斂）**：標的觸及 70 元保護價的統計機率較低，避險轉移的市場成本較小，發行機構開出的年化利息（Coupon）相應偏低。
    * **當 IV 較高（市場預期價格分佈發散）**：標的觸及 70 元保護價的統計機率顯著上升，市場對下行保護的定價更高，因此發行機構提供給投資人的年化利息（Coupon）會隨之提高。

    ---

    #### 4️⃣ 【結算時的履約結果】
    1. **標的未觸及保護門檻（全程維持在 70 元以上）**：無須履行買進義務，投資人領取全期約定之利息（Coupon），本金以 **100% 現金全額返還**。
    2. **標的跌破保護門檻（觸及 70 元且到期未能回升）**：投資人依然收取全期約定之利息（Coupon），並依約定履行承諾，以 **70 元之約定折價價格轉換為股票現貨持有**。

    ---

    > **📌 總結**：FCN 的票息（Coupon）本質上是「**承擔下行價格風險之風險溢價**」；而隱含波動率（IV）則是市場評估該波動幅度與事件機率的定價指標。
    """)

# 1-2. 30天 隱含波動率 (IV) 與 30天 歷史波動率 (HV) 指標解說模組
with st.expander("📖 點此了解：什麼是「30天 隱含波動率 (IV)」與「30天 歷史波動率 (HV)」？", expanded=False):
    tab_vol_plain, tab_vol_academic = st.tabs(["💡 白話版解說與實戰判讀", "📘 數學定義與年化換算公式"])

    with tab_vol_plain:
        st.markdown("""
        ### 1️⃣ 一句話分清楚兩者差別
        * **🔮 30天 隱含波動率 (IV)（往前看未來）**：「**氣象預報**」—— 市場透過未來 30 天到期期權的成交價格，反推出大家**預期未來 30 天**這檔股票會有多震盪。
        * **📜 30天 歷史波動率 (HV)（回頭看過去）**：「**過去一個月的實際天氣紀錄**」—— 統計這檔股票**過去 30 個交易日**每天實際漲跌的劇烈程度。

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
        | 比較項目 | 🔮 30天 隱含波動率 (IV) | 📜 30天 歷史波動率 (HV) |
        | :--- | :--- | :--- |
        | **時間方向** | **看未來 30 天**（市場預期） | **看過去 30 個交易日**（已發生的事實） |
        | **數據來源** | CBOE 期權市場的買賣報價反推 | 過去 30 天每日收盤價報酬率的標準差（年化） |
        | **對 FCN 的意義** | **直接決定現在下單 FCN 的票息高低** | **用來檢驗目前的 IV 報價是否「划算」** |

        * 🟢 **當 30天 IV 明顯高於 30天 HV（例如 IV = 55%，HV = 38%）**：代表市場因為財報將至或短期事件而「過度緊張」，保險費偏貴 ➡️ **此時詢價 FCN 通常能拿到相對優渥的票息（溢價空間大）**，但需留意近期是否有財報跳空風險。
        * 🟡 **當 30天 IV 與 30天 HV 接近**：代表市場預期的未來波動與過去一個月實際震盪差不多，定價處於合理常態。
        * 🔵 **當 30天 IV 低於 30天 HV**：代表過去一個月雖然震盪大，但市場認為風暴已經過去、未來會趨於平靜 ➡️ **FCN 票息可能會比想像中收斂**。
        """)

    with tab_vol_academic:
        st.markdown(r"""
        ### 1️⃣ 30天 歷史波動率（30-Day Historical Volatility, $\text{HV}_{30}$）
        取過去 $N = 30$ 個交易日的每日收盤價 $P_t$，先計算每日報酬率 $r_t$，再求出樣本標準差 $\sigma_{\text{daily}}$，最後乘上**年化因子 $\sqrt{252}$**（美股一年約 252 個交易日，依據布朗運動下變異數與時間成正比、標準差與時間平方根 $\sqrt{T}$ 成正比之性質）：

        $$\sigma_{\text{daily}} = \sqrt{\frac{1}{N - 1} \sum_{t=1}^{N} (r_t - \bar{r})^2}, \quad \text{HV}_{30} = \sigma_{\text{daily}} \times \sqrt{252}$$

        * **本戰情室圖表中的「30天 歷史波動率 (HV)」紫色曲線**：即為每日滾動（Rolling 30-Day Window）計算出的 $\text{HV}_{30}$ 軌跡，可直觀觀察股價急跌或財報跳空時，實際歷史波動率如何急遽飆升。

        ---

        ### 2️⃣ 30天 隱含波動率（30-Day Implied Volatility, $\text{IV}_{30}$）
        由 CBOE 根據未來約 30 天到期之平價（At-The-Money, ATM）與價外期權市場報價 $C_{\text{mkt}}, P_{\text{mkt}}$，代入期權定價模型反解出的年化波動率參數 $\sigma_{\text{imp}}$：

        $$V_{\text{BSM}}(S, K, T, r, \sigma_{\text{imp}}) = V_{\text{market}}$$

        * **與特定期間波動幅度之轉換公式**：若已知年化波動率為 $\sigma_{\text{annual}}$，則在未來 $d$ 個交易日內（1 個標準差，約 68.2% 信賴區間）的預期波動幅度為：

        $$\sigma_{d\text{ days}} = \sigma_{\text{annual}} \times \sqrt{\frac{d}{252}}$$
        """)

# 2. 搜尋表單（空白無預設、按鈕等高水平對齊、支援鍵盤 Enter 送出）
with st.form("search_form", clear_on_submit=False):
    st.markdown("<div style='font-size:14px; color:#94a3b8; margin-bottom: 6px;'>輸入美股代號</div>", unsafe_allow_html=True)
    col_input, col_btn = st.columns([5, 1.2])
    with col_input:
        ticker = st.text_input(
            "ticker_input",
            value="",
            placeholder="例如：MU, NVDA, TSM, COHR, AAPL, QQQ",
            label_visibility="collapsed"
        ).strip().upper()
    with col_btn:
        submitted = st.form_submit_button("🚀 開始分析", width="stretch")

# 3. 狀態判斷與數據分析
if not ticker:
    st.info("💡 請在上方輸入框鍵入美股或 ETF 代號（如 NVDA、TSM、COHR），按 Enter 或點擊「開始分析」即可即時產出報表。")
else:
    with st.spinner(f"正在向 CBOE 抓取 {ticker} 最新市場數據中，請稍候..."):
        try:
            q = obb.cboe.equity.quote(symbol=ticker, provider="cboe").to_dataframe()
            hist = obb.cboe.equity.historical(symbol=ticker, provider="cboe").to_dataframe()
            
            try:
                chains = obb.cboe.options.chains(symbol=ticker)
            except Exception:
                chains = obb.derivatives.options.chains(symbol=ticker, provider="cboe")
            df_chains = chains.to_dataframe()

            # 計算近一年歷史波動率
            hist['close'] = pd.to_numeric(hist['close'], errors='coerce')
            hist = hist.dropna(subset=['close']).tail(280).copy()
            hist['return'] = hist['close'].pct_change()
            hist['vol_30d'] = hist['return'].rolling(window=30).std() * np.sqrt(252) * 100
            hist_plot = hist.dropna(subset=['vol_30d']).copy()

            # 數值讀取防呆
            def get_val(df, col):
                if col in df.columns and len(df[col]) > 0:
                    v = df[col].iloc[0]
                    if pd.notna(v): return v
                return None

            def fmt_pct(val):
                if val is None or pd.isna(val): return None
                v = float(val)
                return f"{v*100:.2f}%" if v < 2.0 else f"{v:.2f}%"

            price = get_val(q, 'bid') or (hist_plot['close'].iloc[-1] if len(hist_plot) > 0 else "N/A")
            iv30 = fmt_pct(get_val(q, 'iv30')) or "N/A"
            hv30_calc = f"{hist_plot['vol_30d'].iloc[-1]:.2f}%" if len(hist_plot) > 0 else "N/A"
            high_iv = fmt_pct(get_val(q, 'iv90_annual_high')) or "N/A"
            low_iv = fmt_pct(get_val(q, 'iv90_annual_low')) or "N/A"

            st.divider()

            # 4 格指標卡片（含 ? 懸浮說明提示）
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "即時參考價",
                f"${price:.2f}" if isinstance(price, (int, float)) else str(price),
                help="CBOE 即時買方報價（若盤前／收盤無報價則顯示最近一日收盤價）。"
            )
            c2.metric(
                "30天 隱含波動率 (IV)",
                iv30,
                help="【看未來】由期權市場報價反推，代表市場預期該股票「未來 30 天」的震盪程度（年化百分比）。IV 越高，FCN 票息通常越高；除以 3.46 即為未來一個月約 68% 機率的漲跌幅區間。"
            )
            c3.metric(
                "30天 歷史波動率 (HV)",
                hv30_calc,
                help="【看過去】統計該股票「過去 30 個交易日」每日收盤報酬率的標準差 × √252 年化而成。可用來與左方「30天 隱含波動率 (IV)」對照，判斷目前市場預期是否高於近期實際波動。"
            )
            c4.metric(
                "52週 IV 區間",
                f"{low_iv} ~ {high_iv}",
                help="過去一年（52 週）隱含波動率的最低點與最高點區間，用來判斷目前 IV 處於歷史高檔還是低檔。"
            )

            # 雙軸圖表
            st.subheader(
                f"📈 {ticker} 過去一年「股價走勢 vs 30天 歷史波動率 (HV)」",
                help="紫色曲線為滾動計算過去 30 個交易日實際漲跌幅的「30天 歷史波動率 (HV)」，藍色曲線為每日收盤價。"
            )
            dates = hist_plot.index if 'date' not in hist_plot.columns else hist_plot['date']

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=hist_plot['vol_30d'], name="30天 歷史波動率 (HV)", line=dict(color='#c084fc', width=2), yaxis="y1"))
            fig.add_trace(go.Scatter(x=dates, y=hist_plot['close'], name="收盤價 (USD)", line=dict(color='#38bdf8', width=2), yaxis="y2"))

            fig.update_layout(
                template="plotly_dark",
                height=450,
                xaxis=dict(title="日期"),
                yaxis=dict(title="30天 歷史波動率 HV (%)", title_font=dict(color="#c084fc"), tickfont=dict(color="#c084fc")),
                yaxis2=dict(title="股價 (USD)", title_font=dict(color="#38bdf8"), tickfont=dict(color="#38bdf8"), overlaying="y", side="right"),
                legend=dict(x=0.01, y=0.99)
            )
            st.plotly_chart(fig, width="stretch")

            # 期權鏈表格
            st.subheader("📋 最近到期日 平價周邊期權鏈與 IV 表格")
            strike_col = next((c for c in df_chains.columns if "strike" in c.lower()), "strike")
            iv_col = next((c for c in df_chains.columns if "implied_volatility" in c.lower() or c.lower() == "iv"), "implied_volatility")
            exp_col = next((c for c in df_chains.columns if "expiration" in c.lower()), "expiration")
            type_col = next((c for c in df_chains.columns if "type" in c.lower() or "side" in c.lower()), "option_type")
            bid_col = next((c for c in df_chains.columns if "bid" in c.lower()), "bid")
            ask_col = next((c for c in df_chains.columns if "ask" in c.lower()), "ask")

            df_chains[strike_col] = pd.to_numeric(df_chains[strike_col], errors='coerce')
            df_chains[iv_col] = pd.to_numeric(df_chains[iv_col], errors='coerce')
            df_chains = df_chains.dropna(subset=[strike_col, iv_col])

            nearest_exp = sorted(df_chains[exp_col].unique())[0]
            df_near = df_chains[df_chains[exp_col] == nearest_exp].copy()
            ref_p = float(price) if isinstance(price, (int, float)) and price != "N/A" else 100.0
            df_near['diff'] = (df_near[strike_col] - ref_p).abs()
            table_display = df_near.sort_values('diff').head(20).sort_values(strike_col)

            display_df = pd.DataFrame({
                "到期日": table_display[exp_col],
                "期權類型": table_display[type_col].astype(str).str.upper(),
                "履約價 ($)": table_display[strike_col].round(1),
                "買價 ($)": table_display[bid_col].round(2) if bid_col in table_display else 0,
                "賣價 ($)": table_display[ask_col].round(2) if ask_col in table_display else 0,
                "隱含波動率 (IV)": (table_display[iv_col] * 100).round(2).astype(str) + "%"
            })
            st.dataframe(display_df, width="stretch")

        except Exception as e:
            st.error(f"查詢失敗，可能是該代號無期權數據或交易所暫時繁忙：{e}")
