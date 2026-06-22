"""MCP 클라이언트 — SSE 트랜스포트.

사전: mcp_server_sse.py 가 먼저 떠 있어야 함.
실행:  python mcp_client_sse.py
"""
import anyio
import json
from contextlib import AsyncExitStack
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

URL = "http://localhost:8080/sse"


async def main():
    async with AsyncExitStack() as stack:
        # 1) SSE 연결 → 읽기/쓰기 스트림
        r, w = await stack.enter_async_context(sse_client(URL))
        # 2) 세션 생성
        session = await stack.enter_async_context(ClientSession(r, w))
        # 3) 핸드쉐이크 (프로토콜 버전/capability 합의)
        await session.initialize()
        # 4) 도구 발견 (선택)
        tools = await session.list_tools()
        print("tools:", [t.name for t in tools.tools])
        # 5) 도구 호출
        res = await session.call_tool("add", {"a": 2, "b": 3})
        print(json.loads(res.content[0].text))   # {'result': 5}


anyio.run(main)
