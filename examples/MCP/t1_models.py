"""LLM 서버에 올라간 모델 목록 확인.

실행:  python t1_models.py
환경변수: BASE_URL, API_KEY
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)

for m in client.models.list().data:
    print(m.id)
