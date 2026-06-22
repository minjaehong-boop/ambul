"""MCP 서버 (SSE) — LLM 기반 pre-KTAS → 사용자 선택 → EMS 지침 파이프라인.

prototype(mark12) 의 동작을 그대로 옮긴다:
  - pre_ktas_assess     : KtasSectionSelector(LLM) 로 섹션 top-3 선정 → 섹션랭크별 체크리스트
  - resolve_ktas_choice : '순위-등급'(1-2) / '순위:항목'(2:호흡곤란) / 등급숫자 / 항목텍스트 매칭
  - execute_ems_pipeline: Selector → 로드 → CRAG → Reader → CoVe (suspect = KTAS 확정 질환)

노출 도구:
  run_pipeline(input_text, params, choice=None)  : 통합 진입점 (need_choice → complete)
  graphrag_search(...)                           : (선택) graphrag_local_vllm 가 있을 때만 동작
"""

import json
import os
import re
import time

import uvicorn
from mcp.server.fastmcp import FastMCP

from . import config
from .agents import ExpertAgent, ProtocolSelector, ReaderAgent, RetrievalEvaluator
from .data import DataManager
from .ktas import (
    KtasSectionSelector,
    KtasSectionStore,
    build_checklist_by_section,
)
from .utils import normalize_symptom_query, normalize_text

mcp = FastMCP("ems-commander-mark10")

# --- 지연 초기화되는 전역 리소스 ---
db_instance = None
evaluator_agent = None
reader_agent = None
expert_agent = None
protocol_selector = None
protocol_desc = None
ktas_store = None
ktas_selector = None


def load_protocol_desc():
    """지침 키워드 목록 문자열. PROTOCOL_DIR 의 .md 파일명을 열거하고, 없으면 인덱스 desc."""
    if os.path.isdir(config.PROTOCOL_DIR):
        keywords = []
        for root, _, files in os.walk(config.PROTOCOL_DIR):
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, filename), config.PROTOCOL_DIR)
                rel_no_ext = os.path.splitext(rel_path)[0].replace("\\", "/")
                keywords.append(rel_no_ext)
        if keywords:
            return "\n".join(sorted(set(keywords)))
    if os.path.exists(config.PROTOCOL_INDEX):
        with open(config.PROTOCOL_INDEX, "r", encoding="utf-8") as f:
            return json.load(f).get("desc", "")
    return ""


def pre_ktas_assess(input_text: str, params: dict) -> str:
    """증상으로 KTAS 섹션을 LLM 선택 → 섹션랭크별 체크리스트를 만든다."""
    global ktas_store, ktas_selector
    started = time.monotonic()

    try:
        if ktas_store is None:
            ktas_store = KtasSectionStore()
        if ktas_selector is None:
            ktas_selector = KtasSectionSelector()
    except Exception as e:
        return json.dumps({"error": f"guideline init failed: {e}"}, ensure_ascii=False)

    symptom_raw = params.get("symptom") or ""
    symptom_query = normalize_symptom_query(symptom_raw)

    special_notes = params.get("special_notes") or []
    if isinstance(special_notes, list):
        notes_text = ", ".join([str(n).strip() for n in special_notes if str(n).strip()])
    else:
        notes_text = str(special_notes).strip()

    selector_query = symptom_query
    if notes_text:
        selector_query = f"{symptom_query}, 특이사항: {notes_text}" if symptom_query else f"특이사항: {notes_text}"

    symptom_sections = []
    selected_titles = []
    if selector_query:
        selected_titles = ktas_selector.select_titles(selector_query, ktas_store.list_titles(), top_k=3)
        if selected_titles:
            symptom_sections = [
                {
                    "title": s.title,
                    "content": s.content,
                    "start_line": s.start_line,
                    "source_file": s.source_file,
                }
                for s in ktas_store.get_sections_by_titles(selected_titles)
            ]
    if not symptom_sections:
        symptom_sections = ktas_store.lexical_search(symptom_query, top_k=1)

    title_to_section = {s.get("title"): s for s in symptom_sections}
    ranked_titles = selected_titles if selected_titles else [s.get("title") for s in symptom_sections]

    section_rankings = []
    ranked_sections = []
    for idx, title in enumerate(ranked_titles[:3], start=1):
        section = title_to_section.get(title)
        if not section:
            continue
        section_rankings.append({
            "rank": idx,
            "title": title,
            "source_file": section.get("source_file"),
        })
        ranked_sections.append(section)

    checklist_by_section = build_checklist_by_section(ranked_sections)
    checklist = []
    for title in ranked_titles:
        checklist.extend(checklist_by_section.get(title) or [])

    guideline_refs = [
        {
            "title": s["title"],
            "start_line": s["start_line"],
            "source_file": s.get("source_file"),
            "preview": s["content"][:200],
        }
        for s in symptom_sections
    ]

    result = {
        "symptom": symptom_query or symptom_raw,
        "required_fields": [],
        "missing_fields": [],
        "ktas_level": None,
        "ktas_reasons": [],
        "status": "need_more_info",
        "allow_early_pipeline": False,
        "section_rankings": section_rankings,
        "checklist_by_section": checklist_by_section,
        "checklist": checklist,
        "guideline_refs": guideline_refs,
        "timings": {"pre_ktas_sec": time.monotonic() - started},
    }
    return json.dumps(result, ensure_ascii=False)


