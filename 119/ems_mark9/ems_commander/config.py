"""배포 설정 단일 지점 — 경로/모델/포트를 환경변수로 오버라이드한다.

기본값은 박스(이 패키지의 상위 폴더)에 번들된 data/ resources/ 를 가리킨다.
다른 곳에 배포할 때는 아래 env 만 바꾸면 된다.
"""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BOX_ROOT = os.path.dirname(PACKAGE_DIR)

DATA_DIR = os.getenv("EMS_DATA_DIR", os.path.join(BOX_ROOT, "data"))
RESOURCES_DIR = os.getenv("EMS_RESOURCES_DIR", os.path.join(BOX_ROOT, "resources"))

# --- 데이터/리소스 경로 ---
PROTOCOL_DIR = os.getenv("PROTOCOL_DIR", os.path.join(DATA_DIR, "protocols"))
KTAS_GUIDELINE_PATH = os.getenv("KTAS_GUIDELINE_PATH", os.path.join(DATA_DIR, "ktas", "2021_KTAS_guideline.md"))
KTAS_EMBED_CACHE = os.getenv("KTAS_EMBED_CACHE", os.path.join(DATA_DIR, "ktas_embedding_cache.pkl"))
KTAS_EMBEDDING_MODEL_ID = os.getenv("KTAS_EMBEDDING_MODEL_ID", "jhgan/ko-sbert-sts")
PROTOCOL_INDEX = os.getenv("PROTOCOL_INDEX", os.path.join(RESOURCES_DIR, "protocol_index2.json"))
DEMO_HTML = os.getenv("DEMO_HTML", os.path.join(RESOURCES_DIR, "demo.html"))

# --- 서버/데모 포트 ---
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", f"http://localhost:{MCP_PORT}/sse")
HTTP_DEMO_HOST = os.getenv("HTTP_DEMO_HOST", "0.0.0.0")
HTTP_DEMO_PORT = int(os.getenv("HTTP_DEMO_PORT", "8090"))

API_KEY = os.getenv("EMS_API_KEY", "EMPTY")


def _endpoint(base_default, model_default, base_env, model_env,
              base_fallback_env=None, model_fallback_env=None):
    """역할별 (base_url, model) 결정. 명시 env > 폴백 env > 기본값."""
    base = os.getenv(base_env)
    if base is None and base_fallback_env:
        base = os.getenv(base_fallback_env)
    base = base or base_default

    model = os.getenv(model_env)
    if model is None and model_fallback_env:
        model = os.getenv(model_fallback_env)
    model = model or model_default

    return base, model


def commander_endpoint():
    """Parser/Commander LLM (활력징후·증상 추출)."""
    return _endpoint(
        "http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
        "CMD_BASE_URL", "CMD_MODEL",
    )


def selector_endpoint():
    """지침 키워드 선정 LLM. 미지정 시 Commander 설정을 폴백으로 사용."""
    return _endpoint(
        "http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
        "SELECT_BASE_URL", "SELECT_MODEL", "CMD_BASE_URL", "CMD_MODEL",
    )


def evaluator_endpoint():
    """CRAG 적합성 평가 LLM."""
    return _endpoint(
        "http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
        "EVAL_BASE_URL", "EVAL_MODEL",
    )


def reader_endpoint():
    """보고서 작성 LLM."""
    return _endpoint(
        "http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
        "READER_BASE_URL", "READER_MODEL",
    )


def expert_endpoint():
    """CoVe 의학 검증 LLM."""
    return _endpoint(
        "http://localhost:8001/v1", "unsloth/medgemma-4b-it-unsloth-bnb-4bit",
        "EXPERT_BASE_URL", "EXPERT_MODEL",
    )
