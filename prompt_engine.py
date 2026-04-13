import os
from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEFAULT_MODEL = "gpt-4o-mini"


def init_client(api_key):
    global client
    if not api_key or not api_key.strip():
        raise ValueError("API 키가 비어 있습니다.")
    client = OpenAI(api_key=api_key.strip())


def ensure_client():
    if client is None:
        raise ValueError("OpenAI 클라이언트가 초기화되지 않았습니다. 먼저 init_client(api_key)를 실행하세요.")

# def get_template_rules(template_type):
#     templates = {

#         "보고서 작성": """
# 너는 공공기관 보고서 작성 전문가다.

# - 보고서 형식으로 작성
# - 논리 구조 유지 (배경 → 내용 → 결론)
# - 불필요한 수식어 제거
# - 설명 문장 금지
# """,

#         "이메일 작성": """
# 너는 공공기관 공문/이메일 작성 전문가다.

# - 정중하고 명확하게 작성
# - 불필요한 감정 표현 금지
# - 실제 발송 가능한 형태로 작성
# """,

#         "계획서 작성": """
# 너는 공공기관 사업계획서 작성 전문가다.

# - 실행 가능한 계획 중심 작성
# - 목적, 추진내용, 기대효과 포함
# - 실무형 문장 사용
# """,

#         "보도자료 작성": """
# 너는 공공기관 보도자료 작성 전문가다.

# - 기사형 문장으로 작성
# - 홍보성 문구 금지 (예: 많은 참여 바랍니다)
# - 설명 문장 금지
# - 실제 언론 배포 수준으로 작성

# [형식]
# - 제목
# - 본문
# """,

#         "국민신문고 답변": """
# 너는 공공기관 민원 답변 전문가다.

# - 정중하고 법적 문제 없는 표현 사용
# - 모호한 표현 금지
# - 민원인의 질문에 정확히 답변
# """,

#         "정보공개청구 답변": """
# 너는 공공기관 정보공개 담당자다.

# - 관련 법령 기준으로 작성
# - 공개 가능 여부 명확히 판단
# - 근거 포함
# """,

#         "행사 시나리오": """
# 너는 공공기관 행사 운영 전문가다.

# - 시간 흐름 중심으로 작성
# - 실제 진행 가능한 시나리오 구성
# - 멘트 포함 가능
# """,
#         "정보 탐색": """
# 너는 특정 주제에 대해 정확하고 이해하기 쉽게 설명하는 정보 탐색 전문가다.

# - 사실 기반으로 설명할 것
# - 불확실한 내용은 생성 금지
# - 추정, 과장, 창작 금지
# - 초보자도 이해할 수 있게 설명할 것
# - 핵심부터 먼저 설명할 것
# - 불필요한 홍보성 문장 금지
# - 설명 외 군더더기 문장 금지

# [형식]
# 1. 핵심 요약
# 2. 주요 내용
# 3. 추가로 알아둘 점
# """
#     }

#     return templates.get(template_type, "")

def detect_task_type(situation, goal):
    text = f"{situation} {goal}".lower()

    # 점수 초기화
    scores = {
        "정보 탐색": 0,
        "문서 작성": 0,
        "콘텐츠 제작": 0,
        "발표 자료": 0,
        "기획": 0,
        "이미지 작업": 0
    }

    # 1. 정보 탐색
    info_keywords = [
        "설명", "정리", "비교", "분석", "알려", "추천",
        "무엇", "이유", "방법", "장단점", "효과"
    ]
    for k in info_keywords:
        if k in text:
            scores["정보 탐색"] += 2

    # 2. 문서 작성
    doc_keywords = [
        "보고서", "보도자료", "공문", "계획서",
        "이메일", "메일", "작성"
    ]
    for k in doc_keywords:
        if k in text:
            scores["문서 작성"] += 2

    # 3. 콘텐츠 제작 🔥
    content_keywords = [
        "블로그", "콘텐츠", "글", "sns", "유튜브",
        "스토리", "마케팅", "카피"
    ]
    for k in content_keywords:
        if k in text:
            scores["콘텐츠 제작"] += 3

    # 4. 발표 자료 🔥
    ppt_keywords = [
        "ppt", "발표", "슬라이드", "프레젠테이션"
    ]
    for k in ppt_keywords:
        if k in text:
            scores["발표 자료"] += 3

    # 5. 기획 🔥
    plan_keywords = [
        "아이디어", "기획", "전략", "컨셉",
        "사업", "프로젝트"
    ]
    for k in plan_keywords:
        if k in text:
            scores["기획"] += 3

    # 6. 이미지 작업 🔥
    image_keywords = [
        "이미지", "사진", "배경", "합성",
        "그림", "스타일", "변환"
    ]
    for k in image_keywords:
        if k in text:
            scores["이미지 작업"] += 3

    # 🔥 패턴 보정 (중요)
    if any(p in text for p in ["알려줘", "설명해줘"]):
        scores["정보 탐색"] += 2

    if any(p in text for p in ["작성해줘", "만들어줘"]):
        scores["문서 작성"] += 1

    # 🔥 최종 선택
    best_type = max(scores, key=scores.get)

    if scores[best_type] == 0:
        return "정보 탐색"

    return best_type

