import json
import os
from datetime import datetime

DATA_FILE = "usage.json"

# 1. 데이터 로드
def load_usage():
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}


# 2. 데이터 저장
def save_usage(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# 3. 오늘 사용량 가져오기
def get_today_usage():
    data = load_usage()
    today = datetime.now().strftime("%Y-%m-%d")

    return data.get(today, 0)


# 4. 사용량 추가
def add_usage(tokens):
    data = load_usage()
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in data:
        data[today] = 0

    data[today] += tokens
    save_usage(data)


# 5. 비용 계산 (대략)
def tokens_to_krw(tokens):
    # gpt-4o-mini 기준 (대략)
    # 1K tokens ≈ $0.0005
    usd = tokens / 1000 * 0.0005
    krw = usd * 1500
    return round(krw, 2)


# 6. 예산 체크
def check_budget(limit_krw=1000):
    today_tokens = get_today_usage()
    cost = tokens_to_krw(today_tokens)

    if cost >= limit_krw:
        return False, cost

    return True, cost