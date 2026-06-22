# AI EMS Commander (mark10)

LLM 기반 119 구급대원 현장 처치 보조 시스템. 구급대원 발화에서 활력징후·증상을
추출하고, **KTAS 규정집 섹션을 LLM 선택기로 top-3 선정**해 1~3순위 체크리스트를
제시한 뒤, 사용자가 등급/질환을 선택하면 표준 처치지침을 검색·요약·검증해
현장 보고서를 생성한다.

> **mark9 와의 차이**: mark9 는 KTAS 단계를 임베딩 검색(top-1)으로 처리하지만, LLM 이 섹션 제목 top-3 를 고르고, 사용자는 `1-2`(순위-등급) / `2:호흡곤란`(순위:항목)형식으로 선택한다.

## 구조

```
ems_mark10/
├── pyproject.toml          # 패키지 메타 + 의존성 + 콘솔 스크립트
├── run.sh                  # 실행 런처 (server | cli | http)
├── README.md
├── ems_commander/          # 파이썬 패키지
│   ├── utils.py            # 공용 헬퍼(JSON/텍스트 파서)
│   ├── config.py           # 경로/모델/포트 단일 설정 (env 오버라이드)
│   ├── skills.py           # 선택기 스킬 텍스트 로더(선택, 없으면 무시)
│   ├── data.py             # DataManager — 지침 파일 직접 접근(파일시스템 스캔)
│   ├── ktas.py             # KtasSectionStore + KtasSectionSelector(LLM) + 체크리스트
│   ├── agents.py           # Selector / CRAG / Reader / Expert LLM 에이전트
│   ├── server.py           # MCP 서버 + 파이프라인 (run_pipeline, graphrag_search[선택])
│   └── cli.py              # 대화형 CLI + HTTP 데모
├── resources/
│   ├── protocol_index2.json   # 지침 키워드 목록(폴백용)
│   └── demo.html              # 웹 데모 UI
└── data/
    ├── protocols/*.md         # 표준 처치지침 코퍼스
    └── ktas/*.md              # KTAS 규정집(### 섹션 분할 대상, 여러 파일 가능)
```

## 파이프라인 흐름

```
발화 → [Parser LLM] params(활력징후/증상/특이사항) 추출
     → [run_pipeline] pre-KTAS: KtasSectionSelector(LLM) 섹션 top-3 → 1~3순위 체크리스트(need_choice)
     → 사용자 선택 (1-2 순위-등급 / 2:호흡곤란 순위:항목 / 등급숫자 / 항목텍스트)
     → [run_pipeline+choice] Selector → 지침 로드 → CRAG → Reader → CoVe → 보고서(complete)
```

## 설치

```bash
cd ems_mark10
uv venv && source .venv/bin/activate     # 또는 python -m venv .venv
uv pip install -e .                        # 콘솔 스크립트 ems-server / ems-cli 등록
```

## 사전 조건 — LLM 서버

OpenAI 호환 엔드포인트(vLLM 권장)가 필요하다. 기본 포트/모델은 `config.py` 참고.
가장 간단하게는 단일 모델 서버를 띄우고 모든 역할을 그쪽으로 묶으면 된다:

```bash
export CMD_BASE_URL=http://localhost:8000/v1   CMD_MODEL=<model>
export SELECT_BASE_URL=$CMD_BASE_URL SELECT_MODEL=$CMD_MODEL
export EVAL_BASE_URL=$CMD_BASE_URL   EVAL_MODEL=$CMD_MODEL
export READER_BASE_URL=$CMD_BASE_URL READER_MODEL=$CMD_MODEL
export EXPERT_BASE_URL=$CMD_BASE_URL EXPERT_MODEL=$CMD_MODEL
export KTAS_BASE_URL=$CMD_BASE_URL   KTAS_MODEL=$CMD_MODEL   # 섹션 선택 LLM
```

## 실행

```bash
./run.sh server      # 1) MCP 서버 (port 8080)
./run.sh cli         # 2) 대화형 클라이언트 (별도 터미널)
./run.sh http        # 또는 HTTP 데모 서버 (port 8090, demo.html)
```

콘솔 스크립트로도 가능: `ems-server`, `ems-cli`, `ems-cli --http`.
`선택 입력>` 프롬프트에서 `1-2`(순위-등급), `2:호흡곤란`(순위:항목), 또는 등급 숫자로 응답한다.

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `CMD_BASE_URL` / `CMD_MODEL` | `http://localhost:8000/v1` / EXAONE 2.4B | Parser/Commander |
| `SELECT_BASE_URL` / `SELECT_MODEL` | CMD 폴백 / EXAONE 7.8B | 지침 선정 |
| `EVAL_BASE_URL` / `EVAL_MODEL` | `:8002` / EXAONE 2.4B | CRAG 평가 |
| `READER_BASE_URL` / `READER_MODEL` | `:8002` / EXAONE 2.4B | 보고서 작성 |
| `EXPERT_BASE_URL` / `EXPERT_MODEL` | `:8001` / MedGemma 4B | CoVe 검증 |
| `KTAS_BASE_URL` / `KTAS_MODEL` | SELECT→CMD 폴백 / MedGemma 4B | **KTAS 섹션 선택 LLM** |
| `PROTOCOL_DIR` | `data/protocols` | 지침 코퍼스 경로 |
| `KTAS_GUIDELINE_DIR` | `data/ktas` | KTAS 규정집 디렉터리(*.md 전부 로드) |
| `KTAS_GUIDELINE_PATHS` | (없음) | 콤마 구분 다중 규정집 경로(우선) |
| `SKILL_BASE` | `resources/ktas-selectors` | 선택기 스킬 텍스트(없으면 무시) |
| `MCP_PORT` / `HTTP_DEMO_PORT` | `8080` / `8090` | 서버 포트 |

> KTAS 단계가 임베딩이 아니라 LLM 선택기이므로 임베딩 모델/캐시는 필요 없다.
> `graphrag_search` 도구는 `graphrag_local_vllm` 모듈이 호스트에 있을 때만 동작한다(선택).
