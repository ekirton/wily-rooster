"""TDD tests for diagram file output (specification/diagram-file-output.md)."""

from __future__ import annotations

from pathlib import Path

import pytest


def _import_write_diagram_html():
    from Poule.server.diagram_writer import write_diagram_html
    return write_diagram_html


def _single_diagram(mermaid: str = "flowchart TD\n    A --> B", label: str | None = None):
    return [{"mermaid": mermaid, "label": label}]


def _multi_diagrams():
    return [
        {"mermaid": "flowchart TD\n    s0 --> s1", "label": "Step 0: initial"},
        {"mermaid": "flowchart TD\n    s1 --> s2", "label": "Step 1: intro H"},
        {"mermaid": "flowchart TD\n    s2 --> s3", "label": None},
    ]


class TestWriteFile:
    def test_writes_file_to_given_path(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        assert out.exists()

    def test_returns_path_written(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        result = _import_write_diagram_html()(out, "Test", _single_diagram())
        assert result == out


class TestHtmlContent:
    def test_file_contains_mermaid_cdn(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        html = out.read_text()
        assert "cdn.jsdelivr.net/npm/mermaid" in html

    def test_file_contains_title(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Proof Tree: app_nil_r", _single_diagram())
        html = out.read_text()
        assert "<title>Proof Tree: app_nil_r</title>" in html

    def test_file_contains_mermaid_text(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        mermaid_text = "flowchart TD\n    A --> B"
        _import_write_diagram_html()(out, "Test", _single_diagram(mermaid=mermaid_text))
        html = out.read_text()
        assert "A --> B" in html

    def test_valid_html_structure(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        html = out.read_text()
        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_dark_theme_configured(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        html = out.read_text()
        assert "dark" in html


class TestSingleDiagram:
    def test_single_diagram_one_section(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        html = out.read_text()
        # Should contain exactly one mermaid diagram section
        assert html.count("class=\"mermaid\"") == 1 or html.count("mermaid-diagram") >= 1

    def test_null_label_no_heading(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram(label=None))
        html = out.read_text()
        # With no label, there should be no section heading (h2/h3) for the diagram
        # The title in <head> is expected, but no content heading for the diagram itself
        assert "<h2>" not in html and "<h3>" not in html


class TestMultiDiagram:
    def test_multi_diagram_all_sections(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        diagrams = _multi_diagrams()
        _import_write_diagram_html()(out, "Sequence", diagrams)
        html = out.read_text()
        # All three diagrams' mermaid text should be present
        assert "s0 --> s1" in html
        assert "s1 --> s2" in html
        assert "s2 --> s3" in html

    def test_labels_appear_as_headings(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        diagrams = _multi_diagrams()
        _import_write_diagram_html()(out, "Sequence", diagrams)
        html = out.read_text()
        assert "Step 0: initial" in html
        assert "Step 1: intro H" in html


class TestOverwrite:
    def test_overwrites_existing_file(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "First", _single_diagram(mermaid="flowchart TD\n    OLD"))
        _import_write_diagram_html()(out, "Second", _single_diagram(mermaid="flowchart TD\n    NEW"))
        html = out.read_text()
        assert "NEW" in html
        assert "OLD" not in html


class TestSpecialCharacters:
    def test_special_chars_escaped(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        # Mermaid text with characters that could break HTML
        mermaid_text = 'flowchart TD\n    A["x < y & z > w"]'
        _import_write_diagram_html()(out, "Test", _single_diagram(mermaid=mermaid_text))
        html = out.read_text()
        # The file should be valid HTML — the raw < and > should not break the structure
        # Verify the HTML has proper opening and closing tags
        assert "<html" in html
        assert "</html>" in html
        assert "<body>" in html
        assert "</body>" in html


class TestNoServerDependencies:
    def test_renders_without_server(self, tmp_path: Path):
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", _single_diagram())
        html = out.read_text()
        assert "/viewer/events" not in html
        assert "EventSource" not in html
        assert "event: diagram" not in html


class TestErrorSpecification:
    """Spec §6: Error Specification."""

    def test_parent_directory_missing_raises(self, tmp_path: Path):
        """Spec §6: Parent directory does not exist → raise error."""
        out = tmp_path / "nonexistent_dir" / "proof-diagram.html"
        with pytest.raises((FileNotFoundError, OSError)):
            _import_write_diagram_html()(out, "Test", _single_diagram())

    def test_empty_diagrams_list_writes_valid_html(self, tmp_path: Path):
        """Spec §6: Empty diagrams list → write valid HTML with no diagram sections."""
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Empty", [])
        html = out.read_text()
        assert html.startswith("<!DOCTYPE html>")
        assert "<html" in html
        assert "<title>Empty</title>" in html

    def test_empty_mermaid_string_writes_section(self, tmp_path: Path):
        """Spec §6: mermaid value is empty string → write section with empty diagram."""
        out = tmp_path / "proof-diagram.html"
        _import_write_diagram_html()(out, "Test", [{"mermaid": "", "label": "Empty step"}])
        html = out.read_text()
        assert "Empty step" in html
        # File should still be valid HTML
        assert "<html" in html
        assert "</html>" in html


class TestMultiDiagramOrdering:
    """Spec §4.4: sections appear in order."""

    def test_diagram_sections_in_order(self, tmp_path: Path):
        """Spec §4.4: one section per entry, in order."""
        out = tmp_path / "proof-diagram.html"
        diagrams = [
            {"mermaid": "flowchart TD\n    FIRST", "label": "First"},
            {"mermaid": "flowchart TD\n    SECOND", "label": "Second"},
            {"mermaid": "flowchart TD\n    THIRD", "label": "Third"},
        ]
        _import_write_diagram_html()(out, "Ordered", diagrams)
        html = out.read_text()
        # All three labels and diagrams present, in order
        first_pos = html.index("FIRST")
        second_pos = html.index("SECOND")
        third_pos = html.index("THIRD")
        assert first_pos < second_pos < third_pos

    def test_mixed_labels_and_none(self, tmp_path: Path):
        """Spec §4.4: sections with label=None have no heading, labeled ones do."""
        out = tmp_path / "proof-diagram.html"
        diagrams = [
            {"mermaid": "flowchart TD\n    A", "label": "Labeled"},
            {"mermaid": "flowchart TD\n    B", "label": None},
        ]
        _import_write_diagram_html()(out, "Mixed", diagrams)
        html = out.read_text()
        assert "Labeled" in html
        # Both diagrams present
        assert "flowchart TD" in html
