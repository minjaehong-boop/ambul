"""MCP 서버 — stdio 트랜스포트.

직접 실행하지 않는다. 클라이언트(mcp_client_stdio.py)가 이 파일을
자식 프로세스로 띄워 표준입출력으로 통신한다.
"""
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-stdio")


@mcp.tool()
def add(a: int, b: int) -> str:
    """두 수를 더한다. Args: a: 첫 수  b: 둘째 수"""
    return json.dumps({"result": a + b})


@mcp.tool()
def echo1(text: str) -> str:
    """입력을 그대로 돌려준다. Args: text: 문자열"""
    return json.dumps({"echo": text}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")   # 표준입출력으로 서빙
