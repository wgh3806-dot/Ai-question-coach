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

def get_template_rules(template_type):
    templates = {

        "보고서 작성": """
너는 공공기관 보고서 작성 전문가다.

- 보고서 형식으로 작성
- 논리 구조 유지 (배경 → 내용 → 결론)
- 불필요한 수식어 제거
- 설명 문장 금지
""",

        "이메일 작성": """
너는 공공기관 공문/이메일 작성 전문가다.

- 정중하고 명확하게 작성
- 불필요한 감정 표현 금지
- 실제 발송 가능한 형태로 작성
""",

        "계획서 작성": """
너는 공공기관 사업계획서 작성 전문가다.

- 실행 가능한 계획 중심 작성
- 목적, 추진내용, 기대효과 포함
- 실무형 문장 사용
""",

        "보도자료 작성": """
너는 공공기관 보도자료 작성 전문가다.

- 기사형 문장으로 작성
- 홍보성 문구 금지 (예: 많은 참여 바랍니다)
- 설명 문장 금지
- 실제 언론 배포 수준으로 작성

[형식]
- 제목
- 본문
""",

        "국민신문고 답변": """
너는 공공기관 민원 답변 전문가다.

- 정중하고 법적 문제 없는 표현 사용
- 모호한 표현 금지
- 민원인의 질문에 정확히 답변
""",

        "정보공개청구 답변": """
너는 공공기관 정보공개 담당자다.

- 관련 법령 기준으로 작성
- 공개 가능 여부 명확히 판단
- 근거 포함
""",

        "행사 시나리오": """
너는 공공기관 행사 운영 전문가다.

- 시간 흐름 중심으로 작성
- 실제 진행 가능한 시나리오 구성
- 멘트 포함 가능
""",
        "정보 탐색": """
너는 특정 주제에 대해 정확하고 이해하기 쉽게 설명하는 정보 탐색 전문가다.

- 사실 기반으로 설명할 것
- 불확실한 내용은 생성 금지
- 추정, 과장, 창작 금지
- 초보자도 이해할 수 있게 설명할 것
- 핵심부터 먼저 설명할 것
- 불필요한 홍보성 문장 금지
- 설명 외 군더더기 문장 금지

[형식]
1. 핵심 요약
2. 주요 내용
3. 추가로 알아둘 점
"""
    }

    return templates.get(template_type, "")

def detect_task_type(situation, goal):
    text = f"{situation} {goal}".lower()

    # 문서 작성 계열
    if "보도자료" in text:
        return "보도자료 작성"
    elif "보고서" in text:
        return "보고서 작성"
    elif "이메일" in text or "메일" in text:
        return "이메일 작성"
    elif "민원" in text or "신문고" in text:
        return "국민신문고 답변"
    elif "정보공개" in text:
        return "정보공개청구 답변"
    elif "계획서" in text or ("계획" in text and "작성" in text):
        return "계획서 작성"
    elif "행사" in text or "시나리오" in text:
        return "행사 시나리오"

    # 정보 탐색 계열
    info_keywords = [
        "무엇", "뭐", "설명", "알려줘", "정리", "비교", "차이",
        "개념", "의미", "이유", "원인", "전망", "동향", "분석",
        "찾아줘", "검색", "조사", "소개", "장단점", "특징", "보여줘",
        "팩트",
        "추천", "순위", "리스트", "top", "best"
    ]

    if any(keyword in text for keyword in info_keywords):
        return "정보 탐색"

    return None

