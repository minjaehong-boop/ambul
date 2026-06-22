"""
Triage RAG (PageIndex edition): Structure-aware, vectorless RAG pipeline.

Flow:
  User query
    → _decompose(query, session_history)
    → parallel:
        KTAS:     chapter_select → page_select → fetch → generate
        Protocol: chapter_select → page_select → fetch → generate
    → synthesize
    → self_correct
    → stream output + save to session
"""

import concurrent.futures
import json
import logging
import os
from typing import Dict, Generator, List, Optional

import pdfplumber
import yaml
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from chain_server.base import BaseExample
from chain_server.tracing import langchain_instrumentation_class_wrapper
from chain_server.utils import get_config

logger = logging.getLogger(__name__)
settings = get_config()

# ---------------------------------------------------------------------------
# Document paths (PageIndex pre-built artifacts)
# ---------------------------------------------------------------------------
_PAGEINDEX_ROOT = os.environ.get(
    "PAGEINDEX_ROOT",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts")),
)
_KTAS_PDF = os.path.join(_PAGEINDEX_ROOT, "docs", "2021_KTAS_guideline.pdf")
_PROTOCOL_PDF = os.path.join(_PAGEINDEX_ROOT, "docs", "표준지침_처치지침_알고리즘_테스트_최종.pdf")
_KTAS_STRUCTURE_FILE = os.path.join(_PAGEINDEX_ROOT, "results", "2021_KTAS_guideline_structure.json")
_PROTOCOL_STRUCTURE_FILE = os.path.join(_PAGEINDEX_ROOT, "results", "표준지침_처치지침_알고리즘_테스트_최종_structure.json")

with open(_KTAS_STRUCTURE_FILE, encoding="utf-8") as _f:
    _KTAS_STRUCT = json.load(_f)

with open(_PROTOCOL_STRUCTURE_FILE, encoding="utf-8") as _f:
    _PROTOCOL_STRUCT = json.load(_f)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "../config/prompt/pageindex_prompt.yaml")
with open(_PROMPT_FILE, encoding="utf-8") as _f:
    _PROMPTS = yaml.safe_load(_f)

# ---------------------------------------------------------------------------
# Per-session conversation history
# ---------------------------------------------------------------------------
_sessions: Dict[str, List[dict]] = {}
_MAX_HISTORY = 10


def _get_history(session_id: str) -> List[dict]:
    return _sessions.get(session_id, [])


def _save_to_session(session_id: str, query: str, answer: str) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": "user", "content": query})
    _sessions[session_id].append({"role": "assistant", "content": answer})
    _sessions[session_id] = _sessions[session_id][-(2 * _MAX_HISTORY):]


def _history_to_text(session_id: str, max_chars: int = 300) -> str:
    history = _get_history(session_id)
    if not history:
        return "없음"
    return "\n".join(f"{m['role']}: {m['content'][:max_chars]}" for m in history)


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------
def _llm(**kwargs) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm.model_name,
        base_url=settings.llm.server_url,
        api_key="EMPTY",
        temperature=kwargs.get("temperature", 0.2),
        top_p=kwargs.get("top_p", 0.7),
        max_tokens=kwargs.get("max_tokens", 1024),
    )


def _strip_think(content: str) -> str:
    """Remove Qwen3 <think>...</think> tags."""
    if "<think>" in content:
        content = content[content.rfind("</think>") + 8:].strip()
    return content


# ---------------------------------------------------------------------------
# Document structure helpers
# ---------------------------------------------------------------------------
def _flatten_structure(nodes: list, depth: int = 0, max_depth: int = 99) -> List[dict]:
    result = []
    for node in nodes:
        result.append({
            "indent": "  " * depth,
            "title": node.get("title", ""),
            "node_id": node.get("node_id", ""),
            "start": node.get("start_index", "?"),
            "end": node.get("end_index", "?"),
            "summary": (node.get("summary") or "")[:150],
        })
        if node.get("nodes") and depth < max_depth:
            result.extend(_flatten_structure(node["nodes"], depth + 1, max_depth))
    return result


def _structure_to_text(structure_data: dict, max_depth: int = 99) -> str:
    sections = _flatten_structure(structure_data.get("structure", []), max_depth=max_depth)
    lines = []
    for s in sections:
        pages = f"p.{s['start']}-{s['end']}" if s['start'] != s['end'] else f"p.{s['start']}"
        lines.append(f"[{s['node_id']}] {s['indent']}{s['title']} ({pages})")
        if s["summary"] and max_depth > 0:
            lines.append(f"       → {s['summary']}")
    return "\n".join(lines)


