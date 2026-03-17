"""SQLite storage layer for the Coq/Rocq search index."""

from .reader import IndexReader
from .writer import IndexWriter

__all__ = ["IndexReader", "IndexWriter"]
