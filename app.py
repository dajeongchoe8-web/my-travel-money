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


# AI 분석 함수
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


# --- Streamlit UI 설정 (모바일 최적화 centered) ---
st.set_page_config(page_title="✈️ 자유 추가형 글로벌 가계부", page_icon="✈️", layout="centered")

# 세션 상태 초기화
if "selected_country" not in st.session_state:
    st.session_state.selected_country = None

# 사이드바 설정
st.sidebar.header("➕ 국가 추가 및 관리")
countries = load_countries()

new_country = st.sidebar.text_input("추가할 국가 이름")
if st.sidebar.button("국가 추가"):
    if new_country and new_country not in countries:
        countries.append(new_country)
        save_countries(countries)
        st.sidebar.success(f"'{new_country}' 국가가 추가되었습니다!")
        st.rerun()

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
    st.write("작성할 국가를 선택하거나 사이드바에서 새 국가를 추가해 주세요.")
    st.markdown("---")

    if not countries:
        st.info("등록된 국가가 없습니다.")
    else:
        for country in countries:
            if st.button(f"📍 {country} 가계부로 이동", key=f"btn_{country}", use_container_width=True):
                st.session_state.selected_country = country
                st.rerun()

# 2. 특정 국가 진입 화면
else:
    current_country = st.session_state.selected_country

    col_title, col_back = st.columns([3, 1])
    with col_title:
        st.title(f"✈️ {current_country} 가계부")
    with col_back:
        if st.button("⬅️ 이동"):
            st.session_state.selected_country = None
            st.rerun()

    # 수입/지출 입력 폼
    selected_date = st.date_input("날짜 선택", datetime.now())
    selected_date_str = selected_date.strftime("%Y-%m-%d")

    # 입력창 자동 초기화를 위한 Key 적용
    user_input = st.text_input(
        "내용 입력",
        placeholder="예: '점심 15파운드 카드', '50유로 환전'",
        key="user_input_field"
    )

    if st.button("AI로 내역 기록하기", use_container_width=True):
        if not user_input:
            st.warning("내용을 입력해주세요!")
        else:
            with st.spinner("AI가 내역 분석 중..."):
                parsed_data = parse_expense_with_ai(user_input, current_country, selected_date_str, API_KEY)

                if parsed_data and isinstance(parsed_data, dict):
                    current_data = load_data()
                    current_data.append(parsed_data)
                    save_data(current_data)

                    trans_type = parsed_data.get('type', '지출')
                    pay_method = parsed_data.get('payment_method', '카드')
                    st.toast(f"기록 완료! [{trans_type}] {parsed_data.get('description')} ({parsed_data.get('amount_krw', 0):,}원)")
                    
                    # 입력 필드 자동 지우기 후 새로고침
                    st.session_state["user_input_field"] = ""
                    st.rerun()

    st.markdown("---")
    
    # 내역 목록 분석
    data = load_data()

    if data:
        df = pd.DataFrame(data)

        if "country" in df.columns:
            country_df = df[df["country"] == current_country].copy()
        else:
            country_df = pd.DataFrame()

        if not country_df.empty:
            # 구버전 호환성 컬럼 보장
            if "type" not in country_df.columns:
                country_df["type"] = "지출"
            if "payment_method" not in country_df.columns:
                country_df["payment_method"] = "카드"
            if "amount_krw" not in country_df.columns:
                country_df["amount_krw"] = country_df["amount"] if "amount" in country_df.columns else 0
            if "original_amount_text" not in country_df.columns:
                country_df["original_amount_text"] = ""

            # 4가지 메인 탭 설정 (입출금 구분 탭 추가)
            tab1, tab2, tab3, tab4 = st.tabs(["📋 전체 보기", "💵/💸 입출금 보기", "🏷️ 카테고리별", "📅 날짜별"])

            total_income = country_df[country_df["type"] == "수입"]["amount_krw"].sum()
            total_expense = country_df[country_df["type"] == "지출"]["amount_krw"].sum()
            balance = total_income - total_expense

            # 1. 전체 보기 (모바일 반응형 카드 구조)
            with tab1:
                st.metric(label="💰 남은 잔액", value=f"{balance:,}원")
                st.caption(f"총 입금: {total_income:,}원 / 총 지출: {total_expense:,}원")
                st.markdown("---")

                # 스마트폰에 최적화된 카드형 리스트
                for _, row in country_df.sort_values(by="date", ascending=False).iterrows():
                    orig_text = row.get("original_amount_text", "")
                    orig_display = f" ({orig_text})" if pd.notna(orig_text) and orig_text else ""
                    type_icon = "💵" if row.get("type") == "수입" else "💸"

                    with st.container():
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**{type_icon} {row.get('description', '')}**")
                            st.caption(
                                f"{row.get('date')} | {row.get('type')} ({row.get('payment_method')}) | {row.get('category')}"
                            )
                            st.markdown(f"**금액:** {row.get('amount_krw', 0):,}원{orig_display}")
                        with c2:
                            if st.button("🗑️", key=f"del_{row.get('id')}"):
                                all_data = load_data()
                                updated_data = [item for item in all_data if item.get("id") != row.get("id")]
                                save_data(updated_data)
                                st.toast("삭제되었습니다!")
                                st.rerun()
                        st.markdown("---")

            # 2. 입금/출금 구분 보기 탭 (새로 추가)
            with tab2:
                st.markdown("#### 💵 수입 (입금) 내역")
                inc_df = country_df[country_df["type"] == "수입"][["date", "payment_method", "description", "amount_krw"]].copy()
                if not inc_df.empty:
                    inc_df.columns = ["날짜", "수단", "내용", "금액(원)"]
                    st.dataframe(inc_df, use_container_width=True)
                    st.caption(f"👉 총 입금 합계: **{total_income:,}원**")
                else:
                    st.info("입금 내역이 없습니다.")

                st.markdown("---")
                st.markdown("#### 💸 지출 (출금) 내역")
                exp_df = country_df[country_df["type"] == "지출"][["date", "payment_method", "category", "description", "amount_krw"]].copy()
                if not exp_df.empty:
                    exp_df.columns = ["날짜", "수단", "카테고리", "내용", "금액(원)"]
                    st.dataframe(exp_df, use_container_width=True)
                    st.caption(f"👉 총 지출 합계: **{total_expense:,}원**")
                else:
                    st.info("지출 내역이 없습니다.")

            # 3. 카테고리별 보기
            with tab3:
                categories = country_df["category"].unique()
                for cat in categories:
                    st.markdown(f"#### 🏷️ {cat}")
                    cat_df = country_df[country_df["category"] == cat][["date", "type", "description", "amount_krw"]].copy()
                    cat_df.columns = ["날짜", "구분", "내용", "금액(원)"]
                    st.dataframe(cat_df, use_container_width=True)
                    cat_total = cat_df["금액(원)"].sum()
                    st.caption(f"👉 **{cat}** 합계: **{cat_total:,}원**")
                    st.markdown("---")

            # 4. 날짜별 보기
            with tab4:
                dates = sorted(country_df["date"].unique(), reverse=True)
                for dt in dates:
                    st.markdown(f"#### 📅 {dt}")
                    dt_df = country_df[country_df["date"] == dt][["type", "category", "description", "amount_krw"]].copy()
                    dt_df.columns = ["구분", "카테고리", "내용", "금액(원)"]
                    st.dataframe(dt_df, use_container_width=True)

                    dt_income = dt_df[dt_df["구분"] == "수입"]["금액(원)"].sum()
                    dt_expense = dt_df[dt_df["구분"] == "지출"]["금액(원)"].sum()
                    st.caption(f"👉 합계 — 입금: **{dt_income:,}원** / 지출: **{dt_expense:,}원**")
                    st.markdown("---")

            # CSV 엑셀 다운로드
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
                use_container_width=True
            )

        else:
            st.info(f"아직 {current_country}에 기록된 내역이 없습니다.")
    else:
        st.info(f"아직 {current_country}에 기록된 내역이 없습니다.")

    st.markdown("---")
    if st.button("전체 데이터 초기화", use_container_width=True):
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            st.rerun()
