"""top_p — 누적확률(nucleus) 샘플링. 낮을수록 보수적, 높을수록 다양.

temperature를 1.0으로 고정하고 top_p만 바꿔 효과를 본다.
(temperature=0 이면 top_p는 사실상 무의미)

실행:  python t3_top_p.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")


def ask(top_p):
    return client.chat.completions.create(
        model=MODEL, temperature=1.0, top_p=top_p, max_tokens=50,
        messages=[{"role": "user", "content": "아무 단어 5개만 나열해"}],
    ).choices[0].message.content


print("top_p=0.1 →", ask(0.1))   # 상위 확률 토큰만 → 보수적/반복적
print("top_p=1.0 →", ask(1.0))   # 전체 분포 → 다양