def get_style_instruction(style):
    if style == "구조형":
        return """
[출력 형식]
- 반드시 아래 4단계 구조를 유지할 것

1. 역할
- 수행해야 할 기능 중심 전문가로 명확히 정의할 것
- 단순 '전문가' 금지 (예: "보고서 작성 전문가", "콘텐츠 기획 전문가")

2. 목표
- 사용자의 목적과 결과 활용 맥락을 포함하여 구체적으로 작성할 것
- 결과물이 어디에 어떻게 쓰이는지 드러나야 함

3. 조건
- 실행 가능한 기준 중심으로 작성할 것
- 모호한 표현 금지 (예: "적절히", "잘")
- 결과 품질에 영향을 주는 핵심 요소만 포함
- 최소 3개 이상 작성

4. 출력 형식
- 결과물이 어떤 형태로 나와야 하는지 명확히 정의할 것
- 바로 복사해서 사용할 수 있는 형태로 작성

[작성 규칙]
- 각 항목은 "제목 1줄 + 다음 줄 본문" 구조 유지
- 번호 형식 (1~4) 절대 변경 금지
- 불필요한 설명 금지
- 실무에서 바로 사용할 수 있는 수준으로 작성
"""
    elif style == "문장형":
        return """
[출력 형식]
- 전체를 자연스럽게 이어진 하나의 요청 문장 또는 문단으로 작성할 것
- 구조형의 1~4 요소(역할, 목표, 조건, 출력 형식)를 모두 포함할 것

[작성 규칙]
- 문장 시작은 반드시 역할로 시작할 것 ("~전문가로서" 형태)
- 목표는 문장 초반에 자연스럽게 포함할 것
- 조건은 문장 중간에 자연스럽게 녹일 것
- 출력 형식은 마지막에 결과 형태로 드러나게 할 것

[표현 규칙]
- 번호형 구조 사용 금지
- 끊어진 문장 금지
- 지나치게 축약 금지
- 불필요한 설명 없이 프롬프트 본문만 작성

[품질 기준]
- 사람이 읽어도 자연스럽고 명확해야 함
- AI가 바로 실행 가능한 수준이어야 함
"""
    
    else:
        return ""
    
def get_reliability_rules():
    return """
[신뢰성 규칙 - 절대 준수]
- 사실이 아닌 정보 절대 생성 금지
- 추정, 가정, 창작 금지
- 불확실한 정보는 반드시 "확인 필요" 표시
- 최신 정보 기준으로 작성
- 검증 가능한 정보만 사용
- 공공기관 기준 표현 사용
- 가능하면 근거 방식 포함 (법령, 공식자료, 통계 등)
- 존재하지 않는 기관, 장소, 프로그램 절대 생성 금지
- 실제 확인 가능한 정보만 기반으로 작성할 것
- 불확실한 경우 반드시 '확인 필요'로 표시
- 구체적 이름/수치/위치는 검증 가능한 경우에만 작성
"""

