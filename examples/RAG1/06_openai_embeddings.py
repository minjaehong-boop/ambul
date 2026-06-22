"""OpenAIEmbeddings — chunk → vector via OpenRouter API (text-embedding-3-small)."""

from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# reuse the chunking step from section B
data = TextLoader("Attention.txt").load()
docs = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=100
).split_documents(data)
print("chunks:", len(docs))

# OpenRouter key from key.txt, OpenAI-compatible endpoint
api_key = Path("key.txt").read_text().strip()
emb = OpenAIEmbeddings(
    model="text-embedding-3-small",
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# embed_documents: many texts at once (for storing in the vector DB)
vectors = emb.embed_documents([d.page_content for d in docs[:3]])
print("dim:", len(vectors[0]))
print("first 5 values:", vectors[0][:5])

# embed_query: a single search query (same model, document vs query는 같은 공간)
qv = emb.embed_query("What is multi-head attention?")
print("query dim:", len(qv))
