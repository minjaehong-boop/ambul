"""Long-Context 데이터 관리자 — 지침서 전문을 통째로 로드 + 병원 DB.

.md(텍스트) 또는 .pdf(바이너리, pypdf 추출) 모두 지원한다.
"""

import json
import math
import os

from . import config


class DataManager:
    def __init__(self):
        print("\n[Server] DataManager (Long-Context) 초기화...")
        self.current_pos = {"lat": 37.4979, "lon": 127.0276}
        self.hospital_db = self._load_hospitals(config.HOSPITAL_DB)
        self.full_text = self._load_guideline(config.GUIDELINE_PATH)

    def _load_hospitals(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                db = json.load(f)
            print(f"[Server] 병원 {len(db)}곳 데이터 로드 완료.")
            return db
        print(f"[Warning] 병원 데이터 파일 없음: {path}")
        return []

    def _load_guideline(self, path):
        if not os.path.exists(path):
            print(f"[Warning] 지침서 파일 없음: {path}")
            return ""
        print(f"[Server] 지침서 로드 시도: {path}")
        try:
            if path.lower().endswith(".pdf"):
                from pypdf import PdfReader
                content = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            print(f"   └─ 지침서 로드 완료 (길이: {len(content)}자)")
            return content
        except Exception as e:
            print(f"   ❌ 로드 실패: {e}")
            return ""

    def get_full_text(self):
        return self.full_text

    def find_hospitals(self, dept, max_results=3):
        candidates = []
        for h in self.hospital_db:
            depts = h.get("dept") or h.get("departments") or []
            if any(dept in d or d in dept for d in depts):
                dist = math.sqrt((h["lat"] - self.current_pos["lat"]) ** 2
                                 + (h["lon"] - self.current_pos["lon"]) ** 2) * 111
                candidates.append({**h, "dist_km": round(dist, 2)})
        candidates.sort(key=lambda x: x["dist_km"])
        return candidates[:max_results]
