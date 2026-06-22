"""mark1 MCP 서버 — Vector RAG 파이프라인.

execute_ems_pipeline(suspect, knowledge_query, hospital_dept):
    임베딩 검색 → 병원 조회 → CRAG → Reader → CoVe
"""

import json

import uvicorn
from mcp.server.fastmcp import FastMCP

from . import config
from .agents import ExpertAgent, ReaderAgent, RetrievalEvaluator
from .data import DataManager

mcp = FastMCP("ems-commander-mark1")

db_instance = None
evaluator_agent = None
reader_agent = None
expert_agent = None


@mcp.tool()
def execute_ems_pipeline(suspect: str, knowledge_query: str, hospital_dept: str) -> str:
    """Args:
        suspect: 의심 질환명
        knowledge_query: 프로토콜 임베딩 검색용 질의
        hospital_dept: 이송 진료과
    """
    global db_instance, evaluator_agent, reader_agent, expert_agent

    if db_instance is None:
        try:
            db_instance = DataManager()
            evaluator_agent = RetrievalEvaluator()
            reader_agent = ReaderAgent()
            expert_agent = ExpertAgent()
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    print(f"\n[Tool] 파이프라인 가동: {suspect}")
    try:
        raw_docs = db_instance.search_knowledge(knowledge_query)
        hospitals = db_instance.find_hospitals(hospital_dept)
        print(f"       └─ [1.검색] 지침 {len(raw_docs)}건")

        verified = evaluator_agent.evaluate_relevance(knowledge_query, raw_docs)
        print(f"       └─ [2.평가] 유효 {len(verified)}건")

        draft = reader_agent.synthesize_report(suspect, verified, hospitals)
        print("       └─ [3.작성] 초안 완료")

        validation = expert_agent.validate_with_cove(draft, suspect, verified)
        print("       └─ [4.검증] 완료")

        return json.dumps({
            "suspect": suspect,
            "draft_report": draft,
            "validation_result": validation,
            "meta": {
                "raw_docs": len(raw_docs),
                "valid_docs": len(verified),
                "hospitals": [h["name"] for h in hospitals],
            },
        }, ensure_ascii=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def main():
    print(f"🚀 EMS Commander(mark1) MCP 서버 시작 (http://{config.MCP_HOST}:{config.MCP_PORT})")
    uvicorn.run(mcp.sse_app(), host=config.MCP_HOST, port=config.MCP_PORT)


if __name__ == "__main__":
    main()
