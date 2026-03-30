import streamlit as st
import html
import re
import streamlit.components.v1 as components
from prompt_engine import explain_diff
from prompt_engine import (
    init_client,
    generate_prompt,
    evaluate_prompt,
    refine_prompt,
    parse_user_input,
    detect_task_type,
)

from data_manager import (
    add_usage,
    check_budget,
    tokens_to_krw,
    get_today_usage
)

import json

DEFAULT_TRUST_RULES = """
[기본 작성 원칙]
- 사실 기반으로 작성할 것
- 불분명하거나 확인되지 않은 정보는 단정하지 말 것
- 필요한 경우 '확인 필요', '추정', '일반적 가능성'으로 구분해 표현할 것
- 허위 정보, 없는 사례, 임의 수치, 존재하지 않는 출처를 생성하지 말 것
- 가능한 경우 근거, 판단 기준, 또는 추가 확인이 필요한 항목을 함께 제시할 것
- 작업 성격에 맞는 근거 자료를 사용할 것
""".strip()

def auto_copy(text):
    components.html(
        f"""
        <script>
        navigator.clipboard.writeText(`{text}`);
        </script>
        """,
        height=0,
    )

def build_question_preview(mode, situation, goal, extra, style):
    situation = (situation or "").strip()
    goal = (goal or "").strip()
    extra = (extra or "").strip()
    style = (style or "간결형").strip()
    mode = (mode or "문서 작성").strip()

    return f"""
{DEFAULT_TRUST_RULES}

[작업 모드]
{mode}

[상황]
{situation if situation else "-"}

[목표]
{goal if goal else "-"}

[추가 요구사항]
{extra if extra else "-"}

[출력 스타일]
{style}
""".strip()

def normalize_prompt_spacing(text):
    text = (text or "").strip()

    # 코드펜스 제거
    text = text.replace("```markdown", "").replace("```", "").strip()

    # 공백만 있는 빈 줄 제거
    text = re.sub(r"\n\s*\n+", "\n", text)

    # "1.\n역할" -> "1. 역할"
    text = re.sub(r"(\d+\.)\s*\n+\s*", r"\1 ", text)

    # 항목 사이 과도한 빈 줄 제거
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()

def render_prompt_box(title, text):
    cleaned = normalize_prompt_spacing(text)
    cleaned = re.sub(r'[ \t]+\n', '\n', cleaned)
    cleaned = re.sub(r'(\d+\.)[ \t]+', r'\1 ', cleaned)
    cleaned = re.sub(
        r'(\d+\.\s*)(목표|역할|조건|출력 형식)\s*\((Role|Goal|Instructions|Format)\)',
        r'\1\2 (\3)',
        cleaned
    )

    safe_text = html.escape(cleaned)

    st.markdown(f"#### {title}")
    st.markdown(
        f"""
        <div style="
            border:1px solid #d1d5db;
            border-radius:10px;
            padding:14px;
            background:#f8fafc;
            white-space:pre-wrap;
            word-break:break-word;
            overflow-wrap:anywhere;
            font-family:monospace;
            font-size:14px;
            line-height:1.35;
        ">{safe_text}</div>
        """,
        unsafe_allow_html=True
    )

