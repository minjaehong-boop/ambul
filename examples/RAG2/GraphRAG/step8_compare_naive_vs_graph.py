from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever, VectorCypherRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j_graphrag.generation import GraphRAG
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPENROUTER_KEY = BASE_DIR.joinpath("openrouter_key.txt").read_text(encoding="utf-8").strip()

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "galaxy2816*")
DATABASE = "neo4j"
INDEX_NAME = "chunk_vector_index"

driver = GraphDatabase.driver(URI, auth=AUTH)

embedder = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
)

llm = OpenAILLM(
    model_name="moonshotai/kimi-k2-0905",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_params={"temperature": 0},
)

# Naive RAG: 청크 텍스트만 컨텍스트로 사용
naive_retriever = VectorRetriever(
    driver=driver,
    index_name=INDEX_NAME,
    embedder=embedder,
    neo4j_database=DATABASE,
)

# GraphRAG: 검색된 청크 + 청크에 연결된 엔티티와 관계까지 컨텍스트로 사용
GRAPH_TRAVERSAL_QUERY = """
WITH node AS chunk, score
OPTIONAL MATCH (chunk)<-[:FROM_CHUNK]-(e)
OPTIONAL MATCH (e)-[r]->(e2)
WHERE NOT e2:Chunk AND NOT e2:Document
WITH chunk, score,
     collect(DISTINCT e.name) AS entities,
     collect(DISTINCT e.name + ' -[' + type(r) + ']-> ' + e2.name) AS relations
RETURN chunk.text AS text,
       score,
       'ENTITIES: ' + apoc.text.join(entities, ', ') +
       '\\nRELATIONS: ' + apoc.text.join(relations, '; ') AS graph_context
"""

graph_retriever = VectorCypherRetriever(
    driver=driver,
    index_name=INDEX_NAME,
    embedder=embedder,
    retrieval_query=GRAPH_TRAVERSAL_QUERY,
    neo4j_database=DATABASE,
)

naive_rag = GraphRAG(retriever=naive_retriever, llm=llm)
graph_rag = GraphRAG(retriever=graph_retriever, llm=llm)

#QUESTION = "Transformers architecture를 아주 자세하게 설명해줘."
QUESTION = "이 논문에서 가장 많은 관계를 가진 핵심 개념 상위 5개를 degree 순으로 알려줘."
print("=" * 80)
print(f"QUESTION: {QUESTION}")
print("=" * 80)

print("\n" + "#" * 80)
print("# NAIVE RAG (VectorRetriever - 청크 텍스트만)")
print("#" * 80)
naive_response = naive_rag.search(query_text=QUESTION, retriever_config={"top_k": 5})
print(naive_response.answer)

print("\n" + "#" * 80)
print("# GRAPH RAG (VectorCypherRetriever - 청크 + 엔티티/관계)")
print("#" * 80)
graph_response = graph_rag.search(query_text=QUESTION, retriever_config={"top_k": 5})
print(graph_response.answer)
