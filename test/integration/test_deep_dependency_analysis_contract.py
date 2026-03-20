"""Contract tests for Deep Dependency Analysis against real Coq environment.

These tests verify that mocked IndexReader and DOT file interfaces match
the real implementations.

Spec: specification/deep-dependency-analysis.md
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _import_build_graph():
    from Poule.analysis.graph import build_graph
    return build_graph


def _import_graph_types():
    from Poule.analysis.graph import DependencyGraph, NodeMetadata
    return DependencyGraph, NodeMetadata


def _import_index_reader():
    from Poule.storage.reader import IndexReader
    return IndexReader


class TestContractTests:
    """Contract tests for mocked interfaces. Each requires real dependencies."""

    def test_contract_real_index_reader(self, test_fixture_db):
        """Contract test: build_graph works with a real IndexReader."""
        build_graph = _import_build_graph()
        DependencyGraph, _ = _import_graph_types()
        IndexReader = _import_index_reader()
        reader = IndexReader.open(str(test_fixture_db))
        graph = build_graph(index_reader=reader)
        assert isinstance(graph, DependencyGraph)
        assert graph.node_count >= 0
        reader.close()

    def test_contract_index_reader_declarations_table(self, test_fixture_db):
        """Contract: IndexReader can query declarations table for graph construction."""
        IndexReader = _import_index_reader()
        reader = IndexReader.open(str(test_fixture_db))
        # The engine reads all declarations
        rows = reader._conn.execute(
            "SELECT id, name, module, kind FROM declarations"
        ).fetchall()
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            # Must have id, name, module, kind
            assert row[0] is not None  # id
            assert row[1] is not None  # name
        reader.close()

    def test_contract_index_reader_dependencies_table(self, test_fixture_db):
        """Contract: IndexReader can query dependencies table for graph edges."""
        IndexReader = _import_index_reader()
        reader = IndexReader.open(str(test_fixture_db))
        rows = reader._conn.execute(
            "SELECT src, dst, relation FROM dependencies WHERE relation = 'uses'"
        ).fetchall()
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            assert row[0] is not None  # src
            assert row[1] is not None  # dst
            assert row[2] == "uses"
        reader.close()

    def test_contract_index_reader_meta_created_at(self, test_fixture_db):
        """Contract: IndexReader can read created_at from index_meta for cache validation."""
        IndexReader = _import_index_reader()
        reader = IndexReader.open(str(test_fixture_db))
        row = reader._conn.execute(
            "SELECT value FROM index_meta WHERE key = 'created_at'"
        ).fetchone()
        # created_at may or may not exist; just verify the query works
        assert row is None or isinstance(row[0], str)
        reader.close()

    def test_contract_build_graph_from_real_dot_file(self, test_fixture_dot):
        """Contract: build_graph parses a real coq-dpdgraph DOT file."""
        build_graph = _import_build_graph()
        DependencyGraph, _ = _import_graph_types()
        # Requires a real DOT file from coq-dpdgraph
        graph = build_graph(dot_file_path=test_fixture_dot)
        assert isinstance(graph, DependencyGraph)
        assert graph.node_count >= 0
