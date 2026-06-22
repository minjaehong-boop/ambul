"""클라이언트 — 대화형 CLI(기본) / HTTP 데모 서버(--http).

서버의 run_pipeline 도구를 호출해 pre-KTAS 체크리스트 → 사용자 선택 → 최종 보고서를 진행한다.
"""

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
from openai import OpenAI
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

from . import config
from .utils import safe_json_parse

TOOL_NAME = "run_pipeline"


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


def extract_prektas_params(client, user_input, model):
    """Parser LLM — 발화에서 Pre-KTAS 변수만 JSON으로 추출 (판단 없이 사실만)."""
    system_prompt = """
당신은 119 구급대 보고에서 Pre-KTAS 판단에 필요한 변수만 추출합니다.
판단/분류/추정은 하지 말고, 들린 사실만 JSON으로 반환하세요.

[출력 JSON 스키마]
{
  "age": 숫자 또는 null,
  "sex": "M" 또는 "F" 또는 null,
  "symptom": "주호소(짧은 한글 명사구)" 또는 null,
  "bp_sys": 숫자 또는 null,
  "bp_dia": 숫자 또는 null,
  "pulse": 숫자 또는 null,
  "resp_rate": 숫자 또는 null,
  "spo2": 숫자 또는 null,
  "temp_c": 숫자 또는 null,
  "mental_status": "의식 상태(예: 명료/혼미/혼수)" 또는 null,
  "pain_level": 숫자(0-10) 또는 null,
  "onset_time": "발병 시각/경과(예: 30분 전)" 또는 null,
  "radiation": true/false 또는 null,
  "diaphoresis": true/false 또는 null,
  "fever": true/false 또는 null,
  "immunocompromised": true/false 또는 null,
  "bleeding": true/false 또는 null,
  "trauma_mechanism": "사고기전" 또는 null,
  "pregnancy": true/false 또는 null,
  "seizure": true/false 또는 null,
  "dyspnea": true/false 또는 null,
  "chest_pain": true/false 또는 null,
  "abdominal_pain": true/false 또는 null,
  "signs": ["추가 증상/징후"] 또는 []
}

규칙:
- 추정 금지, 들은 값이 없으면 null/[].
- symptom은 한국어 표현을 우선 사용.
- JSON만 출력.
"""
    started = time.monotonic()
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=0.0, max_tokens=1000
        )
        content = response.choices[0].message.content.strip()
        try:
            return safe_json_parse(content), time.monotonic() - started
        except Exception:
            retry_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "JSON만 다시 출력하세요. 다른 문장은 포함하지 마세요."},
            ]
            retry_res = client.chat.completions.create(
                model=model, messages=retry_messages, temperature=0.0, max_tokens=180
            )
            return safe_json_parse(retry_res.choices[0].message.content.strip()), time.monotonic() - started
    except Exception as e:
        logger.log("error", f"Extraction failed: {e}")
        print(f"[Error] Extraction parsing failed: {e}")
        return None, None


def merge_params(base, new_values):
    """누적 params 병합. signs는 합집합, 빈 값은 무시."""
    merged = dict(base)
    for key, value in new_values.items():
        if key == "signs":
            existing = merged.get("signs") or []
            for item in value or []:
                if item not in existing:
                    existing.append(item)
            merged["signs"] = existing
            continue
        if value is None or value == "" or value == []:
            continue
        merged[key] = value
    return merged


def format_assessment_output(assessment):
    if "error" in assessment:
        return f"오류 발생: {assessment['error']}"
    lines = []
    checklist = assessment.get("checklist") or []
    if checklist:
        lines.append("📋 체크리스트(근거 요약):")
        grouped = {}
        for item in checklist:
            grouped.setdefault(item.get("category") or "other", []).append(item)
        order = ["활력징후 1 차 고려사항", "그 밖의 1 차 고려사항", "증상별 2 차 고려사항", "other"]
        for cat in order:
            items = grouped.get(cat, [])
            if not items:
                continue
            lines.append(f"[{cat}]")
            for item in items:
                lines.append(f"- [{item.get('level')}] {item.get('text')} ({item.get('source')})")
    return "\n".join(lines)


