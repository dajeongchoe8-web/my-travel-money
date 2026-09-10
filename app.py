import json
import os
import time
import uuid
from datetime import datetime
import pandas as pd
from google import genai
from google.genai import types
import streamlit as st

# ==========================================
# 🔑 자동으로 적용된 Gemini API 키
# ==========================================
API_KEY = "AQ.Ab8RN6KJthDRoQQeW3-N9qsx9bRUd4j3FlNvdTwfk-FuAa5gDw"

DATA_FILE = "account_book.json"
COUNTRIES_FILE = "countries.json"


# --- 데이터 로드 및 저장 함수 ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            cleaned_data = []
            for item in raw_data:
                if isinstance(item, list):
                    for sub_item in item:
                        if isinstance(sub_item, dict):
                            if "id" not in sub_item:
                                sub_item["id"] = str(uuid.uuid4())
                            cleaned_data.append(sub_item)
                elif isinstance(item, dict):
                    if "id" not in item:
                        item["id"] = str(uuid.uuid4())
                    cleaned_data.append(item)

            return cleaned_data
        except Exception:
            return []
    return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_countries():
    if os.path.exists(COUNTRIES_FILE):
        try:
            with open(COUNTRIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return ["한국", "영국", "프랑스", "미국", "일본"]
    return ["한국", "영국", "프랑스", "미국", "일본"]


def save_countries(countries):
    with open(COUNTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(countries, f, ensure_ascii=False, indent=4)


# AI 분석 및 재시도 함수
def parse_expense_with_ai(user_input, selected_country, selected_date_str, api_key):
    if not api_key:
        st.error("API Key가 지정되지 않았습니다.")
        return None

    client = genai.Client(api_key=api_key)

    prompt = f"""
    사용자의 수입/지출 내역을 분석해서 하나의 JSON 객체({{}}) 형식으로 응답해줘. 리스트([])로 감싸지 마.
    
    [기본 정보]
    - 국가: '{selected_country}'
    - 선택된 날짜: '{selected_date_str}'
    
    [필수 추출 키]
    - date: 입력에 별도 언급이 없으면 '{selected_date_str}' 사용 (YYYY-MM-DD)
    - country: '{selected_country}'
    - type: '수입' 또는 '지출' 중 하나 (입금, 충전, 용돈, 돈 들어옴 등의 표현은 '수입')
    - payment_method: '카드' 또는 '현금' 중 하나 (언급이 없으면 '카드'를 기본값으로 함)
    - category: 
      - type이 '수입'인 경우: '수입(입금)'
      - type이 '지출'인 경우: 식비, 교통, 쇼핑, 숙박, 여가, 기타 중 하나
    - amount_krw: 원화 기준 최종 환산 금액 (숫자만, 정수 형태)
    - original_amount_text: 입력된 원본 금액 표현 (예: "15 GBP", "20 EUR", "15000원")
    - description: 간단한 내역 요약
    
    사용자 입력: "{user_input}"
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            result = json.loads(response.text.strip())

            if isinstance(result, list):
                if len(result) > 0:
                    result = result[0]
                else:
                    return None

            if isinstance(result, dict):
                result["id"] = str(uuid.uuid4())

            return result

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                st.error(f"AI 분석 중 오류가 발생했습니다: {e}")
                return None


# --- Streamlit UI 설정 ---
st.set_page_config(page_title="✈️ 자유 추가형 글로벌 가계부", page_icon="✈️", layout="centered")

# 세션 상태 초기화
if "selected_country" not in st.session_state:
    st.session_state.selected_country = None

# 사이드바 설정
st.sidebar.header("➕ 국가 추가 및 관리")

countries = load_countries()

# 새 국가 추가
new_country = st.sidebar.text_input("추가할 국가 이름")
if st.sidebar.button("국가 추가"):
    if new_country and new_country not in countries:
        countries.append(new_country)
        save_countries(countries)
        st.sidebar.success(f"'{new_country}' 국가가 추가되었습니다!")
        st.rerun()

# 국가 삭제
if countries:
    delete_country = st.sidebar.selectbox("삭제할 국가 선택", countries)
    if st.sidebar.button("선택 국가 삭제"):
        countries.remove(delete_country)
        save_countries(countries)
        if st.session_state.selected_country == delete_country:
            st.session_state.selected_country = None
        st.sidebar.warning(f"'{delete_country}' 국가가 삭제되었습니다.")
        st.rerun()

# --- 메인 화면 로직 ---

# 1. 국가 선택 전 홈 화면
if st.session_state.selected_country is None:
    st.title("🌍 여행 국가 선택")
    st.write("작성할 국가를 아래 버튼에서 클릭하거나, 사이드바에서 새로 추가해 주세요.")
    st.markdown("---")

    if not countries:
        st.info("등록된 국가가 없습니다. 사이드바에서 국가를 추가해 주세요!")
    else:
        cols = st.columns(3)
        for idx, country in enumerate(countries):
            with cols[idx % 3]:
                if st.button(f"📍 {country} 가계부로 이동", key=f"btn_{country}", use_container_width=True):
                    st.session_state.selected_country = country
                    st.rerun()

# 2. 특정 국가 진입 화면
else:
    current_country = st.session_state.selected_country

    col_title, col_back = st.columns([4, 1])
    with col_title:
        st.title(f"✈️ {current_country} 가계부")
    with col_back:
        if st.button("⬅️ 다른 국가 선택"):
            st.session_state.selected_country = None
            st.rerun()

    st.write(f"**{current_country}** 전용 가계부입니다. 현지 통화(유로, 파운드 등)나 원화로 자유롭게 입력해 주세요.")

    # 수입/지출 입력 폼
    input_col1, input_col2 = st.columns([1, 2])
    with input_col1:
        selected_date = st.date_input("날짜 선택", datetime.now())
        selected_date_str = selected_date.strftime("%Y-%m-%d")

    with input_col2:
        user_input = st.text_input("내용 입력 (예: '점심 15파운드 카드', '현금으로 50유로 환전', '택시비 8000원'):")

    if st.button("AI로 내역 기록하기"):
        if not user_input:
            st.warning("내용을 입력해주세요!")
        else:
            with st.spinner(f"AI가 {current_country} 내역을 분석 중입니다..."):
                parsed_data = parse_expense_with_ai(user_input, current_country, selected_date_str, API_KEY)

                if parsed_data and isinstance(parsed_data, dict):
                    current_data = load_data()
                    current_data.append(parsed_data)
                    save_data(current_data)

                    trans_type = parsed_data.get('type', '지출')
                    pay_method = parsed_data.get('payment_method', '카드')
                    st.success(
                        f"기록 완료! 👉 [{parsed_data.get('date')}] "
                        f"[{trans_type}/{pay_method}/{parsed_data.get('category')}] {parsed_data.get('description')} : "
                        f"{parsed_data.get('amount_krw', 0):,}원 ({parsed_data.get('original_amount_text', '')})"
                    )

    st.markdown("---")
    
    # 내역 목록 및 탭 구분
    st.subheader(f"📊 {current_country} 수입/지출 내역 전체 분석")
    data = load_data()

    if data:
        df = pd.DataFrame(data)

        # 현재 선택된 국가의 데이터만 필터링
        if "country" in df.columns:
            country_df = df[df["country"] == current_country].copy()
        else:
            country_df = pd.DataFrame()

        if not country_df.empty:
            # 구버전 데이터 호환성을 위한 하위 호환 컬럼 자동 생성
            if "type" not in country_df.columns:
                country_df["type"] = "지출"
            if "payment_method" not in country_df.columns:
                country_df["payment_method"] = "카드"
            if "amount_krw" not in country_df.columns:
                country_df["amount_krw"] = country_df["amount"] if "amount" in country_df.columns else 0
            if "original_amount_text" not in country_df.columns:
                country_df["original_amount_text"] = ""

            tab1, tab2, tab3 = st.tabs(["📋 전체 보기 (개별 삭제 가능)", "🏷️ 카테고리별 전체 보기", "📅 날짜별 전체 보기"])

            # 1. 전체 보기 (개별 삭제 기능 포함)
            with tab1:
                total_income = country_df[country_df["type"] == "수입"]["amount_krw"].sum()
                total_expense = country_df[country_df["type"] == "지출"]["amount_krw"].sum()
                balance = total_income - total_expense

                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.metric(label="💵 총 입금 금액", value=f"{total_income:,}원")
                m_col2.metric(label="💸 총 지출 금액", value=f"{total_expense:,}원")
                m_col3.metric(label="💰 현재 남은 잔액", value=f"{balance:,}원")
                
                st.markdown("---")

                # 헤더 출력
                h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7 = st.columns([1.5, 1, 1, 1.5, 2.5, 2, 0.8])
                h_col1.markdown("**날짜**")
                h_col2.markdown("**구분**")
                h_col3.markdown("**수단**")
                h_col4.markdown("**카테고리**")
                h_col5.markdown("**내용**")
                h_col6.markdown("**금액(원)**")
                h_col7.markdown("**삭제**")

                # 개별 행 목록 출력 및 삭제 처리
                for _, row in country_df.iterrows():
                    r_col1, r_col2, r_col3, r_col4, r_col5, r_col6, r_col7 = st.columns([1.5, 1, 1, 1.5, 2.5, 2, 0.8])
                    r_col1.write(row.get("date", ""))
                    r_col2.write(row.get("type", "지출"))
                    r_col3.write(row.get("payment_method", "카드"))
                    r_col4.write(row.get("category", ""))
                    r_col5.write(row.get("description", ""))
                    
                    orig_text = row.get("original_amount_text", "")
                    orig_display = f" ({orig_text})" if pd.notna(orig_text) and orig_text else ""
                    r_col6.write(f"{row.get('amount_krw', 0):,}원{orig_display}")
                    
                    # 삭제 버튼
                    if r_col7.button("🗑️", key=f"del_{row.get('id')}"):
                        all_data = load_data()
                        updated_data = [item for item in all_data if item.get("id") != row.get("id")]
                        save_data(updated_data)
                        st.toast("선택한 항목이 삭제되었습니다!")
                        st.rerun()

            # 2. 카테고리별 보기
            with tab2:
                categories = country_df["category"].unique()
                for cat in categories:
                    st.markdown(f"#### 🏷️ 카테고리: {cat}")
                    cat_df = country_df[country_df["category"] == cat][["date", "type", "payment_method", "description", "amount_krw"]].copy()
                    cat_df.columns = ["날짜", "구분", "수단", "내용", "금액(원)"]
                    st.dataframe(cat_df, use_container_width=True)
                    cat_total = cat_df["금액(원)"].sum()
                    st.caption(f"👉 **{cat}** 합계: **{cat_total:,}원**")
                    st.markdown("---")

            # 3. 날짜별 보기
            with tab3:
                dates = sorted(country_df["date"].unique(), reverse=True)
                for dt in dates:
                    st.markdown(f"#### 📅 날짜: {dt}")
                    dt_df = country_df[country_df["date"] == dt][["type", "payment_method", "category", "description", "amount_krw"]].copy()
                    dt_df.columns = ["구분", "수단", "카테고리", "내용", "금액(원)"]
                    st.dataframe(dt_df, use_container_width=True)

                    dt_income = dt_df[dt_df["구분"] == "수입"]["금액(원)"].sum()
                    dt_expense = dt_df[dt_df["구분"] == "지출"]["금액(원)"].sum()
                    st.caption(f"👉 **{dt}** 합계 — 수입: **{dt_income:,}원** / 지출: **{dt_expense:,}원**")
                    st.markdown("---")

            # CSV 엑셀 다운로드 기능
            st.markdown("---")
            csv_cols = ["date", "type", "payment_method", "category", "description", "amount_krw", "original_amount_text"]
            csv_data = country_df[csv_cols].copy()
            csv_data.columns = ["날짜", "구분", "결제수단", "카테고리", "내용", "금액(원)", "입력금액(표현)"]
            csv = csv_data.to_csv(index=False, encoding="utf-8-sig")

            st.download_button(
                label=f"📥 {current_country} 가계부 엑셀(CSV) 다운로드",
                data=csv,
                file_name=f"{current_country}_가계부_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

        else:
            st.info(f"아직 {current_country}에 기록된 내역이 없습니다.")
    else:
        st.info(f"아직 {current_country}에 기록된 내역이 없습니다.")

    # 전체 데이터 초기화 버튼
    st.markdown("---")
    if st.button("전체 데이터 초기화"):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            st.rerun()