def get_style_instruction(style):
    if style == "간결형":
        return """
                출력 형식:
                - 1. 역할 (Role), 2. 목표 (Goal), 3. 조건 (Instructions), 4. 출력 형식 (Format) 구조는 유지할 것
                - 다만 전문가형보다 짧고 직관적으로 작성할 것
                - 역할은 실제 수행자처럼 자연스럽게 표현할 것
                - 목표는 사용자가 바로 이해할 수 있게 구체적으로 작성할 것
                - 조건은 핵심만 남기되, 실행에 필요한 검증 기준과 확인 필요 사항은 유지할 것
                - 전체적으로 짧지만 실제로 바로 사용할 수 있는 프롬프트가 되도록 작성할 것
                """
    elif style == "문장형":
        return """
                출력 형식:
                - 전체를 자연스러운 요청 문장 형태로 작성할 것
                - 1. 역할 (Role), 2. 목표 (Goal), 3. 조건 (Instructions), 4. 출력 형식 (Format)의 핵심 내용을 모두 포함할 것
                - 번호형 구조로 나열하지 말고, 한두 문단의 연결된 문장으로 자연스럽게 작성할 것
                - 프롬프트 자체는 읽기 쉽게 정리하되, 핵심 정보가 빠지지 않게 할 것
                - 반드시 문장 첫 부분에 "구체적인 역할 + 전문가로서" 형태로 포함할 것 (예: 공공기관 협조 요청 공문 작성 전문가로서)
                - 역할은 사용자의 요청 내용에 맞게 자동으로 구체화할 것 (단순 '전문가' 금지)
                - 구조형의 역할(Role)을 그대로 반영하거나 유사하게 생성할 것
                - 목표와 조건이 문장 안에 자연스럽게 드러나도록 작성할 것
                - 출력 형식은 마지막 부분에 어떤 형태로 작성할지 드러나게 할 것
                - 지나치게 짧게 축약하지 말 것
                - 불필요한 설명문 없이 최종 프롬프트 본문만 출력할 것

                예:
                공공기관 협조 요청 공문 작성 전문가로서, 경주시 정보통신과와의 협조를 통해 필요한 정보를 수집하고 업무를 원활하게 진행할 수 있도록 방문 협조 요청 공문을 작성해줘. 협조 요청 목적이 분명하게 드러나도록 하고 공공기관 문체에 맞게 작성하며, 결과는 실제로 바로 활용할 수 있는 방문 요청 공문 형식으로 정리해줘.
                """
    elif style == "초간결형":
        return """
                출력 형식:
                - 최소 문장으로 핵심만 전달할 것
                - 불필요한 표현을 제거할 것
                - 너무 짧아서 목적이 흐려지지 않도록 할 것
                """
    
    elif style == "간결구조형":
        return """
                출력 형식:
                - 1. 역할, 2. 목표, 3. 조건, 4. 출력 형식 구조 유지
                - 각 항목은 짧고 간단하게 작성할 것
                - 조건은 3개 이내로 제한
                - 불필요한 설명 금지
                - 실무에서 바로 사용할 수 있게 작성
                """

    else:
        return """
                출력 형식:
                - 1. 역할 (Role), 2. 목표 (Goal), 3. 조건 (Instructions), 4. 출력 형식 (Format) 구조를 정확히 유지할 것
                - 각 항목은 실제 실무자가 바로 사용할 수 있을 정도로 구체적이고 완성도 있게 작성할 것
                - 역할은 수행해야 할 전문 역할로 명확하게 정의할 것
                - 목표는 기관, 목적, 활용 맥락이 드러나도록 구체적으로 작성할 것
                - 조건은 실행에 필요한 핵심 기준, 검증 기준, 확인 정보, 실무 요소를 빠짐없이 포함할 것
                - 출력 형식은 결과를 바로 활용할 수 있도록 항목과 순서를 명확하게 제시할 것
                - 전체적으로 구조적이고 논리적이며 신뢰감 있는 고품질 프롬프트로 작성할 것
                """
    
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
    if template_type == "정보 탐색":
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
    # 템플릿 기반
    if template_type:

        expert_map = {
            "보도자료 작성": "10년 이상 경력의 공공기관 홍보담당 사무관",
            "보고서 작성": "10년 이상 경력의 정책기획 담당 사무관",
            "이메일 작성": "공공기관 행정업무 담당자",
            "계획서 작성": "공공기관 사업기획 전문가",
            "국민신문고 답변": "민원 대응 담당 공무원",
            "정보공개청구 답변": "정보공개 및 법령 검토 담당자",
            "행사 시나리오": "공공기관 행사 운영 전문가"
        }

        role = expert_map.get(template_type, "공공기관 실무 담당자")

        return f"""
너는 {role}다.

실제 업무를 수행하는 입장에서
결과를 작성하라.
"""

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
def generate_prompt(preview_text, style, max_tokens=500):
    style_instruction = get_style_instruction(style)
    reliability = get_reliability_rules()

    structure_block = ""
    if style != "문장형":
        structure_block = """
[프롬프트 구조]
1. 역할 (Role)
2. 목표 (Goal)
3. 조건 (Instructions)
4. 출력 형식 (Format)

[형식 고정 규칙]
- 반드시 위 구조를 그대로 따를 것
- 번호와 제목 형식을 임의로 바꾸지 말 것
- '역할:', '목표:' 같은 축약 표기는 사용하지 말 것
- 번호 앞의 점만 쓰거나 형식을 깨뜨리지 말 것
- 각 항목은 줄바꿈으로 명확히 구분할 것
- 1, 2, 3, 4 각 항목은 한 줄 제목 + 다음 줄 본문 형식을 유지할 것
"""

    system_prompt = f"""
너는 생성형 AI 질문 코치 시스템이다.

목표:
사용자가 바로 사용할 수 있는 "완성된 프롬프트"를 만든다.

{reliability}

[핵심 규칙]
- 반드시 프롬프트만 생성
- 절대 답변 생성 금지
- 설명 금지
- style이 문장형이면 1, 2, 3, 4 번호 구조로 나열하지 말 것
- 구조형일 때만 정해진 항목 구조를 따를 것
- ```markdown, ``` 같은 코드펜스를 붙이지 말 것
- 제목 설명 없이 프롬프트 본문만 출력할 것

{structure_block}

[Role 작성 규칙]
- 역할(Role)은 사용자의 소속, 기관명, 부서명이 아니라 수행해야 할 전문 역할로 작성할 것
- 예: '포항시 정보통신과의 전문가'처럼 쓰지 말고, '선진지 견학 장소 추천 전문가'처럼 작성할 것
- 기관명이나 부서명은 상황 또는 목표에 포함할 것

[목표 작성 규칙]
- 목표(Goal)에는 사용자의 기관, 목적, 활용 맥락을 반영할 것
- 역할과 목표를 혼동하지 말 것

[작업 성격별 근거 규칙]
- 작업 성격에 맞는 근거를 사용할 것
- 모든 작업에 동일한 근거를 기계적으로 적용하지 말 것
- 견학/일정/방문/벤치마킹 작업에서는 법령보다 공식 홈페이지, 기관 안내자료, 운영시간, 예약 여부, 위치, 연락처, 프로그램 운영 여부, 이동 동선 등 실무 확인 정보에 우선순위를 둘 것
- 변동 가능성이 큰 항목은 '확인 필요'로 표시할 것
- 보고서/정책/행정답변처럼 법령이 핵심인 작업에만 관련 법령·지침·정책 기준을 우선 반영할 것

[구조형 품질 기준]
- 구조형 프롬프트는 실제 실무자가 바로 사용할 수 있는 수준으로 작성할 것
- 특히 견학 장소 추천/탐색 작업에서는 운영 시간, 예약 여부, 프로그램 내용, 위치, 연락처, 공식 링크, 벤치마킹 포인트를 포함하는 방향으로 구체화할 것
- 'fact-based' 같은 영어 표현 대신 자연스러운 한국어로 작성할 것

[핵심 작성 기준]
- 실무에서 바로 사용할 수 있게 작성
- 불필요한 조건 제거
- 핵심 정보 위주로 작성
- 사실 기반 유지

[문장형 말투 규칙]
- 문장형일 때는 공문체, 의뢰문체, 안내문체를 사용하지 말 것
- '요청드립니다', '직원으로서', '귀하' 같은 표현을 사용하지 말 것
- AI에게 직접 지시하는 요청문처럼 작성할 것
- 예: '포항시 정보통신과의 선진지 견학 목적에 맞는 장소를 추천해줘'처럼 작성할 것
- 문장형 결과는 구조형 프롬프트를 문장으로 풀어쓴 수준이 아니라, 실제로 AI에 바로 붙여넣을 수 있는 자연스러운 최종 요청문이어야 할 것

[스타일]
{style_instruction}
"""

    user_input = f"""
아래 요구사항을 기반으로 최종 프롬프트를 작성하라.

{preview_text}
"""

    return request_chat(system_prompt, user_input, max_tokens)

