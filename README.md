# ambul — 한국어 응급의료(119) LLM 시스템 & LLM 학습 자료

NVIDIA Jetson AGX Orin 환경을 염두에 둔 **한국어 119 구급 현장 처치 보조 시스템(119)** 과,
그 시스템을 만들기 위해 정리한 **LLM 학습 노트·예제(LLM_STUDY)** 를 하나로 묶은 저장소입니다.

- **`docs/`** — LLM 학습 노트(UV / vLLM / LLM 기본·적용 / MCP / RAG / OCR 등).
- **`examples/`** — 노트에 대응하는 실습 예제 코드.
- **`119/`** — 119 EMS 처치 보조 시스템의 아키텍처 변천(버전별 폴더).

모든 문서/주석은 한국어이며, 코드 식별자는 영어입니다.

---

## 1. `docs/` — 학습 노트

`*.odt` 형식의 학습 정리 노트입니다. `examples/` 의 실습 코드와 1:1 로 대응합니다.

| 노트 | 주제 | 대응 예제 |
|---|---|---|
| `1_UV.odt` | uv 패키지/환경 관리 | (전 예제 공통) |
| `2_VLLM.odt` | vLLM OpenAI 호환 서빙 | — |
| `3_LLM기본.odt` | LLM 호출 기본 | `examples/MCP`, `examples/LLM적용` |
| `4_LLM적용.odt` | LLM 적용 패턴 | `examples/LLM적용` |
| `5_MCP.odt` | MCP(Model Context Protocol) | `examples/MCP` |
| `6_RAG1.odt` | RAG 기초(청킹·임베딩·검색) | `examples/RAG1` |
| `7_RAG2.odt` | GraphRAG(Neo4j) | `examples/RAG2` |
| `8_그 외 기법.odt` | 기타 기법 | — |
| `9_OCR.odt` | 문서 OCR/파싱 | (아래 OCR 섹션 참고) |

---

## 2. `examples/` — 실습 예제

> 공통: 대부분의 예제는 **OpenAI 호환 LLM 서버(vLLM 등)** 가 필요합니다.
> ```bash
> export BASE_URL=http://localhost:8000/v1
> export API_KEY=EMPTY
> export MODEL=your-model-id
> ```

- **`MCP/`, `LLM적용/`** — LLM 호출 기본형(temperature·max_tokens·stream·top_p·stop·JSON 안정화)과
  MCP stdio/SSE 서버·클라이언트 예제. 각 파일은 단독 실행 가능(`README.md` 참고).
- **`RAG1/`** — 청킹(character / recursive / tiktoken) → 임베딩(OpenAI·HuggingFace) →
  유사도 검색(Chroma) 까지의 RAG 기초 9단계 스크립트.
- **`RAG2/GraphRAG/`** — 표준지침 문서를 분할·임베딩하고 Neo4j 에 엔티티 그래프를 구축해
  GraphRAG vs naive RAG 를 비교하는 `step1~8` 파이프라인.

### API 키 설정

`RAG1` / `RAG2` 의 일부 스크립트는 OpenRouter API 키를 파일에서 읽습니다.
키 파일은 보안상 커밋되지 않으므로, 동봉된 예시 파일을 복사해 실제 키를 넣으세요.

```bash
# RAG1
cp examples/RAG1/openrouter_key.txt.example examples/RAG1/key.txt
# RAG2/GraphRAG
cp examples/RAG2/GraphRAG/openrouter_key.txt.example examples/RAG2/GraphRAG/openrouter_key.txt
```

### OCR (코드 미포함 — 공식 레포 참고)

OCR/문서 파싱 실습은 아래 공식 오픈소스를 그대로 사용했습니다. 용량 문제로 코드는 포함하지
않으며, 원본 레포를 참고하세요(`docs/9_OCR.odt` 에 정리).

