"""stream — 토큰 스트리밍 출력.

실행:  python t3_stream.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")

stream = client.chat.completions.create(
    model=MODEL, stream=True,

    messages=[{"role": "user", "content": "안녕"}],
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
print()
