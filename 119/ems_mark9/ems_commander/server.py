"""MCP 서버 (SSE) — pre-KTAS 평가 → 사용자 선택 → EMS 지침 파이프라인.

노출 도구:
    run_pipeline(params, choice=None)  : 통합 진입점 (need_choice → complete 2-스텝)
내부 단계:
    pre_ktas_assess / resolve_ktas_choice / execute_ems_pipeline
"""

import json
import time

import uvicorn
from mcp.server.fastmcp import FastMCP

from . import config
from .agents import ExpertAgent, ProtocolSelector, ReaderAgent, RetrievalEvaluator
from .data import DataManager
from .ktas import KtasEmbeddingStore, build_checklist_from_sections
from .utils import normalize_symptom_query, normalize_text

mcp = FastMCP("ems-commander")

# --- 지연 초기화되는 전역 리소스 ---
db_instance = None
evaluator_agent = None
reader_agent = None
expert_agent = None
protocol_selector = None
protocol_desc = None
ktas_store = None


def load_protocol_desc():
    import os
    if os.path.exists(config.PROTOCOL_INDEX):
        with open(config.PROTOCOL_INDEX, "r", encoding="utf-8") as f:
            return json.load(f).get("desc", "")
    return ""


def pre_ktas_assess(params: dict) -> str:
    """증상 키워드로 KTAS 규정집을 임베딩 검색해 체크리스트를 만든다."""
    global ktas_store
    started = time.monotonic()
    try:
        if ktas_store is None:
            ktas_store = KtasEmbeddingStore()
    except Exception as e:
        return json.dumps({"error": f"guideline init failed: {e}"}, ensure_ascii=False)

    symptom_raw = params.get("symptom") or ""
    symptom_query = normalize_symptom_query(symptom_raw)
    symptom_sections = ktas_store.search(symptom_query, top_k=1) if symptom_query else []
    if not symptom_sections:
        symptom_sections = ktas_store.lexical_search(symptom_query, top_k=1)

    checklist = build_checklist_from_sections(symptom_sections)
    guideline_refs = [
        {
            "title": s["title"],
            "start_line": s["start_line"],
            "score": s["score"],
            "preview": s["content"][:200],
        }
        for s in symptom_sections
    ]

    return json.dumps({
        "symptom": symptom_query or symptom_raw,
        "checklist": checklist,
        "guideline_refs": guideline_refs,
        "timings": {"pre_ktas_sec": time.monotonic() - started},
    }, ensure_ascii=False)


def resolve_ktas_choice(choice: str, checklist: list) -> str:
    """사용자 선택(등급 숫자 또는 항목 텍스트)을 KTAS 등급/의심질환으로 확정."""
    choice_text = normalize_text(choice)

    if choice_text.isdigit() and choice_text in ["1", "2", "3", "4", "5"]:
        ktas_suspect = None
        for item in checklist or []:
            if str(item.get("level")) == choice_text:
                ktas_suspect = item.get("disease") or item.get("source")
                break
        return json.dumps({
            "ktas_level": choice_text,
            "ktas_reason": f"사용자 선택 등급: {choice_text}",
            "ktas_suspect": ktas_suspect,
        }, ensure_ascii=False)

    for item in checklist or []:
        if choice_text and choice_text in normalize_text(item.get("text") or ""):
            return json.dumps({
                "ktas_level": item.get("level"),
                "ktas_reason": f"사용자 선택 항목: {item.get('text')}",
                "ktas_suspect": item.get("disease") or item.get("source"),
            }, ensure_ascii=False)

    return json.dumps({"error": "choice_not_matched"}, ensure_ascii=False)


