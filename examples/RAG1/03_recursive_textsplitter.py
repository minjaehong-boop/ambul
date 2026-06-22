"""RecursiveCharacterTextSplitter — semantic-aware split."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

data = TextLoader("Attention.txt").load()
print("chars:", len(data[0].page_content))

# tries ['\n\n','\n',' ',''] in order, descending granularity
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    length_function=len,
)
texts = splitter.split_text(data[0].page_content)

print("chunks:", len(texts))
print("first 3 lens:", [len(t) for t in texts[:3]])
print("max len:", max(len(t) for t in texts))
print(texts[0][:300], "...")
