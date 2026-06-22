"""mark4 MCP 서버 — Direct Access 파이프라인 (병원 DB 없음).

execute_ems_pipeline(suspect, target_files):
    파일 직접 로드 → CRAG → Reader → CoVe
"""

import json

import uvicorn
from mcp.server.fastmcp import FastMCP

from . import config
from .agents import ExpertAgent, ReaderAgent, RetrievalEvaluator
from .data import DataManager

mcp = FastMCP("ems-commander-mark4")

db_instance = None
evaluator_agent = None
reader_agent = None
expert_agent = None


@mcp.tool()
def execute_ems_pipeline(suspect: str, target_files: list[str]) -> str:
    """Args:
        suspect: 의심 질환명
        target_files: 지휘관이 선정한 지침 파일 키워드 리스트
    """
    global db_instance, evaluator_agent, reader_agent, expert_agent

    if db_instance is None:
        try:
            db_instance = DataManager()
            evaluator_agent = RetrievalEvaluator()
            reader_agent = ReaderAgent()
            expert_agent = ExpertAgent()
        except Exception as e:
            return json.dumps({"error": f"초기화 실패: {str(e)}"}, ensure_ascii=False)

    print(f"\n[Tool] 파이프라인 시작 (Target: {target_files})")
    try:
        raw_docs = db_instance.read_specific_files(target_files)
        print(f"       └─ [1.로드] 파일 {len(raw_docs)}개 로드됨")

        verified = evaluator_agent.evaluate_relevance(suspect, raw_docs)
        draft = reader_agent.synthesize_report(suspect, verified)
        print("       └─ [3.작성] 초안 완료")
        validation = expert_agent.validate_with_cove(draft, suspect, verified)
        print("       └─ [4.검증] 완료")

        return json.dumps({
            "suspect": suspect,
            "draft_report": draft,
            "validation_result": validation,
            "meta": {"ref_files": [d["source"] for d in verified]},
        }, ensure_ascii=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def main():
    print(f"🚀 EMS Commander(mark4) MCP 서버 시작 (http://{config.MCP_HOST}:{config.MCP_PORT})")
    uvicorn.run(mcp.sse_app(), host=config.MCP_HOST, port=config.MCP_PORT)


if __name__ == "__main__":
    main()
