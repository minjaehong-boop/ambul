"""LLM 호출 기본형.

실행:  python t2_call.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")

res = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "너는 친절한 비서다."},
        {"role": "user", "content": "한 문장으로 자기소개 해줘."},
    ],
)
print(res.choices[0].message.content)
