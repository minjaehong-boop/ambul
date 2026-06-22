# AI EMS Commander (배포판)

LLM 기반 119 구급대원 현장 처치 보조 시스템. 구급대원 발화에서 활력징후·증상을
추출하고, KTAS 규정집 임베딩 검색으로 체크리스트를 제시한 뒤, 사용자가 등급/질환을
선택하면 표준 처치지침을 검색·요약·검증해 현장 보고서를 생성한다.

## 구조

```
ems_commander/
├── pyproject.toml          # 패키지 메타 + 의존성 + 콘솔 스크립트
├── run.sh                  # 실행 런처 (server | cli | http)
├── README.md
├── ems_commander/          # 파이썬 패키지
│   ├── utils.py            # 공용 헬퍼(JSON/텍스트 파서) — 중복 제거 지점
│   ├── config.py           # 경로/모델/포트 단일 설정 (env 오버라이드)
│   ├── data.py             # DataManager — 지침 파일 직접 접근
│   ├── ktas.py             # KTAS 임베딩 스토어 + 체크리스트 생성
│   ├── agents.py           # Selector / CRAG / Reader / Expert LLM 에이전트
│   ├── server.py           # MCP 서버 + 파이프라인 (run_pipeline 도구)
│   └── cli.py              # 대화형 CLI + HTTP 데모
├── resources/
│   ├── protocol_index2.json   # 지침 키워드 목록(Selector 입력)
│   └── demo.html              # 웹 데모 UI
└── data/
    ├── protocols/*.md         # 표준 처치지침 코퍼스(64개)
    ├── ktas/2021_KTAS_guideline.md
    └── ktas_embedding_cache.pkl   # 사전 계산 임베딩 캐시
```

## 파이프라인 흐름

```
발화 → [Parser LLM] params 추출
     → [run_pipeline] pre-KTAS 임베딩 검색 → 체크리스트(need_choice)
     → 사용자 등급/질환 선택
     → [run_pipeline+choice] Selector → 지침 로드 → CRAG → Reader → CoVe → 보고서(complete)
```

## 설치

```bash
cd ems_commander
uv venv && source .venv/bin/activate     # 또는 python -m venv .venv
uv pip install -e .                        # 콘솔 스크립트 ems-server / ems-cli 등록
```

## 사전 조건 — LLM 서버

OpenAI 호환 엔드포인트(vLLM 권장)가 필요하다. 기본 포트/모델은 `config.py` 참고.
가장 간단하게는 **단일 모델 서버를 띄우고 모든 역할을 그쪽으로** 환경변수로 묶으면 된다:

```bash
# 예: 단일 vLLM 서버(8000)로 모든 단계 통일
export CMD_BASE_URL=http://localhost:8000/v1   CMD_MODEL=<model>
export SELECT_BASE_URL=$CMD_BASE_URL SELECT_MODEL=$CMD_MODEL
export EVAL_BASE_URL=$CMD_BASE_URL   EVAL_MODEL=$CMD_MODEL
export READER_BASE_URL=$CMD_BASE_URL READER_MODEL=$CMD_MODEL
export EXPERT_BASE_URL=$CMD_BASE_URL EXPERT_MODEL=$CMD_MODEL
```

## 실행

```bash
./run.sh server      # 1) MCP 서버 (port 8080)
./run.sh cli         # 2) 대화형 클라이언트 (별도 터미널)
./run.sh http        # 또는 HTTP 데모 서버 (port 8090, demo.html)
```

콘솔 스크립트로도 가능: `ems-server`, `ems-cli`, `ems-cli --http`.

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `CMD_BASE_URL` / `CMD_MODEL` | `http://localhost:8000/v1` / EXAONE 7.8B | Parser/Commander |
| `SELECT_BASE_URL` / `SELECT_MODEL` | CMD 폴백 / EXAONE 2.4B | 지침 선정 |
| `EVAL_BASE_URL` / `EVAL_MODEL` | `:8002` / EXAONE 2.4B | CRAG 평가 |
| `READER_BASE_URL` / `READER_MODEL` | `:8002` / EXAONE 2.4B | 보고서 작성 |
| `EXPERT_BASE_URL` / `EXPERT_MODEL` | `:8001` / MedGemma 4B | CoVe 검증 |
| `PROTOCOL_DIR` | `data/protocols` | 지침 코퍼스 경로 |
| `KTAS_GUIDELINE_PATH` | `data/ktas/2021_KTAS_guideline.md` | KTAS 규정집 |
| `KTAS_EMBED_CACHE` | `data/ktas_embedding_cache.pkl` | 임베딩 캐시 |
| `KTAS_EMBEDDING_MODEL_ID` | `jhgan/ko-sbert-sts` | 임베딩 모델 |
| `MCP_PORT` / `HTTP_DEMO_PORT` | `8080` / `8090` | 서버 포트 |

> 임베딩 캐시는 규정집 mtime/모델ID가 바뀌면 자동 재생성된다(첫 실행 시 임베딩 모델 다운로드).
