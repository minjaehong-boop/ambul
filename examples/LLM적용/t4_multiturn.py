"""멀티턴 — assistant 메시지로 직전 답을 되먹여 맥락을 유지한다.

실행:  python t4_multiturn.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")

history = [{"role": "user", "content": "내 이름은 JH야."}]
a1 = client.chat.completions.create(model=MODEL, messages=history).choices[0].message.content
print("1턴:", a1)

history.append({"role": "assistant", "content": a1})
history.append({"role": "user", "content": "내 이름 뭐라고 했지?"})
a2 = client.chat.completions.create(model=MODEL, messages=history).choices[0].message.content
print("2턴:", a2)   # "JH"를 기억해야 함
