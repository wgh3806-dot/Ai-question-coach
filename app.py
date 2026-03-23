import streamlit as st
import html
from prompt_engine import (
    init_client,
    generate_prompt,
    evaluate_prompt,
    refine_prompt,
    parse_user_input
)
from data_manager import (
    add_usage,
    check_budget,
    tokens_to_krw,
    get_today_usage
)

def copy_button(text, key):
    safe_text = html.escape(text)

    st.components.v1.html(f"""
        <button onclick="navigator.clipboard.writeText(`{safe_text}`)" 
        style="background-color:#4CAF50;color:white;padding:8px 12px;border:none;border-radius:6px;cursor:pointer;">
        복사하기
        </button>
    """, height=40)

# -------------------------------
# 기본 설정
# -------------------------------
st.set_page_config(page_title="생성형 AI 질문 코치", page_icon="🧠", layout="centered")

st.title("생성형 AI 질문(프롬프트) 코치")
st.markdown("""
AI가 당신의 질문을 분석하고  
더 정확하고 잘 작동하는 프롬프트로 개선합니다.
""")

st.divider()

# -------------------------------
# 세션 초기화
# -------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

# 템플릿 입력값
if "situation_input" not in st.session_state:
    st.session_state.situation_input = ""

if "goal_input" not in st.session_state:
    st.session_state.goal_input = ""

from datetime import datetime

# 사용자 요청 횟수
if "request_count" not in st.session_state:
    st.session_state.request_count = 0

# 날짜 저장
if "request_date" not in st.session_state:
    st.session_state.request_date = datetime.now().strftime("%Y-%m-%d")

today = datetime.now().strftime("%Y-%m-%d")

if st.session_state.request_date != today:
    st.session_state.request_count = 0
    st.session_state.request_date = today

MAX_REQUEST = 30

def check_user_limit():
    return st.session_state.request_count < MAX_REQUEST

# -------------------------------
# API 키 입력
# -------------------------------
st.subheader("1. API 설정")

api_key = st.text_input("OpenAI API Key 입력", type="password")

if api_key:
    try:
        init_client(api_key)
        st.success("API 연결 완료")
    except Exception as e:
        st.error(f"API 초기화 오류: {e}")

with st.expander("사용 방법 보기"):
    st.markdown("""
1. 템플릿 선택 또는 자유롭게 입력하세요  
2. 프롬프트 생성 버튼을 클릭하세요  
3. 결과를 확인하고 평가/개선을 활용하세요  
4. 최종 결과를 복사해서 사용하세요  
""")        



# -------------------------------
# 입력 영역
# -------------------------------
st.markdown("## STEP 1. 입력")

st.markdown("### 자유 입력 (AI 자동 분석)")

free_input = st.text_area(
    "그냥 편하게 입력하세요",
    height=100,
    placeholder="예: 스마트시티 사업 관련 보도자료 써줘"
)

if st.button("자동 분석"):
    if free_input.strip():
        with st.spinner("분석 중..."):
            try:
                situation_part, goal_part = parse_user_input(free_input)

                st.session_state.situation_input = situation_part
                st.session_state.goal_input = goal_part

                st.success("자동 입력 완료")

            except Exception as e:
                st.error(f"분석 오류: {e}")

st.markdown("### 빠른 템플릿 선택")

# 1행
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("보고서 작성"):
        st.session_state.situation_input = "업무 보고서를 작성해야 하는 상황"
        st.session_state.goal_input = "논리적이고 구조적인 보고서 초안 작성"

with col2:
    if st.button("이메일 작성"):
        st.session_state.situation_input = "민원인 또는 내부 직원에게 이메일을 보내야 하는 상황"
        st.session_state.goal_input = "정중하고 명확한 업무 이메일 작성"

with col3:
    if st.button("계획서 작성"):  # ✅ 변경됨
        st.session_state.situation_input = "사업 또는 프로젝트 계획서를 작성해야 하는 상황"
        st.session_state.goal_input = "실행 가능하고 설득력 있는 계획서 작성"

# 2행
col4, col5, col6 = st.columns(3)

with col4:
    if st.button("보도자료 작성"):  # ✅ 추가
        st.session_state.situation_input = "기관의 정책 또는 사업을 외부에 알리기 위한 보도자료를 작성해야 하는 상황"
        st.session_state.goal_input = "언론에 적합한 형식의 명확하고 신뢰감 있는 보도자료 작성"

with col5:
    if st.button("국민신문고 답변"):  # ✅ 추가
        st.session_state.situation_input = "국민신문고 민원에 대해 공식 답변을 작성해야 하는 상황"
        st.session_state.goal_input = "정중하고 법적 문제 없이 명확한 민원 답변 작성"

with col6:
    if st.button("정보공개청구 답변"):  # ✅ 추가
        st.session_state.situation_input = "정보공개청구 요청에 대해 답변을 작성해야 하는 상황"
        st.session_state.goal_input = "관련 법령을 준수하면서 명확한 정보 제공 답변 작성"

