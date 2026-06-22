"""max_tokens — 출력 길이 상한(작으면 잘림).

실행:  python t3_maxtok.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")


def ask(n):
    return client.chat.completions.create(
        model=MODEL, max_tokens=n, temperature=0.0,
        messages=[{"role": "user", "content": "1부터 50까지 세어줘"}],
    ).choices[0].message.content


print("max_tokens=10  →", ask(10))    # 중간에 끊김
print("max_tokens=500 →", ask(500))   # 끝까지
