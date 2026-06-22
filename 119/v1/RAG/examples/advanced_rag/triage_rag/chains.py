"""
Triage RAG: Combined KTAS assessment + Emergency Protocol pipeline.

Flow:
  User query
    → Query Decomposition LLM → (ktas_query, protocol_query)
    → [KTAS RAG | Protocol RAG] (each: embed×3 + rerank×3)
    → Answer Synthesis LLM → Final output

Collections:
  ktas_db        - KTAS reference documents
  protocol_db    - Emergency protocol documents
  triage_conv    - Shared conversation history (Q&A pairs)
  triage_meta    - Shared retrieval metadata (previously hit sources)
"""

import json
import logging
import os
from typing import Generator, List

import requests
import yaml
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from RAG.src.chain_server.base import BaseExample
from RAG.src.chain_server.tracing import langchain_instrumentation_class_wrapper
from RAG.src.chain_server.utils import (
    create_vectorstore_langchain,
    get_config,
    get_embedding_model,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singletons
# ---------------------------------------------------------------------------
document_embedder = get_embedding_model()
settings = get_config()

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompt.yaml")
with open(_PROMPT_FILE) as f:
    _PROMPTS = yaml.safe_load(f)

# Milvus collections
_ktas_store = create_vectorstore_langchain(document_embedder, collection_name="ktas_db")
_protocol_store = create_vectorstore_langchain(document_embedder, collection_name="protocol_db")
_conv_store = create_vectorstore_langchain(document_embedder, collection_name="triage_conv")
_meta_store = create_vectorstore_langchain(document_embedder, collection_name="triage_meta")

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


# ---------------------------------------------------------------------------
# Reranker (vLLM /v1/rerank)
# ---------------------------------------------------------------------------
def _rerank(query: str, docs: List[Document], top_n: int) -> List[Document]:
    """Call vLLM reranker endpoint and return top_n documents sorted by score."""
    if not docs:
        return docs

    rerank_url = settings.ranking.server_url.rstrip("/") + "/rerank"
    texts = [d.page_content for d in docs]
    try:
        resp = requests.post(
            rerank_url,
            json={
                "model": settings.ranking.model_name,
                "query": query,
                "documents": texts,
                "top_n": top_n,
            },
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        ranked = sorted(results, key=lambda x: x["relevance_score"], reverse=True)
        return [docs[r["index"]] for r in ranked[:top_n]]
    except Exception as e:
        logger.warning(f"Reranker call failed ({e}), using original order")
        return docs[:top_n]


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------
def _retrieve(store, query: str, top_k: int = 10) -> List[Document]:
    """Embed-based retrieval from a Milvus collection."""
    try:
        retriever = store.as_retriever(search_kwargs={"k": top_k})
        return retriever.invoke(query)
    except Exception as e:
        logger.warning(f"Retrieval failed: {e}")
        return []


def _docs_to_text(docs: List[Document]) -> str:
    if not docs:
        return "No relevant information found."
    return "\n\n---\n\n".join(d.page_content for d in docs)


def _meta_to_text(docs: List[Document]) -> str:
    if not docs:
        return "No previous retrieval metadata."
    return "\n".join(d.page_content for d in docs)


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------
def _save_conversation(query: str, answer: str) -> None:
    """Save Q&A pair to conv_store for future history retrieval."""
    try:
        _conv_store.add_documents([
            Document(page_content=f"User previously asked: {query}"),
            Document(page_content=f"Agent previously answered: {answer}"),
        ])
    except Exception as e:
        logger.warning(f"Failed to save conversation: {e}")


def _save_metadata(query: str, docs: List[Document], label: str) -> None:
    """Save retrieval metadata (source + content preview) to meta_store."""
    try:
        meta_docs = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            preview = doc.page_content[:120].replace("\n", " ")
            meta_docs.append(Document(
                page_content=f"[{label}] Query: '{query}' | Source: {source} | Preview: {preview}"
            ))
        if meta_docs:
            _meta_store.add_documents(meta_docs)
    except Exception as e:
        logger.warning(f"Failed to save metadata: {e}")


# ---------------------------------------------------------------------------
# Sub-pipeline: single domain RAG (embed×3 + rerank×3)
# ---------------------------------------------------------------------------
def _domain_rag(sub_query: str, domain_store, prompt_template: str, top_k: int = 4, **kwargs) -> str:
    """
    Run RAG for one domain (KTAS or Protocol).
    Retrieves from: domain_store, conv_store, meta_store.
    Reranks each result set independently.
    """
    top_initial = max(top_k * 3, 12)

    # --- Embed phase (3×) ---
    raw_docs = _retrieve(domain_store, sub_query, top_k=top_initial)
    raw_history = _retrieve(_conv_store, sub_query, top_k=top_initial)
    raw_meta = _retrieve(_meta_store, sub_query, top_k=top_initial)

    # --- Rerank phase (3×) ---
    docs = _rerank(sub_query, raw_docs, top_n=top_k)
    history = _rerank(sub_query, raw_history, top_n=top_k)
    meta = _rerank(sub_query, raw_meta, top_n=top_k)

    # --- Save metadata of what was retrieved ---
    _save_metadata(sub_query, docs, label=domain_store.collection_name if hasattr(domain_store, "collection_name") else "domain")

    # --- Generate answer ---
    context_text = _docs_to_text(docs)
    history_text = _docs_to_text(history)
    meta_text = _meta_to_text(meta)

    filled_prompt = (
        prompt_template
        .replace("{{ context }}", context_text)
        .replace("{{ history }}", history_text)
        .replace("{{ metadata }}", meta_text)
        .replace("{{ query }}", sub_query)
    )

    llm = _llm(**kwargs)
    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=filled_prompt)])
    return response.content


