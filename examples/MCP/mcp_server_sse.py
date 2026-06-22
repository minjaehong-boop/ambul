"""MCP 서버 — SSE 트랜스포트.

실행:  python mcp_server_sse.py   (포트 8080)
짝 클라이언트: mcp_client_sse.py
"""
import json
import uvicorn
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-sse")


@mcp.tool()
def add(a: int, b: int) -> str:
    """두 수를 더한다. Args: a: 첫 수  b: 둘째 수"""
    return json.dumps({"result": a + b})


@mcp.tool()
def echo(text: str) -> str:
    """입력을 그대로 돌려준다. Args: text: 문자열"""
    return json.dumps({"echo": text}, ensure_ascii=False)


if __name__ == "__main__":
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8080)
