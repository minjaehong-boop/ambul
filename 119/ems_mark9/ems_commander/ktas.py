"""KTAS 규정집 임베딩 검색 + 체크리스트 생성.

- KtasEmbeddingStore: 규정집을 "### " 헤더로 섹션 분할 → 임베딩 캐시 → 유사도/문자열 검색
- _parse_section_details / build_checklist_from_sections: 섹션 본문에서 등급 라인 추출

캐시는 plain dict/numpy 만 저장한다(커스텀 클래스 비의존 → 다른 환경/패키지에서도 이식 가능).
"""

import os
import pickle
import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from . import config
from .utils import normalize_text


class KtasEmbeddingStore:
    def __init__(self, guideline_path=None, model_id=None, cache_path=None):
        self.guideline_path = guideline_path or config.KTAS_GUIDELINE_PATH
        self.model_id = model_id or config.KTAS_EMBEDDING_MODEL_ID
        self.cache_path = cache_path or config.KTAS_EMBED_CACHE
        self.embedder = None
        self.docs = []          # list[dict]: {"title","content","start_line"}
        self.embs = None
        self._build_or_load()

    def _get_embedder(self):
        # SentenceTransformer 는 무거우므로 실제 임베딩이 필요할 때만 로드한다.
        if self.embedder is None:
            from sentence_transformers import SentenceTransformer
            print(f"[Server] KTAS 임베딩 모델 로드 중 ({self.model_id})...")
            self.embedder = SentenceTransformer(self.model_id)
        return self.embedder

    def _load_sections(self):
        if not os.path.exists(self.guideline_path):
            raise FileNotFoundError(f"guideline not found: {self.guideline_path}")
        with open(self.guideline_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        sections = []
        current_title = None
        current_start = None
        current_lines = []

        def flush_section():
            if current_title and current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) > 30:
                    sections.append({
                        "title": current_title,
                        "content": content,
                        "start_line": current_start,
                    })

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

    def _build_or_load(self):
        source_mtime = os.path.getmtime(self.guideline_path) if os.path.exists(self.guideline_path) else None
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    payload = pickle.load(f)
                if (payload.get("model_id") == self.model_id
                        and payload.get("source_mtime") == source_mtime):
                    self.docs = payload.get("docs", [])
                    self.embs = payload.get("embs")
                    return
            except Exception:
                pass  # 캐시 손상/불일치 → 재구축

        sections = self._load_sections()
        texts = [s["content"] for s in sections]
        embs = self._get_embedder().encode(texts, show_progress_bar=True, batch_size=16) if texts else np.array([])

        self.docs = sections
        self.embs = embs
        with open(self.cache_path, "wb") as f:
            pickle.dump({
                "model_id": self.model_id,
                "source_mtime": source_mtime,
                "docs": self.docs,
                "embs": self.embs,
            }, f)

    def search(self, query, top_k=3, min_score=0.25):
        if not query or self.embs is None or len(self.docs) == 0:
            return []
        q_vec = self._get_embedder().encode([query])
        sims = cosine_similarity(q_vec, self.embs)[0]
        top_indices = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if sims[idx] >= min_score:
                d = self.docs[idx]
                results.append({
                    "title": d["title"],
                    "content": d["content"],
                    "start_line": d["start_line"],
                    "score": float(sims[idx]),
                })
        return results

    def lexical_search(self, query, top_k=3):
        if not query:
            return []
        q = normalize_text(query)
        hits = []
        for d in self.docs:
            if q in normalize_text(d["title"]) or q in normalize_text(d["content"]):
                hits.append({
                    "title": d["title"],
                    "content": d["content"],
                    "start_line": d["start_line"],
                    "score": 1.0,
                })
                if len(hits) >= top_k:
                    break
        return hits


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
    """임베딩 매칭 섹션들에서 (등급, 항목, 질병명) 체크리스트를 생성."""
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