def get_task_evidence_rules(preview_text):
    text = (preview_text or "").lower()

    rules = """
            [작업 성격별 근거 규칙]
            - 작업 성격에 맞는 근거를 사용할 것
            - 모든 작업에 동일한 근거를 기계적으로 적용하지 말 것
            - 법령, 정책, 운영정보, 공식자료, 통계, 일정, 연락처, 예약정보 등은 작업 목적에 따라 우선순위를 다르게 둘 것
            """

    if any(keyword in text for keyword in ["계획", "일정", "견학", "방문", "출장", "투어", "벤치마킹"]):
        return rules + """
            - 일정 계획, 견학, 방문, 벤치마킹 작업에서는 법령보다 공식 홈페이지, 기관 안내자료, 운영시간, 예약 여부, 위치, 연락처, 프로그램 운영 여부, 이동 동선 등 실무 확인 정보에 우선순위를 둘 것
            - 변동 가능성이 큰 항목은 '확인 필요'로 표시할 것
            """

    elif any(keyword in text for keyword in ["보고서", "정책", "기획", "계획서", "분석", "검토"]):
        return rules + """
            - 보고서, 정책 검토, 기획, 분석 작업에서는 공공기관 공식 문서, 정책 자료, 통계, 연구자료, 보도자료, 기관 발간자료 등 신뢰 가능한 근거를 우선 사용할 것
            - 법령이나 지침이 직접 관련되는 경우에는 해당 기준을 반영할 것
            """

    elif any(keyword in text for keyword in ["민원", "신문고", "답변", "정보공개", "공문", "행정"]):
        return rules + """
            - 민원 답변, 정보공개, 공문, 행정 답변 작업에서는 관련 법령, 지침, 행정 기준, 공식 절차를 우선 근거로 사용할 것
            - 불명확한 경우 단정하지 말고 확인 필요 사항으로 분리할 것
            """

    elif any(keyword in text for keyword in ["이메일", "안내문", "공지", "홍보", "보도자료"]):
        return rules + """
            - 이메일, 안내문, 공지, 홍보, 보도자료 작업에서는 공식 안내 내용, 기관 확인 정보, 행사 정보, 일정, 위치, 연락처 등 실제 전달 정확성이 중요한 정보를 우선 사용할 것
            - 법령은 직접 관련이 있을 때만 반영할 것
            """

    elif any(keyword in text for keyword in ["정보 탐색", "조사", "리서치", "비교", "추천", "찾아줘"]):
        return rules + """
            - 정보 탐색, 조사, 비교, 추천 작업에서는 공식 홈페이지, 기관 소개자료, 신뢰 가능한 보도자료, 공개 통계, 제품/서비스 공식 문서 등 확인 가능한 자료를 우선 사용할 것
            - 광고성 표현, 추정, 과장, 검증되지 않은 후기 기반 단정은 금지할 것

            [정보탐색 전용 강화 규칙]
            - 존재하지 않는 기관, 장소, 서비스, 프로그램 절대 생성 금지
            - 실제 존재 여부가 확인되지 않은 대상은 반드시 '확인 필요'로 표시할 것
            - 구체적인 이름, 수치, 위치는 검증 가능한 경우에만 작성할 것
            - 추천 시 반드시 '선정 기준' 또는 '판단 근거'를 포함할 것
            - "가능성이 높다", "일반적으로 알려져 있다" 등 모호한 표현 사용 금지
            - 추정 기반 설명 금지
            """

    else:
        return rules + """
- 특별한 유형이 명확하지 않다면 공식 문서, 기관 안내자료, 공개 통계, 신뢰 가능한 설명 자료 등 확인 가능한 근거를 우선 사용할 것
- 작업 목적에 맞지 않는 법령·정책·통계·운영정보를 억지로 끼워 넣지 말 것
"""

def generate_dynamic_expert(situation, goal):
    text = f"{situation} {goal}"

    return f"""
너는 아래 업무를 수행하는 공공기관 실무 전문가다.

업무:
{text}

해당 업무를 가장 잘 수행할 수 있는 전문 역할로 행동하라.
"""


def request_chat(system_prompt, user_input, max_tokens=500, model=DEFAULT_MODEL):
    ensure_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        max_tokens=max_tokens
    )

    content = response.choices[0].message.content
    total_tokens = response.usage.total_tokens if response.usage else 0

    return content, total_tokens

def build_expert_role(situation, goal, template_type=None):
     # 🔥 정보 탐색 먼저 처리 (이게 핵심)
    if template_type in ["정보 탐색", "리서치", "분석"]:
        text = f"{situation} {goal}".strip()

        return f"""
    너는 해당 주제에 대해 정확한 정보를 조사·분석·설명하는 전문 연구자다.

    주제:
    {text}

    규칙:
    - 사실 기반으로 설명
    - 불확실한 내용 생성 금지
    - 핵심부터 정리
    - 과장, 추정, 창작 금지
    """
#     # 템플릿 기반
#     if template_type:

#         expert_map = {
#             "보도자료 작성": "10년 이상 경력의 공공기관 홍보담당 사무관",
#             "보고서 작성": "10년 이상 경력의 정책기획 담당 사무관",
#             "이메일 작성": "공공기관 행정업무 담당자",
#             "계획서 작성": "공공기관 사업기획 전문가",
#             "국민신문고 답변": "민원 대응 담당 공무원",
#             "정보공개청구 답변": "정보공개 및 법령 검토 담당자",
#             "행사 시나리오": "공공기관 행사 운영 전문가"
#         }

