# AI EMS Commander — mark3 (Direct Access)

벡터 검색 없이, Commander가 지침 카테고리 목록을 보고 **필요한 지침 파일을 직접 지정**하면
그 파일을 읽어 CRAG → 보고서 → CoVe 로 처리하는 버전. `archive/mark3` 의 배포용 박스화.

## 흐름
```
발화 → [Parser LLM] suspect / target_files(지침 키워드) / hospital_dept
     → execute_ems_pipeline: 파일 직접 로드 → 병원조회 → CRAG → Reader → CoVe
```

## 구조
```
ems_mark3/
├── pyproject.toml / run.sh / README.md
├── ems_mark3/
│   ├── utils.py / config.py
│   ├── data.py     # 지침 디렉터리 스캔 + 병원 DB
│   ├── agents.py   # CRAG / Reader / Expert
│   ├── server.py   # execute_ems_pipeline(suspect, target_files, hospital_dept)
│   └── cli.py      # 카테고리 desc 기반 target_files 선정
├── resources/protocol_index.json   # 카테고리 desc (선정 프롬프트용)
└── data/
    ├── protocols/*.md   # 표준 처치지침 코퍼스(64개)
    └── hospitals.json
```

## 설치 / 실행
```bash
cd ems_mark3 && uv venv && source .venv/bin/activate
uv pip install -e .
./run.sh server     # MCP 서버 (8080)
./run.sh cli        # 대화형 클라이언트 (별도 터미널)
```
OpenAI 호환 LLM 서버 필요. 포트/모델은 `config.py`, env(`CMD/EVAL/READER/EXPERT_*`)로 오버라이드.
임베딩이 필요 없어 mark1 대비 가볍다(LLM 서버만 있으면 동작).
