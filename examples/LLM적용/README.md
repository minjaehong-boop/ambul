# 테스트 스크립트

`../docs/HANDOVER_MCP_LLM.md` 의 코드 블록과 1:1 대응. 각 파일 단독 실행 가능.

## 공통 환경변수 (LLM 테스트용)
```bash
export BASE_URL=http://localhost:8000/v1
export API_KEY=EMPTY
export MODEL=your-model-id
```

## LLM 테스트 (LLM 서버 필요)
| 파일 | 내용 |
|---|---|
| `t1_models.py` | 모델 목록 확인 |
| `t2_call.py` | 호출 기본형 |
| `t3_temp.py` | temperature |
| `t3_maxtok.py` | max_tokens |
| `t3_stream.py` | 스트리밍 |
| `t3_top_p.py` | top_p |
| `t3_stop.py` | stop |
| `t4_inject.py` | 컨텍스트 주입 |
| `t4_multiturn.py` | 멀티턴 |
| `t5_json.py` | JSON 안정화 |

## MCP 테스트
| 파일 | 내용 |
|---|---|
| `mcp_server_sse.py` / `mcp_client_sse.py` | SSE (서버 먼저 → 클라) |
| `mcp_server_stdio.py` / `mcp_client_stdio.py` | stdio (클라만 실행, 서버 자동 기동) |

```bash
pip install openai "mcp[cli]" uvicorn anyio
```
