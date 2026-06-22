from neo4j import GraphDatabase
from neo4j_graphrag.experimental.components.neo4j_reader import Neo4jChunkReader

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "galaxy2816*")
DATABASE = "neo4j"

driver = GraphDatabase.driver(URI, auth=AUTH)
reader = Neo4jChunkReader(driver=driver, neo4j_database=DATABASE)

print(reader)
