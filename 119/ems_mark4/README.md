# AI EMS Commander — mark4 (Direct Access, 병원 DB 제거)

mark3와 동일한 Direct Access 방식이지만 **병원 DB 입력을 제거**하고, 이송 병원 '기준'을
지침 본문에서 도출하도록 한 변형. `archive/mark4` 의 배포용 박스화.

## 흐름
```
발화 → [Parser LLM] suspect / target_files(지침 키워드)
     → execute_ems_pipeline: 파일 직접 로드 → CRAG → Reader(이송기준 포함) → CoVe
```

## 구조
```
ems_mark4/
├── pyproject.toml / run.sh / README.md
├── ems_mark4/
│   ├── utils.py / config.py
│   ├── data.py     # 지침 디렉터리 스캔 (병원 DB 없음)
│   ├── agents.py   # CRAG / Reader(이송기준) / Expert
│   ├── server.py   # execute_ems_pipeline(suspect, target_files)
│   └── cli.py      # 카테고리 desc 기반 target_files 선정
├── resources/protocol_index.json
└── data/protocols/*.md   # 표준 처치지침 코퍼스(64개)
```

## 설치 / 실행
```bash
cd ems_mark4 && uv venv && source .venv/bin/activate
uv pip install -e .
./run.sh server     # MCP 서버 (8080)
./run.sh cli        # 대화형 클라이언트 (별도 터미널)
```
mark3와 차이: 병원 DB가 없고, 이송 병원은 '유형/조건'으로만 기술(특정 병원명 생성 금지).