#         role = expert_map.get(template_type, "공공기관 실무 담당자")

#         return f"""
# 너는 {role}다.

# 실제 업무를 수행하는 입장에서
# 결과를 작성하라.
# """

    # 🔥 자유 입력 기반 (강화 버전)
    text = f"{situation} {goal}".strip()

    return f"""
너는 해당 업무를 수행하는 가장 적합한 전문 역할을 가진 전문가다.

반드시 다음 기준으로 역할을 구체화하라:
- 수행 업무에 특화된 전문가여야 한다
- 단순 '실무자'가 아니라 기능 중심 전문가여야 한다
- 예: "정보통신 선진지 견학 장소 추천 전문가"

업무:
{text}

현장에서 바로 사용할 수 있는 수준으로 작성하라.
"""
@st.cache_data(ttl=3600)
def generate_prompt(preview_text, style, task_type=None, max_tokens=500):

    if not task_type:
        task_type = detect_task_type(preview_text, preview_text)

    reliability = get_reliability_rules()

    # 🔥 task_type별 핵심 규칙 통합
    if task_type == "정보 탐색":
        task_rules = """
[작업 규칙]
- 실제 존재하는 정보만 기반으로 작성
- 사례 또는 핵심 정보 중심으로 정리
- 과장, 추정, 창작 금지
- 불확실한 내용은 '확인 필요'로 표시
- 분석, 개선방안, 의견 포함 금지
"""
        format_rules = """
[출력 형식]
- 핵심 요약 → 주요 내용 → 추가 정보 순으로 구성
- 항목별로 간결하게 정리
"""
    elif task_type == "보도자료":
        task_rules = """
- 기사형 문체로 작성
- 홍보성 표현 금지
- 객관적 사실 중심
"""
        format_rules = """
- 제목
- 리드문
- 본문
"""
    elif task_type == "공문":
        task_rules = """
- 공공기관 공식 문체 사용
- 정중하고 명확하게 작성
- 불필요한 감정 표현 금지
"""
        format_rules = """
- 제목
- 수신/참조
- 본문
- 결론
"""
    elif task_type == "이메일":
        task_rules = """
- 정중하고 간결하게 작성
- 핵심만 전달
"""
        format_rules = """
- 인사
- 본문
- 마무리
"""
    elif task_type == "이메일":
        task_rules = """
- 정중하고 간결하게 작성
- 핵심만 전달
"""
        format_rules = """
- 인사
- 본문
- 마무리
"""

    elif task_type == "보고서":
        task_rules = """
- 논리적 구조 유지
- 객관적 사실 기반
"""
        format_rules = """
- 제목
- 요약
- 본문
"""
    elif task_type == "계획서":
        task_rules = """
- 실행 가능성 중심 작성
- 구체적인 계획 포함
"""
        format_rules = """
- 목적
- 추진 내용
- 기대 효과
"""
    elif task_type == "콘텐츠 제작":
        task_rules = """
- 읽기 쉽게 작성 (가독성 최우선)
- 흥미 요소 포함
- 자연스러운 흐름 유지
- 과도한 설명 금지
- 딱딱한 보고서 문체 금지
"""
        format_rules = """
- 도입 → 본문 → 결론
- 소제목 활용 가능
"""

    elif task_type == "발표 자료":
        task_rules = """
- 슬라이드 단위로 구성 가능하게 작성
- 핵심 메시지 중심
- 문장은 짧고 명확하게
"""
        format_rules = """
- 슬라이드별 제목 + 핵심 bullet 구조
"""

    elif task_type == "기획":
        task_rules = """
- 창의성과 실행 가능성 동시에 고려
- 논리적 구조 유지
- 구체적인 실행 방향 포함
"""
        format_rules = """
- 문제 정의 → 아이디어 → 실행 방안 → 기대효과
"""

    elif task_type == "이미지 작업":
        task_rules = """
- 시각적 요소 중심으로 작성
- 스타일, 분위기, 색감 명확히 표현
- 모호한 표현 금지
"""
        format_rules = """
- 장면 설명 → 스타일 → 디테일 요소
"""

    else:
        task_rules = """
[작업 규칙]
- 사용자의 의도를 명확하게 해석하여 작성
- 상황에 맞는 적절한 방식으로 결과 구성
- 불필요한 설명 제거
- 결과가 바로 활용 가능하도록 작성
- 입력 내용이 모호할 경우 일반적인 상황을 가정하여 보완
"""

        format_rules = """
[출력 형식]
- 내용의 성격에 맞게 가장 적절한 구조로 구성
- 가독성을 고려하여 정리
- 필요 시 항목 구분 또는 단계 구조 활용
"""

    system_prompt = f"""
너는 생성형 AI 질문(프롬프트) 설계 전문가다.

목표:
사용자가 AI에 그대로 입력하면 최적의 결과가 나오도록
"완성된 구조형 프롬프트"를 생성하는 것이다.

{reliability}

[절대 규칙]
- 반드시 프롬프트만 생성 (설명 금지)
- 답변 생성 금지
- 코드블럭(```) 사용 금지

[프롬프트 구조]
1. 역할 
2. 목표 
3. 조건 
4. 출력 형식 

[구조 규칙]
- 반드시 위 구조를 그대로 따를 것
- 번호 형식 (1~4) 절대 변경 금지
- 각 항목은 "제목 1줄 + 본문" 구조 유지
- 줄바꿈 오류 절대 금지

[조건 작성 강제 규칙]
- 조건 항목에는 반드시 실행 기준이 포함되어야 한다
- 모호한 표현 금지 (예: "적절히", "잘")
- 결과 품질에 영향을 주는 요소만 포함할 것
- 최소 3개 이상 작성할 것

[역할 작성 규칙]
- 수행 기능 중심 전문가로 정의할 것
- 단순 '전문가' 금지
- 예: "정책 보고서 작성 전문가", "AI 교육 사례 분석 전문가"

[목표 작성 규칙]
- 사용 목적이 명확히 드러나야 함
- 결과 활용 맥락 포함

[유형별 금지 규칙]
- 작업 유형에 맞지 않는 문체나 구조 사용 금지

[해석 규칙]
- 입력이 불완전해도 의도를 보완하여 작성

{task_rules}

{format_rules}
"""

    user_input = f"""
다음 입력을 기반으로 최종 프롬프트를 작성하라:

{preview_text}
"""

    return request_chat(system_prompt, user_input, max_tokens)
