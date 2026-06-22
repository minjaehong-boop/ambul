"""mark1 배포 설정 — 경로/모델/포트 단일 지점 (env 오버라이드)."""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BOX_ROOT = os.path.dirname(PACKAGE_DIR)
DATA_DIR = os.getenv("EMS_DATA_DIR", os.path.join(BOX_ROOT, "data"))

# --- 데이터 경로 ---
# 벡터 캐시(번들). 존재하면 PDF 없이도 동작한다.
CACHE_PATH = os.getenv("EMS_CACHE", os.path.join(DATA_DIR, "ems_cache.pkl"))
HOSPITAL_DB = os.getenv("HOSPITAL_DB", os.path.join(DATA_DIR, "hospitals.json"))
# 캐시 재빌드용 원본 PDF (용량이 커서 기본 번들 제외 — 필요 시 경로 지정)
PROTOCOL_PDF = os.getenv("PROTOCOL_PDF", os.path.join(DATA_DIR, "guideline.pdf"))
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "jhgan/ko-sbert-sts")

# --- 서버/데모 포트 ---
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", f"http://localhost:{MCP_PORT}/sse")

API_KEY = os.getenv("EMS_API_KEY", "EMPTY")


def _endpoint(base_default, model_default, base_env, model_env):
    return os.getenv(base_env, base_default), os.getenv(model_env, model_default)


def commander_endpoint():
    """Parser/Commander LLM (의심질환·검색질의·진료과 추출)."""
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "CMD_BASE_URL", "CMD_MODEL")


def evaluator_endpoint():
    """CRAG 적합성 평가 LLM."""
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "EVAL_BASE_URL", "EVAL_MODEL")


def reader_endpoint():
    """보고서 작성 LLM."""
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "READER_BASE_URL", "READER_MODEL")


def expert_endpoint():
    """CoVe 의학 검증 LLM."""
    return _endpoint("http://localhost:8001/v1", "unsloth/medgemma-4b-it-unsloth-bnb-4bit",
                     "EXPERT_BASE_URL", "EXPERT_MODEL")
