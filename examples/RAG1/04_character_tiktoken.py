"""CharacterTextSplitter + tiktoken — token-based sizing."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

data = TextLoader("Attention.txt").load()
print("chars:", len(data[0].page_content))

# chunk_size/overlap now counted in tokens (cl100k_base)
splitter = CharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=600,
    chunk_overlap=200,
    encoding_name="cl100k_base",
)
docs = splitter.split_documents(data)

print("chunks:", len(docs))
print("first len:", len(docs[0].page_content))
print("meta:", docs[0].metadata)
print(docs[0].page_content[:300], "...")