def strip_code_fence(text):
    text = (text or "").strip()

    if text.startswith("```markdown"):
        text = text[len("```markdown"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text

def copy_button(text, key):
    safe_text = json.dumps(text)
    button_id = f"copy_btn_{key}"
    result_id = f"copy_result_{key}"

    st.components.v1.html(
        f"""
        <div style="margin-top:4px; margin-bottom:8px;">
            <button id="{button_id}"
                style="background-color:#2563eb;color:white;padding:8px 12px;border:none;border-radius:8px;cursor:pointer;width:100%;">
                복사하기
            </button>
            <div id="{result_id}" style="font-size:13px; color:#16a34a; margin-top:6px;"></div>
        </div>

        <script>
        const btn = document.getElementById("{button_id}");
        const result = document.getElementById("{result_id}");
        btn.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({safe_text});
                result.innerText = "복사되었습니다.";
            }} catch (err) {{
                result.innerText = "복사에 실패했습니다. 수동 복사를 사용해주세요.";
            }}
        }});
        </script>
        """,
        height=70,
    )

def render_ai_service_links():
    st.markdown("## 🔗 AI 서비스 바로가기")

    col1, col2 = st.columns(2)
    with col1:
        st.link_button("ChatGPT", "https://chat.openai.com", use_container_width=True)
    with col2:
        st.link_button("Gemini", "https://gemini.google.com", use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.link_button("Claude", "https://claude.ai", use_container_width=True)
    with col4:
        st.link_button("Perplexity", "https://www.perplexity.ai", use_container_width=True)

# def apply_template(base_situation, base_goal, template_mode):
#     if template_mode == "새로 적용 (기존 내용 교체)":
#         st.session_state.situation_input = base_situation
#         st.session_state.goal_input = base_goal
#         st.success("템플릿이 새로 적용되었습니다")
#     else:
#         st.session_state.situation_input = (
#             st.session_state.situation_input + " / " + base_situation
#             if st.session_state.situation_input else base_situation
#         )
#         st.session_state.goal_input = (
#             st.session_state.goal_input + " / " + base_goal
#             if st.session_state.goal_input else base_goal
#         )
#         st.success("기존 입력에 템플릿이 추가되었습니다")

# -------------------------------
# 기본 설정
# -------------------------------
st.set_page_config(page_title="생성형 AI 질문 코치", page_icon="🧠", layout="centered")

st.title("생성형 AI 질문(프롬프트) 코치")
ui_mode = st.radio(
    "사용 모드",
    ["간결 모드", "심화 모드"],
    horizontal=True
)
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
    
if "prev_score" not in st.session_state:
    st.session_state.prev_score = None

if "current_score" not in st.session_state:
    st.session_state.current_score = None
    
if "high_quality" not in st.session_state:
    st.session_state.high_quality = False

if "low_quality" not in st.session_state:
    st.session_state.low_quality = False

if "eval_result" not in st.session_state:
    st.session_state.eval_result = ""

if "refine_result" not in st.session_state:
    st.session_state.refine_result = ""

if "show_post_result" not in st.session_state:
    st.session_state.show_post_result = False

if "selected_template" not in st.session_state:
    st.session_state.selected_template = None

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

import os

api_key = st.secrets["OPENAI_API_KEY"]
init_client(api_key)

with st.expander("사용 방법"):
    st.markdown("""
1. 자유 입력으로 요청을 작성합니다.  
2. 자동 분석으로 상황과 목표를 정리합니다.  
3. 필요하면 템플릿을 적용합니다.  
4. 프롬프트 생성을 눌러 최종 질문을 만듭니다.  
""")

# -------------------------------
# 입력 영역
# -------------------------------
if ui_mode == "간결 모드":

    st.markdown("## 간편 입력")

    simple_input = st.text_area(
        "요청 내용을 입력하세요",
        height=150,
        placeholder="예: 시민 대상 AI 교육 프로그램 사례 정리"
    )

    if st.button("프롬프트 생성", key="simple_generate"):

        if not simple_input.strip():
            st.warning("내용을 입력하세요")
        else:
            with st.spinner("생성 중..."):

                # 1. 자동 분석
                situation_part, goal_part = parse_user_input(simple_input)

                # 2. 프롬프트 생성용 질문 구성
                preview_text = build_question_preview(
                    "문서 작성",
                    situation_part,
                    goal_part,
                    "",
                    "전문가형"
                )

                # 3. 최종 프롬프트 생성
                structured_result, tokens1 = generate_prompt(preview_text, "전문가형")
                sentence_result, tokens2 = generate_prompt(preview_text, "문장형")

                structured_result = strip_code_fence(structured_result)
                sentence_result = strip_code_fence(sentence_result)

                st.markdown("### 결과")

                render_prompt_box("1. 구조형 프롬프트", structured_result)
                copy_button(structured_result, "copy_simple_structured")

                render_prompt_box("2. 문장형 프롬프트", sentence_result)
                copy_button(sentence_result, "copy_simple_sentence")

                st.success("두 가지 형식으로 생성되었습니다. 편한 형태를 복사해 사용하세요.")
                st.caption("구조형은 정밀한 요청에, 문장형은 초보자용 복사-붙여넣기에 적합합니다.")

                add_usage(tokens1 + tokens2)
                st.session_state.request_count += 1

                st.divider()
                st.caption("복사한 프롬프트를 아래 AI 서비스에 바로 붙여넣어 사용해보세요.")
                render_ai_service_links()


elif ui_mode == "심화 모드":

    st.markdown("## STEP 1. 입력")
    st.info("이 시스템은 허위 정보 생성을 방지하기 위해 검증 기반 프롬프트만 생성합니다.")

    input_mode = st.radio(
        "입력 방식 선택",
        ["자유 입력", "육하원칙 입력"],
        key="expert_input_mode"
    )

    free_input = ""

    if input_mode == "자유 입력":
        st.markdown("### 자유 입력 (AI 자동 분석)")
        free_input = st.text_area(
            "편하게 입력하세요",
            height=100,
            placeholder="예: 스마트시티 사업 관련 보도자료 써줘"
        )

    elif input_mode == "육하원칙 입력":
        who = st.text_input("누가")
        what = st.text_input("무엇을")
        why = st.text_input("왜")
        when = st.text_input("언제")
        where = st.text_input("어디서")
        how = st.text_input("어떻게")

        st.session_state.situation_input = f"{when}, {where}에서 {who}가 {what}을 수행하는 상황"
        st.session_state.goal_input = f"{why} 목적을 달성하기 위해 {how} 방식으로 결과 생성"

    if st.button("자동 분석", key="auto_analyze"):
        if input_mode == "자유 입력" and free_input.strip():
            with st.spinner("분석 중..."):
                try:
                    situation_part, goal_part = parse_user_input(free_input)

                    st.session_state.situation_input = situation_part
                    st.session_state.goal_input = goal_part

                    st.success("분석 결과가 입력란에 자동 반영되었습니다")

                except Exception as e:
                    st.error(f"분석 오류: {e}")
        elif input_mode == "자유 입력":
            st.warning("자유 입력 내용을 먼저 입력하세요.")

    # if "auto_eval" in st.session_state:
    #     with st.container():
    #         st.markdown("### 자동 분석 결과")
    #         col_a, col_b = st.columns(2)

    #         with col_a:
    #             st.markdown("**상황**")
    #             st.write(st.session_state.get("situation_input", "") or "-")

    #         with col_b:
    #             st.markdown("**목표**")
    #             st.write(st.session_state.get("goal_input", "") or "-")

    #         with st.expander("입력 평가 보기"):
    #             st.write(st.session_state.auto_eval)

    # template_mode = st.radio(
    #     "템플릿 적용 방식",
    #     ["새로 적용 (기존 내용 교체)", "기존 내용에 추가"],
    #     key="template_mode"
    # )
    # st.info(f"현재 템플릿 적용 방식: {template_mode}")

    # st.markdown("### 빠른 템플릿 선택")


    # # 1행
    # col1, col2, col3 = st.columns(3)

    # with col1:
    #     if st.button("보고서 작성"):
    #         st.session_state.selected_template = "보고서 작성" 
    #         base_situation = "업무 보고서를 작성해야 하는 상황"
    #         base_goal = "논리적이고 구조적인 보고서 초안 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")


    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # with col2:
    #     if st.button("이메일 작성"):
    #         st.session_state.selected_template = "이메일 작성" 
    #         base_situation = "민원인 또는 내부 직원에게 이메일을 보내야 하는 상황"
    #         base_goal = "정중하고 명확한 업무 이메일 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # with col3:
    #     if st.button("계획서 작성"):
    #         st.session_state.selected_template = "계획서 작성" 
    #         base_situation = "사업 또는 프로젝트 계획서를 작성해야 하는 상황"
    #         base_goal = "실행 가능하고 설득력 있는 계획서 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # # 2행
    # col4, col5, col6 = st.columns(3)

    # with col4:
    #     if st.button("보도자료 작성"):
    #         st.session_state.selected_template = "보도자료 작성" 
    #         base_situation = "기관의 정책 또는 사업을 외부에 알리기 위한 보도자료를 작성해야 하는 상황"
    #         base_goal = "언론에 적합한 형식의 명확하고 신뢰감 있는 보도자료 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # with col5:
    #     if st.button("국민신문고 답변"):
    #         st.session_state.selected_template = "국민신문고 답변" 
    #         base_situation = "국민신문고 민원에 대해 공식 답변을 작성해야 하는 상황"
    #         base_goal = "정중하고 법적 문제 없이 명확한 민원 답변 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # with col6:
    #     if st.button("정보공개청구 답변"):
    #         st.session_state.selected_template = "정보공개청구 답변" 
    #         base_situation = "정보공개청구 요청에 대해 답변을 작성해야 하는 상황"
    #         base_goal = "관련 법령을 준수하면서 명확한 정보 제공 답변 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")


    # # 3행
    # col7, col8, col9 = st.columns(3)

    # with col7:
    #     if st.button("행사 시나리오"):
    #         st.session_state.selected_template = "행사 시나리오" 
    #         base_situation = "위원회, 행사 또는 공식 일정 진행을 위한 시나리오를 작성해야 하는 상황"
    #         base_goal = "행사 흐름이 자연스럽고 진행이 원활한 시나리오 작성"
    #         apply_template(base_situation, base_goal, template_mode)

    #         # if template_mode == "새로 적용 (기존 내용 교체)":
    #         #     st.session_state.situation_input = base_situation
    #         #     st.session_state.goal_input = base_goal
    #         #     st.success("템플릿이 새로 적용되었습니다")

    #         # st.session_state.situation_input = (
    #         #     st.session_state.situation_input + " / " + base_situation
    #         #     if st.session_state.situation_input else base_situation
    #         # )

    #         # st.session_state.goal_input = (
    #         #     st.session_state.goal_input + " / " + base_goal
    #         #     if st.session_state.goal_input else base_goal
    #         # )

    #         # st.success("기존 입력에 템플릿이 추가되었습니다")

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

    st.info("현재 입력 상태: 자유 입력 기반")

    style = st.radio(
        "스타일 선택",
        ["전문가형", "간결형", "초간결형"],
        horizontal=True
    )

    # with st.expander("좋은 질문 예시 보기"):
    #     st.markdown("""
    # 예시:

    # 상황: 지자체 AI 교육 프로그램 운영 사례 분석  
    # 목표: 정책 수립 참고를 위한 사례 정리  

    # → 좋은 질문 특징:
    # - 상황 명확
    # - 목표 구체적
    # - 결과 방향 있음
    # """)

    # -------------------------------
    # 프롬프트 미리보기
    # -------------------------------
    st.markdown("### 입력 내용 미리보기")
    st.info("현재 입력 내용이 실시간으로 반영됩니다")
    st.caption("기본적으로 사실 기반, 불확실 정보 단정 금지 원칙이 자동 적용됩니다.")

    preview_situation = st.session_state.get("situation_input", "").strip()
    preview_goal = st.session_state.get("goal_input", "").strip()
    preview_extra = extra_input.strip()

    # 🔥 입력 부족 체크
    if not preview_goal:
        st.warning("⚠ 목표가 없습니다 → '무엇을 얻고 싶은지' 입력하세요")

    if len(preview_situation) < 10:
        st.warning("⚠ 상황이 부족합니다 → 배경을 조금 더 구체적으로 입력하세요")

    if preview_situation or preview_goal:
        preview_text = f"""
    [상황]
    {preview_situation if preview_situation else "-"}

    [목표]
    {preview_goal if preview_goal else "-"}

    [추가 요구사항]
    {preview_extra if preview_extra else "-"}
    """.strip()

        render_prompt_box("입력 내용 미리보기", preview_text)
    else:
        st.caption("아직 입력된 내용이 없습니다.")

    st.caption(f"오늘 남은 사용 횟수: {MAX_REQUEST - st.session_state.request_count}회")

    # -------------------------------
    # 🔥 적용 전문가 표시 (여기에 추가)
    # -------------------------------
    auto_detect = detect_task_type(preview_situation, preview_goal)

    # 🔥 모드 기준 결정
    active_mode = auto_detect or "문서 작성"

    st.caption(f"적용 모드: {active_mode}")

    # -------------------------------
    # 기존 코드
    # -------------------------------
    question_prompt = build_question_preview(
    active_mode,
    preview_situation,
    preview_goal,
    preview_extra,
    style
    )

    with st.expander("AI가 읽는 요청 구조 보기"):
        st.caption("AI가 더 정확한 프롬프트를 만들기 위해 내부적으로 정리한 설계안입니다.")
        render_prompt_box("AI가 읽는 요청 구조", question_prompt)
    # -------------------------------
    # 프롬프트 생성
    # -------------------------------
    if ui_mode == "심화 모드":
        st.markdown("## STEP 2. 프롬프트 생성")
        if st.button("프롬프트 생성"):
            if not check_user_limit():
                st.error("오늘 사용 가능한 요청 횟수를 초과했습니다.")

            else:
                allowed, cost = check_budget(limit_krw=1000)

                if not allowed:
                    st.error("현재 사용량이 많아 잠시 후 다시 시도해주세요.")
                else:
                    with st.spinner("생성 중..."):
                        try:
                            question_prompt  = build_question_preview(
                                active_mode,
                                st.session_state.situation_input,
                                st.session_state.goal_input,
                                extra_input,
                                style
                            )

                            # 🔥 기존 generate_prompt 호출 교체
                            result, tokens = generate_prompt(
                                question_prompt,
                                style
                            )
                            result = strip_code_fence(result)

                            # # 🔥 평가 실행
                            eval_text, _ = evaluate_prompt(result, "전문가형")

                            # 🔥 점수 추출
                            score = 0
                            try:
                                score_line = eval_text.split("[점수]")[1].split("\n")[1].strip()
                                score = int(score_line)
                                st.session_state.current_score = score
                            except:
                                score = 50  # fallback

                            # 🔥 점수 표시
                            st.markdown("### 프롬프트 품질")

                            st.metric("점수", f"{score} / 100")

                            # 🔥 점수 기반 추천
                            if score < 60:
                                st.error("⚠ 낮은 품질 → 반드시 개선하세요")
                                st.warning("👉 자동 개선 버튼 사용 추천")

                            elif score < 80:
                                st.warning("👉 조금만 개선하면 더 좋아집니다")

                            else:
                                st.success("✅ 바로 사용 가능한 프롬프트입니다")

                            # 🔥 평가 내용 (이해용)
                            with st.expander("왜 이 점수인가요?"):
                                st.write(eval_text)
                                
                            # 🔥 평가 결과 저장 (여기에 추가)
                            st.session_state.prompt_score_text = eval_text
                            st.session_state.low_quality = "부족" in eval_text or "개선" in eval_text
                            st.session_state.high_quality = "우수" in eval_text or "완성도 높음" in eval_text

                            add_usage(tokens)

                            # ✅ 요청 카운트 증가
                            st.session_state.request_count += 1

                            st.session_state.last_prompt = result
                            st.session_state.show_post_result = True
                            st.session_state.history.append(result)

                            st.success("프롬프트 생성 완료! 아래에서 바로 실행하세요.")

                        except Exception as e:
                            st.error(f"오류 발생: {e}")

        # 🔥 생성된 프롬프트 항상 표시 (여기에 추가)
        if st.session_state.last_prompt:
            if st.session_state.last_prompt:
                st.markdown("### 생성된 프롬프트")

                render_prompt_box("생성된 프롬프트", st.session_state.last_prompt)

                copy_button(st.session_state.last_prompt, "copy_gen_fixed")

            render_ai_service_links()

            st.caption("※ 이 프롬프트를 AI 서비스에 입력하면 결과가 생성됩니다.")

            # 🔥 자동 개선 추천
        if ui_mode == "심화 모드" and st.session_state.show_post_result:
            if st.session_state.low_quality:
                st.warning("👉 자동 개선 버튼을 눌러 더 나은 프롬프트로 만드세요")
            refine_clicked = False
                                
            st.markdown("## STEP 3. 개선")

            col1, col2 = st.columns([1, 2])

            with col1:
                if st.session_state.high_quality:
                    st.caption("이미 완성도가 높습니다")
                    refine_clicked = st.button("🚀 프롬프트 개선")
                else:
                    refine_clicked = st.button("🚀 프롬프트 개선")


            # -------------------------------
            # 프롬프트 개선
            # -------------------------------
            st.markdown("### 프롬프트 개선")

            feedback = st.text_area("수정 요청", placeholder="예: 더 간결하게, 마케팅 느낌으로 등")

            if refine_clicked:

                if st.session_state.get("refine_running"):
                    st.warning("이미 개선 작업이 진행 중입니다.")
                                
                else:
                    st.session_state.refine_running = True

                    try:
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

                                    st.session_state.prev_score = st.session_state.current_score

                                    base_prompt = st.session_state.last_prompt
                                    base_score = st.session_state.current_score or 0

                                    best_prompt = base_prompt
                                    best_score = base_score
                                    best_eval_text = st.session_state.prompt_score_text or ""

                                    total_tokens_used = 0

                                    for _ in range(3):
                                        candidate_prompt, tokens_refine = refine_prompt(
                                            base_prompt,
                                            feedback,
                                            style
                                        )
                                        candidate_prompt = strip_code_fence(candidate_prompt)
                                        total_tokens_used += tokens_refine

                                        candidate_eval_text, tokens_eval = evaluate_prompt(candidate_prompt, "전문가형")
                                        total_tokens_used += tokens_eval

                                        try:
                                            score_line = candidate_eval_text.split("[점수]")[1].split("\n")[1].strip()
                                            candidate_score = int(score_line)
                                        except:
                                            candidate_score = 50

                                        if candidate_score > best_score:
                                            best_prompt = candidate_prompt
                                            best_score = candidate_score
                                            best_eval_text = candidate_eval_text

                                    add_usage(total_tokens_used)
                                    st.session_state.request_count += 1

                                    st.markdown("### 📊 개선 결과")

                                    if best_score > base_score:
                                        st.session_state.last_prompt = best_prompt
                                        st.session_state.current_score = best_score
                                        st.session_state.prompt_score_text = best_eval_text
                                        st.session_state.history.append(best_prompt)

                                        st.success(f"이전: {base_score}점 → 개선 후: {best_score}점 (+{best_score - base_score})")

                                        st.markdown("### 개선된 프롬프트")
                                        render_prompt_box("개선된 프롬프트", best_prompt)
                                        copy_button(best_prompt, "copy_refine")

                                    elif best_score == base_score:
                                        st.info(f"이전: {base_score}점 → 개선 후: {best_score}점 (변화 없음)")
                                        st.warning("자동개선 결과가 기존 프롬프트보다 확실히 좋아지지 않아 기존 프롬프트를 유지합니다.")

                                    else:
                                        st.error(f"이전: {base_score}점 → 개선 후 후보 최고점: {best_score}점")
                                        st.warning("자동개선 결과가 기존보다 낮아 기존 프롬프트를 유지합니다.")

                    except Exception as e:
                        st.error(f"오류 발생: {e}")

                    finally:
                        st.session_state.refine_running = False

            st.markdown("## STEP 4. 결과 히스토리")


            if st.session_state.history:
                for i, item in enumerate(st.session_state.history):
                    with st.expander(f"버전 {i+1}"):
                        render_prompt_box(f"버전 {i+1}", item)

                        copy_button(item, f"copy_hist_{i}")

            # -------------------------------
            # Before / After 비교
            # -------------------------------


            st.subheader("변경된 부분")

            if len(st.session_state.history) >= 2:
                st.caption("※ + 추가 / - 삭제된 내용입니다")

                import difflib

                before = st.session_state.history[-2].splitlines()
                after = st.session_state.history[-1].splitlines()

                diff_lines = list(
                    difflib.unified_diff(
                        before,
                        after,
                        lineterm=""
                    )
                )

                cleaned_diff = [
                    line for line in diff_lines
                    if not line.startswith("---")
                    and not line.startswith("+++")
                    and not line.startswith("@@")
                ]

                if cleaned_diff:
                    st.code("\n".join(cleaned_diff), language="diff")
                else:
                    st.info("변경된 내용이 없습니다.")

                before_text = st.session_state.history[-2]
                after_text = st.session_state.history[-1]

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


       


