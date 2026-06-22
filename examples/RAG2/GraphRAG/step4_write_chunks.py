from langchain_text_splitters import RecursiveCharacterTextSplitter
from neo4j_graphrag.experimental.components.text_splitters.langchain import LangChainTextSplitterAdapter
from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
from neo4j_graphrag.experimental.components.lexical_graph import LexicalGraphBuilder
from neo4j_graphrag.experimental.components.kg_writer import Neo4jWriter
from neo4j_graphrag.experimental.components.types import LexicalGraphConfig, DocumentInfo
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j import GraphDatabase
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPENROUTER_KEY = BASE_DIR.joinpath("openrouter_key.txt").read_text(encoding="utf-8").strip()

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "galaxy2816*")
DATABASE = "neo4j"

driver = GraphDatabase.driver(URI, auth=AUTH)

splitter = LangChainTextSplitterAdapter(
    RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=400)
)

embedder = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
)
chunk_embedder = TextChunkEmbedder(embedder)

lexical_graph_config = LexicalGraphConfig()
lexical_graph_builder = LexicalGraphBuilder(config=lexical_graph_config)
writer = Neo4jWriter(driver=driver, neo4j_database=DATABASE)


async def main():
    text = BASE_DIR.joinpath("2021_KTAS_guideline.md").read_text(encoding="utf-8")

    chunks = await splitter.run(text=text)
    embedded_chunks = await chunk_embedder.run(text_chunks=chunks)

    document_info = DocumentInfo(path="2021_KTAS_guideline.md")
    graph_result = await lexical_graph_builder.run(
        text_chunks=embedded_chunks,
        document_info=document_info,
    )

    await writer.run(
        graph=graph_result.graph,
        lexical_graph_config=lexical_graph_config,
    )
    print("Chunks written to Neo4j.")


asyncio.run(main())
