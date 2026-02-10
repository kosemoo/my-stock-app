import streamlit as st
import yfinance as yf
import pandas as pd
import os
import FinanceDataReader as fdr

# 페이지 설정
st.set_page_config(page_title="내 주식 대시보드", page_icon="📈", layout="wide")

SAVE_FILE = "stock_list.csv"

# [1. 한국 거래소 종목 리스트 로드 - 안정성 강화]
@st.cache_data(ttl=3600)
def get_krx_data():
    try:
        # KRX 리스트 로딩 시도
        df = fdr.StockListing('KRX')
        if df is None or df.empty:
            # KRX 실패 시 KOSPI, KOSDAQ 개별 시도
            df_kospi = fdr.StockListing('KOSPI')
            df_kosdaq = fdr.StockListing('KOSDAQ')
            df = pd.concat([df_kospi, df_kosdaq])
        
        df['Name'] = df['Name'].astype(str).str.strip()
        return df[['Name', 'Code']]
    except Exception as e:
        st.error(f"종목 리스트를 불러오는 중 오류 발생: {e}")
        return pd.DataFrame(columns=['Name', 'Code'])

krx_df = get_krx_data()

# [2. 데이터 로드/저장]
def save_data(df):
    df.to_csv(SAVE_FILE, index=False)

if 'master_df' not in st.session_state:
    if os.path.exists(SAVE_FILE):
        try:
            st.session_state.master_df = pd.read_csv(SAVE_FILE)
        except:
            st.session_state.master_df = pd.DataFrame(columns=["종목명", "목표가"])
    else:
        st.session_state.master_df = pd.DataFrame([{"종목명": "삼성전자", "목표가": 80000}])

# --- 사이드바 ---
st.sidebar.title("➕ 종목 추가 및 설정")

if krx_df.empty:
    st.sidebar.warning("⚠️ 거래소 리스트를 불러오는 중입니다. 잠시만 기다려주세요...")
    if st.sidebar.button("리스트 다시 불러오기"):
        st.cache_data.clear()
        st.rerun()
else:
    search_query = st.sidebar.text_input("종목명 검색 (예: 삼성, 에코)")
    if search_query:
        query = search_query.strip()
        filtered_stocks = krx_df[krx_df['Name'].str.contains(query, case=False, na=False)]
        
        if not filtered_stocks.empty:
            selected_stock = st.sidebar.selectbox(f"검색 결과 ({len(filtered_stocks)}건)", options=filtered_stocks['Name'].tolist())
            target_input = st.sidebar.number_input("목표가 설정", value=10000, step=100)
            
            if st.sidebar.button("📍 이 종목 추가/수정"):
                temp_df = st.session_state.master_df.copy()
                if selected_stock in temp_df['종목명'].values:
                    temp_df.loc[temp_df['종목명'] == selected_stock, '목표가'] = target_input
                else:
                    new_row = pd.DataFrame([{"종목명": selected_stock, "목표가": target_input}])
                    temp_df = pd.concat([temp_df, new_row], ignore_index=True)
                st.session_state.master_df = temp_df
                save_data(temp_df)
                st.rerun()
        else:
            st.sidebar.error("검색 결과가 없습니다.")

st.sidebar.divider()
st.sidebar.subheader("📋 내 종목 리스트")
edited_df = st.sidebar.data_editor(st.session_state.master_df, num_rows="dynamic", use_container_width=True, disabled=["종목명", "목표가"], key="editor")

if not edited_df.equals(st.session_state.master_df):
    save_data(edited_df)
    st.session_state.master_df = edited_df
    st.rerun()

# [3. 시세 조회]
@st.cache_data(ttl=60)
def fetch_display_data(df_input):
    results = []
    name_to_code = dict(zip(krx_df['Name'], krx_df['Code']))
    for _, row in df_input.iterrows():
        name, target = str(row['종목명']).strip(), row['목표가']
        code = name_to_code.get(name)
        if not code: continue
        try:
            for suffix in [".KS", ".KQ"]:
                stock = yf.Ticker(f"{code}{suffix}")
                hist = stock.history(period="2d")
                if not hist.empty and len(hist) >= 2:
                    curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                    results.append({"종목명": name, "현재가": int(curr), "목표가": int(target), 
                                    "달성률(%)": round((curr/target)*100, 1) if target > 0 else 0,
                                    "전일대비(%)": round(((curr-prev)/prev)*100, 2)})
                    break
        except: continue
    return pd.DataFrame(results)

# --- 메인 화면 ---
st.title("📊 실시간 목표 달성 현황판")
if not st.session_state.master_df.empty:
    display_df = fetch_display_data(st.session_state.master_df)
    if not display_df.empty:
        cols = st.columns(4)
        for i, (idx, row) in enumerate(display_df.iterrows()):
            status = "🔥" if row['달성률(%)'] >= 100 else "📈"
            cols[i % 4].metric(label=f"{row['종목명']} {status}", value=f"{row['현재가']:,}원", delta=f"{row['전일대비(%)']}%")
        st.divider()
        st.dataframe(display_df.style.format({"현재가": "{:,}원", "목표가": "{:,}원", "달성률(%)": "{:.1f}%", "전일대비(%)": "{:+.2f}%"}), use_container_width=True)
    else:
        st.info("데이터를 불러오는 중입니다... (검색창에서 종목을 추가해 보세요)")
else:
    st.info("사이드바에서 종목을 검색해 추가해 주세요.")

if st.button('🔄 시세 새로고침'):
    st.cache_data.clear()
    st.rerun()
