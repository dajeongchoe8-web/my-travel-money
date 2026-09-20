import json
import time
import uuid
from datetime import datetime
import pandas as pd
from google import genai
from google.genai import types
import streamlit as st
from supabase import create_client, Client

# ==========================================
# 🔑 API 키 및 Secrets에서 Supabase 정보 가져오기
# ==========================================
API_KEY = "AQ.Ab8RN6KJthDRoQQeW3-N9qsx9bRUd4j3FlNvdTwfk-FuAa5gDw"

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    SUPABASE_URL = ""
    SUPABASE_KEY = ""


def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Streamlit Secrets에 SUPABASE_URL과 SUPABASE_KEY를 설정해 주세요!")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# --- DB 통신 함수 ---
def load_data():
    try:
        supabase = get_supabase()
        response = supabase.table("expenses").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return []


def save_single_data(item):
    try:
        supabase = get_supabase()
        supabase.table("expenses").insert(item).execute()
        return True
    except Exception as e:
        st.error(f"데이터 저장 실패: {e}")
        return False


def delete_single_data(item_id):
    try:
        supabase = get_supabase()
        supabase.table("expenses").delete().eq("id", item_id).execute()
        return True
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False


def clear_all_data():
    try:
        supabase = get_supabase()
        supabase.table("expenses").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return True
    except Exception as e:
        st.error(f"초기화 실패: {e}")
        return False


def load_countries():
    try:
        supabase = get_supabase()
        response = supabase.table("countries").select("name").execute()
        if response.data:
            return [r["name"] for r in response.data]
    except Exception:
        pass
    return ["한국", "영국", "프랑스", "미국", "일본", "유로(공통)"]


def add_country_db(country_name):
    try:
        supabase = get_supabase()
        supabase.table("countries").insert({"name": country_name}).execute()
        return True
    except Exception:
        return False


def delete_country_db(country_name):
    try:
        supabase = get_supabase()
        supabase.table("countries").delete().eq("name", country_name).execute()
        return True
    except Exception:
        return False


