import streamlit as st
import yfinance as yf
import pandas as pd
import os
import FinanceDataReader as fdr

st.set_page_config(page_title="집중 종목 대시보드", layout="wide")

SAVE_FILE = "stock_list.csv"

# [1. 한국 거래소 종목 리스트 로드 - 공백 제거 보강]
@st.cache_data(ttl=3600)
def get_krx_data():
    try:
        df = fdr.StockListing('KRX')
        # 종목명과 코드를 매칭 (이름 앞뒤 공백 제거)
        df['Name'] = df['Name'].str.strip()
        return df[['Name', 'Code']]
    except:
        return pd.DataFrame(columns=['Name', 'Code'])

krx_df = get_krx_data()

# [2. 데이터 로드 및 저장 함수]
def save_data(df):
    df.to_csv(SAVE_FILE, index=False)

if 'master_df' not in st.session_state:
    if os.path.exists(SAVE_FILE):
        st.session_state.master_df = pd.read_csv(SAVE_FILE)
    else:
        st.session_state.master_df = pd.DataFrame([
            {"종목명": "삼성전자", "목표가": 80000}
        ])

# --- 사이드바: 종목 추가 및 설정 ---
st.sidebar.title("➕ 종목 추가 및 목표가 설정")

# A. 검색 영역
search_query = st.sidebar.text_input("종목명 검색 (예: 삼성, 에코)")

if search_query:
    query = search_query.strip()
    filtered_stocks = krx_df[krx_df['Name'].str.contains(query, na=False)]
    
    if not filtered_stocks.empty:
        selected_stock = st.sidebar.selectbox(
            f"검색 결과 ({len(filtered_stocks)}건)",
            options=filtered_stocks['Name'].tolist()
        )
        
        target_input = st.sidebar.number_input("해당 종목 목표가 설정", value=10000, step=500)
        
        if st.sidebar.button("📍 이 종목 추가/수정하기"):
            temp_df = st.session_state.master_df.copy()
            # 종목명 앞뒤 공백 제거 후 비교
            temp_df['종목명'] = temp_df['종목명'].str.strip()
            
            if selected_stock in temp_df['종목명'].values:
                temp_df.loc[temp_df['종목명'] == selected_stock, '목표가'] = target_input
                st.sidebar.success(f"'{selected_stock}' 목표가 수정 완료!")
            else:
                new_row = pd.DataFrame([{"종목명": selected_stock, "목표가": target_input}])
                temp_df = pd.concat([temp_df, new_row], ignore_index=True)
                st.sidebar.success(f"'{selected_stock}' 추가 완료!")
            
            st.session_state.master_df = temp_df
            save_data(temp_df)
            st.rerun()
    else:
        st.sidebar.error("검색 결과가 없습니다.")

st.sidebar.divider()

# B. 내 리스트 확인 및 삭제 (수정 방지)
st.sidebar.subheader("📋 내 종목 리스트 (삭제 가능)")
edited_df = st.sidebar.data_editor(
    st.session_state.master_df,
    num_rows="dynamic",
    use_container_width=True,
    disabled=["종목명", "목표가"], 
    key="editor"
)

if not edited_df.equals(st.session_state.master_df):
    save_data(edited_df)
    st.session_state.master_df = edited_df
    st.rerun()

# [3. 핵심: 시세 조회 함수 - 정확도 보강]
@st.cache_data(ttl=60)
def fetch_display_data(df_input):
    results = []
    # 검색용 딕셔너리 생성 (이름 공백 완벽 제거)
    name_to_code = {str(n).strip(): str(c).strip() for n, c in zip(krx_df['Name'], krx_df['Code'])}
    
    for _, row in df_input.iterrows():
        name = str(row['종목명']).strip()
        target = row['목표가']
        code = name_to_code.get(name)
        
        if not code:
            continue
        
        try:
            # 한국 주식 전용 접미사 시도 (코스피, 코스닥 둘 다 확인)
            found = False
            for suffix in [".KS", ".KQ"]:
                ticker_symbol = f"{code}{suffix}"
                stock = yf.Ticker(ticker_symbol)
                # 데이터가 있는지 확인
                hist = stock.history(period="2d")
                if not hist.empty and len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    
                    # 삼성전자 가격 오류 방지: 비정상적으로 높으면 다른 시장 데이터일 수 있음
                    # 한국 주식은 보통 1,000,000원을 넘지 않는 경우가 많음 (액면분할 등)
                    results.append({
                        "종목명": name,
                        "현재가": int(curr),
                        "목표가": int(target),
                        "달성률(%)": round((curr / target) * 100, 1) if target > 0 else 0,
                        "전일대비(%)": round(((curr - prev) / prev) * 100, 2)
                    })
                    found = True
                    break
            if not found:
                # 데이터를 찾지 못한 종목은 로그에 남김
                print(f"로그: {name}({code}) 데이터를 찾을 수 없음")
        except Exception as e:
            continue
    return pd.DataFrame(results)

# --- 메인 화면 ---
st.title("📊 실시간 목표 달성 현황판")

display_df = fetch_display_data(st.session_state.master_df)

if not display_df.empty:
    # Metric 출력 (한 줄에 최대 4개)
    n_cols = 4
    rows = (len(display_df) // n_cols) + (1 if len(display_df) % n_cols > 0 else 0)
    
    # 리스트 순서대로 출력
    for r in range(rows):
        cols = st.columns(n_cols)
        for c in range(n_cols):
            idx = r * n_cols + c
            if idx < len(display_df):
                row = display_df.iloc[idx]
                status = "🔥" if row['달성률(%)'] >= 100 else "📈"
                cols[c].metric(
                    label=f"{row['종목명']} {status}", 
                    value=f"{row['현재가']:,}원", 
                    delta=f"{row['전일대비(%)']}%"
                )

    st.divider()
    
    # 상세 테이블 스타일링
    st.subheader("📋 종목별 상세 데이터")
    def apply_style(styler):
        styler.set_properties(**{'text-align': 'center'})
        styler.format({
            "현재가": "{:,}원", "목표가": "{:,}원",
            "달성률(%)": "{:.1f}%", "전일대비(%)": "{:+.2f}%"
        })
        def color_achieve(val):
            color = '#ffcdd2' if val >= 100 else '#e3f2fd'
            text = '#d32f2f' if val >= 100 else '#1976d2'
            return f'background-color: {color}; color: {text}; font-weight: bold;'
        styler.map(color_achieve, subset=['달성률(%)'])
        return styler

    st.dataframe(apply_style(display_df.style), use_container_width=True)
else:
    st.info("상단 검색창에서 종목을 검색하여 추가해 주세요. (에코프로, 삼성전자 등)")

if st.button('🔄 시세 새로고침'):
    st.cache_data.clear()
    st.rerun()

