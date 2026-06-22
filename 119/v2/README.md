# Triage RAG — PageIndex Edition (v2)

한국어 응급의료 Triage RAG 시스템 — **PageIndex 파이프라인**(구조 기반 2단계 선택, 결정적 경로). KTAS 규정집과 표준처치지침 PDF에서 관련 섹션을 LLM이 직접 선택하고, 선택된 페이지를 `pdfplumber`로 읽어 답변을 생성합니다.


## 파이프라인 개요

1. 사용자 질의를 KTAS/Protocol sub-query로 분해(`_decompose`)
2. 도메인별 병렬(`ThreadPoolExecutor`):
   - `chapter_select` → `section_select` → `fetch_pages` → `generate`
3. KTAS/Protocol 답변 합성(`synthesis`)
4. 의학적 자기검증(`self_correction`)
5. SSE 스트리밍 응답

각 단계는 `triage_rag_pageindex/chains.py`에서 구현되고, 프롬프트는 `config/prompt/pageindex_prompt.yaml`에서 정의됩니다.

## 실행

```bash
# 1. 의존성 설치 (Python >= 3.10)
pip install -r requirements.txt

# 2. vLLM/OpenAI 호환 LLM 서버 기동 (기본 http://localhost:8002/v1, config.yaml 참조)

# 3. API 서버 (기본 포트 8082)
./run.sh server
# 또는 수동:
#   EXAMPLE_TYPE=pageindex PAGEINDEX_ROOT="$(pwd)/artifacts" \
#   APP_CONFIG_FILE="$(pwd)/config.yaml" PORT=8082 python server.py

# 4. Playground UI (별도 포트)
./run.sh ui 3000
```

### 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `APP_LLM_SERVER_URL` | `http://localhost:8002/v1` (config.yaml) | LLM 서버 URL |
| `APP_LLM_MODEL_NAME` | `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` (config.yaml) | 모델명 |
| `PAGEINDEX_ROOT` | `./artifacts` (번들) | PDF + JSON 구조 파일 루트 |
| `APP_CONFIG_FILE` | `./config.yaml` | YAML 설정 파일 |
| `PORT` | `8082` | API 서버 포트 |
| `LOGLEVEL` | `INFO` | 로그 레벨 |
| `ENABLE_TRACING` | 미설정 | OpenTelemetry 트레이싱 활성화 |

### API 예시

```bash
# Health
curl http://localhost:8082/health

# Streaming generate (SSE)
curl -N -X POST http://localhost:8082/generate \
  -H "Content-Type: application/json" \
  -d '{
        "messages": [{"role": "user", "content": "60대 남성, 흉통과 식은땀, 혈압 80/50"}],
        "use_knowledge_base": true,
        "session_id": "test-001"
      }'
```

## 디렉터리 구조

```
v2/
├── server.py                 # FastAPI + SSE entrypoint (pageindex 고정)
├── run.sh                    # server/ui 런처
├── config.yaml               # LLM server_url / model_name 기본값
├── requirements.txt
├── chain_server/             # BaseExample, config wizard, tracing, utils
├── triage_rag_pageindex/     # PageIndex 파이프라인 구현 (chains.py)
├── config/
│   ├── prompt/pageindex_prompt.yaml
│   └── vllm/gemma-command.yaml
├── playground/               # 정적 UI + 소형 HTTP 서버
├── artifacts/                # ★ 사전 생성된 PageIndex 아티팩트 (번들)
│   ├── docs/{2021_KTAS_guideline.pdf, 표준지침_처치지침_알고리즘_테스트_최종.pdf}
│   └── results/{...}_structure.json
├── CLAUDE.md                 # 기존 업스트림 Claude 가이드
└── PROVENANCE.md             # 스냅샷 출처 및 수정 내역
```
