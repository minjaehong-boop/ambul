from neo4j import GraphDatabase
from neo4j_graphrag.indexes import create_vector_index

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "galaxy2816*")
DATABASE = "neo4j"

INDEX_NAME = "chunk_vector_index"
EMBEDDING_DIMENSION = 3072

driver = GraphDatabase.driver(URI, auth=AUTH)

create_vector_index(
    driver,
    name=INDEX_NAME,
    label="Chunk",
    embedding_property="embedding",
    dimensions=EMBEDDING_DIMENSION,
    similarity_fn="cosine",
    neo4j_database=DATABASE,
)

print(f"Vector index '{INDEX_NAME}' created.")
