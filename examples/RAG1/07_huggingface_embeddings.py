"""HuggingFaceEmbeddings — local, free, on-prem (no API call)."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

data = TextLoader("Attention.txt").load()
docs = RecursiveCharacterTextSplitter(
    chunk_size=500, chunk_overlap=100
).split_documents(data)
print("chunks:", len(docs))

# multilingual / Korean models for a 한글 RAG corpus:
#   "BAAI/bge-m3"                       (다국어, 1024 dim)
#   "intfloat/multilingual-e5-base"     (다국어, query에 "query: " prefix 필요)
#   "jhgan/ko-sbert-sts"                (한국어, 이 프로젝트 KTAS 임베딩 모델)
emb = HuggingFaceEmbeddings(
    model_name="jhgan/ko-sbert-sts",
    encode_kwargs={"normalize_embeddings": True},  # cosine 유사도용 정규화
)

vectors = emb.embed_documents([d.page_content for d in docs[:3]])
print("dim:", len(vectors[0]))
print("first 5 values:", vectors[0][:5])