def execute_ems_pipeline(params: dict, assessment=None) -> str:
    """지침 선정 → 로드 → CRAG → 보고서 작성 → CoVe 검증."""
    global db_instance, evaluator_agent, reader_agent, expert_agent, protocol_selector, protocol_desc

    if db_instance is None:
        try:
            db_instance = DataManager()
            evaluator_agent = RetrievalEvaluator()
            reader_agent = ReaderAgent()
            expert_agent = ExpertAgent()
        except Exception as e:
            return json.dumps({"error": f"초기화 실패: {str(e)}"})

    try:
        pipeline_start = time.monotonic()
        if protocol_selector is None:
            protocol_selector = ProtocolSelector()
        if protocol_desc is None:
            protocol_desc = load_protocol_desc()

        assessment = assessment or {}
        ktas_level = assessment.get("ktas_level")
        ktas_reasons = assessment.get("ktas_reasons", [])
        suspect = assessment.get("ktas_suspect") or params.get("symptom") or "의심 질환 미상"

        select_start = time.monotonic()
        selection = protocol_selector.select_targets(protocol_desc, suspect)
        selector_sec = time.monotonic() - select_start
        target_files = selection.get("target_files", [])

        print(f"\n[Tool] 파이프라인 시작 (Target: {target_files})")

        load_start = time.monotonic()
        raw_docs = db_instance.read_specific_files(target_files)
        data_load_sec = time.monotonic() - load_start
        print(f"       └─ [1.로드] 파일 {len(raw_docs)}개 로드됨")

        if not raw_docs:
            return json.dumps({
                "suspect": suspect,
                "params": params,
                "ktas_level": ktas_level,
                "ktas_reasons": ktas_reasons,
                "target_files": target_files,
                "draft_report": "해당하는 지침 파일을 찾을 수 없습니다. 파일명이나 경로를 확인하세요.",
                "validation_result": "N/A",
            }, ensure_ascii=False)

        crag_start = time.monotonic()
        verified_docs = evaluator_agent.evaluate_relevance(suspect, raw_docs)
        crag_sec = time.monotonic() - crag_start

        reader_start = time.monotonic()
        draft = reader_agent.synthesize_report(suspect, verified_docs)
        reader_sec = time.monotonic() - reader_start
        print("       └─ [3.작성] 초안 완료")

        expert_start = time.monotonic()
        validation = expert_agent.validate_with_cove(draft, suspect, verified_docs)
        expert_sec = time.monotonic() - expert_start
        print("       └─ [4.검증] 완료")

        timings = {
            "selector_sec": selector_sec,
            "data_load_sec": data_load_sec,
            "crag_sec": crag_sec,
            "reader_sec": reader_sec,
            "expert_sec": expert_sec,
            "pipeline_sec": time.monotonic() - pipeline_start,
        }
        if assessment.get("timings"):
            timings["pre_ktas_sec"] = assessment["timings"].get("pre_ktas_sec")

        return json.dumps({
            "suspect": suspect,
            "params": params,
            "ktas_level": ktas_level,
            "ktas_reasons": ktas_reasons,
            "target_files": target_files,
            "draft_report": draft,
            "validation_result": validation,
            "timings": timings,
            "meta": {"ref_files": [d["source"] for d in verified_docs]},
        }, ensure_ascii=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def run_pipeline(params: dict, choice: str | None = None) -> str:
    """통합 진입점. choice 없으면 체크리스트(need_choice) 반환, 있으면 완주(complete).

    Args:
        params: 추출된 활력징후/증상 파라미터
        choice: 사용자 선택 (등급 숫자 또는 체크리스트 항목)
    """
    assessment = json.loads(pre_ktas_assess(params))
    if "error" in assessment:
        return json.dumps({"stage": "error", "error": assessment["error"]}, ensure_ascii=False)

    if not choice:
        return json.dumps({"stage": "need_choice", "assessment": assessment}, ensure_ascii=False)

    choice_data = json.loads(resolve_ktas_choice(choice, assessment.get("checklist", [])))
    if "error" in choice_data:
        return json.dumps({"stage": "error", "error": choice_data["error"]}, ensure_ascii=False)

    assessment["ktas_level"] = choice_data.get("ktas_level")
    assessment["ktas_reasons"] = [choice_data.get("ktas_reason")]
    assessment["ktas_suspect"] = choice_data.get("ktas_suspect")

    ems = json.loads(execute_ems_pipeline(params, assessment))
    if "error" in ems:
        return json.dumps({"stage": "error", "error": ems["error"]}, ensure_ascii=False)

    return json.dumps({"stage": "complete", "assessment": assessment, "ems": ems}, ensure_ascii=False)


def main():
    print(f"🚀 EMS Commander MCP 서버 시작 (http://{config.MCP_HOST}:{config.MCP_PORT})")
    uvicorn.run(mcp.sse_app(), host=config.MCP_HOST, port=config.MCP_PORT)


if __name__ == "__main__":
    main()
