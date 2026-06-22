"""Vector RAG 데이터 관리자 — PDF 임베딩 검색 + 병원 DB.

캐시(ems_cache.pkl)가 있으면 그대로 로드(PDF 불필요). 없으면 PROTOCOL_PDF에서
페이지 텍스트를 추출·임베딩해 캐시를 생성한다. 캐시는 plain dict/numpy 라 이식 가능.
"""

import json
import math
import os
import pickle

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from . import config


class DataManager:
    def __init__(self):
        print("\n[Server] DataManager 초기화 (Vector RAG)...")
        self.current_pos = {"lat": 37.4979, "lon": 127.0276}
        self.embedding_model = None
        self.embedding_model_id = config.EMBEDDING_MODEL_ID
        self._load_hospital_db(config.HOSPITAL_DB)
        self.knowledge_base = self._build_or_load_vector_db()

    def _load_hospital_db(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.hospital_db = json.load(f)
            print(f"[Server] 병원 {len(self.hospital_db)}곳 데이터 로드 완료.")
        else:
            print(f"[Warning] 병원 데이터 파일 없음: {path}")
            self.hospital_db = []

    def _get_embedder(self):
        if self.embedding_model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[Server] 임베딩 모델 로드 중 ({self.embedding_model_id})...")
            self.embedding_model = SentenceTransformer(self.embedding_model_id)
        return self.embedding_model

    def _load_pdf(self, path):
        docs = []
        if not os.path.exists(path):
            print(f"[Warning] PDF 파일 없음: {path}")
            return docs
        from pypdf import PdfReader
        print(f"   └─ PDF 페이지 추출 중: {path}")
        for i, page in enumerate(PdfReader(path).pages):
            txt = page.extract_text()
            if txt and len(txt) > 50:
                docs.append({"source": os.path.basename(path), "page": i + 1, "content": txt})
        return docs

    def _build_or_load_vector_db(self):
        if os.path.exists(config.CACHE_PATH):
            print(f"[Server] 캐시된 벡터 DB 로드: {config.CACHE_PATH}")
            try:
                with open(config.CACHE_PATH, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"[Server] 캐시 로드 실패, 재구축: {e}")

        docs = self._load_pdf(config.PROTOCOL_PDF)
        texts = [d["content"] for d in docs]
        embs = self._get_embedder().encode(texts, show_progress_bar=True, batch_size=16) if texts else np.array([])
        db = {"docs": docs, "embs": embs}
        with open(config.CACHE_PATH, "wb") as f:
            pickle.dump(db, f)
        print(f"[Server] 벡터 DB 구축 완료 ({len(docs)} docs).")
        return db

    def search_knowledge(self, query, top_k=3, min_score=0.3):
        embs = self.knowledge_base["embs"]
        if embs is None or len(embs) == 0:
            return []
        q_vec = self._get_embedder().encode([query])
        sims = cosine_similarity(q_vec, embs)[0]
        top = np.argsort(sims)[::-1][:top_k]
        return [self.knowledge_base["docs"][i] for i in top if sims[i] > min_score]

    def find_hospitals(self, dept):
        candidates = []
        for h in self.hospital_db:
            if any(dept in d or d in dept for d in h.get("dept", [])):
                dist = math.sqrt((h["lat"] - self.current_pos["lat"]) ** 2
                                 + (h["lon"] - self.current_pos["lon"]) ** 2) * 111
                candidates.append({**h, "dist_km": round(dist, 2)})
        candidates.sort(key=lambda x: x["dist_km"])
        return candidates[:3]
