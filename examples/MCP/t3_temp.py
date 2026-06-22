"""temperature — 결정론(0.0) vs 다양성(높음).

실행:  python t3_temp.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")


def ask(temp):
    return client.chat.completions.create(
        model=MODEL, temperature=temp, max_tokens=5000,
        messages=[{"role": "user", "content": "아무 단어 5개만 나열해"}],
    ).choices[0].message.content


print("temp=0.0 →", ask(0.0))
print("temp=0.0 →", ask(0.0))   # 위와 (거의) 동일해야 함
print("temp=1.2 →", ask(1.2))   # 매번 달라짐
