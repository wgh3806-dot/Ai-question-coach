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


def get_style_instruction(style):
    if style == "간결형":
        return "구조를 유지하되 자연스러운 문장형으로 간결하게 작성하라."
    elif style == "초간결형":
        return "최소 문장으로 핵심만 전달하라. 불필요한 표현 금지."
    else:
        return "구조와 설명을 포함하여 작성하라."


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

def generate_prompt(situation, goal, style, max_tokens=500):
    style_instruction = get_style_instruction(style)

    system_prompt = f"""
너는 생성형 AI 질문 코치 시스템이다.

목적:
사용자의 질문을 분석하고 100점 수준의 프롬프트로 개선한다.

반드시 아래 사고 과정을 거쳐라:
1. 사용자 상황 분석
2. 목표 재정의
3. 최적 전략 수립
4. 최종 프롬프트 생성

출력 규칙:
- 반드시 아래 구조 유지

1. 역할 (Role)
2. 목표 (Goal)
3. 조건 (Instructions)
4. 출력 형식 (Format)

추가 규칙:
- 초보자도 복사해서 바로 사용 가능해야 한다
- 불필요한 표현 제거
- 모호한 표현 금지
- 항상 완성형 결과 제공
- {style_instruction}
"""
    if style in ["간결형", "초간결형"]:
        system_prompt += "\n구조를 유지하되 문장형으로 변환하라."

    user_input = f"""
상황: {situation}
목표: {goal}

정보가 부족하면 일반적인 업무 상황 기준으로 보완하라.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        max_tokens=max_tokens
    )

    return response.choices[0].message.content, response.usage.total_tokens

def evaluate_prompt(prompt, style, max_tokens=500):
    prompt = prompt.strip() if prompt else ""
    style_instruction = get_style_instruction(style)

    if not prompt:
        raise ValueError("평가할 프롬프트가 비어 있습니다.")

    system_prompt = f"""
너는 프롬프트 평가 전문가다.

아래 기준으로 프롬프트를 분석하라:
1. 구조 완성도
2. 명확성
3. 실행 가능성
4. 초보자 사용성
5. 결과 품질 가능성

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