# def generate_prompt(preview_text, style, task_type=None, max_tokens=500):
#     if not task_type:
#         task_type = detect_task_type(preview_text, preview_text)

#     style_instruction = get_style_instruction(style)
#     reliability = get_reliability_rules()

#     structure_block = ""
#     if style != "문장형":
#         structure_block = """
# [프롬프트 구조]
# 1. 역할
# 2. 목표
# 3. 조건
# 4. 출력 형식

# [형식 고정 규칙]
# - 반드시 위 구조를 그대로 따를 것
# - 번호와 제목 형식을 임의로 바꾸지 말 것
# - '역할:', '목표:' 같은 축약 표기는 사용하지 말 것
# - 번호 앞의 점만 쓰거나 형식을 깨뜨리지 말 것
# - 각 항목은 줄바꿈으로 명확히 구분할 것
# - 1, 2, 3, 4 각 항목은 한 줄 제목 + 다음 줄 본문 형식을 유지할 것
# """

#     # 🔥🔥🔥 여기 추가 (핵심 위치) 🔥🔥🔥
#     if style != "문장형":

#         if task_type == "정보 탐색":
#             instruction_block = """
# 3. 조건
# - 실제 사례 중심으로 정리
# - 핵심 내용 위주로 간단히 설명
# - 불필요한 분석, 개선방안, 지표 포함하지 말 것
# """
#         else:
#             instruction_block = """
# 3. 조건
# - 실무에서 바로 사용할 수 있도록 작성
# - 목적이 명확하게 드러나도록 작성
# - 조건은 3~4개 이내로 핵심만 작성
# - 결과 품질에 직접 영향을 주는 요소만 포함
# """
#     else:
#         instruction_block = ""
#     # 🔥🔥🔥 여기까지 🔥🔥🔥

#     if style != "문장형":

#         if task_type == "정보 탐색":
#             format_block = """
# 4. 출력 형식
# - 사례 또는 정보 중심으로 정리
# - 항목별로 간단하고 명확하게 구성
# """

#         elif task_type == "보고서 작성":
#             format_block = """
# 4. 출력 형식
# - 보고서 형식으로 작성
# - 제목, 요약, 본문 구조로 구성
# """

#         elif task_type == "보도자료 작성":
#             format_block = """
# 4. 출력 형식
# - 보도자료 형식으로 작성
# - 제목, 개요, 본문 포함
# """

