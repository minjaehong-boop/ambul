"""mark4 배포 설정 — 경로/모델/포트 단일 지점 (env 오버라이드)."""

import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BOX_ROOT = os.path.dirname(PACKAGE_DIR)
DATA_DIR = os.getenv("EMS_DATA_DIR", os.path.join(BOX_ROOT, "data"))
RESOURCES_DIR = os.getenv("EMS_RESOURCES_DIR", os.path.join(BOX_ROOT, "resources"))

# --- 데이터/리소스 경로 (병원 DB 없음) ---
PROTOCOL_DIR = os.getenv("PROTOCOL_DIR", os.path.join(DATA_DIR, "protocols"))
PROTOCOL_INDEX = os.getenv("PROTOCOL_INDEX", os.path.join(RESOURCES_DIR, "protocol_index.json"))

# --- 서버 포트 ---
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", f"http://localhost:{MCP_PORT}/sse")

API_KEY = os.getenv("EMS_API_KEY", "EMPTY")


def _endpoint(base_default, model_default, base_env, model_env):
    return os.getenv(base_env, base_default), os.getenv(model_env, model_default)


def commander_endpoint():
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "CMD_BASE_URL", "CMD_MODEL")


def evaluator_endpoint():
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "EVAL_BASE_URL", "EVAL_MODEL")


def reader_endpoint():
    return _endpoint("http://localhost:8000/v1", "cyankiwi/Qwen3-4B-Instruct-2507-AWQ-4bit",
                     "READER_BASE_URL", "READER_MODEL")


def expert_endpoint():
    return _endpoint("http://localhost:8001/v1", "unsloth/medgemma-4b-it-unsloth-bnb-4bit",
                     "EXPERT_BASE_URL", "EXPERT_MODEL")
