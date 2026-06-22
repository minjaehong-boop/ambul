"""mark2 배포 설정 — 경로/모델/포트 단일 지점 (env 오버라이드).

MAX_CONTEXT_CHARS: 지침서 전문은 매우 길어(수십만 토큰) 컨텍스트를 초과하므로,
system 프롬프트에 넣기 전 이 길이로 절단한다. 기본값은 4096 컨텍스트 서버 기준으로 보수적.
"""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BOX_ROOT = os.path.dirname(PACKAGE_DIR)
DATA_DIR = os.getenv("EMS_DATA_DIR", os.path.join(BOX_ROOT, "data"))

# --- 데이터 경로 ---
GUIDELINE_PATH = os.getenv("GUIDELINE_PATH", os.path.join(DATA_DIR, "guideline.md"))
HOSPITAL_DB = os.getenv("HOSPITAL_DB", os.path.join(DATA_DIR, "hospitals.json"))
# 전문 주입 절단 길이(문자). 컨텍스트가 큰 서버면 늘려도 된다.
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "3000"))

# --- 서버 포트 ---
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", f"http://localhost:{MCP_PORT}/sse")

API_KEY = os.getenv("EMS_API_KEY", "EMPTY")


def _endpoint(base_default, model_default, base_env, model_env):
    return os.getenv(base_env, base_default), os.getenv(model_env, model_default)


def commander_endpoint():
    """Parser + CRAG + Reader 공용 LLM."""
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "CMD_BASE_URL", "CMD_MODEL")


def expert_endpoint():
    """CoVe 의학 검증 LLM."""
    return _endpoint("http://localhost:8001/v1", "unsloth/medgemma-4b-it-unsloth-bnb-4bit",
                     "EXPERT_BASE_URL", "EXPERT_MODEL")
