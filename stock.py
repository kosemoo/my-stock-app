import streamlit as st
import yfinance as yf
import pandas as pd
import os

# 페이지 설정
st.set_page_config(page_title="내 주식 대시보드", page_icon="📈", layout="wide")

SAVE_FILE = "stock_list.csv"

# [1. 데이터 로드/저장 함수]
def save_data(df):
    df.to_csv(SAVE_FILE, index=False)

def load_data():
    if os.path.exists(SAVE_FILE):
        try:
            return pd.read_csv(SAVE_FILE)
        except:
            return pd.DataFrame(columns=["종목명", "종목코드", "목표가"])
    return pd.DataFrame([{"종목명": "삼성전자", "종목코드": "005930", "목표가": 80000}])

if 'master_df' not in st.session_state:
    st.session_state.master_df = load_data()

# --- 사이드바: 종목 직접 추가 ---
st.sidebar.title("➕ 종목 추가")
st.sidebar.info("한국 종목 코드는 숫자 6자리입니다.\n(예: 삼성전자 005930, 에코프로 086520)")

with st.sidebar.form("add_form", clear_on_submit=True):
    new_name = st.text_input("종목명 (예: 삼성전자)")
    new_code = st.text_input("종목코드 (숫자 6자리)")
    new_target = st.number_input("목표가 설정", value=10000, step=1000)
    submitted = st.form_submit_button("리스트에 추가")

    if submitted:
        if new_name and new_code:
            new_row = pd.DataFrame([{"종목명": new_name.strip(), "종목코드": new_code.strip(), "목표가": new_target}])
            st.session_state.master_df = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
            save_data(st.session_state.master_df)
            st.rerun()
        else:
            st.error("이름과 코드를 모두 입력해주세요.")

st.sidebar.divider()
st.sidebar.subheader("📋 내 종목 리스트 (삭제 가능)")
# 종목명, 코드는 수정 불가, 목표가만 수정 가능하게 설정
edited_df = st.sidebar.data_editor(
    st.session_state.master_df, 
    num_rows="dynamic", 
    use_container_width=True,
    disabled=["종목명", "종목코드"],
    key="editor"
)

if not edited_df.equals(st.session_state.master_df):
    save_data(edited_df)
    st.session_state.master_df = edited_df
    st.rerun()

# [2. 시세 조회 함수]
@st.cache_data(ttl=60)
def fetch_display_data(df_input):
    results = []
    for _, row in df_input.iterrows():
        name = str(row['종목명'])
        code = str(row['종목코드']).strip()
        target = row['목표가']
        
        try:
            # 코스피(.KS), 코스닥(.KQ) 순차 시도
            found = False
            for suffix in [".KS", ".KQ"]:
                stock = yf.Ticker(f"{code}{suffix}")
                hist = stock.history(period="2d")
                if not hist.empty and len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    results.append({
                        "종목명": name,
                        "현재가": int(curr),
                        "목표가": int(target),
                        "달성률(%)": round((curr/target)*100, 1) if target > 0 else 0,
                        "전일대비(%)": round(((curr-prev)/prev)*100, 2)
                    })
                    found = True
                    break
        except:
            continue
    return pd.DataFrame(results)

# --- 메인 화면 ---
st.title("📊 실시간 목표 달성 현황판")

if not st.session_state.master_df.empty:
    with st.spinner('시세를 불러오는 중...'):
        display_df = fetch_display_data(st.session_state.master_df)
    
    if not display_df.empty:
        # Metric 카드 출력
        cols = st.columns(4)
        for i, (idx, row) in enumerate(display_df.iterrows()):
            status = "🔥" if row['달성률(%)'] >= 100 else "📈"
            cols[i % 4].metric(
                label=f"{row['종목명']} {status}", 
                value=f"{row['현재가']:,}원", 
                delta=f"{row['전일대비(%)']}%"
            )
        
        st.divider()
        # 데이터 표
        st.dataframe(
            display_df.style.format({
                "현재가": "{:,}원", "목표가": "{:,}원", 
                "달성률(%)": "{:.1f}%", "전일대비(%)": "{:+.2f}%"
            }), 
            use_container_width=True
        )
    else:
        st.info("시세 데이터를 가져오지 못했습니다. 종목코드가 정확한지 확인해 주세요.")
else:
    st.info("왼쪽 사이드바에서 종목을 추가해 주세요.")

if st.button('🔄 시세 새로고침'):
    st.cache_data.clear()
    st.rerun()
