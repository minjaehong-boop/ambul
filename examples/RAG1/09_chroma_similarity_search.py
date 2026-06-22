"""Chroma 벡터 저장소 — HF local 임베딩으로 저장 후 similarity_search."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

data = TextLoader("Attention.txt").load()
docs = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=100
).split_documents(data)
print("chunks:", len(docs))

emb = HuggingFaceEmbeddings(
    model_name="jhgan/ko-sbert-sts",
    encode_kwargs={"normalize_embeddings": True},  # cosine 유사도용 정규화
)

db = Chroma.from_documents(
    docs,
    emb,
    collection_name="attention",
    persist_directory="./db/chromadb",
    collection_metadata={"hnsw:space": "cosine"},  # 기본값은 l2
)
print("stored:", db._collection.count())

query = "How does self-attention work?"
results = db.similarity_search(query, k=3)

print(f"\nquery: {query}\n")
for rank, doc in enumerate(results, 1):
    print(f"#{rank}  {doc.page_content[:200].replace(chr(10), ' ')} ...\n")


for doc, dist in db.similarity_search_with_score(query, k=3):
    print(dist, doc.page_content[:80])
