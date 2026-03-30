from openai import OpenAI

client = None
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
        "팩트"
    ]

    if any(keyword in text for keyword in info_keywords):
        return "정보 탐색"

    return None

def get_style_instruction(style):
    if style == "간결형":
        return "구조를 유지하되 자연스러운 문장형으로 간결하게 작성하라."
    elif style == "문장형":
        return """
        출력 형식:
        - 전체를 자연스러운 요청 문장으로 작성할 것
        - 역할(Role), 목표(Goal), 조건(Instructions), 출력 형식(Format)을 모두 포함할 것
        - 항목 나열형보다 연결된 문장형 프롬프트를 우선할 것
        - 항목형 나열보다 연결된 한두 개 단락의 요청문 형태를 우선할 것
        - 초보자가 그대로 복사해 AI에 붙여넣어도 잘 작동하도록 충분히 구체적으로 작성할 것
        - 사용자가 AI에 직접 넣는 실전 요청문처럼 작성할 것
        - 설명문 없이 최종 프롬프트 본문만 출력할 것
        - 공문, 안내문, 의뢰문처럼 쓰지 말 것
        - '귀하', '요청합니다', '직원으로서' 같은 표현 대신 AI에게 직접 지시하는 요청문으로 작성할 것
        """
    elif style == "초간결형":
        return "최소 문장으로 핵심만 전달하라. 불필요한 표현 금지."
    else:
        return """
                출력 형식:
                - 1. 역할 (Role), 2. 목표 (Goal), 3. 조건 (Instructions), 4. 출력 형식 (Format) 구조를 정확히 유지할 것
                - 각 항목은 전문가가 바로 사용할 수 있을 정도로 구체적으로 작성할 것
                - 역할, 목표, 조건, 출력 형식의 구분이 분명해야 함
                - 형식은 예시처럼 정돈된 구조형 프롬프트로 작성할 것
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
너는 아래 업무를 수행하는 10년 이상 경력의 실무 전문가다.

업무:
{text}

현장에서 바로 사용할 수 있는 수준으로 작성하라.
"""

def generate_prompt(preview_text, style, max_tokens=700):

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
- 예: '포항시 정보통신과의 전문가'처럼 쓰지 말고, '정보통신 선진지 견학 장소 추천 전문가'처럼 작성할 것
- 기관명이나 부서명은 상황 또는 목표에 포함할 것

[목표 작성 규칙]
- 목표(Goal)에는 사용자의 기관, 부서, 목적, 활용 맥락을 반영할 것
- 역할과 목표를 혼동하지 말 것

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

def evaluate_prompt(prompt, style, max_tokens=500):
    prompt = prompt.strip() if prompt else ""
    style_instruction = get_style_instruction(style)

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

{style_instruction}
"""

    user_input = f"""
다음 프롬프트를 평가하라:

{prompt}
"""

    return request_chat(system_prompt, user_input, max_tokens=max_tokens)

def refine_prompt(last_prompt, feedback, style, max_tokens=500):
    last_prompt = last_prompt.strip() if last_prompt else ""
    feedback = feedback.strip() if feedback else "더 명확하고 실무적으로 개선하라."
    style_instruction = get_style_instruction(style)

    if not last_prompt:
        raise ValueError("수정할 기존 프롬프트가 비어 있습니다.")

    system_prompt = f"""
너는 프롬프트 최적화 전문가다.

목표:
- 기존보다 반드시 더 나은 프롬프트 생성

최우선:
- 신뢰성 강화
- 할루시네이션 제거

규칙:
- 기존 프롬프트보다 반드시 더 나아져야 한다
- 구조는 유지해야 한다
- 모호한 표현은 줄여야 한다
- 초보자도 이해 가능해야 한다
- 점수 평가 기준상 기존 프롬프트보다 개선될 가능성이 높은 방향으로만 수정할 것
- {style_instruction}

반드시 아래 구조를 유지하라:
1. 역할 (Role)
2. 목표 (Goal)
3. 조건 (Instructions)
4. 출력 형식 (Format)
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