def format_final_output(tool_result_json, timing_info=None):
    try:
        data = json.loads(tool_result_json)
        if "error" in data:
            return f"오류 발생: {data['error']}"

        output = "\n" + "=" * 50 + "\n"
        output += "[AI EMS-Cockpit Report]\n"
        output += "=" * 50 + "\n"
        output += f"❗ 의심 질환: {data.get('suspect')}\n"
        output += f"KTAS 등급: {data.get('ktas_level')} ({', '.join(data.get('ktas_reasons', []))})\n"
        output += f"KTAS {data.get('ktas_level')} 등급에 맞는 병원으로 이송하세요.\n"
        output += f"📂 선택 지침: {data.get('target_files', [])}\n"
        output += f"📂 참조 지침: {data.get('meta', {}).get('ref_files', [])}\n"
        output += "-" * 50 + "\n"
        output += f"{data.get('draft_report')}\n"
        output += "-" * 50 + "\n"
        output += f"📋 전문가 검수: {data.get('validation_result')}\n"
        if timing_info:
            output += timing_info
        output += "=" * 50
        return output
    except Exception:
        return f"Raw Output: {tool_result_json}"


def _build_timing_info(parser_sec, timings, total_start):
    info = ""
    if parser_sec is not None:
        info += f"⏱️ Parser LLM: {parser_sec:.2f}s\n"
    if timings:
        info += (
            "⏱️ Server LLM: "
            f"selector={(timings.get('selector_sec') or 0):.2f}s, "
            f"crag={(timings.get('crag_sec') or 0):.2f}s, "
            f"reader={(timings.get('reader_sec') or 0):.2f}s, "
            f"expert={(timings.get('expert_sec') or 0):.2f}s\n"
        )
        info += (
            "⏱️ Server 기타: "
            f"pre_ktas={(timings.get('pre_ktas_sec') or 0):.2f}s, "
            f"data_load={(timings.get('data_load_sec') or 0):.2f}s, "
            f"pipeline={(timings.get('pipeline_sec') or 0):.2f}s\n"
        )
    info += f"⏱️ 총 소요시간: {time.monotonic() - total_start:.2f}s\n"
    return info


# ---------------- HTTP 데모 서버 ----------------

