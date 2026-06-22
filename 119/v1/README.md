# Triage RAG — NVIDIA Framework Edition (v1)

한국어 응급의료 Triage RAG 시스템 — **NVIDIA GenerativeAIExamples 프레임워크**(`RAG/src/chain_server`) 슬라이스 위에서 동작. 질의를 KTAS/Protocol 두 서브쿼리로 분해한 뒤, 각 도메인별로 Milvus 임베딩 top-k 를 뽑고 vLLM `/v1/rerank` 로 리랭킹, 문서·대화이력·메타 3-경로 컨텍스트를 합쳐 답변을 생성합니다.


## 파이프라인 개요

1. 사용자 질의를 KTAS/Protocol sub-query 로 분해 (`decompose`)
2. 도메인별 병렬:
   - 문서(`ktas_db` / `protocol_db`) + 대화이력(`triage_conv`) + 메타(`triage_meta`) 세 Milvus 컬렉션에서 embed top-20
   - vLLM `/v1/rerank` 로 각 경로 리랭킹 → top-3 선정
   - 도메인 답변 생성
3. KTAS/Protocol 답변 합성 (`synthesize`)
4. 대화/메타정보를 Milvus 에 영속화 (`persist`)

구현은 `RAG/examples/advanced_rag/triage_rag/chains.py` 의 `TriageChatbot`(BaseExample 구현), 프롬프트는 같은 디렉터리의 `prompt.yaml` 에 정의됩니다.

## 실행

```bash
# 1. 의존성 설치 (Python >= 3.10)
pip install -r requirements.txt

# 2. 백엔드 서비스 기동 (별도)
#    - Milvus (기본 localhost:19530) — 컬렉션: ktas_db, protocol_db, triage_conv, triage_meta
#    - vLLM/OpenAI 호환 LLM 서버 (+ /v1/rerank 엔드포인트)
#    - 임베딩 서버 (sentence-transformers 또는 NIM)

# 3. API 서버 (기본 포트 8081)
./run.sh
# 또는 포트 지정:
./run.sh 9000
# 또는 수동:
#   EXAMPLE_PATH=advanced_rag/triage_rag PYTHONPATH="$(pwd)" \
#   python -m uvicorn RAG.src.chain_server.server:app --host 0.0.0.0 --port 8081
```

`chain_server/server.py` 가 cwd 기준 `RAG/examples/$EXAMPLE_PATH/` 를 스캔해 `BaseExample` 구현체를 자동 로드하므로, 반드시 v1 루트를 cwd 로 하고 실행해야 합니다 (`run.sh` 가 처리).

### 환경 변수

NVIDIA 프레임워크의 `configuration_wizard` 가 `APP_` 프리픽스 환경변수를 YAML 설정으로 매핑합니다 (v2 와 달리 키 사이에 `_` 가 없는 평탄한 이름 규약).

| 변수 | 기본값 | 설명 |
|---|---|---|
| `APP_LLM_SERVERURL` | — | vLLM/OpenAI 호환 LLM 서버 URL |
| `APP_LLM_MODELNAME` | — | 모델명 |
| `APP_EMBEDDINGS_SERVERURL` | — | 임베딩 서버 URL |
| `APP_EMBEDDINGS_MODELNAME` | — | 임베딩 모델명 |
| `APP_VECTORSTORE_URL` | `http://localhost:19530` | Milvus URL |
| `APP_VECTORSTORE_NAME` | `milvus` | 벡터스토어 종류 |
| `APP_RANKING_SERVERURL` | — | rerank 엔드포인트 (vLLM `/v1/rerank`) |
| `APP_RANKING_MODELNAME` | — | rerank 모델명 |
| `EXAMPLE_PATH` | `advanced_rag/triage_rag` | 로드할 예제 상대경로 |
| `APP_CONFIG_FILE` | 미설정 | YAML 설정 파일 (선택) |
| `PORT` | `8081` | API 서버 포트 |
| `LOGLEVEL` | `INFO` | 로그 레벨 |

### API 예시

```bash
# Health
curl http://localhost:8081/health

# Streaming generate
curl -N -X POST http://localhost:8081/generate \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "60대 남성, 흉통과 식은땀, 혈압 80/50"}],
        "use_knowledge_base": true,
        "session_id": "test-001"
      }'
```

## 디렉터리 구조

```
v1/
├── run.sh                                  # uvicorn 런처 (cwd 고정 + EXAMPLE_PATH 세팅)
├── requirements.txt                        # 최소 의존성 (업스트림 엄격핀은 RAG/src/chain_server/requirements.txt)
├── README.md
└── RAG/
    ├── src/chain_server/                   # FastAPI 서버 + Base/utils/tracing
    │   ├── server.py                       # EXAMPLE_PATH 기반 동적 로더
    │   ├── base.py                         # BaseExample 추상 클래스
    │   ├── utils.py                        # LLM/embed/vectorstore 팩토리
    │   ├── configuration_wizard.py         # YAML + env var 설정
    │   ├── tracing.py                      # OpenTelemetry (선택)
    │   └── requirements.txt                # 업스트림 엄격핀 (참고용)
    ├── tools/observability/                # langchain + llamaindex tracing 래퍼
    └── examples/advanced_rag/triage_rag/
        ├── chains.py                       # TriageChatbot (이 예제의 핵심)
        └── prompt.yaml                     # decompose/synthesize/rerank 프롬프트
```

## 주의

- v2(PageIndex)PDF 아티팩트를 번들하지 않습니다. Milvus 컬렉션이 외부에 미리 구축되어 있어야 합니다.
- 자체 `playground/` UI 가 없습니다 — UI 가 필요하면 v2 의 playground 를 그대로 가리켜 써도 무방합니다.
- `ingest_docs()` 는 NVIDIA 프레임워크 BaseExample 규약에 따라 구현되어 있으나, 업스트림 컬렉션 스키마에 의존하므로 운영 환경에 맞춰 별도 점검이 필요합니다.
- `APP_*` 환경변수 명명규약이 v2 와 다릅니다 (v1: `APP_LLM_SERVERURL`, v2: `APP_LLM_SERVER_URL`).
