"""RecursiveCharacterTextSplitter + tiktoken — the go-to combo."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

data = TextLoader("Attention.txt").load()
print("chars:", len(data[0].page_content))

# recursive split + token budget
splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=600,
    chunk_overlap=200,
    encoding_name="cl100k_base",
)
docs = splitter.split_documents(data)

print("chunks:", len(docs))
print("first 3 lens:", [len(d.page_content) for d in docs[:3]])
print(docs[0].page_content[:300], "...")
