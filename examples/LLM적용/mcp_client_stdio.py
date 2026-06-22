"""MCP 클라이언트 — stdio 트랜스포트.

서버를 자식 프로세스로 직접 띄운다(별도 서버 실행 불필요).
실행:  python mcp_client_stdio.py
"""
import anyio
import json
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession

# 같은 폴더의 stdio 서버를 자식 프로세스로 기동
params = StdioServerParameters(command="python", args=["mcp_server_stdio.py"])


async def main():
    async with stdio_client(params) as (r, w):       # 1) 서버 프로세스 + 파이프
        async with ClientSession(r, w) as session:   # 2) 세션
            await session.initialize()               # 3) 핸드쉐이크
            tools = await session.list_tools()       # 4) 도구 발견
            print("tools:", [t.name for t in tools.tools])
            res = await session.call_tool("echo1", {"text": "안녕"})  # 5) 호출
            print(json.loads(res.content[0].text))   # {'echo': '안녕'}


anyio.run(main)
