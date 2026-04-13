import streamlit as st
import html
import re
import requests
import streamlit.components.v1 as components
from prompt_engine import explain_diff
from prompt_engine import (
    init_client,
    generate_prompt,
    evaluate_prompt,
    refine_prompt,
    parse_user_input,
    detect_task_type,
    convert_prompt_to_sentence
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
    style = (style or "구조형").strip()
    mode = (mode or "문서 작성").strip()
    return f"""
다음 입력을 바탕으로 사용자가 바로 활용할 수 있는 최종 프롬프트를 설계하라.

{DEFAULT_TRUST_RULES}

[작업 유형]
{mode}

[상황]
{situation if situation else "-"}

[목표]
{goal if goal else "-"}

[추가 요구사항]
{extra if extra else "-"}

[작성 지침]
- 반드시 "프롬프트"만 생성할 것 (답변 금지)
- 사용자가 AI에 그대로 복사해서 사용할 수 있어야 함
- 역할, 목표, 조건, 출력 형식을 명확히 포함할 것
- 초보자도 이해하고 사용할 수 있도록 작성할 것
- 불필요한 설명 없이 바로 사용할 수 있는 형태로 작성할 것
""".strip()
    
#     return f"""
# {DEFAULT_TRUST_RULES}

# [작업 모드]
# {mode}

# [상황]
# {situation if situation else "-"}

# [목표]
# {goal if goal else "-"}

# [추가 요구사항]
# {extra if extra else "-"}

# [출력 스타일]
# {style}
# """.strip()

def normalize_prompt_spacing(text):
    text = (text or "").strip()

    # 코드펜스 제거
    text = text.replace("```markdown", "").replace("```", "").strip()

    # 줄 끝 공백 제거
    text = re.sub(r"[ \t]+\n", "\n", text)

    # 1.\n역할 -> 1. 역할
    text = re.sub(r"(\d+\.)\s*\n+\s*", r"\1 ", text)

    # 2.    목표 -> 2. 목표
    text = re.sub(r"(\d+\.)[ \t]+", r"\1 ", text)

    # 제목 줄 앞 들여쓰기 제거
    text = re.sub(
        r"^[ \t]*(\d+\.\s*(역할|목표|조건|출력 형식)\s*\((Role|Goal|Instructions|Format)\))",
        r"\1",
        text,
        flags=re.MULTILINE
    )

    # 제목 다음 여러 줄 공백 제거
    text = re.sub(
        r"((?:\d+\.\s*(?:역할|목표|조건|출력 형식)\s*\((?:Role|Goal|Instructions|Format)\)))\n+",
        r"\1\n",
        text
    )

    # 각 줄 앞뒤 공백 제거
    lines = [line.strip() for line in text.splitlines()]

    cleaned_lines = []
    prev_was_heading = False

    for line in lines:
        if not line:
            continue

        is_heading = bool(
            re.match(r"^\d+\.\s*(역할|목표|조건|출력 형식)\s*\((Role|Goal|Instructions|Format)\)$", line)
        )

        # 새 항목 시작 전에는 빈 줄 1개만 넣기
        if is_heading and cleaned_lines:
            if cleaned_lines[-1] != "":
                cleaned_lines.append("")

        cleaned_lines.append(line)
        prev_was_heading = is_heading

    text = "\n".join(cleaned_lines).strip()

    # 혹시 남은 과도한 빈 줄 최종 정리
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text

def is_valid_structure(text):
    return (
        "1. 역할" in text and
        "2. 목표" in text and
        "3. 조건" in text and
        "4. 출력 형식" in text and
        not re.search(r"\d+\.\s*\n", text)  # 줄 깨짐 방지
    )

def render_prompt_box(text):
    cleaned = normalize_prompt_spacing(text)
    safe_text = html.escape(cleaned)

    st.markdown(
        f"""
        <div style="
            border:1px solid rgba(128,128,128,0.25);
            border-radius:10px;
            padding:14px;
            background-color: var(--secondary-background-color, #f3f4f6);
            color: var(--text-color, #111827);
            white-space:pre-wrap;
            word-break:break-word;
            overflow-wrap:anywhere;
            font-family:monospace;
            font-size:14px;
            line-height:1.45;
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
    "프롬프트 생성 방식 선택",
    ["빠른 생성 모드", "상세 설정 모드"],
    horizontal=True
)
st.markdown("""
복잡하게 생각하지 말고, 원하는 결과를 그대로 적어주세요  
AI가 자동으로 정리해서 바로 사용할 수 있는 프롬프트로 만들어드립니다
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

# api_key = st.secrets["OPENAI_API_KEY"]
# init_client(api_key)

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
if ui_mode == "빠른 생성 모드":

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

                # 2. 유형 감지 (추가!)
                task_type = detect_task_type(situation_part, goal_part)

                # 3. mode 결정


                # 4. 프롬프트 생성용 질문 구성
                preview_text = build_question_preview(
                    task_type,
                    situation_part,
                    goal_part,
                    "",
                    "구조형"
                )
                # 3. 최종 프롬프트 생성
                structured_result, tokens1 = generate_prompt(preview_text, "구조형",task_type=task_type)
                structured_result = strip_code_fence(structured_result)\
                
                sentence_result, tokens2 = convert_prompt_to_sentence(structured_result)
                sentence_result = strip_code_fence(sentence_result)

                st.markdown("### 결과")

                st.markdown("### 1. 구조형 프롬프트")
                render_prompt_box(structured_result)
                copy_button(structured_result, "copy_simple_structured")

                st.markdown("### 2. 문장형 프롬프트")
                render_prompt_box(sentence_result)
                copy_button(sentence_result, "copy_simple_sentence")

                st.success("두 가지 형식으로 생성되었습니다. 편한 형태를 복사해 사용하세요.")
                st.caption("구조형은 정밀한 요청에, 문장형은 초보자용 복사-붙여넣기에 적합합니다.")

                add_usage(tokens1 + tokens2)
                st.session_state.request_count += 1

                st.divider()
                st.caption("복사한 프롬프트를 아래 AI 서비스에 바로 붙여넣어 사용해보세요.")
                render_ai_service_links()


elif ui_mode == "상세 설정 모드":

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
        "프롬프트 유형 선택",
        ["구조형", "문장형"],
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

        st.markdown("### 입력 내용 미리보기")
        render_prompt_box(preview_text)
    else:
        st.caption("아직 입력된 내용이 없습니다.")

    st.caption(f"오늘 남은 사용 횟수: {MAX_REQUEST - st.session_state.request_count}회")

    # -------------------------------
    # 🔥 적용 전문가 표시 (여기에 추가)
    # -------------------------------
    auto_detect = detect_task_type(preview_situation, preview_goal)

    # 🔥 모드 기준 결정
    task_type = detect_task_type(preview_situation, preview_goal)

    st.caption(f"적용 모드: {task_type}")

    # -------------------------------
    # 기존 코드
    # -------------------------------
    question_prompt = build_question_preview(
    task_type,
    preview_situation,
    preview_goal,
    preview_extra,
    style
    )

    with st.expander("AI가 읽는 요청 구조 보기"):
        st.caption("AI가 더 정확한 프롬프트를 만들기 위해 내부적으로 정리한 설계안입니다.")
        clean_preview = strip_code_fence(question_prompt)
        st.markdown("### AI가 읽는 요청 구조")
        render_prompt_box(clean_preview)
    # -------------------------------
    # 프롬프트 생성
    # -------------------------------
    if ui_mode == "상세 설정 모드":
        st.markdown("## STEP 2. 프롬프트 생성")
        result = None
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
                            task_type = detect_task_type(
                            st.session_state.situation_input,
                            st.session_state.goal_input
)  
                            question_prompt  = build_question_preview(
                                task_type,
                                st.session_state.situation_input,
                                st.session_state.goal_input,
                                extra_input,
                                style
                            )

                            # 🔥 기존 generate_prompt 호출 교체
                            # result, tokens = generate_prompt(
                            #     question_prompt,
                            #     style
                            # )

                            # response = requests.post(
                            #     "https://ai-question-coaching-production.up.railway.app/generate",
                            #     json={
                            #         "preview_text": question_prompt,
                            #         "style": style
                            #     }
                            # )

                            # if response.status_code == 200:
                            #     result = response.json()["result"]
                            #     tokens = 0  # 서버에서 아직 안 주니까 임시
                            # else:
                            #     st.error("서버 오류 발생")
                            #     result = ""
                            #     tokens = 0
                            # result = strip_code_fence(result)

                            # 🔥 로컬 GPT 직접 호출
                            structured_result, tokens = generate_prompt(
                                question_prompt,
                                "구조형",
                                task_type=task_type
                            )

                            structured_result = strip_code_fence(structured_result)

                            if not structured_result:
                                st.error("구조형 프롬프트 생성에 실패했습니다.")
                                st.stop()

                            # 🔥 문장형 선택 시 변환
                            if style == "문장형":
                                result, tokens2 = convert_prompt_to_sentence(structured_result)
                                result = strip_code_fence(result)
                                tokens += tokens2
                            else:
                                result = structured_result

                            if not result:
                                st.error("프롬프트 생성에 실패했습니다.")
                                st.stop()

                        except Exception as e:
                            st.error(f"오류 발생: {e}")
                            st.stop()

                        # 🔥 hallucination 검증 추가
                        from prompt_engine import detect_hallucination

                        if task_type == "정보 탐색":

                            safe_prompt = result

                            risk_detected = False

                            for _ in range(2):  # 최대 2번 재시도
                                check_text, check_tokens = detect_hallucination(safe_prompt)
                                tokens += check_tokens

                                if "SAFE" in check_text:
                                    break

                                risk_detected = True
     
                                # 🔥 문제 있으면 재생성
                                improved_preview = question_prompt + "\n\n[추가 지시]\n- 위 문제를 수정하여 더 신뢰성 높은 프롬프트로 다시 작성하라"

                                safe_prompt, regen_tokens = generate_prompt(
                                    improved_preview,
                                    "구조형",
                                    task_type=task_type
                                )
                                safe_prompt = strip_code_fence(safe_prompt)
                                tokens += regen_tokens

                            if risk_detected:
                                st.warning("⚠ 일부 정보는 검증이 필요하여 자동으로 재구성되었습니다")

                            result = safe_prompt

                        # # 🔥 평가 실행
                        eval_text, _ = evaluate_prompt(result, "구조형")

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
        # 🔥 생성된 프롬프트 항상 표시 (여기에 추가)
        if st.session_state.last_prompt:
            if st.session_state.last_prompt:
                st.markdown("### 생성된 프롬프트")
                render_prompt_box(st.session_state.last_prompt)
                copy_button(st.session_state.last_prompt, "copy_gen_fixed")

            render_ai_service_links()

            st.caption("※ 이 프롬프트를 AI 서비스에 입력하면 결과가 생성됩니다.")

            # 🔥 자동 개선 추천
        if ui_mode == "상세 설정 모드" and st.session_state.show_post_result:
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

                                    base_prompt = normalize_prompt_spacing(st.session_state.last_prompt)
                                    base_score = st.session_state.current_score or 0

                                    best_prompt = base_prompt
                                    best_score = base_score
                                    best_eval_text = st.session_state.prompt_score_text or ""

                                    total_tokens_used = 0

                                    candidates = []

                                    for _ in range(2):
                                        candidate_prompt, tokens_refine = refine_prompt(
                                            base_prompt,
                                            feedback,
                                            style
                                        )
                                        total_tokens_used += tokens_refine

                                        # 개선 결과를 저장/평가 전에 먼저 정리
                                        candidate_prompt = strip_code_fence(candidate_prompt)
                                        candidate_prompt = normalize_prompt_spacing(candidate_prompt)

                                        if not is_valid_structure(candidate_prompt):
                                            continue  # 아예 버림

                                        candidates.append(candidate_prompt)
                                    if not candidates:
                                        candidates.append(base_prompt)

                                    candidate_eval_text, tokens_eval = evaluate_prompt(candidate_prompt, "구조형")
                                    total_tokens_used += tokens_eval

                                    try:
                                        score_line = candidate_eval_text.split("[점수]")[1].split("\n")[1].strip()
                                        candidate_score = int(score_line)
                                    except:
                                        candidate_score = 50

                                    if candidate_score > best_score:
                                        best_prompt = normalize_prompt_spacing(candidate_prompt)
                                        best_score = candidate_score
                                        best_eval_text = candidate_eval_text

                                    add_usage(total_tokens_used)
                                    st.session_state.request_count += 1

                                    st.markdown("### 📊 개선 결과")

                                    # 점수가 올랐을 때
                                    if best_score > base_score:
                                        best_prompt = normalize_prompt_spacing(best_prompt)

                                        st.session_state.last_prompt = best_prompt
                                        st.session_state.current_score = best_score
                                        st.session_state.prompt_score_text = best_eval_text
                                        st.session_state.history.append(best_prompt)

                                        st.success(f"이전: {base_score}점 → 개선 후: {best_score}점 (+{best_score - base_score})")

                                        # st.markdown("### 개선된 프롬프트")
                                        # render_prompt_box(best_prompt)
                                        # copy_button(best_prompt, "copy_refine")

                                    # 점수 변화 없음
                                    elif best_score == base_score:
                                        st.info(f"이전: {base_score}점 → 개선 후: {best_score}점 (변화 없음)")
                                        st.warning("자동개선 결과가 기존과 동일 수준이어서 기존 프롬프트를 유지합니다.")

                                        # st.markdown("### 현재 유지된 프롬프트")
                                        best_prompt = normalize_prompt_spacing(best_prompt)
                                        # st.markdown("### 현재 유지된 프롬프트")
                                        # render_prompt_box(best_prompt)
                                        # copy_button(best_prompt, "copy_refine_same")
                                        st.session_state.last_prompt = best_prompt

                                    # 더 낮은 경우
                                    else:
                                        st.error(f"이전: {base_score}점 → 개선 후보 최고점: {best_score}점")
                                        st.warning("자동개선 결과가 기존보다 낮아 기존 프롬프트를 유지합니다.")

                                        # st.markdown("### 현재 유지된 프롬프트")
                                        best_prompt = normalize_prompt_spacing(best_prompt)
                                        # st.markdown("### 현재 유지된 프롬프트")
                                        # render_prompt_box(best_prompt)
                                        # copy_button(best_prompt, "copy_refine_keep")
                                        st.session_state.last_prompt = best_prompt

                    except Exception as e:
                        st.error(f"오류 발생: {e}")

                    finally:
                        st.session_state.refine_running = False

                    if st.session_state.last_prompt:
                        st.markdown("### 생성된 프롬프트")
                        render_prompt_box(st.session_state.last_prompt)
                        copy_button(st.session_state.last_prompt, "copy_final")       

            st.markdown("## STEP 4. 결과 히스토리")


            if st.session_state.history:
                for i, item in enumerate(st.session_state.history):
                    with st.expander(f"버전 {i+1}"):
                        clean_item = strip_code_fence(item)
                        st.markdown(f"### 버전 {i+1}")
                        render_prompt_box(clean_item)

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


       