# AI 분석 함수 (gemini-1.5-flash 모델 적용)
def parse_expense_with_ai(user_input, selected_country, selected_city, selected_date_str, api_key):
    if not api_key:
        st.error("API Key가 지정되지 않았습니다.")
        return None

    client = genai.Client(api_key=api_key)

    city_info = f" ({selected_city})" if selected_city and selected_city != "전체" else ""

    prompt = f"""
    사용자의 수입/지출 내역을 분석해서 하나의 JSON 객체({{}}) 형식으로 응답해줘. 리스트([])로 감싸지 마.
    
    [기본 정보]
    - 국가: '{selected_country}'
    - 도시: '{selected_city if selected_city else "미지정"}'
    - 선택된 날짜: '{selected_date_str}'
    
    [필수 추출 키]
    - date: 입력에 별도 언급이 없으면 '{selected_date_str}' 사용 (YYYY-MM-DD)
    - country: '{selected_country}'
    - payment_method: '카드' 또는 '현금' 중 하나 (언급이 없으면 '카드'를 기본값으로 함)
    - type: '수입' 또는 '지출' 중 하나 (입금, 충전, 용돈, 돈 들어옴 등의 표현은 '수입')
    - category: 
      - type이 '수입'인 경우: '수입(입금)'
      - type이 '지출'인 경우: 식비, 교통, 쇼핑, 숙박, 여가, 기타 중 하나
    - amount_krw: 원화 기준 최종 환산 금액 (숫자만, 정수 형태)
    - original_amount_text: 입력된 원본 금액 표현 (예: "15 GBP", "20 EUR", "15000원")
    - description: 간단한 내역 요약 (예: "점심 식사{city_info}")
    
    사용자 입력: "{user_input}"
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
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
                if selected_city and selected_city != "전체":
                    result["city"] = selected_city

            return result

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                st.error(f"AI 분석 오류: {e}")
                return None


# --- 입력 제출 처리 함수 ---
def process_submission(country, city, date_str):
    user_input = st.session_state.get("user_input_field", "").strip()
    if not user_input:
        st.warning("내용을 입력해주세요!")
        return

    with st.spinner("AI 분석 및 DB 저장 중..."):
        parsed_data = parse_expense_with_ai(user_input, country, city, date_str, API_KEY)
        if parsed_data and isinstance(parsed_data, dict):
            target_city = city if (city and city != "전체") else "기본"
            parsed_data["city"] = target_city

            if save_single_data(parsed_data):
                st.session_state["user_input_field"] = ""
                st.toast(f"✅ [{target_city}] 저장 완료! {parsed_data.get('description')} ({parsed_data.get('amount_krw', 0):,}원)")


# --- Streamlit UI 설정 ---
st.set_page_config(page_title="✈️ 자유 추가형 글로벌 가계부", page_icon="✈️", layout="centered")

if "selected_country" not in st.session_state:
    st.session_state.selected_country = None

if "cities" not in st.session_state:
    st.session_state.cities = {}

# 사이드바: 국가 및 도시 관리
st.sidebar.header("➕ 국가 및 도시 관리")
countries = load_countries()

# 국가 추가
new_country = st.sidebar.text_input("추가할 국가 이름")
if st.sidebar.button("국가 추가"):
    if new_country and new_country not in countries:
        if add_country_db(new_country):
            st.sidebar.success(f"'{new_country}' 국가 추가 완료!")
            st.rerun()

# 특정 국가 선택 시 도시 관리 활성화
current_country = st.session_state.selected_country
if current_country:
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"🏙️ {current_country} 도시 관리")

    if current_country not in st.session_state.cities:
        st.session_state.cities[current_country] = ["전체"]

    new_city = st.sidebar.text_input(f"[{current_country}] 도시 추가", placeholder="예: 런던, 파리")
    if st.sidebar.button("도시 추가"):
        if new_city and new_city not in st.session_state.cities[current_country]:
            st.session_state.cities[current_country].append(new_city)
            st.sidebar.success(f"도시 '{new_city}' 추가 완료!")
            st.rerun()

    existing_cities = [c for c in st.session_state.cities[current_country] if c != "전체"]
    if existing_cities:
        del_city = st.sidebar.selectbox("삭제할 도시 선택", existing_cities)
        if st.sidebar.button("선택 도시 삭제"):
            st.session_state.cities[current_country].remove(del_city)
            st.sidebar.warning(f"도시 '{del_city}'가 삭제되었습니다.")
            st.rerun()

    st.sidebar.markdown("---")

if countries and not current_country:
    delete_country = st.sidebar.selectbox("삭제할 국가 선택", countries)
    if st.sidebar.button("선택 국가 삭제"):
        if delete_country_db(delete_country):
            st.sidebar.warning(f"'{delete_country}' 국가가 삭제되었습니다.")
            st.rerun()


# --- 메인 화면 로직 ---

# 1. 국가 선택 홈 화면
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
    col_title, col_back = st.columns([3, 1])
    with col_title:
        st.title(f"✈️ {current_country} 가계부")
    with col_back:
        if st.button("⬅️ 국가 선택"):
            st.session_state.selected_country = None
            st.rerun()

    # 도시 선택 탭/필터
    city_list = st.session_state.cities.get(current_country, ["전체"])
    if "전체" not in city_list:
        city_list.insert(0, "전체")

    selected_city = st.radio("🏙️ 도시 선택/필터", city_list, horizontal=True)

    st.markdown("---")

    # 수입/지출 입력 폼
    selected_date = st.date_input("날짜 선택", datetime.now())
    selected_date_str = selected_date.strftime("%Y-%m-%d")

    target_city_display = f" [{selected_city}]" if selected_city != "전체" else ""
    st.text_input(
        f"내용 입력{target_city_display}",
        placeholder="예: '점심 15파운드 카드', '50유로 환전'",
        key="user_input_field"
    )

    st.button(
        f"AI로 내역 기록하기 ({selected_city})",
        use_container_width=True,
        on_click=process_submission,
        args=(current_country, selected_city, selected_date_str)
    )

    st.markdown("---")

    # 데이터 로드 및 도시별 필터링
    data = load_data()

    if data:
        df = pd.DataFrame(data)

        if "country" in df.columns:
            country_df = df[df["country"] == current_country].copy()
        else:
            country_df = pd.DataFrame()

        # 도시 필터링
        if not country_df.empty and selected_city != "전체":
            if "city" in country_df.columns:
                country_df = country_df[country_df["city"] == selected_city].copy()

        if not country_df.empty:
            if "type" not in country_df.columns:
                country_df["type"] = "지출"
            if "payment_method" not in country_df.columns:
                country_df["payment_method"] = "카드"
            if "amount_krw" not in country_df.columns:
                country_df["amount_krw"] = country_df["amount"] if "amount" in country_df.columns else 0
            if "original_amount_text" not in country_df.columns:
                country_df["original_amount_text"] = ""
            if "city" not in country_df.columns:
                country_df["city"] = "기본"

            tab1, tab2, tab3, tab4 = st.tabs(["📋 전체 보기", "💵/💸 입출금 보기", "🏷️ 카테고리별", "📅 날짜별"])

            total_income = country_df[country_df["type"] == "수입"]["amount_krw"].sum()
            total_expense = country_df[country_df["type"] == "지출"]["amount_krw"].sum()
            balance = total_income - total_expense

            # 1. 전체 보기
            with tab1:
                st.metric(label=f"💰 {selected_city} 남은 잔액", value=f"{balance:,}원")
                st.caption(f"총 입금: {total_income:,}원 / 총 지출: {total_expense:,}원")
                st.markdown("---")

                for _, row in country_df.sort_values(by="date", ascending=False).iterrows():
                    orig_text = row.get("original_amount_text", "")
                    orig_display = f" ({orig_text})" if pd.notna(orig_text) and orig_text else ""
                    type_icon = "💵" if row.get("type") == "수입" else "💸"
                    row_city = row.get("city", "기본")
                    city_tag = f" 📍[{row_city}]" if row_city and row_city != "기본" else ""

                    with st.container():
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**{type_icon} {row.get('description', '')}{city_tag}**")
                            st.caption(
                                f"{row.get('date')} | {row.get('type')} ({row.get('payment_method')}) | {row.get('category')}"
                            )
                            st.markdown(f"**금액:** {row.get('amount_krw', 0):,}원{orig_display}")
                        with c2:
                            if st.button("🗑️", key=f"del_{row.get('id')}"):
                                if delete_single_data(row.get("id")):
                                    st.toast("삭제되었습니다!")
                                    st.rerun()
                        st.markdown("---")

            # 2. 입/출금 탭
            with tab2:
                st.markdown("#### 💵 수입 (입금) 내역")
                inc_df = country_df[country_df["type"] == "수입"][["date", "city", "payment_method", "description", "amount_krw"]].copy()
                if not inc_df.empty:
                    inc_df.columns = ["날짜", "도시", "수단", "내용", "금액(원)"]
                    st.dataframe(inc_df, use_container_width=True)
                    st.caption(f"👉 총 입금 합계: **{total_income:,}원**")
                else:
                    st.info("입금 내역이 없습니다.")

                st.markdown("---")
                st.markdown("#### 💸 지출 (출금) 내역")
                exp_df = country_df[country_df["type"] == "지출"][["date", "city", "payment_method", "category", "description", "amount_krw"]].copy()
                if not exp_df.empty:
                    exp_df.columns = ["날짜", "도시", "수단", "카테고리", "내용", "금액(원)"]
                    st.dataframe(exp_df, use_container_width=True)
                    st.caption(f"👉 총 지출 합계: **{total_expense:,}원**")
                else:
                    st.info("지출 내역이 없습니다.")

            # 3. 카테고리별
            with tab3:
                categories = country_df["category"].unique()
                for cat in categories:
                    st.markdown(f"#### 🏷️ {cat}")
                    cat_df = country_df[country_df["category"] == cat][["date", "city", "type", "description", "amount_krw"]].copy()
                    cat_df.columns = ["날짜", "도시", "구분", "내용", "금액(원)"]
                    st.dataframe(cat_df, use_container_width=True)
                    cat_total = cat_df["금액(원)"].sum()
                    st.caption(f"👉 **{cat}** 합계: **{cat_total:,}원**")
                    st.markdown("---")

            # 4. 날짜별
            with tab4:
                dates = sorted(country_df["date"].unique(), reverse=True)
                for dt in dates:
                    st.markdown(f"#### 📅 {dt}")
                    dt_df = country_df[country_df["date"] == dt][["city", "type", "category", "description", "amount_krw"]].copy()
                    dt_df.columns = ["도시", "구분", "카테고리", "내용", "금액(원)"]
                    st.dataframe(dt_df, use_container_width=True)

                    dt_income = dt_df[dt_df["구분"] == "수입"]["금액(원)"].sum()
                    dt_expense = dt_df[dt_df["구분"] == "지출"]["금액(원)"].sum()
                    st.caption(f"👉 합계 — 입금: **{dt_income:,}원** / 지출: **{dt_expense:,}원**")
                    st.markdown("---")

            # CSV 다운로드
            st.markdown("---")
            csv_cols = ["date", "city", "type", "payment_method", "category", "description", "amount_krw", "original_amount_text"]
            csv_data = country_df[csv_cols].copy()
            csv_data.columns = ["날짜", "도시", "구분", "결제수단", "카테고리", "내용", "금액(원)", "입력금액(표현)"]
            csv = csv_data.to_csv(index=False, encoding="utf-8-sig")

            st.download_button(
                label=f"📥 [{current_country} - {selected_city}] 가계부 엑셀(CSV) 다운로드",
                data=csv,
                file_name=f"{current_country}_{selected_city}_가계부_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        else:
            st.info(f"아직 [{selected_city}]에 기록된 내역이 없습니다.")
    else:
        st.info(f"아직 {current_country}에 기록된 내역이 없습니다.")

    st.markdown("---")
    if st.button("전체 데이터 초기화", use_container_width=True):
        if clear_all_data():
            st.toast("모든 내역이 초기화되었습니다.")
            st.rerun()