def _write_json(handler, status, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "content-type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _write_text(handler, status, body, content_type="text/plain; charset=utf-8"):
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _load_demo_html():
    try:
        return Path(config.DEMO_HTML).read_text(encoding="utf-8")
    except Exception:
        return None


async def _call_mcp_tool_once(name, args):
    mcp = MCPClientWrapper()
    await mcp.connect()
    try:
        res = await mcp.call_tool(name, args)
        if not res or not res.content:
            return ""
        return res.content[0].text
    finally:
        await mcp.close()


class DemoRequestHandler(BaseHTTPRequestHandler):
    server_version = "ems-commander-demo/1.0"

    def do_OPTIONS(self):
        _write_json(self, 200, {"ok": True})

    def do_GET(self):
        if self.path in ["/", "/demo.html"]:
            html = _load_demo_html()
            if html is None:
                _write_text(self, 500, "demo.html load failed")
                return
            _write_text(self, 200, html, "text/html; charset=utf-8")
            return
        if self.path == "/health":
            _write_json(self, 200, {"status": "ok"})
            return
        _write_json(self, 404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            _write_json(self, 400, {"error": "invalid_json"})
            return

        if self.path == "/parse":
            text = (payload.get("text") or "").strip()
            if not text:
                _write_json(self, 400, {"error": "missing_text"})
                return
            params, elapsed = extract_prektas_params(
                self.server.commander_client, text, self.server.cmd_model
            )
            if not params:
                _write_json(self, 500, {"error": "parse_failed"})
                return
            _write_json(self, 200, {"params": params, "elapsed": elapsed})
            return

        if self.path in ("/prektas", "/choice"):
            params = payload.get("params") or {}
            args = {"params": params}
            if self.path == "/choice":
                choice = (payload.get("choice") or "").strip()
                if not choice:
                    _write_json(self, 400, {"error": "missing_choice"})
                    return
                args["choice"] = choice
            try:
                stage_data = json.loads(asyncio.run(_call_mcp_tool_once(TOOL_NAME, args)))
            except Exception as e:
                _write_json(self, 500, {"error": f"mcp_failed: {e}"})
                return
            _write_json(self, 200, stage_data)
            return

        _write_json(self, 404, {"error": "not_found"})


def run_http_demo_server(host=None, port=None):
    host = host or config.HTTP_DEMO_HOST
    port = port or config.HTTP_DEMO_PORT
    server = ThreadingHTTPServer((host, port), DemoRequestHandler)
    server.cmd_model = config.commander_endpoint()[1]
    server.commander_client = get_commander_client()
    print(f"[HTTP Demo] http://{host}:{port} 실행 중...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[HTTP Demo] 종료합니다.")
    finally:
        server.server_close()


# ---------------- 대화형 CLI ----------------

async def run_agent_system():
    cmd_model = config.commander_endpoint()[1]
    mcp = MCPClientWrapper()
    client = get_commander_client()

    current_params = {}
    current_symptom = None

    print("[Init] MCP Client 준비 완료.")
    print("\n[Interactive Mode] (종료: Ctrl+C)")

    while True:
        try:
            q = input("\n구급대원> ").strip()
            if not q:
                continue
            if "초기화" in q or q.lower() == "reset":
                current_params, current_symptom = {}, None
                print("[System] 상태를 초기화했습니다.")
                continue

            logger.log("user", q)
            total_start = time.monotonic()

            print("[Parser] 활력징후/증상 추출 중...")
            params, parser_sec = extract_prektas_params(client, q, cmd_model)
            if not params:
                print("상황 분석 실패 (JSON 파싱 오류 또는 모델 응답 오류)")
                continue

            new_symptom = params.get("symptom")
            if new_symptom and current_symptom and new_symptom != current_symptom:
                current_params = {}
            current_params = merge_params(current_params, params)
            current_symptom = current_params.get("symptom")

            logger.log("params", json.dumps(current_params, ensure_ascii=False))
            print(f"   👉 추출 데이터: {current_params}")

            print("[System] KTAS 규정 기반 평가 중...")
            stage_res = await mcp.call_tool(TOOL_NAME, {"params": current_params})
            stage_data = json.loads(stage_res.content[0].text)
            if stage_data.get("stage") == "error":
                print(f"오류 발생: {stage_data.get('error')}")
                continue

            assessment = stage_data.get("assessment", {})
            print(format_assessment_output(assessment))

            checklist = assessment.get("checklist") or []
            if not checklist:
                print("체크리스트가 없습니다. 다음 입력을 기다립니다.")
                continue

            print("추가 입력: 등급 숫자(1-5) 또는 체크리스트 항목을 입력하세요.")
            user_choice = input("등급 선택> ").strip()
            if not user_choice:
                continue

            stage_res = await mcp.call_tool(TOOL_NAME, {"params": current_params, "choice": user_choice})
            stage_data = json.loads(stage_res.content[0].text)
            if stage_data.get("stage") == "error":
                print(f"오류 발생: {stage_data.get('error')}")
                continue
            if stage_data.get("stage") == "complete":
                print("[System] 환자 지침 파이프라인 실행...")
                ems = stage_data.get("ems", {})
                timing_info = _build_timing_info(parser_sec, ems.get("timings", {}), total_start)
                print(format_final_output(json.dumps(ems, ensure_ascii=False), timing_info))
                current_params, current_symptom = {}, None

        except KeyboardInterrupt:
            print("\n종료합니다.")
            await mcp.close()
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="AI EMS Commander 클라이언트")
    parser.add_argument("--http", action="store_true", help="HTTP 데모 서버 모드 (기본: 대화형 CLI)")
    args = parser.parse_args()

    if args.http:
        run_http_demo_server()
    else:
        anyio.run(run_agent_system)


if __name__ == "__main__":
    main()
