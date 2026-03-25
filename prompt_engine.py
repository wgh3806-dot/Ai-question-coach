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
"""
    }

    return templates.get(template_type, "")

def get_style_instruction(style):
    if style == "간결형":
        return "구조를 유지하되 자연스러운 문장형으로 간결하게 작성하라."
    elif style == "초간결형":
        return "최소 문장으로 핵심만 전달하라. 불필요한 표현 금지."
    else:
        return "구조와 설명을 포함하여 작성하라."
    
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

def generate_prompt(situation, goal, style, extra="", template_type=None, max_tokens=500):
    style_instruction = get_style_instruction(style)
    reliability = get_reliability_rules()
    template_rule = get_template_rules(template_type)

    system_prompt = f"""
너는 생성형 AI 질문 코치 시스템이다.

목적:
사용자의 질문을 분석하고 100점 프롬프트를 생성한다.

{reliability}

{template_rule}

[프롬프트 구조]
1. 역할 (Role)
2. 목표 (Goal)
3. 조건 (Instructions)
4. 출력 형식 (Format)

[중요 규칙]
- 결과물 생성이 목적이다 (설명 금지)
- "이 프롬프트를 활용하여" 같은 문장 절대 금지
- 반드시 실제 결과가 나오도록 작성

[스타일]
{style_instruction}
"""

    user_input = f"""
[상황]
{situation}

[목표]
{goal}

[추가 요구사항]
{extra}
"""

    return request_chat(system_prompt, user_input, max_tokens)

def evaluate_prompt(prompt, style, max_tokens=500):
    prompt = prompt.strip() if prompt else ""
    style_instruction = get_style_instruction(style)

    if not prompt:
        raise ValueError("평가할 프롬프트가 비어 있습니다.")

    system_prompt = f"""
너는 프롬프트 평가 전문가다.

아래 기준으로 프롬프트를 분석하라:
평가 기준:
1. 구조 완성도
2. 명확성
3. 실행 가능성
4. 공공기관 적합성
5. 신뢰성 (가장 중요)

[신뢰성 평가]
- 사실 기반 여부
- 할루시네이션 위험
- 검증 가능성
- 출처 유도 여부

출력 형식:
1. 총점 (100점 만점)
2. 잘된 점
3. 부족한 점
4. 개선 방향
5. 개선된 프롬프트

{style_instruction}
"""

    user_input = f"""
다음 프롬프트를 평가하고 개선하라.

프롬프트:
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