- **MinerU** — PDF/문서 레이아웃·표 파싱 CLI: <https://github.com/opendatalab/MinerU>
- **marker** — PDF → Markdown 변환: <https://github.com/datalab-to/marker>
- **chandra** — OCR/문서 이해 모델: <https://github.com/datalab-to/chandra>

---

## 3. `119/` — AI EMS Commander 아키텍처 변천

구급대원 발화에서 활력징후·증상을 추출하고, KTAS 규정집과 표준 처치지침을 근거로
체크리스트·처치 보고서를 생성하는 시스템입니다. 검색/주입 전략을 달리한 여러 버전을
**버전 폴더 그대로** 보존했습니다. 각 폴더의 `README.md` 가 해당 버전의 권위 있는 문서입니다.

| 버전 | 컨셉 | 핵심 차이 |
|---|---|---|
| `ems_mark1` | **Vector RAG** | PDF 표준지침 임베딩 검색 → CRAG → Reader → CoVe. 임베딩 캐시 번들로 PDF 없이 동작 |
| `ems_mark2` | **Long-Context** | 지침서 전문을 system 프롬프트에 주입(컨텍스트 한계로 앞부분 절단) |
| `ems_mark3` | **Direct Access** | 벡터 검색 없이 Commander 가 필요한 지침 파일을 직접 지정해 로드 |
| `ems_mark4` | Direct Access (병원 DB 제거) | mark3 변형 — 병원 DB 없이 이송 '기준'을 지침 본문에서 도출 |
| `ems_mark9` | **배포판** | KTAS 임베딩 검색(top-1) 체크리스트 → 등급/질환 선택 → 지침 검색·요약·검증 |
| `ems_mark10` | KTAS LLM Selector | KTAS 섹션을 LLM 선택기로 top-3 선정해 1~3순위 체크리스트 제시 |
| `v1` | **NVIDIA Framework RAG** | NVIDIA GenerativeAIExamples 위에서 Milvus 임베딩 + vLLM `/v1/rerank` 리랭킹 |
| `v2` | **PageIndex** | 구조 기반 2단계(chapter→section) LLM 선택 + `pdfplumber` 페이지 읽기 + 자기검증 + SSE |

> mark1~4 는 검색/주입 전략 비교용 초기 박스, mark9/mark10 은 KTAS 체크리스트 흐름을 갖춘
> 배포 지향 버전, v1/v2 는 프레임워크 기반 재구현입니다.

### 아키텍처 플로우차트 / 버전별 변경·개선점

각 버전(mark1·2·3·4·9·10, v1·v2)의 파이프라인 플로우차트와 버전 간 변경/개선점을
한눈에 비교한 다이어그램:

📊 **[Whimsical — 119 Architectures](https://whimsical.com/software83/119-architectures-RN2HNaDYcMMRUkHwmV7BbK)**

### 공통 요구사항 / 실행

- **공통**: OpenAI 호환 LLM 서버(vLLM 등). 역할별 모델/포트는 각 버전의 `config.py` 또는
  `config.yaml`, 그리고 환경변수로 오버라이드합니다.
- **mark 계열**(uv 관리):
  ```bash
  cd 119/ems_mark9 && uv venv && source .venv/bin/activate
  uv pip install -e .
  ./run.sh server     # MCP 서버 (8080)
  ./run.sh cli        # 대화형 클라이언트 (별도 터미널)
  ```
- **v 계열**(requirements 관리):
  ```bash
  cd 119/v2 && pip install -r requirements.txt
  ./run.sh server     # API 서버
  ```

자세한 흐름·구조·환경변수는 각 버전 폴더의 `README.md` 를 참고하세요.

---

## 참고

- 대용량 가중치/엔진/캐시·가상환경(`.venv`)·생성 산출물(`output/`)·벡터 DB(`db/`)·OCR 코드는
  저장소에 포함하지 않습니다(`.gitignore` 참고).
- 하드코딩된 절대경로/포트/모델명은 환경변수 또는 설정 파일로 오버라이드하세요.