def resolve_ktas_choice(choice: str, checklist: list, section_rankings=None, checklist_by_section=None) -> str:
    """사용자 선택을 KTAS 등급/의심질환으로 확정.

    지원 형식: '순위-등급'(1-2) / '순위:항목'(2:호흡곤란) / 등급숫자(1~5) / 항목 텍스트
    """
    choice_text = normalize_text(choice)
    section_rankings = section_rankings or []
    checklist_by_section = checklist_by_section or {}

    # 1) 순위-등급 (예: 1-2, 2:3)
    match = re.match(r"^\s*([1-3])\s*[:\-\s]\s*([1-5])\s*$", choice_text)
    if match and section_rankings:
        section_idx = int(match.group(1))
        level = match.group(2)
        section = next((s for s in section_rankings if s.get("rank") == section_idx), None)
        if section:
            title = section.get("title")
            items = checklist_by_section.get(title) or []
            selected_item = next((i for i in items if str(i.get("level")) == level), None)
            ktas_suspect = None
            if selected_item:
                ktas_suspect = selected_item.get("disease") or selected_item.get("source") or title
            return json.dumps({
                "ktas_level": level,
                "ktas_reason": f"사용자 선택: {section_idx}순위 {title} - 등급 {level}",
                "ktas_suspect": ktas_suspect or title,
            }, ensure_ascii=False)

    # 2) 순위:항목 (예: 2:호흡곤란)
    match = re.match(r"^\s*([1-3])\s*[:\-]\s*(.+)$", choice_text)
    if match and section_rankings:
        section_idx = int(match.group(1))
        item_text = match.group(2).strip()
        section = next((s for s in section_rankings if s.get("rank") == section_idx), None)
        if section:
            title = section.get("title")
            items = checklist_by_section.get(title) or []
            selected_item = None
            for item in items:
                if item_text and item_text in normalize_text(item.get("text") or ""):
                    selected_item = item
                    break
            if selected_item:
                return json.dumps({
                    "ktas_level": selected_item.get("level"),
                    "ktas_reason": f"사용자 선택: {section_idx}순위 {title} - 항목 {selected_item.get('text')}",
                    "ktas_suspect": selected_item.get("disease") or selected_item.get("source") or title,
                }, ensure_ascii=False)

    # 3) 등급 숫자 단독
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

    # 4) 항목 텍스트 매칭
    for item in checklist or []:
        if choice_text and choice_text in normalize_text(item.get("text") or ""):
            return json.dumps({
                "ktas_level": item.get("level"),
                "ktas_reason": f"사용자 선택 항목: {item.get('text')}",
                "ktas_suspect": item.get("disease") or item.get("source"),
            }, ensure_ascii=False)

    return json.dumps({"error": "choice_not_matched"}, ensure_ascii=False)


def execute_ems_pipeline(input_text: str, params: dict, assessment=None) -> str:
    """지침 선정 → 로드 → CRAG → 보고서 작성 → CoVe 검증. suspect 는 KTAS 확정 질환."""
    global db_instance, evaluator_agent, reader_agent, expert_agent, protocol_selector, protocol_desc

    if db_instance is None:
        try:
            db_instance = DataManager()
            evaluator_agent = RetrievalEvaluator()
            reader_agent = ReaderAgent()
            expert_agent = ExpertAgent()
        except Exception as e:
            return json.dumps({"error": f"초기화 실패: {str(e)}"}, ensure_ascii=False)

    try:
        pipeline_start = time.monotonic()
        if protocol_selector is None:
            protocol_selector = ProtocolSelector()
        if protocol_desc is None:
            protocol_desc = load_protocol_desc()

        assessment = assessment or {}
        ktas_level = assessment.get("ktas_level")
        ktas_reasons = assessment.get("ktas_reasons", [])
        # 불변식: ProtocolSelector 에 넘기는 suspect 는 'KTAS 확정 질환'이어야 한다.
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
def run_pipeline(input_text: str, params: dict, choice: str | None = None) -> str:
    """통합 진입점. choice 없으면 체크리스트(need_choice) 반환, 있으면 완주(complete).

    Args:
        input_text: 구급대원 보고 원문
        params: 추출된 활력징후/증상 파라미터
        choice: 사용자 선택 ('순위-등급' / '순위:항목' / 등급 숫자 / 항목 텍스트)
    """
    assessment = json.loads(pre_ktas_assess(input_text, params))
    if "error" in assessment:
        return json.dumps({"stage": "error", "error": assessment["error"]}, ensure_ascii=False)

    if not choice:
        return json.dumps({"stage": "need_choice", "assessment": assessment}, ensure_ascii=False)

    choice_data = json.loads(resolve_ktas_choice(
        choice,
        assessment.get("checklist", []),
        assessment.get("section_rankings", []),
        assessment.get("checklist_by_section", {}),
    ))
    if "error" in choice_data:
        return json.dumps({"stage": "error", "error": choice_data["error"]}, ensure_ascii=False)

    assessment["ktas_level"] = choice_data.get("ktas_level")
    assessment["ktas_reasons"] = [choice_data.get("ktas_reason")]
    assessment["ktas_suspect"] = choice_data.get("ktas_suspect")
    assessment["status"] = "complete"

    ems = json.loads(execute_ems_pipeline(input_text, params, assessment))
    if "error" in ems:
        return json.dumps({"stage": "error", "error": ems["error"]}, ensure_ascii=False)

    return json.dumps({"stage": "complete", "assessment": assessment, "ems": ems}, ensure_ascii=False)