# 3행
col7, col8, col9 = st.columns(3)

with col7:
    if st.button("행사 시나리오"):  # ✅ 추가
        st.session_state.situation_input = "위원회, 행사 또는 공식 일정 진행을 위한 시나리오를 작성해야 하는 상황"
        st.session_state.goal_input = "행사 흐름이 자연스럽고 진행이 원활한 시나리오 작성"

situation = st.text_area(
    "상황",
    height=100,
    key="situation_input"
)

goal = st.text_area(
    "목표",
    height=100,
    key="goal_input"
)

style = st.selectbox("스타일 선택", ["전문가형", "간결형", "초간결형"])

st.caption(f"오늘 남은 사용 횟수: {MAX_REQUEST - st.session_state.request_count}회")

# -------------------------------
# 프롬프트 생성
# -------------------------------
st.markdown("## STEP 2. 프롬프트 생성")
if st.button("프롬프트 생성"):
    if not api_key:
        st.warning("API 키를 먼저 입력하세요.")

    elif not check_user_limit():
        st.error("오늘 사용 가능한 요청 횟수를 초과했습니다.")

    else:
        allowed, cost = check_budget(limit_krw=1000)

        if not allowed:
            st.error("현재 사용량이 많아 잠시 후 다시 시도해주세요.")
        else:
            with st.spinner("생성 중..."):
                try:
                    result, tokens = generate_prompt(
                                                        st.session_state.situation_input,
                                                        st.session_state.goal_input,
                                                        style
                                                    )

                    add_usage(tokens)

                    # ✅ 요청 카운트 증가
                    st.session_state.request_count += 1

                    st.session_state.last_prompt = result
                    st.session_state.history.append(result)

                    st.markdown("### 생성 결과")

                    with st.container():
                        st.code(result, language="markdown")

                        # ✅ 복사 버튼 (여기)
                        copy_button(result, "copy_gen")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

# -------------------------------
# 프롬프트 평가
# -------------------------------
st.markdown("## STEP 3. 평가 및 개선")

col1, col2 = st.columns(2)

with col1:
    eval_clicked = st.button("프롬프트 평가")

with col2:
    refine_clicked = st.button("프롬프트 개선")

if eval_clicked:
    if not st.session_state.last_prompt:
        st.warning("먼저 프롬프트를 생성하세요.")

    elif not check_user_limit():
        st.error("오늘 사용 가능한 요청 횟수를 초과했습니다.")

    else:
        allowed, cost = check_budget(limit_krw=1000)

        if not allowed:
            st.error("현재 사용량이 많아 잠시 후 다시 시도해주세요.")
        else:
            with st.spinner("평가 중..."):
                try:
                    result, tokens = evaluate_prompt(st.session_state.last_prompt, style)

                    add_usage(tokens)

                    st.session_state.request_count += 1

                    with st.container():
                        st.markdown("### 평가 결과")
                        st.write(result)
                        copy_button(result, "copy_eval")

                except Exception as e:
                    st.error(f"오류 발생: {e}")
        

# -------------------------------
# 프롬프트 개선
# -------------------------------
st.subheader("4. 프롬프트 개선")

feedback = st.text_area("수정 요청", placeholder="예: 더 간결하게, 마케팅 느낌으로 등")

if refine_clicked:
    if not st.session_state.last_prompt:
        st.warning("먼저 프롬프트를 생성하세요.")

    elif not check_user_limit():
        st.error("오늘 사용 가능한 요청 횟수를 초과했습니다.")

    else:
        allowed, cost = check_budget(limit_krw=1000)

        if not allowed:
            st.error("현재 사용량이 많아 잠시 후 다시 시도해주세요.")
        else:
            with st.spinner("개선 중..."):
                try:
                    result, tokens = refine_prompt(
                        st.session_state.last_prompt,
                        feedback,
                        style
                    )

                    add_usage(tokens)
                    st.session_state.request_count += 1

                    st.session_state.history.append(result)
                    st.session_state.last_prompt = result

                    with st.container():
                        st.markdown("### 개선된 프롬프트")
                        st.code(result, language="markdown")
                        copy_button(result, "copy_refine")

                except Exception as e:
                    st.error(f"오류 발생: {e}")

# -------------------------------
# 히스토리 & 비교
# -------------------------------
st.markdown("## STEP 4. 결과 히스토리")

if st.session_state.history:
    for i, item in enumerate(st.session_state.history):
        with st.expander(f"버전 {i+1}"):
            st.code(item, language="markdown")

            copy_button(item, f"copy_hist_{i}")

# -------------------------------
# Before / After 비교
# -------------------------------
st.subheader("6. 비교")

if len(st.session_state.history) >= 2:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 이전")
        st.code(st.session_state.history[-2], language="markdown")

    with col2:
        st.markdown("### 현재")
        st.code(st.session_state.history[-1], language="markdown")