def _get_children_of_nodes(nodes: list, node_ids: list) -> list:
    result = []
    for node in nodes:
        if node.get("node_id") in node_ids:
            children = node.get("nodes", [])
            result.extend(children if children else [node])
        elif node.get("nodes"):
            result.extend(_get_children_of_nodes(node["nodes"], node_ids))
    return result


# ---------------------------------------------------------------------------
# PDF page reader
# ---------------------------------------------------------------------------
def _parse_pages(pages_str: str) -> List[int]:
    result = []
    for part in pages_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            result.extend(range(int(lo.strip()), int(hi.strip()) + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def _fetch_pdf_pages(pdf_path: str, pages_str: str, max_pages: int = 15) -> str:
    try:
        page_nums = _parse_pages(pages_str)[:max_pages]
        texts = []
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
            for p in page_nums:
                if 1 <= p <= total:
                    content = pdf.pages[p - 1].extract_text() or ""
                    if content.strip():
                        texts.append(f"[페이지 {p}]\n{content.strip()}")
        return "\n\n---\n\n".join(texts) if texts else "해당 페이지에서 내용을 추출할 수 없습니다."
    except Exception as e:
        logger.warning(f"PDF read error ({pdf_path}): {e}")
        return "PDF 읽기 실패"


# ---------------------------------------------------------------------------
# 2-step section selection: chapter → page
# ---------------------------------------------------------------------------
def _select_sections_two_step(query: str, structure_data: dict, **kwargs) -> str:
    top_nodes = structure_data.get("structure", [])
    llm = _llm(**kwargs)

    # Step 1: Chapter selection (depth=0 only)
    chapter_text = _structure_to_text({"structure": top_nodes}, max_depth=0)
    chapter_prompt = (
        _PROMPTS["chapter_select_prompt"]
        .replace("{{ query }}", query)
        .replace("{{ structure }}", chapter_text)
    )
    try:
        resp = llm.invoke([HumanMessage(content=chapter_prompt)])
        content = _strip_think(resp.content.strip())
        node_ids = json.loads(content).get("node_ids", [])
        logger.info(f"[pageindex] Chapter selected: {node_ids}")
    except Exception as e:
        logger.warning(f"Chapter selection failed ({e}), using first 3 chapters")
        node_ids = [n.get("node_id") for n in top_nodes[:3]]

    # Step 2: Page selection within selected chapters
    children = _get_children_of_nodes(top_nodes, node_ids)
    if not children:
        children = top_nodes[:3]

    detail_text = _structure_to_text({"structure": children}, max_depth=1)
    detail_prompt = (
        _PROMPTS["section_select_prompt"]
        .replace("{{ query }}", query)
        .replace("{{ structure }}", detail_text)
    )
    try:
        resp2 = llm.invoke([HumanMessage(content=detail_prompt)])
        content2 = _strip_think(resp2.content.strip())
        pages_str = json.loads(content2).get("pages", "").strip()
        logger.info(f"[pageindex] Section selected for '{query[:60]}': pages={pages_str}")
        return pages_str if pages_str else "1-5"
    except Exception as e:
        logger.warning(f"Section selection (step 2) failed ({e}), using first 5 pages")
        return "1-5"


# ---------------------------------------------------------------------------
# Domain RAG
# ---------------------------------------------------------------------------
def _pageindex_domain_rag(
    sub_query: str,
    pdf_path: str,
    structure_data: dict,
    prompt_template: str,
    session_id: str,
    **kwargs,
) -> str:
    pages_str = _select_sections_two_step(sub_query, structure_data, **kwargs)
    context_text = _fetch_pdf_pages(pdf_path, pages_str)
    history_text = _history_to_text(session_id)

    filled_prompt = (
        prompt_template
        .replace("{{ context }}", context_text)
        .replace("{{ history }}", history_text)
        .replace("{{ metadata }}", f"참조 페이지: {pages_str}")
        .replace("{{ query }}", sub_query)
    )

    llm = _llm(**kwargs)
    response = llm.invoke([HumanMessage(content=filled_prompt)])
    return response.content


# ---------------------------------------------------------------------------
# Self-correction
# ---------------------------------------------------------------------------
def _self_correct(answer: str, **kwargs) -> str:
    correction_prompt = _PROMPTS["self_correction_prompt"].replace("{{ answer }}", answer)
    llm = _llm(**kwargs)
    try:
        resp = llm.invoke([HumanMessage(content=correction_prompt)])
        corrected = _strip_think(resp.content.strip())
        if corrected == "OK":
            logger.info("[triage_pageindex] Self-correction: no issues found")
            return answer
        logger.info("[triage_pageindex] Self-correction applied")
        return corrected
    except Exception as e:
        logger.warning(f"Self-correction failed ({e}), using original answer")
        return answer


# ---------------------------------------------------------------------------
# Main chatbot class
# ---------------------------------------------------------------------------
@langchain_instrumentation_class_wrapper
class TriagePageIndexChatbot(BaseExample):

    def ingest_docs(self, filepath: str, filename: str) -> None:
        raise ValueError(
            "triage_rag_pageindex는 문서 업로드가 필요 없습니다. "
            "사전 구축된 PageIndex 구조 JSON을 사용합니다.\n"
            f"  KTAS: {_KTAS_STRUCTURE_FILE}\n"
            f"  처치: {_PROTOCOL_STRUCTURE_FILE}"
        )

    def llm_chain(self, query: str, chat_history, **kwargs) -> Generator[str, None, None]:
        llm = _llm(**kwargs)
        prompt = ChatPromptTemplate.from_messages([("user", "{query}")])
        chain = prompt | llm | StrOutputParser()
        return chain.stream({"query": query}, config={"callbacks": [self.cb_handler]})

    def rag_chain(self, query: str, chat_history, **kwargs) -> Generator[str, None, None]:
        """
        Full PageIndex triage pipeline:
          decompose → [ktas_rag ‖ protocol_rag] (parallel) → synthesize → self_correct
        """
        session_id: str = kwargs.pop("session_id", None) or "default"
        logger.info(f"[triage_pageindex] Session={session_id} | Query: {query}")

        # Step 1: Query decomposition
        sub_queries = self._decompose(query, session_id, **kwargs)
        ktas_query = sub_queries.get("ktas_query", query)
        protocol_query = sub_queries.get("protocol_query", query)
        logger.info(f"[triage_pageindex] KTAS sub-query: {ktas_query}")
        logger.info(f"[triage_pageindex] Protocol sub-query: {protocol_query}")

        # Step 2: Parallel domain RAG
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            ktas_future = executor.submit(
                _pageindex_domain_rag,
                ktas_query, _KTAS_PDF, _KTAS_STRUCT,
                _PROMPTS["ktas_rag_prompt"], session_id, **kwargs
            )
            protocol_future = executor.submit(
                _pageindex_domain_rag,
                protocol_query, _PROTOCOL_PDF, _PROTOCOL_STRUCT,
                _PROMPTS["protocol_rag_prompt"], session_id, **kwargs
            )
            ktas_answer = ktas_future.result()
            protocol_answer = protocol_future.result()

        logger.info(f"[triage_pageindex] KTAS answer length: {len(ktas_answer)}")
        logger.info(f"[triage_pageindex] Protocol answer length: {len(protocol_answer)}")

        # Step 3: Synthesis
        synthesis_text = (
            _PROMPTS["synthesis_prompt"]
            .replace("{{ ktas_answer }}", ktas_answer)
            .replace("{{ protocol_answer }}", protocol_answer)
            .replace("{{ query }}", query)
        )
        llm = _llm(**kwargs)
        prompt = ChatPromptTemplate.from_messages([("user", "{synthesis}")])
        chain = prompt | llm | StrOutputParser()

        raw_answer = ""
        for chunk in chain.stream({"synthesis": synthesis_text}, config={"callbacks": [self.cb_handler]}):
            raw_answer += chunk

        # Step 4: Self-correction
        final_answer = _self_correct(raw_answer, **kwargs)

        # Step 5: Save to session history
        _save_to_session(session_id, query, final_answer)

        chunk_size = 80
        for i in range(0, len(final_answer), chunk_size):
            yield final_answer[i:i + chunk_size]

    def _decompose(self, query: str, session_id: str, **kwargs) -> dict:
        history_text = _history_to_text(session_id)
        decompose_text = (
            _PROMPTS["decompose_prompt"]
            .replace("{{ history }}", history_text)
            .replace("{{ query }}", query)
        )
        llm = _llm(**kwargs)
        try:
            response = llm.invoke([HumanMessage(content=decompose_text)])
            content = _strip_think(response.content.strip())
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Query decomposition failed ({e}), using original query for both")
            return {"ktas_query": query, "protocol_query": query}
