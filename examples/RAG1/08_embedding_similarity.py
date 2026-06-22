"""왜 검색이 되는가 — query vs chunk 코사인 유사도 시연."""

import numpy as np
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

data = TextLoader("Attention.txt").load()
docs = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=100
).split_documents(data)

emb = HuggingFaceEmbeddings(
    model_name="jhgan/ko-sbert-sts",
    encode_kwargs={"normalize_embeddings": True},
)


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


query = "How does self-attention work?"
qv = emb.embed_query(query)
chunk_vecs = emb.embed_documents([d.page_content for d in docs])

# 질의와 모든 청크의 유사도 → 상위 3개가 곧 retriever 의 검색 결과
scores = [(cosine(qv, cv), i) for i, cv in enumerate(chunk_vecs)]
scores.sort(reverse=True)

print(f"query: {query}\n")
for rank, (score, i) in enumerate(scores[:3], 1):
    print(f"#{rank}  score={score:.4f}")
    print(docs[i].page_content[:200].replace("\n", " "), "...\n")