def convert_prompt_to_sentence(prompt_text, max_tokens=500):
    ensure_client()

    system_prompt = """
너는 구조형 프롬프트를 초보자도 바로 복사해서 사용할 수 있는 자연스러운 문장형 프롬프트로 바꾸는 전문가다.

반드시 아래 원칙을 지켜라.
- 구조형 프롬프트의 핵심 의미를 유지할 것
- 역할(Role), 목표(Goal), 조건(Instructions), 출력 형식(Format)을 빠뜨리지 말 것
- 결과는 항목 나열형보다 자연스러운 요청문 형태로 만들 것
- 단, 너무 짧게 줄이지 말고 실제로 AI가 잘 이해할 수 있게 충분히 구체적으로 작성할 것
- 최종 결과는 사용자가 그대로 복사해 AI에 붙여넣을 수 있어야 함
- 군더더기 설명 없이 프롬프트 본문만 출력할 것

좋은 예시 느낌:
너는 공공기관 보고서 작성 전문가다. 아래 상황과 목표를 바탕으로 보고서를 작성해줘. 핵심 내용은 논리적으로 정리하고, 사실 기반으로 작성하며, 불확실한 정보는 단정하지 말아줘. 문체는 공공기관 실무에 맞게 유지하고, 결과는 제목, 핵심 요약, 본문 순서로 정리해줘.
"""

    user_input = f"""
다음 구조형 프롬프트를 위 원칙에 따라 충분히 자연스러운 문장형 프롬프트로 바꿔라.

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
너는 프롬프트 평가 전문가다.

반드시 아래 형식으로만 출력하라:

[점수]
숫자만 출력 (예: 82)

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

[자기 검증 단계 - 반드시 수행]
- 작성 후 아래 항목을 스스로 점검할 것
1. 1~4 구조가 정확한가?
2. "번호 + 항목명"이 한 줄에 있는가?
3. 줄 분리 오류가 없는가?
→ 하나라도 틀리면 다시 작성할 것

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
    
    system_prompt = """
너는 사용자 요청을 구조화하는 전문가다.

반드시 아래 JSON 형식으로만 출력하라:

{
  "situation": "...",
  "goal": "..."
}

규칙:
- JSON 외 다른 텍스트 절대 금지
- key 이름은 반드시 situation, goal
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
    content = content.strip().replace("```json", "").replace("```", "")

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
        return free_text, "사용자의 요청을 기반으로 결과 생성"

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