# ----------------- (선택) GraphRAG 검색 도구 -----------------
# graphrag_local_vllm 모듈이 호스트에 있을 때만 동작한다. 없으면 안내 메시지 반환.

@mcp.tool()
def graphrag_search(
    query: str,
    top_k: int = 20,
    rerank: bool = True,
    rerank_limit: int = 10,
    chunk_size: int = 1024,
    delimiter: str | None = None,
    heading_split: bool = True,
    embed_model: str = "Qwen/Qwen3-Embedding-0.6B",
    embed_base_url: str = "http://localhost:8001/v1",
    embed_batch: int = 32,
    embed_cache_dir: str | None = None,
    rerank_model: str = "zeroentropy/zerank-2",
    debug_rerank: bool = False,
    file_paths: list[str] | None = None,
) -> str:
    """(선택) KTAS 규정집 등에 대한 독립 임베딩 검색. graphrag_local_vllm 필요."""
    try:
        import graphrag_local_vllm as gr
    except Exception:
        return json.dumps(
            {"error": "graphrag_local_vllm 모듈이 없어 graphrag_search 를 사용할 수 없습니다."},
            ensure_ascii=False,
        )

    if rerank_limit < 2 or rerank_limit > 20 or rerank_limit % 2 != 0:
        return json.dumps({"error": "rerank_limit must be 2..20 (step 2)"}, ensure_ascii=False)

    if embed_cache_dir is None:
        embed_cache_dir = os.path.join(config.BOX_ROOT, ".local_rag")

    paths = file_paths or config.ktas_guideline_paths()
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return json.dumps({"error": "no valid paths found"}, ensure_ascii=False)

    chunks: list[str] = []
    chunk_meta: list[dict] = []
    for path in paths:
        text = gr.read_text(path)
        for c in gr.chunk_markdown(text, chunk_size, delimiter, heading_split):
            chunk_meta.append({"source_file": path})
            chunks.append(c)

    if not chunks:
        return json.dumps({"error": "no chunks created"}, ensure_ascii=False)

    os.makedirs(embed_cache_dir, exist_ok=True)
    cache_file = os.path.join(embed_cache_dir, f"emb_cache_{gr.model_cache_name(embed_model)}.json")

    q_vec = gr.embed_texts(embed_base_url, embed_model, [query])[0]
    c_vecs, cache_hits, cache_misses = gr.get_chunk_embeddings_with_cache(
        embed_base_url, embed_model, chunks, embed_batch, cache_file,
    )
    sims = [(i, gr.cosine(q_vec, c_vecs[i])) for i in range(len(chunks))]
    sims.sort(key=lambda x: x[1], reverse=True)
    base_rank = sims[: min(top_k, len(sims))]
    ranked = list(base_rank)

    reranked = None
    if rerank:
        base_idx = [i for i, _ in ranked[: min(rerank_limit, len(ranked))]]
        rr = gr.llm_rerank(rerank_model, query, [chunks[i] for i in base_idx], debug_rerank)
        if rr:
            reranked = [(base_idx[i], score) for i, score in rr]
            ranked = reranked + base_rank[len(reranked):]

    candidates = []
    for i, s in ranked[: min(top_k, len(ranked))]:
        text = chunks[i]
        first_line = text.strip().splitlines()[0] if text.strip() else ""
        candidates.append({
            "id": i,
            "score": s,
            "title": first_line,
            "preview": text.strip()[:200],
            "source_file": chunk_meta[i].get("source_file"),
        })

    return json.dumps({
        "query": query,
        "paths": paths,
        "top_k": top_k,
        "rerank": bool(reranked),
        "embedding_cache": cache_file,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "candidates": candidates,
    }, ensure_ascii=False)


def main():
    print(f"🚀 EMS Commander(mark10) MCP 서버 시작 (http://{config.MCP_HOST}:{config.MCP_PORT})")
    uvicorn.run(mcp.sse_app(), host=config.MCP_HOST, port=config.MCP_PORT)


if __name__ == "__main__":
    main()
