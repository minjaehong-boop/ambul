"""KTAS 규정집 — 'LLM 섹션 선택기' 기반 검색 + 체크리스트 생성 (prototype 방식).

ems_mark9 의 임베딩 검색(KtasEmbeddingStore)과 달리, mark10 은:
  - KtasSectionStore     : 규정집(여러 파일)을 "### " 헤더로 섹션 분할 + 문자열 폴백 검색
  - KtasSectionSelector  : LLM 이 증상에 맞는 섹션 제목 top-3 를 직접 고름
  - build_checklist_*    : 섹션 본문에서 (등급, 항목, 질병명) 체크리스트 추출
"""

import os
import re
from dataclasses import dataclass

from openai import OpenAI

from . import config
from .skills import load_selector_skill_text
from .utils import normalize_text, safe_json_parse


@dataclass
class KtasSection:
    title: str
    content: str
    start_line: int
    source_file: str


class KtasSectionStore:
    """규정집 파일들을 '### ' 헤더 기준 섹션으로 적재한다(임베딩 불필요)."""

    def __init__(self, guideline_paths=None):
        self.guideline_paths = guideline_paths or config.ktas_guideline_paths()
        self.sections = []
        self._load_all()

    def _load_sections_from_file(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"guideline not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        sections = []
        current_title = None
        current_start = None
        current_lines = []

        def flush_section():
            if current_title and current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) > 30:
                    sections.append(
                        KtasSection(
                            title=current_title,
                            content=content,
                            start_line=current_start,
                            source_file=os.path.basename(path),
                        )
                    )

        for idx, line in enumerate(lines, start=1):
            if line.startswith("### "):
                flush_section()
                current_title = line.replace("### ", "").strip()
                current_start = idx
                current_lines = []
                continue
            if current_title is not None:
                current_lines.append(line)

        flush_section()
        return sections

    def _load_all(self):
        sections = []
        for path in self.guideline_paths:
            if not os.path.exists(path):
                continue
            sections.extend(self._load_sections_from_file(path))
        self.sections = sections

    def list_titles(self):
        return [s.title for s in self.sections]

    def get_sections_by_titles(self, titles):
        title_set = set(titles or [])
        return [s for s in self.sections if s.title in title_set]

    def lexical_search(self, query, top_k=3):
        """선택기 LLM 이 빈손이면 쓰는 문자열 폴백 검색."""
        if not query:
            return []
        q = normalize_text(query)
        hits = []
        for section in self.sections:
            if q in normalize_text(section.title) or q in normalize_text(section.content):
                hits.append({
                    "title": section.title,
                    "content": section.content,
                    "start_line": section.start_line,
                    "source_file": section.source_file,
                })
                if len(hits) >= top_k:
                    break
        return hits


class KtasSectionSelector:
    """증상 → 규정집 섹션 제목 top-k 를 LLM 으로 선택."""

    def __init__(self):
        base_url, self.model = config.ktas_selector_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def select_titles(self, symptom, titles, top_k=3):
        if not titles:
            return []
        skill_text = load_selector_skill_text("ktas")
        titles_text = "\n".join([f"- {t}" for t in titles])
        system_prompt = f"""
당신은 KTAS 섹션 선택기입니다.
증상과 가장 관련된 섹션 제목을 아래 목록에서만 선택하세요.

[섹션 제목 목록]
{titles_text}

[규칙]
1. 반드시 목록에 있는 제목만 고르세요.
2. 최대 {top_k}개까지 선택하세요.
3. JSON only로 출력하세요.

[출력 형식 (JSON Only)]
{{ "titles": ["제목1", "제목2"] }}

[스킬 참고]
{skill_text}
"""
        user_content = f"증상: {symptom}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        res = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.0)
        content = res.choices[0].message.content.strip()
        try:
            return safe_json_parse(content).get("titles", [])
        except Exception:
            retry_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "JSON만 다시 출력하세요. 다른 문장은 포함하지 마세요."},
            ]
            retry_res = self.client.chat.completions.create(
                model=self.model, messages=retry_messages, temperature=1.0
            )
            return safe_json_parse(retry_res.choices[0].message.content.strip()).get("titles", [])


def _parse_section_details(content):
    """섹션 본문을 '활력징후/그 밖의 1차/증상별 2차 고려사항' 그룹별 등급 라인으로 파싱."""
    categories = {
        "활력징후 1 차 고려사항": [],
        "그 밖의 1 차 고려사항": [],
        "증상별 2 차 고려사항": [],
        "other": [],
    }
    current = "other"
    for line in content.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if "활력징후 1 차 고려사항" in line_stripped:
            current = "활력징후 1 차 고려사항"
            continue
        if "그 밖의 1 차 고려사항" in line_stripped:
            current = "그 밖의 1 차 고려사항"
            continue
        if "증상별 2 차 고려사항" in line_stripped:
            current = "증상별 2 차 고려사항"
            continue
        match = re.match(r"^\s*(\d)\s*[:\).]?\s*(.+)", line_stripped)
        if match:
            categories[current].append({"level": match.group(1), "text": match.group(2).strip()})
    return categories


def build_checklist_from_sections(sections, max_items=20):
    """섹션 리스트(dict)에서 (등급, 항목, 질병명) 평면 체크리스트를 생성."""
    checklist = []
    seen = set()
    for section in sections:
        content = section.get("content") or ""
        title = section.get("title") or ""
        disease_name = title.split(" - ", 1)[-1].strip() if " - " in title else title
        categories = _parse_section_details(content)
        for cat_label, items in categories.items():
            for item in items:
                level = item.get("level")
                text = item.get("text")
                if not level or not text:
                    continue
                key = (cat_label, level, text)
                if key in seen:
                    continue
                seen.add(key)
                checklist.append({
                    "level": level,
                    "text": text,
                    "source": title,
                    "disease": disease_name,
                    "category": cat_label,
                })
                if len(checklist) >= max_items:
                    return checklist
    return checklist


def build_checklist_by_section(sections):
    """섹션 제목 → 해당 섹션 체크리스트 매핑(섹션랭크 선택용)."""
    section_map = {}
    for section in sections:
        title = section.get("title") or ""
        section_map[title] = build_checklist_from_sections([section], max_items=200)
    return section_map
