from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j_graphrag.generation import GraphRAG
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPENROUTER_KEY = BASE_DIR.joinpath("openrouter_key.txt").read_text(encoding="utf-8").strip()

URI = "neo4j://localhost:7687"

#AUTH = ("neo4j", "12345678")
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
    model_name="google/gemini-2.5-flash-lite",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_params={"temperature": 0},
)

retriever = VectorRetriever(
    driver=driver,
    index_name=INDEX_NAME,
    embedder=embedder,
    neo4j_database=DATABASE,
)

rag = GraphRAG(retriever=retriever, llm=llm)

QUESTION = "전신 쇠약이 심하면 어떤 증상과 관련이 있나요?"

response = rag.search(
    query_text=QUESTION,
    retriever_config={"top_k": 5},
    return_context=True,
)

print("=" * 80)
print("ANSWER")
print("=" * 80)
print(response.answer)

print("\n" + "=" * 80)
print("RETRIEVED CHUNKS")
print("=" * 80)

chunk_ids = []
for i, item in enumerate(response.retriever_result.items, start=1):
    print(f"\n[Chunk {i}] score-meta: {item.metadata}")
    print(item.content[:300].replace("\n", " ") + ("..." if len(item.content) > 300 else ""))
    meta = item.metadata or {}
    cid = meta.get("id") or meta.get("chunk_id")
    if cid is not None:
        chunk_ids.append(cid)

print("\n" + "=" * 80)
print("ENTITIES & RELATIONS LINKED TO RETRIEVED CHUNKS")
print("=" * 80)

with driver.session(database=DATABASE) as session:
    result = session.run(
        """
        MATCH (c:Chunk)
        WHERE c.id IN $ids OR elementId(c) IN $ids
        OPTIONAL MATCH (c)<-[:FROM_CHUNK]-(e)
        OPTIONAL MATCH (e)-[r]->(e2)
        WHERE NOT e2:Chunk AND NOT e2:Document
        RETURN c.id AS chunk_id,
               collect(DISTINCT {label: labels(e), name: e.name, id: e.id}) AS entities,
               collect(DISTINCT {from: e.name, type: type(r), to: e2.name}) AS relations
        """,
        ids=chunk_ids,
    )
    for record in result:
        print(f"\nChunk {record['chunk_id']}")
        ents = [e for e in record["entities"] if e["name"]]
        rels = [r for r in record["relations"] if r["from"] and r["to"]]
        print(f"  Entities ({len(ents)}):")
        for e in ents[:20]:
            print(f"    - {e['label']} {e['name']}")
        print(f"  Relations ({len(rels)}):")
        for r in rels[:20]:
            print(f"    - ({r['from']}) -[{r['type']}]-> ({r['to']})")
