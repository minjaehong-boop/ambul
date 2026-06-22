"""CharacterTextSplitter — empty separator (char-level)."""

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter

data = TextLoader("Attention.txt").load()
print("chars:", len(data[0].page_content))

# "" separator -> splits per character, exact chunk_size
splitter = CharacterTextSplitter(
    separator="",
    chunk_size=500,
    chunk_overlap=100,
    length_function=len,
)
texts = splitter.split_text(data[0].page_content)

print("chunks:", len(texts))
print("first len:", len(texts[0]))
print(texts[0][:200], "...")
