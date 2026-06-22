from langchain_text_splitters import RecursiveCharacterTextSplitter
from neo4j_graphrag.experimental.components.text_splitters.langchain import LangChainTextSplitterAdapter
from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPENROUTER_KEY = BASE_DIR.joinpath("openrouter_key.txt").read_text(encoding="utf-8").strip()

splitter = LangChainTextSplitterAdapter(
    RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=400)
)

embedder = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
)
chunk_embedder = TextChunkEmbedder(embedder)


async def main():
    text = BASE_DIR.joinpath("2021_KTAS_guideline.md").read_text(encoding="utf-8")
    chunks = await splitter.run(text=text)
    embedded = await chunk_embedder.run(text_chunks=chunks)
    print(embedded)


asyncio.run(main())
