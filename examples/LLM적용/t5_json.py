"""JSON 출력 안정화 — 추출 → 파싱 → 1회 재시도.

실행:  python t5_json.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
import re
import json
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")


def extract_json(text):
    """첫 번째 균형 잡힌 {...} 한 덩어리만 추출 (코드펜스 제거)."""
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = in_str = esc = 0
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = 0
            elif c == "\\":
                esc = 1
            elif c == '"':
                in_str = 0
            continue
        if c == '"':
            in_str = 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def ask_json(prompt):
    msgs = [{"role": "user", "content": prompt}]
    content = client.chat.completions.create(
        model=MODEL, messages=msgs, temperature=0.0).choices[0].message.content
    obj = extract_json(content)
    print(f"첫 답변:{obj}")
    if obj is None:   # 재시도: 방금 답을 되먹이고 다시 요청
        msgs += [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "JSON만 다시 출력. 다른 문장 금지."},
        ]
        content = client.chat.completions.create(
            model=MODEL, messages=msgs, temperature=0.0).choices[0].message.content
        obj = extract_json(content)
    return json.loads(obj)

print(f"두 번째 답변:{ask_json('네 이름이 뭐니')}")
#print(ask_json('이름="JH", 나이=26 을 {"name":..,"age":..} 로'))
