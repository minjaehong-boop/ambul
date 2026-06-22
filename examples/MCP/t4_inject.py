"""컨텍스트 주입 — 자료를 프롬프트에 넣고 그 자료에만 근거해 답하게 한다.

실행:  python t4_inject.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")

doc = "회사 점심시간은 12:00~13:00이다. 회의실 예약은 사내포털에서 한다."

res = client.chat.completions.create(
    model=MODEL, temperature=0.0,
    messages=[
        {"role": "system", "content": f"아래 자료에만 근거해 답하라.\n[자료]\n{doc}"},
        {"role": "user", "content": "점심시간 언제야?"},
    ],
)
print(res.choices[0].message.content)
