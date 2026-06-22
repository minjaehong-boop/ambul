"""mark3 클라이언트 — Commander가 지침 카테고리 목록을 보고 target_files를 선정해 호출."""

import json
import os
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


def load_protocol_desc():
    if os.path.exists(config.PROTOCOL_INDEX):
        with open(config.PROTOCOL_INDEX, "r", encoding="utf-8") as f:
            return json.load(f).get("categories", {})
    return {}


def plan_mission(client, user_input, model, protocol_desc_str):
    system_prompt = f"""
    당신은 119 구급대 현장 지휘관 AI입니다.
    사용자의 보고를 분석하여 필요한 응급처치 지침 파일을 선정해야 합니다.

    아래는 보유 중인 [지침 카테고리 및 내용]입니다:
    {protocol_desc_str}

    [중요 규칙]
    'target_files'에는 카테고리 영어 이름(예: general, pediatrics)을 쓰지 마십시오.
    반드시 위 '지침 카테고리 및 내용'의 'desc'에 적혀 있는 **단어 그대로**를 발췌하십시오.
    (예시: "심정지", "응급 분만", "경련", "화상")

    [임무]
    1. 환자의 증상을 분석하여 '의심 질환명(suspect)'을 도출하세요.
    2. 위 목록의 'desc' 내용을 참고하여 실제 파일명과 매칭될 수 있는 **한글 키워드**를 'target_files'에 담으세요.
    3. 이송에 필요한 '진료과(hospital_dept)'를 판단하세요.

    [출력 형식 (JSON Only)]
    {{
        "suspect": "의심 질환명",
        "target_files": ["키워드1", "키워드2","키워드3","키워드4"],
        "hospital_dept": "진료과"
    }}
    """
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_input}],
            temperature=0.0, max_tokens=1000,
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
        out += f"🚑 의심 질환: {data.get('suspect')}\n"
        out += f"📂 참조 지침: {data.get('meta', {}).get('ref_files', [])}\n" + "-" * 50 + "\n"
        out += f"{data.get('draft_report')}\n" + "-" * 50 + "\n"
        out += f"🛡️ 전문가 검수: {data.get('validation_result')}\n" + "=" * 50
        return out
    except Exception:
        return f"Raw Output: {tool_result_json}"


async def run_agent_system():
    cmd_model = config.commander_endpoint()[1]
    protocol_desc_str = json.dumps(load_protocol_desc(), ensure_ascii=False, indent=2)
    mcp = MCPClientWrapper()
    client = get_commander_client()

    print("[Init] MCP Client + 프로토콜 인덱스 로드 완료.")
    print("\n[Interactive Mode] (종료: Ctrl+C)")
    while True:
        try:
            q = input("\n구급대원> ").strip()
            if not q:
                continue
            logger.log("user", q)
            print("[Commander] 상황 판단 및 지침 선정 중...")
            plan = plan_mission(client, q, cmd_model, protocol_desc_str)
            if not plan:
                print("상황 분석 실패")
                continue
            print(f"   👉 판단: {plan.get('suspect')}")
            print(f"   👉 선택한 지침: {plan.get('target_files')}")
            print("[System] 파일 로드 및 분석 파이프라인 실행...")
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
