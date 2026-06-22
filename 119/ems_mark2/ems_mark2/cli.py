"""mark2 클라이언트 — Parser가 의심질환/진료과를 뽑아 Long-Context 파이프라인 호출."""

import json
from datetime import datetime
from pathlib import Path

import anyio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from . import config
from .utils import safe_json_parse

TOOL_NAME = "execute_ems_pipeline"


class LogManager:
    def __init__(self, log_dir="logs"):
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.log_file = Path(log_dir) / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    def log(self, type, content, meta=None):
        entry = {"ts": datetime.now().isoformat(), "type": type, "content": content, "meta": meta or {}}
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


logger = LogManager()


class MCPClientWrapper:
    def __init__(self, sse_url=None):
        self.sse_url = sse_url or config.MCP_SSE_URL
        self.session = None
        self.exit_stack = None

    async def connect(self):
        from contextlib import AsyncExitStack
        self.exit_stack = AsyncExitStack()
        read_stream, write_stream = await self.exit_stack.enter_async_context(sse_client(self.sse_url))
        self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()

    async def call_tool(self, name, args):
        if not self.session:
            await self.connect()
        return await self.session.call_tool(name, args)

    async def close(self):
        if self.exit_stack:
            await self.exit_stack.aclose()


def get_commander_client():
    base_url, _ = config.commander_endpoint()
    return OpenAI(base_url=base_url, api_key=config.API_KEY)


def plan_mission(client, user_input, model):
    system_prompt = """
당신은 EMS 지휘관 AI입니다. 구급대원의 보고를 분석하여 'execute_ems_pipeline' 도구에
전달할 인자를 JSON으로 생성하세요.

[필수 필드]
1. suspect: 의심 질환명
2. hospital_dept: 필요한 진료과

반드시 JSON 형식으로만 답하세요.
"""
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_input}],
            temperature=0.0, max_tokens=300,
        )
        return safe_json_parse(res.choices[0].message.content.strip())
    except Exception as e:
        logger.log("error", f"Planning failed: {e}")
        return None


def format_final_output(tool_result_json):
    try:
        data = json.loads(tool_result_json)
        if "error" in data:
            return f"오류 발생: {data['error']}"
        out = "\n" + "=" * 50 + "\n[AI EMS-Cockpit Report]\n" + "=" * 50 + "\n"
        out += f"의심 질환: {data.get('suspect')}\n" + "-" * 50 + "\n"
        out += f"{data.get('draft_report')}\n" + "-" * 50 + "\n"
        out += f"전문가 검수: {data.get('validation_result')}\n" + "=" * 50
        return out
    except Exception:
        return f"Raw Output: {tool_result_json}"


async def run_agent_system():
    cmd_model = config.commander_endpoint()[1]
    mcp = MCPClientWrapper()
    client = get_commander_client()

    print("[Init] MCP Client 준비 완료.")
    print("\n[Interactive Mode] (종료: Ctrl+C)")
    while True:
        try:
            q = input("\n구급대원> ").strip()
            if not q:
                continue
            logger.log("user", q)
            print("[Commander] 상황 분석 중...")
            plan = plan_mission(client, q, cmd_model)
            if not plan:
                print("상황 분석 실패")
                continue
            print(f"   └─ 분석 결과: {plan}")
            print("[System] 지침서 분석 및 검증 수행 중...")
            result = await mcp.call_tool(TOOL_NAME, plan)
            print(format_final_output(result.content[0].text))
        except KeyboardInterrupt:
            print("\n종료합니다.")
            await mcp.close()
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    anyio.run(run_agent_system)


if __name__ == "__main__":
    main()
