# AI EMS Commander — mark1 (Vector RAG)

PDF 표준지침을 임베딩 검색해 관련 페이지를 가져오고, CRAG 필터 → 보고서 작성 →
CoVe 검증을 수행하는 버전. `archive/mark1` 의 배포용 박스화.

## 흐름
```
발화 → [Parser LLM] suspect / knowledge_query / hospital_dept
     → execute_ems_pipeline: 임베딩 검색 → 병원조회 → CRAG → Reader → CoVe
```

## 구조
```
ems_mark1/
├── pyproject.toml / run.sh / README.md
├── ems_mark1/
│   ├── utils.py    # 공용 JSON 파서
│   ├── config.py   # 경로/모델/포트 (env)
│   ├── data.py     # Vector DataManager (PDF 임베딩 + 병원)
│   ├── agents.py   # CRAG / Reader / Expert
│   ├── server.py   # execute_ems_pipeline 도구
│   └── cli.py      # Parser + 호출
└── data/
    ├── ems_cache.pkl    # 사전 임베딩 캐시(번들, 751 docs) — PDF 없이 동작
    └── hospitals.json
```

## 설치 / 실행
```bash
cd ems_mark1 && uv venv && source .venv/bin/activate
uv pip install -e .
./run.sh server     # MCP 서버 (8080)
./run.sh cli        # 대화형 클라이언트 (별도 터미널)
```
OpenAI 호환 LLM 서버 필요(vLLM 등). 기본 포트/모델은 `config.py` 참고,
모든 역할은 `CMD/EVAL/READER/EXPERT_BASE_URL`·`*_MODEL` env로 오버라이드.

## 데이터
- 임베딩 캐시(`ems_cache.pkl`)가 번들돼 있어 **PDF 없이 즉시 동작**한다.
- 캐시를 다시 만들려면 원본 PDF 경로를 `PROTOCOL_PDF` 로 지정 후 캐시를 지우면 된다.
- 임베딩 모델(`jhgan/ko-sbert-sts`)은 질의 인코딩에 필요하므로 첫 실행 시 1회 다운로드된다.
