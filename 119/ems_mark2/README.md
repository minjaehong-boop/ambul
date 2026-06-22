# AI EMS Commander — mark2 (Long-Context)

지침서 **전문을 system 프롬프트에 통째로 주입**하고 CRAG → Reader → CoVe 를 수행하는 버전.
`archive/mark2` 의 배포용 박스화.

## ⚠️ 중요 — Long-Context 한계
번들된 지침서 전문(`data/guideline.md`)은 약 **70만 토큰(116만 자)** 으로, 어떤 일반
컨텍스트 창(4K~256K)에도 통째로 들어가지 않는다. 따라서 이 박스는 `MAX_CONTEXT_CHARS`
(기본 **3000자**, ≈ 4096 컨텍스트 서버 기준)로 전문을 **앞부분만 절단**해 주입한다.

- 즉, "전문 Long-Context" 컨셉은 이 모델/지침 조합에서는 **완전하게는 성립하지 않는다.**
- 실제 처치 품질이 필요하면 mark3/mark4(Direct Access) 또는 mark1(Vector RAG)을 권장.
- 큰 컨텍스트 서버(예: 128K)를 쓰면 `MAX_CONTEXT_CHARS` 를 키워 더 많이 주입할 수 있다.

## 흐름
```
발화 → [Parser LLM] suspect / hospital_dept
     → execute_ems_pipeline: 전문(절단) 주입 → CRAG → Reader → CoVe
```

## 구조
```
ems_mark2/
├── pyproject.toml / run.sh / README.md
├── ems_mark2/
│   ├── utils.py / config.py
│   ├── data.py     # 지침서 전문(md/pdf) 로더 + 병원 DB
│   ├── server.py   # execute_ems_pipeline(suspect, hospital_dept) — CRAG/Reader/CoVe
│   └── cli.py      # Parser + 호출
└── data/
    ├── guideline.md   # 표준지침 전문(번들)
    └── hospitals.json
```

## 설치 / 실행
```bash
cd ems_mark2 && uv venv && source .venv/bin/activate
uv pip install -e .
export MAX_CONTEXT_CHARS=3000     # 서버 컨텍스트에 맞게 조정
./run.sh server                   # MCP 서버 (8080)
./run.sh cli                      # 대화형 클라이언트 (별도 터미널)
```
OpenAI 호환 LLM 서버 필요. 포트/모델은 `config.py`, env(`CMD_*`, `EXPERT_*`)로 오버라이드.