#         else:
#             format_block = """
# 4. 출력 형식
# - 실무 문서 형식으로 작성
# - 목적이 명확하게 드러나도록 구성
# """
#     else:
#         format_block = ""

#     system_prompt = f"""
# 너는 생성형 AI 질문 코치 시스템이다.

# 목표:
# 사용자가 바로 사용할 수 있는 "완성된 프롬프트"를 만든다.

#         {reliability}

# [핵심 규칙]
# - 반드시 프롬프트만 생성
# - 절대 답변 생성 금지
# - 설명 금지
# - style이 문장형이면 1, 2, 3, 4 번호 구조로 나열하지 말 것
# - 구조형일 때만 정해진 항목 구조를 따를 것
# - ```markdown, ``` 같은 코드펜스를 붙이지 말 것
#  - 제목 설명 없이 프롬프트 본문만 출력할 것

#         {structure_block}
#         {format_block}
#         {instruction_block}

# [Role 작성 규칙]
# - 역할(Role)은 사용자의 소속, 기관명, 부서명이 아니라 수행해야 할 전문 역할로 작성할 것
# - 예: '포항시 정보통신과의 전문가'처럼 쓰지 말고, '선진지 견학 장소 추천 전문가'처럼 작성할 것
# - 기관명이나 부서명은 상황 또는 목표에 포함할 것

# [목표 작성 규칙]
# - 목표에는 사용자의 기관, 목적, 활용 맥락을 반영할 것
# - 역할과 목표를 혼동하지 말 것

# [작업 성격별 근거 규칙]
# - 작업 목적에 맞는 핵심 정보만 사용할 것
# - 실무에서 확인 가능한 정보(공식 자료, 운영 정보 등)를 우선 활용할 것
# - 작업 목적에 맞는 근거만 선택적으로 반영할 것
# - 변동 가능성이 있는 정보는 필요 시 '확인 필요'로 표시할 것
# - 불필요하게 많은 요소를 조건으로 나열하지 말 것

# [핵심 작성 기준]
# - 실무에서 바로 사용할 수 있도록 작성할 것
# - 불필요하게 많은 조건을 나열하지 말 것
# - 조건은 3~4개 이내로 핵심만 작성할 것
# - 결과 품질에 직접 영향을 주는 핵심 요소만 포함할 것
# - 사실 기반 유지

# [정보 탐색 작성 기준]
# - 실제 사례 또는 정보 중심으로 정리할 것
# - 핵심 내용 위주로 간단히 설명할 것
# - 불필요한 분석, 개선 방안, 지표는 포함하지 말 것

# [스타일]
# {style_instruction}
# """

#     user_input = f"""
# 아래 요구사항을 기반으로 최종 프롬프트를 작성하라.

# {preview_text}
# """

#     return request_chat(system_prompt, user_input, max_tokens)

def convert_prompt_to_sentence(prompt_text, max_tokens=500):
    ensure_client()

    system_prompt = """
너는 구조형 프롬프트를 초보자도 바로 복사해서 사용할 수 있는 자연스러운 문장형 프롬프트로 바꾸는 전문가다.

[목표]
단순 변환이 아니라, 사람이 바로 사용할 수 있는 자연스러운 요청 문장으로 재구성한다.

[변환 규칙]

1. 전체 흐름 (반드시 유지)
- 역할 → 목표 → 조건 → 결과 형태 순서로 자연스럽게 연결할 것

2. 역할
- 반드시 문장 시작에 "~전문가로서" 형태로 작성

3. 목표
- 문장 초반에 자연스럽게 포함

4. 조건 (핵심)
- 절대 나열 금지
- 반드시 문장 안에 자연스럽게 녹일 것
- 다음 표현을 활용하여 연결:
  → "~하도록 하고"
  → "~을 고려하며"
  → "~을 포함하여"
  → "~을 기반으로"

5. 출력 형식
- 문장 마지막에 결과 형태로 자연스럽게 표현
- "~형식으로 작성해줘", "~구조로 정리해줘" 형태 사용

[표현 규칙]
- "~입니다", "~해주세요" 금지
- 반드시 요청형 (~해줘)으로 작성
- 번호형 구조 절대 금지
- 항목 나열 금지
- 끊어진 문장 금지

[품질 기준]
- 사람이 읽어도 자연스럽고 명확해야 함
- AI가 바로 실행 가능한 수준이어야 함
- 너무 짧게 축약하지 말 것 (최소 2문장 이상)

[출력]
- 설명 없이 최종 프롬프트 문장만 출력
"""

    user_input = f"""
다음 구조형 프롬프트를 위 규칙에 따라 자연스럽고 완성도 높은 문장형 프롬프트로 변환하라.

[구조형 프롬프트]
{prompt_text}
"""

    return request_chat(system_prompt, user_input, max_tokens=max_tokens)

