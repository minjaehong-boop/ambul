"""배포 설정 단일 지점 — 경로/모델/포트를 환경변수로 오버라이드한다.

기본값은 박스(이 패키지의 상위 폴더)에 번들된 data/ resources/ 를 가리킨다.
다른 곳에 배포할 때는 아래 env 만 바꾸면 된다.

mark10 은 KTAS 단계가 임베딩 검색이 아니라 'LLM 섹션 선택기'(prototype 방식)이므로
KTAS 임베딩 모델 대신 KTAS_BASE_URL / KTAS_MODEL(섹션 선택 LLM)을 사용한다.
"""

import glob
import os

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
BOX_ROOT = os.path.dirname(PACKAGE_DIR)

DATA_DIR = os.getenv("EMS_DATA_DIR", os.path.join(BOX_ROOT, "data"))
RESOURCES_DIR = os.getenv("EMS_RESOURCES_DIR", os.path.join(BOX_ROOT, "resources"))

# --- 데이터/리소스 경로 ---
PROTOCOL_DIR = os.getenv("PROTOCOL_DIR", os.path.join(DATA_DIR, "protocols"))
KTAS_GUIDELINE_DIR = os.getenv("KTAS_GUIDELINE_DIR", os.path.join(DATA_DIR, "ktas"))
PROTOCOL_INDEX = os.getenv("PROTOCOL_INDEX", os.path.join(RESOURCES_DIR, "protocol_index2.json"))
DEMO_HTML = os.getenv("DEMO_HTML", os.path.join(RESOURCES_DIR, "demo.html"))

# 선택기 스킬 텍스트(SKILL.md / references/examples.md) 위치. 없으면 조용히 빈 문자열.
SKILL_BASE = os.getenv("SKILL_BASE", os.path.join(RESOURCES_DIR, "ktas-selectors"))

# --- 서버/데모 포트 ---
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_SSE_URL = os.getenv("MCP_SSE_URL", f"http://localhost:{MCP_PORT}/sse")
HTTP_DEMO_HOST = os.getenv("HTTP_DEMO_HOST", "0.0.0.0")
HTTP_DEMO_PORT = int(os.getenv("HTTP_DEMO_PORT", "8090"))

API_KEY = os.getenv("EMS_API_KEY", "mcp")


def ktas_guideline_paths():
    """KTAS 규정집 파일 경로 목록을 결정한다.

    우선순위:
      1) KTAS_GUIDELINE_PATHS (콤마 구분 다중 경로)
      2) KTAS_GUIDELINE_DIR 안의 모든 *.md (정렬)
      3) KTAS_GUIDELINE_PATH (단일 파일)
    """
    env_paths = os.getenv("KTAS_GUIDELINE_PATHS")
    if env_paths:
        return [p.strip() for p in env_paths.split(",") if p.strip()]

    if os.path.isdir(KTAS_GUIDELINE_DIR):
        md = sorted(glob.glob(os.path.join(KTAS_GUIDELINE_DIR, "*.md")))
        if md:
            return md

    return [os.getenv("KTAS_GUIDELINE_PATH", os.path.join(KTAS_GUIDELINE_DIR, "2021_KTAS_guideline.md"))]


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
        "http://localhost:8000/v1", "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct-AWQ",
        "CMD_BASE_URL", "CMD_MODEL",
    )


def selector_endpoint():
    """지침 키워드 선정 LLM. 미지정 시 Commander 설정을 폴백으로 사용."""
    return _endpoint(
        "http://localhost:8000/v1", "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct-AWQ",
        "SELECT_BASE_URL", "SELECT_MODEL", "CMD_BASE_URL", "CMD_MODEL",
    )


def evaluator_endpoint():
    """CRAG 적합성 평가 LLM."""
    return _endpoint(
        "http://localhost:8002/v1", "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct-AWQ",
        "EVAL_BASE_URL", "EVAL_MODEL",
    )


def reader_endpoint():
    """보고서 작성 LLM."""
    return _endpoint(
        "http://localhost:8002/v1", "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct-AWQ",
        "READER_BASE_URL", "READER_MODEL",
    )


def expert_endpoint():
    """CoVe 의학 검증 LLM."""
    return _endpoint(
        "http://localhost:8001/v1", "unsloth/medgemma-4b-it-unsloth-bnb-4bit",
        "EXPERT_BASE_URL", "EXPERT_MODEL",
    )


def ktas_selector_endpoint():
    """KTAS 섹션 선택 LLM. 미지정 시 Selector → Commander 순으로 폴백."""
    base = os.getenv("KTAS_BASE_URL") or os.getenv("SELECT_BASE_URL") or os.getenv("CMD_BASE_URL")
    base = base or "http://localhost:8001/v1"
    model = os.getenv("KTAS_MODEL", "unsloth/medgemma-4b-it-unsloth-bnb-4bit")
    return base, model
