"""선택기(Selector) 시스템 프롬프트에 주입할 스킬 텍스트 로더.

prototype 의 server.py 에 있던 _load_selector_skill_text 를 분리한 것.
SKILL.md / references/examples.md 가 없으면 조용히 빈 문자열로 degrade 한다
(파이프라인 동작에는 영향 없음 — 프롬프트 보강용 참고 자료일 뿐).
"""

import os

from . import config


def _load_skill_section(path: str, start_heading: str, end_heading: str | None = None) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    start_idx = text.find(start_heading)
    if start_idx == -1:
        return ""
    if end_heading:
        end_idx = text.find(end_heading, start_idx)
        if end_idx != -1:
            return text[start_idx:end_idx].strip()
    return text[start_idx:].strip()


def load_selector_skill_text(selector_kind: str) -> str:
    """selector_kind: 'ktas' | 'protocol'."""
    skill_path = os.path.join(config.SKILL_BASE, "SKILL.md")
    examples_path = os.path.join(config.SKILL_BASE, "references", "examples.md")

    if selector_kind == "ktas":
        skill_section = _load_skill_section(skill_path, "## 1) KTAS 섹션 선택", "## 2) 지침 키워드 선택")
        examples_section = _load_skill_section(examples_path, "## KTAS 섹션 선택", "## 지침 키워드 선택")
    else:
        skill_section = _load_skill_section(skill_path, "## 2) 지침 키워드 선택")
        examples_section = _load_skill_section(examples_path, "## 지침 키워드 선택")

    return "\n\n".join([s for s in [skill_section, examples_section] if s])
