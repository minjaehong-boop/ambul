"""Base interface that all RAG examples should implement."""

from abc import ABC, abstractmethod
from typing import Generator, List


class BaseExample(ABC):
    """This class defines the basic structure for building RAG chain server examples."""

    @abstractmethod
    def llm_chain(self, query: str, chat_history: List, **kwargs) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def rag_chain(self, query: str, chat_history: List, **kwargs) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def ingest_docs(self, data_dir: str, filename: str) -> None:
        pass
