"""server / cli 공용 헬퍼 (JSON/텍스트 파서). 중복 제거 지점."""

import re

__all__ = ["extract_json_object", "safe_json_parse", "normalize_text"]


def extract_json_object(text: str):
    """LLM 출력에서 첫 번째 완결된 JSON 객체 문자열만 추출. 없으면 None."""
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
    import json
    candidate = extract_json_object(content)
    if candidate is None:
        raise ValueError("No JSON object found in model output.")
    return json.loads(candidate)


def normalize_text(text) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()