def evaluate_prompt(prompt, style, max_tokens=300):
    prompt = prompt.strip() if prompt else ""
    style_instruction = get_style_instruction(style)
    task_evidence_rules = get_task_evidence_rules(prompt)

    if not prompt:
        raise ValueError("평가할 프롬프트가 비어 있습니다.")

    system_prompt = f"""
너는 프롬프트 품질을 객관적으로 평가하는 전문가다.

반드시 아래 형식으로만 출력하라:

[목표]
프롬프트의 실무 활용 가능성과 명확성을 기준으로 점수를 평가한다.

[평가 기준] (각 20점, 총 100점)

1. 역할 명확성
- 수행 역할이 구체적인가
- 단순 '전문가'가 아닌가

2. 목표 구체성
- 무엇을 위한 프롬프트인지 명확한가
- 활용 맥락이 포함되어 있는가

3. 조건 적절성
- 실행 가능한 기준인가
- 모호한 표현이 없는가

4. 출력 형식 명확성
- 결과 형태가 명확한가
- 바로 사용 가능한가

5. 실행 가능성
- AI가 바로 이해하고 실행 가능한 수준인가

[점수 계산 규칙]
- 각 항목을 0~20점으로 평가
- 총점 = 5개 항목 합계

[점수 기준 강화]
- 기본적으로 구조가 맞으면 70점 이상 부여
- 실무 사용 가능하면 80점 이상 부여
- 매우 우수한 경우에만 90점 이상 부여
- 지나치게 낮은 점수 금지

[평가]
각 항목별 간단한 평가 작성

[점수 출력 규칙 - 매우 중요]
- 반드시 숫자만 단독으로 출력
- "85점", "총점 85" 절대 금지
- 반드시 아래 형식 유지

[점수]
85

[등급]
S / A / B / C 중 하나

[잘된 점]
- ...

[부족한 점]
- ...

[개선 방향]
- ...

규칙:
- 점수는 100점 기준
- 공공기관 기준
- 신뢰성 최우선
- 불필요한 설명 금지

{task_evidence_rules}

{style_instruction}
"""

    user_input = f"""
다음 프롬프트를 평가하라:

{prompt}
"""

    return request_chat(system_prompt, user_input, max_tokens=max_tokens)

def detect_hallucination(prompt_text, max_tokens=300):
    ensure_client()

    system_prompt = """
너는 생성된 프롬프트의 신뢰성을 검증하는 전문가다.

다음 기준으로 판단하라:

[검증 기준]
- 존재하지 않는 기관/장소/프로그램이 포함되어 있는가
- 근거 없는 추천이 있는가
- 사실 확인 없이 단정하는 표현이 있는가
- 검증 불가능한 구체 정보가 포함되어 있는가

출력 형식:
[판정]
SAFE 또는 RISK

[이유]
- 간단히 설명

규칙:
- 반드시 SAFE 또는 RISK로만 판단
- 설명은 최소화
"""

    user_input = f"""
다음 프롬프트를 검증하라:

{prompt_text}
"""

    result, tokens = request_chat(system_prompt, user_input, max_tokens)

    return result, tokens

