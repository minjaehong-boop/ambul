from langchain_text_splitters import RecursiveCharacterTextSplitter
from neo4j_graphrag.experimental.components.text_splitters.langchain import LangChainTextSplitterAdapter
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).parent

splitter = LangChainTextSplitterAdapter(
    RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
)


async def main():
    text = BASE_DIR.joinpath("2021_KTAS_guideline.md").read_text(encoding="utf-8")
    chunks = await splitter.run(text=text)
    print(chunks)


asyncio.run(main())
