"""stop — 지정 문자열을 만나면 생성 중단(해당 문자열은 출력에 포함되지 않음).

실행:  python t3_stop.py
환경변수: BASE_URL, API_KEY, MODEL
"""
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("API_KEY", "EMPTY"),
)
MODEL = os.getenv("MODEL", "your-model-id")

# stop 없음: 끝까지 나열
no_stop = client.chat.completions.create(
    model=MODEL, temperature=0.0, max_tokens=100,
    messages=[{"role": "user", "content": "1, 2, 3, 4, 5, 6 처럼 콤마로 숫자를 나열해"}],
).choices[0].message.content

# stop=["3"]: "3"을 만나면 그 직전까지만
with_stop = client.chat.completions.create(
    model=MODEL, temperature=0.0, max_tokens=100, stop=["3"],
    messages=[{"role": "user", "content": "1, 2, 3, 4, 5, 6 처럼 콤마로 숫자를 나열해"}],
).choices[0].message.content

print("stop 없음   →", repr(no_stop))
print("stop=['3'] →", repr(with_stop))   # "3" 직전에서 끊김
