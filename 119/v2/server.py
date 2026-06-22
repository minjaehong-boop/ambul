"""
Triage RAG - FastAPI Chain Server

EXAMPLE_TYPE 환경변수로 실행할 파이프라인을 선택합니다:
  EXAMPLE_TYPE=pageindex   → TriagePageIndexChatbot  (기본값)
  EXAMPLE_TYPE=agent       → TriageAgentChatbot

기타 환경변수:
  APP_LLM_SERVER_URL   — LLM 서버 URL (기본: http://localhost:8000/v1)
  APP_LLM_MODEL_NAME   — 모델명 (기본: Qwen/Qwen3-8B)
  PAGEINDEX_ROOT       — PageIndex 아티팩트 루트 경로 (기본: /e/project/PageIndex)
  APP_CONFIG_FILE      — YAML/JSON 설정 파일 경로 (선택)
  LOGLEVEL             — 로그 레벨 (기본: INFO)
"""

import logging
import os
from typing import List, Optional
from uuid import uuid4

import bleach
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, constr, validator

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="Triage RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str = Field(default="user", max_length=256, pattern=r'[\s\S]*')
    content: str = Field(default="", max_length=131072, pattern=r'[\s\S]*')

    @validator('role')
    def validate_role(cls, value):
        value = bleach.clean(value, strip=True)
        if value.lower() not in {'user', 'assistant', 'system'}:
            raise ValueError("Role must be one of 'user', 'assistant', or 'system'")
        return value.lower()

    @validator('content')
    def sanitize_content(cls, v):
        return bleach.clean(v, strip=True)


class Prompt(BaseModel):
    messages: List[Message] = Field(..., max_items=50000)
    use_knowledge_base: bool = Field(...)
    temperature: float = Field(0.2, ge=0.1, le=1.0)
    top_p: float = Field(0.7, ge=0.1, le=1.0)
    max_tokens: int = Field(1024, ge=0, le=2048, format="int64")
    stop: List[constr(max_length=256, pattern=r'[\s\S]*')] = Field(default=[], max_items=256)
    session_id: Optional[str] = Field(None, max_length=128)

    @validator('use_knowledge_base')
    def sanitize_use_kb(cls, v):
        v = bleach.clean(str(v), strip=True)
        try:
            return {"True": True, "False": False}[v]
        except KeyError:
            raise ValueError("use_knowledge_base must be a boolean value")


class ChainResponseChoices(BaseModel):
    index: int = Field(default=0, ge=0, le=256, format="int64")
    message: Message = Field(default=Message(role="assistant", content=""))
    finish_reason: str = Field(default="", max_length=4096, pattern=r'[\s\S]*')


class ChainResponse(BaseModel):
    id: str = Field(default="", max_length=100000, pattern=r'[\s\S]*')
    choices: List[ChainResponseChoices] = Field(default=[], max_items=256)


class HealthResponse(BaseModel):
    message: str = Field(default="", max_length=4096, pattern=r'[\s\S]*')


# ── Example loading ────────────────────────────────────────────────────────────
@app.on_event("startup")
def load_example() -> None:
    from triage_rag_pageindex.chains import TriagePageIndexChatbot
    app.example = TriagePageIndexChatbot
    logger.info("Loaded: TriagePageIndexChatbot")


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health_check():
    """서버 상태 확인."""
    return HealthResponse(message="Service is up.")


@app.post("/generate", response_model=ChainResponse)
async def generate_answer(request: Request, prompt: Prompt) -> StreamingResponse:
    """스트리밍 응답 생성."""
    chat_history = list(prompt.messages)

    # 마지막 user 메시지 추출
    last_user_message = next(
        (m.content for m in reversed(chat_history) if m.role == "user"), None
    )
    for i in reversed(range(len(chat_history))):
        if chat_history[i].role == "user":
            del chat_history[i]
            break

    llm_settings = {
        k: v for k, v in vars(prompt).items()
        if k not in ("messages", "use_knowledge_base")
    }

    try:
        example = app.example()
        if prompt.use_knowledge_base:
            generator = example.rag_chain(
                query=last_user_message, chat_history=chat_history, **llm_settings
            )
        else:
            generator = example.llm_chain(
                query=last_user_message, chat_history=chat_history, **llm_settings
            )

        def response_generator():
            resp_id = str(uuid4())
            if generator:
                for chunk in generator:
                    cr = ChainResponse()
                    cr.id = resp_id
                    cr.choices.append(
                        ChainResponseChoices(
                            index=0, message=Message(role="assistant", content=chunk)
                        )
                    )
                    yield "data: " + cr.json() + "\n\n"
            cr = ChainResponse()
            cr.id = resp_id
            cr.choices.append(ChainResponseChoices(finish_reason="[DONE]"))
            yield "data: " + cr.json() + "\n\n"

        return StreamingResponse(response_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Error in /generate: {e}")
        cr = ChainResponse()
        cr.choices.append(
            ChainResponseChoices(
                index=0,
                message=Message(role="assistant", content=f"오류가 발생했습니다: {e}"),
                finish_reason="[DONE]",
            )
        )
        return StreamingResponse(
            iter(["data: " + cr.json() + "\n\n"]),
            media_type="text/event-stream",
            status_code=500,
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8082))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
