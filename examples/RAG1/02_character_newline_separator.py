"""CharacterTextSplitter — newline separator."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

data = TextLoader("Attention.txt").load()
print("chars:", len(data[0].page_content))

# split on "\n" -> keeps lines intact, len may drift from chunk_size
splitter = CharacterTextSplitter(
    separator="\n",
    chunk_size=500,
    chunk_overlap=100,
    length_function=len,
)
texts = splitter.split_text(data[0].page_content)

print("chunks:", len(texts))
print("first 3 lens:", [len(t) for t in texts[:3]])
print(texts[0][:200], "...")