# ---------------------------------------------------------------------------
# Main chatbot class
# ---------------------------------------------------------------------------
@langchain_instrumentation_class_wrapper
class TriageChatbot(BaseExample):

    def ingest_docs(self, filepath: str, filename: str) -> None:
        """Ingest document into the appropriate collection based on filename."""
        if not filename.endswith((".txt", ".pdf", ".md")):
            raise ValueError(f"{filename} is not a valid Text, PDF or Markdown file")

        if "ktas" in filename.lower():
            target_store = _ktas_store
            collection_label = "ktas_db"
        elif "protocol" in filename.lower():
            target_store = _protocol_store
            collection_label = "protocol_db"
        else:
            raise ValueError(
                f"Cannot determine collection for '{filename}'. "
                "Filename must contain 'ktas' or 'protocol'."
            )

        try:
            raw_docs = UnstructuredFileLoader(filepath).load()
            if not raw_docs:
                logger.warning("No documents loaded from file.")
                return

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.text_splitter.chunk_size,
                chunk_overlap=settings.text_splitter.chunk_overlap,
            )
            chunks = splitter.split_documents(raw_docs)
            target_store.add_documents(chunks)
            logger.info(f"Ingested {len(chunks)} chunks into '{collection_label}' from '{filename}'")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            raise ValueError("Failed to upload document. Please upload an unstructured text document.")

    def llm_chain(self, query: str, chat_history, **kwargs) -> Generator[str, None, None]:
        """Simple LLM chain (no KB) - direct answer."""
        llm = _llm(**kwargs)
        prompt = ChatPromptTemplate.from_messages([("user", "{query}")])
        chain = prompt | llm | StrOutputParser()
        return chain.stream({"query": query}, config={"callbacks": [self.cb_handler]})

    def rag_chain(self, query: str, chat_history, **kwargs) -> Generator[str, None, None]:
        """
        Full triage RAG pipeline:
          decompose → [ktas_rag, protocol_rag] → synthesize
        """
        logger.info(f"[triage_rag] Query: {query}")

        # --- Step 1: Query decomposition ---
        sub_queries = self._decompose(query, **kwargs)
        ktas_query = sub_queries.get("ktas_query", query)
        protocol_query = sub_queries.get("protocol_query", query)
        logger.info(f"[triage_rag] KTAS sub-query: {ktas_query}")
        logger.info(f"[triage_rag] Protocol sub-query: {protocol_query}")

        # --- Step 2: Domain RAG (each: embed×3 + rerank×3) ---
        ktas_answer = _domain_rag(
            ktas_query, _ktas_store, _PROMPTS["ktas_rag_prompt"], **kwargs
        )
        protocol_answer = _domain_rag(
            protocol_query, _protocol_store, _PROMPTS["protocol_rag_prompt"], **kwargs
        )
        logger.info(f"[triage_rag] KTAS answer length: {len(ktas_answer)}")
        logger.info(f"[triage_rag] Protocol answer length: {len(protocol_answer)}")

        # --- Step 3: Answer synthesis (streaming) ---
        synthesis_text = (
            _PROMPTS["synthesis_prompt"]
            .replace("{{ ktas_answer }}", ktas_answer)
            .replace("{{ protocol_answer }}", protocol_answer)
            .replace("{{ query }}", query)
        )

        llm = _llm(**kwargs)
        prompt = ChatPromptTemplate.from_messages([("user", "{synthesis}")])
        chain = prompt | llm | StrOutputParser()

        resp_str = ""
        for chunk in chain.stream({"synthesis": synthesis_text}, config={"callbacks": [self.cb_handler]}):
            yield chunk
            resp_str += chunk

        # --- Step 4: Save to memory ---
        _save_conversation(query, resp_str)

    def _decompose(self, query: str, **kwargs) -> dict:
        """Split user query into ktas_query and protocol_query."""
        decompose_text = _PROMPTS["decompose_prompt"].replace("{{ query }}", query)
        llm = _llm(**kwargs)
        from langchain_core.messages import HumanMessage
        try:
            response = llm.invoke([HumanMessage(content=decompose_text)])
            content = response.content.strip()
            # Strip thinking tags if present (Qwen3 thinking mode)
            if "<think>" in content:
                content = content[content.rfind("</think>") + 8:].strip()
            return json.loads(content)
        except Exception as e:
            logger.warning(f"Query decomposition failed ({e}), using original query for both")
            return {"ktas_query": query, "protocol_query": query}
