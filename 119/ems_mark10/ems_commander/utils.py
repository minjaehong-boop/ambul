"""server / cli 양쪽에서 공용으로 쓰는 순수 헬퍼 모음.

prototype 의 server.py·agent.py 에 중복 복사돼 있던 JSON/텍스트 파서를
한 곳으로 모았다.
"""

import json
import re

__all__ = [
    "extract_json_object",
    "safe_json_parse",
    "normalize_text",
    "normalize_symptom_query",
]


def extract_json_object(text: str):
    """LLM 출력에서 첫 번째 완결된 JSON 객체 문자열만 추출한다.

    마크다운 코드펜스(```json ... ```)를 제거하고, 문자열 리터럴 내부의
    중괄호는 무시하면서 깊이를 세어 균형 잡힌 `{...}` 한 덩어리를 반환한다.
    찾지 못하면 None.
    """
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]
    return None


def safe_json_parse(content: str):
    """extract_json_object 로 뽑은 객체를 json.loads 한다. 없으면 ValueError."""
    candidate = extract_json_object(content)
    if candidate is None:
        raise ValueError("No JSON object found in model output.")
    return json.loads(candidate)


def normalize_text(text) -> str:
    """공백 정규화 + 소문자화. 매칭/검색 비교용."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def normalize_symptom_query(symptom) -> str:
    """복합 증상 문자열에서 대표 키워드 1개를 뽑는다.

    예) "흉통, 식은땀" -> "흉통" / "복통 및 구토" -> "복통"
    """
    if not symptom:
        return ""
    cleaned = str(symptom).replace("및", ",")
    parts = [p.strip() for p in re.split(r"[,/]", cleaned) if p.strip()]
    return parts[0] if parts else cleaned.strip()
