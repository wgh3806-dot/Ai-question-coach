import streamlit as st
import html
from prompt_engine import explain_diff
from prompt_engine import (
    init_client,
    generate_prompt,
    evaluate_prompt,
    refine_prompt,
    parse_user_input,
    detect_task_type   # 🔥 이거 추가
)
from data_manager import (
    add_usage,
    check_budget,
    tokens_to_krw,
    get_today_usage
)

import json

def copy_button(text, key):
    safe_text = json.dumps(text)

    st.components.v1.html(f"""
        <button onclick='navigator.clipboard.writeText({safe_text})'
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

st.markdown("## 🔗 AI 서비스 바로가기")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.link_button("ChatGPT", "https://chat.openai.com")

with col2:
    st.link_button("Gemini", "https://gemini.google.com")

with col3:
    st.link_button("Claude", "https://claude.ai")

with col4:
    st.link_button("Perplexity", "https://www.perplexity.ai")
    
# -------------------------------
# 세션 초기화
# -------------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = ""

if "eval_result" not in st.session_state:
    st.session_state.eval_result = ""

if "refine_result" not in st.session_state:
    st.session_state.refine_result = ""

if "selected_template" not in st.session_state:
    st.session_state.selected_template = None

if "mode" not in st.session_state:
    st.session_state.mode = "자동"

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

import os

api_key = st.secrets["OPENAI_API_KEY"]
init_client(api_key)

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
st.markdown("### 작업 모드 선택")

mode = st.radio(
    "작업 유형을 선택하세요",
    ["자동", "문서 작성", "정보 탐색"],
    index=0
)

st.session_state.mode = mode

st.markdown("## STEP 1. 입력")

st.info("이 시스템은 허위 정보 생성을 방지하기 위해 검증 기반 프롬프트만 생성합니다.")

input_mode = st.radio(
    "입력 방식 선택",
    ["자유 입력", "육하원칙 입력"]
)

if input_mode == "자유 입력":

    st.markdown("### 자유 입력 (AI 자동 분석)")

    free_input = st.text_area(
        "그냥 편하게 입력하세요",
        height=100,
        placeholder=
        "예: 스마트시티 사업 관련 보도자료 써줘"
    )

if input_mode == "육하원칙 입력":

    who = st.text_input("누가")
    what = st.text_input("무엇을")
    why = st.text_input("왜")
    when = st.text_input("언제")
    where = st.text_input("어디서")
    how = st.text_input("어떻게")

    st.session_state.situation_input = f"{when}, {where}에서 {who}가 {what}을 수행하는 상황"
    st.session_state.goal_input = f"{why} 목적을 달성하기 위해 {how} 방식으로 결과 생성"

if st.button("자동 분석"):
    if input_mode == "자유 입력" and free_input.strip():
        with st.spinner("분석 중..."):
            try:
                situation_part, goal_part = parse_user_input(free_input)

                st.session_state.situation_input = situation_part
                st.session_state.goal_input = goal_part

                # 👉 추가: 평가 실행
                eval_result, _ = evaluate_prompt(free_input, "전문가형")
                st.session_state.auto_eval = eval_result

                st.success("자동 입력 + 평가 완료")

            except Exception as e:
                st.error(f"분석 오류: {e}")
            if "auto_eval" in st.session_state:
                st.info("자동 분석 평가 결과")
                st.write(st.session_state.auto_eval)
template_mode = st.radio(
    "템플릿 적용 방식",
    ["새로 적용 (기존 내용 교체)", "기존 내용에 추가"]
)

st.markdown("### 빠른 템플릿 선택")
st.info(f"현재 템플릿 적용 방식: {template_mode}")

# 1행
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("보고서 작성"):
        st.session_state.selected_template = "보고서 작성" 
        base_situation = "업무 보고서를 작성해야 하는 상황"
        base_goal = "논리적이고 구조적인 보고서 초안 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")


        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


with col2:
    if st.button("이메일 작성"):
        st.session_state.selected_template = "이메일 작성" 
        base_situation = "민원인 또는 내부 직원에게 이메일을 보내야 하는 상황"
        base_goal = "정중하고 명확한 업무 이메일 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


with col3:
    if st.button("계획서 작성"):
        st.session_state.selected_template = "계획서 작성" 
        base_situation = "사업 또는 프로젝트 계획서를 작성해야 하는 상황"
        base_goal = "실행 가능하고 설득력 있는 계획서 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


# 2행
col4, col5, col6 = st.columns(3)

with col4:
    if st.button("보도자료 작성"):
        st.session_state.selected_template = "보도자료 작성" 
        base_situation = "기관의 정책 또는 사업을 외부에 알리기 위한 보도자료를 작성해야 하는 상황"
        base_goal = "언론에 적합한 형식의 명확하고 신뢰감 있는 보도자료 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


with col5:
    if st.button("국민신문고 답변"):
        st.session_state.selected_template = "국민신문고 답변" 
        base_situation = "국민신문고 민원에 대해 공식 답변을 작성해야 하는 상황"
        base_goal = "정중하고 법적 문제 없이 명확한 민원 답변 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


with col6:
    if st.button("정보공개청구 답변"):
        st.session_state.selected_template = "정보공개청구 답변" 
        base_situation = "정보공개청구 요청에 대해 답변을 작성해야 하는 상황"
        base_goal = "관련 법령을 준수하면서 명확한 정보 제공 답변 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")


# 3행
col7, col8, col9 = st.columns(3)

with col7:
    if st.button("행사 시나리오"):
        st.session_state.selected_template = "행사 시나리오" 
        base_situation = "위원회, 행사 또는 공식 일정 진행을 위한 시나리오를 작성해야 하는 상황"
        base_goal = "행사 흐름이 자연스럽고 진행이 원활한 시나리오 작성"

        if template_mode == "새로 적용 (기존 내용 교체)":
            st.session_state.situation_input = base_situation
            st.session_state.goal_input = base_goal
            st.success("템플릿이 새로 적용되었습니다")

        st.session_state.situation_input = (
            st.session_state.situation_input + " / " + base_situation
            if st.session_state.situation_input else base_situation
        )

        st.session_state.goal_input = (
            st.session_state.goal_input + " / " + base_goal
            if st.session_state.goal_input else base_goal
        )

        st.success("기존 입력에 템플릿이 추가되었습니다")

extra_input = st.text_area(
    "추가 요구사항",
    height=80,
    placeholder="예: 간부 보고용, 1페이지 요약, 쉬운 표현, 표 없이 문장형으로 작성"
)

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

style = st.radio(
    "스타일 선택",
    ["전문가형", "간결형", "초간결형"]
)

# 설명
if style == "전문가형":
    st.caption("구조 + 설명 포함 (학습용)")
    st.code("""1. 역할 (Role)
너는 공공기관 보고서 작성 전문가다.

2. 목표 (Goal)
상급자가 빠르게 이해할 수 있는 보고서를 작성한다.

3. 조건 (Instructions)
- 핵심 위주로 작성
- 논리 구조 유지
- 불필요한 표현 제거

4. 출력 형식 (Format)
- 제목 + 본문 구조
""")

elif style == "간결형":
    st.caption("실무용 문장형")
    st.code("""공공기관 보고서를 작성하되, 핵심만 간결하게 정리하고 상급자가 빠르게 이해할 수 있도록 작성하라.""")

elif style == "초간결형":
    st.caption("최소 문장")
    st.code("""보고서 작성. 핵심만.""")

# -------------------------------
# 프롬프트 미리보기
# -------------------------------
st.markdown("### 📌 현재 입력 미리보기")
st.info("현재 입력 내용이 실시간으로 반영됩니다")

preview_situation = st.session_state.get("situation_input", "").strip()
preview_goal = st.session_state.get("goal_input", "").strip()
preview_extra = extra_input.strip()

if preview_situation or preview_goal:
    preview_text = f"""
[상황]
{preview_situation if preview_situation else "-"}

[목표]
{preview_goal if preview_goal else "-"}

[추가 요구사항]
{preview_extra if preview_extra else "-"}

"""
    st.code(preview_text)
else:
    st.caption("아직 입력된 내용이 없습니다.")

st.caption(f"오늘 남은 사용 횟수: {MAX_REQUEST - st.session_state.request_count}회")

# -------------------------------
# 🔥 적용 전문가 표시 (여기에 추가)
# -------------------------------
auto_detect = detect_task_type(preview_situation, preview_goal)

# 🔥 모드 기준 결정
if st.session_state.mode == "정보 탐색":
    active_mode = "정보 탐색"

elif st.session_state.mode == "문서 작성":
    active_mode = st.session_state.selected_template or "문서 작성"

else:
    active_mode = auto_detect or st.session_state.selected_template or "문서 작성"

st.caption(f"적용 모드: {active_mode}")

# -------------------------------
# 기존 코드
# -------------------------------
st.markdown("### 🧠 AI에게 이렇게 질문됩니다")
st.caption("※ 이 질문을 그대로 AI에 입력하면 최적의 결과가 생성됩니다")

# 🔥 질문 미리보기 (모드 반영)
def build_question_preview(mode, situation, goal, extra, style):

    if style == "간결형":
        style_text = "핵심만 간결하게 작성"
    elif style == "초간결형":
        style_text = "최소 문장으로 작성"
    else:
        style_text = "구조적으로 작성"

    if mode == "정보 탐색":

        if style == "초간결형":
            return f"""
정보 탐색

상황: {situation}
목표: {goal}

팩트만. 불확실 내용 생성 금지
"""

        elif style == "간결형":
            return f"""
너는 정보 탐색 전문가다.

- 상황: {situation}
- 목표: {goal}

사실 기반으로 간결하게 설명하라.
불확실한 내용은 생성하지 마라.
"""

        else:
            return f"""
너는 정보 탐색 전문가다.

다음 주제에 대해 설명하라.

- 상황: {situation}
- 목표: {goal}

조건:
- 사실 기반
- 추정 금지
- 불확실한 내용 생성 금지
- 핵심부터 정리
"""

    else:

        if style == "초간결형":
            return f"""
문서 작성

상황: {situation}
목표: {goal}

바로 실행
"""

        elif style == "간결형":
            return f"""
너는 {mode} 전문가다.

- 상황: {situation}
- 목표: {goal}

실무용으로 간결하게 작성하라.
"""

        else:
            return f"""
너는 {mode} 전문가다.

- 상황: {situation}
- 목표: {goal}

조건:
- 실무 적용 가능
- 구조 유지
- 불필요 표현 제거
"""

question_preview = build_question_preview(
    active_mode,
    preview_situation,
    preview_goal,
    preview_extra,
    style
)

st.code(question_preview)

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
                    if st.session_state.mode == "정보 탐색":
                        template_type = "정보 탐색"

                    elif st.session_state.mode == "문서 작성":
                        template_type = st.session_state.selected_template

                    else:
                        template_type = st.session_state.selected_template  # 자동

                    preview_text = build_question_preview(
                        active_mode,
                        st.session_state.situation_input,
                        st.session_state.goal_input,
                        extra_input,
                        style
                    )

                    # 🔥 기존 generate_prompt 호출 교체
                    result, tokens = generate_prompt(
                        preview_text,
                        style
                    )

                    add_usage(tokens)

                    # ✅ 요청 카운트 증가
                    st.session_state.request_count += 1

                    st.session_state.last_prompt = result
                    st.session_state.history.append(result)

                    st.success("프롬프트 생성 완료! 아래에서 바로 실행하세요.")

                except Exception as e:
                    st.error(f"오류 발생: {e}")

                # 🔥 생성된 프롬프트 항상 표시 (여기에 추가)
                if st.session_state.last_prompt:
                    st.markdown("### 생성된 프롬프트")

                    st.code(st.session_state.last_prompt, language="markdown")

                    copy_button(st.session_state.last_prompt, "copy_gen_fixed")

                    st.markdown("### 🤖 AI로 바로 실행")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.link_button("ChatGPT 열기", "https://chat.openai.com")

                    with col2:
                        st.link_button("Gemini 열기", "https://gemini.google.com")

                    with col3:
                        st.link_button("Claude 열기", "https://claude.ai")

                    with col4:
                        st.link_button("Perplexity 열기", "https://www.perplexity.ai")

                    st.caption("※ 프롬프트를 복사해서 사용하세요.")

# -------------------------------
# 프롬프트 평가
# -------------------------------
st.markdown("## STEP 3. 평가 및 개선")

col1, col2 = st.columns(2)

with col1:
    eval_clicked = st.button("프롬프트 평가")

if st.session_state.eval_result:
    st.markdown("### 평가 결과")
    st.write(st.session_state.eval_result)
    copy_button(st.session_state.eval_result, "copy_eval_fixed")

with col2:
    refine_clicked = st.button("프롬프트 개선")

if eval_clicked and "eval_running" not in st.session_state:
    st.session_state.eval_running = True
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
                        st.session_state.eval_result = result

                except Exception as e:
                    st.error(f"오류 발생: {e}")
    del st.session_state.eval_running
        

# -------------------------------
# 프롬프트 개선
# -------------------------------
st.subheader("4. 프롬프트 개선")

feedback = st.text_area("수정 요청", placeholder="예: 더 간결하게, 마케팅 느낌으로 등")

if refine_clicked and "refine_running" not in st.session_state:
    st.session_state.refine_running = True
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
    del st.session_state.refine_running

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
st.subheader("개선 비교 (Before → After)")

if len(st.session_state.history) >= 2:

    st.markdown("### 이전")
    with st.container():
        st.code(st.session_state.history[-2], language="markdown")
        copy_button(st.session_state.history[-2], "copy_before")

    st.divider()

    st.markdown("### 현재")
    with st.container():
        st.code(st.session_state.history[-1], language="markdown")
        copy_button(st.session_state.history[-1], "copy_after")

    # 🔥 여기 추가
    st.divider()
    st.markdown("### 변경된 부분 (Diff)")

    st.caption("※ + 추가 / - 삭제된 내용입니다")

    import difflib

    before = st.session_state.history[-2]
    after = st.session_state.history[-1]

    diff = difflib.ndiff(
        before.splitlines(),
        after.splitlines()
    )

    st.code("\n".join(diff), language="diff")

    # -------------------------------
    # 🔥 AI 개선 설명 추가
    # -------------------------------
    st.divider()
    st.markdown("### AI 개선 설명")

    with st.spinner("AI가 개선 이유를 분석 중입니다..."):
        try:
            explanation, tokens = explain_diff(before, after)

            add_usage(tokens)

            st.write(explanation)
            copy_button(explanation, "copy_explain")

        except Exception as e:
            st.error(f"설명 생성 오류: {e}")