@st.cache_data(ttl=3600)
def refine_prompt(last_prompt, feedback, style, max_tokens=500):
    last_prompt = last_prompt.strip() if last_prompt else ""
    feedback = feedback.strip() if feedback else "더 명확하고 실무적으로 개선하라."
    style_instruction = get_style_instruction(style)
    task_evidence_rules = get_task_evidence_rules(last_prompt)

    if not last_prompt:
        raise ValueError("수정할 기존 프롬프트가 비어 있습니다.")

    system_prompt = f"""
너는 프롬프트 최적화 전문가다.

목표:
- 기존보다 반드시 더 나은 프롬프트 생성
- 구조를 절대 깨지 않게 유지

{task_evidence_rules}

[최우선]
- 신뢰성 강화
- 할루시네이션 제거

[절대 형식 규칙 - 위반 금지]
[출력 템플릿 - 반드시 그대로 따를 것]

1. 역할
[여기에 역할 작성]

2. 목표
[여기에 목표 작성]

3. 조건
[여기에 조건 작성]

4. 출력 형식
[여기에 출력 형식 작성]

[형식 강제 규칙]
- "2. 목표 (Goal)"처럼 반드시 한 줄로 작성할 것
- "2.\\n목표" 같은 줄 분리 절대 금지
- 번호와 항목명은 절대 줄바꿈하지 말 것
- 각 항목은 "제목 1줄 + 다음 줄 본문" 구조 유지
- 제목만 따로 떨어지는 경우 절대 금지
- 불필요한 빈 줄 생성 금지
- 번호 형식 절대 변경 금지 (1. 2. 3. 4.)

[작업 유형 유지 규칙]
- 기존 프롬프트의 작업 유형을 유지할 것
- 정보 탐색, 문서 작성, 콘텐츠 제작, 발표 자료, 기획 등
- 작업 유형에 맞는 구조와 표현을 강화할 것

[자기 검증 단계 - 반드시 수행]
- 작성 후 아래 항목을 스스로 점검할 것
1. 1~4 구조가 정확한가?
2. "번호 + 항목명"이 한 줄에 있는가?
3. 줄 분리 오류가 없는가?
→ 하나라도 틀리면 다시 작성할 것

[개선 기준]
- 기존보다 더 구체적으로 작성할 것
- 조건은 더 명확하게 수정할 것
- 결과 활용성이 더 높아지도록 개선할 것

[해석 규칙]
- 사용자 요청이 부족하더라도 의도를 보완하여 개선할 것

[추가 규칙]
- 기존 프롬프트보다 반드시 개선될 것
- 모호한 표현 제거
- 실무에서 바로 사용 가능해야 함
- {style_instruction}

[출력 규칙]
- 설명 금지
- 프롬프트 본문만 출력
"""

    user_input = f"""
기존 프롬프트:
{last_prompt}

사용자 수정 요청:
{feedback}

위 요청을 반영하여 더 나은 최종 프롬프트를 작성하라.
"""

    return request_chat(system_prompt, user_input, max_tokens=max_tokens)

import json

def parse_user_input(free_text, max_tokens=300, retry=1):
    ensure_client()   # ✅ 여기 추가

    if len(free_text.strip()) < 5:
        return free_text, "요청 의도를 기반으로 적절한 결과 생성"
    
    system_prompt = """
너는 사용자의 입력을 분석하여 상황(situation)과 목표(goal)로 구조화하는 전문가다.

반드시 아래 JSON 형식으로만 출력하라:

[목표]
사용자가 무엇을 하려는지 명확하게 정리한다.

[출력 형식]
{
  "situation": "...",
  "goal": "..."
}

[규칙]
- JSON 외 다른 텍스트 절대 금지
- key 이름은 반드시 situation, goal

[해석 규칙]
- 입력이 짧거나 모호해도 의미를 추론할 것
- 사용자의 의도를 최대한 구체적으로 보완할 것
- 상황이 없으면 일반적인 상황을 생성할 것
- 목표가 모호하면 결과 형태까지 명확하게 작성할 것
- 초보자가 입력한 것으로 가정하고 보정할 것
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": free_text}
        ],
        max_tokens=max_tokens
    )

    content = response.choices[0].message.content

    # ✅ 코드블럭 제거 (여기!)
    content = content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]

    try:
        data = json.loads(content)

        # ✅ 1차 검증 (키 존재 여부)
        if "situation" in data and "goal" in data:
            return data["situation"], data["goal"]
        else:
            raise ValueError("JSON 구조 오류")

    except Exception:

        # ✅ 재시도 (1회)
        if retry > 0:
            return parse_user_input(free_text, max_tokens, retry=0)

        # ✅ 최종 fallback
        return free_text, "사용자의 요청 의도에 맞는 결과를 생성"

def explain_diff(before, after, max_tokens=400):
    ensure_client()

    system_prompt = """
너는 프롬프트 코치 전문가다.

역할:
이전 프롬프트와 개선된 프롬프트를 비교하여
왜 변경되었는지 설명한다.

설명 기준:
1. 무엇이 개선되었는지
2. 왜 더 좋은지
3. 어떤 효과가 있는지
4. 실무에서 어떤 차이가 나는지

규칙:
- 초보자도 이해 가능하게 설명
- 불필요한 이론 금지
- 핵심만 명확하게
- 공공기관 실무 기준 유지
"""

    user_input = f"""
이전 프롬프트:
{before}

개선된 프롬프트:
{after}

차이와 개선 이유를 설명하라.
"""

    return request_chat(system_prompt, user_input, max_tokens)